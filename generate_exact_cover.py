import networkx as nx
import os
import sys
import subprocess
import argparse
import random
import glob

# ============================================================
# 步骤 1: 读取图数据
# ============================================================
def read_graph(file_path):
    G = nx.Graph()
    total_v = 0
    with open(file_path, 'r') as f:
        first_line = f.readline().strip().split()
        if len(first_line) >= 2:
            total_v = int(first_line[0])
        for line in f:
            if line.strip():
                u, v = map(int, line.strip().split())
                G.add_edge(u, v)
    for i in range(total_v):
        if i not in G.nodes:
            G.add_node(i)
    return G, total_v


# ============================================================
# 步骤 2: Min-fill 树分解与深度优先遍历排序
# ============================================================
def min_fill_tree_decomposition_order(graph):
    print("[1] 计算 Min-fill 树分解排序...")
    G = graph.copy()
    G.remove_edges_from(nx.selfloop_edges(G))
    clean_graph = G.copy()
    fill_in_edges = []

    while len(G.nodes) > 0:
        min_fill = float('inf')
        best_node = None
        for node in G.nodes:
            neighbors = list(G.neighbors(node))
            fill_count = 0
            for i in range(len(neighbors)):
                for j in range(i + 1, len(neighbors)):
                    if not G.has_edge(neighbors[i], neighbors[j]):
                        fill_count += 1
            if fill_count < min_fill:
                min_fill = fill_count
                best_node = node
            elif fill_count == min_fill:
                if best_node is None or G.degree(node) < G.degree(best_node):
                    best_node = node

        neighbors = list(G.neighbors(best_node))
        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                if not graph.has_edge(neighbors[i], neighbors[j]):
                    fill_in_edges.append((neighbors[i], neighbors[j]))
                G.add_edge(neighbors[i], neighbors[j])
        G.remove_node(best_node)

    chordal_G = clean_graph.copy()
    chordal_G.add_edges_from(fill_in_edges)
    cliques = list(nx.chordal_graph_cliques(chordal_G))

    clique_graph = nx.Graph()
    for i, c1 in enumerate(cliques):
        clique_graph.add_node(i, bag=c1)
        for j, c2 in enumerate(cliques):
            if i < j:
                intersection = set(c1).intersection(set(c2))
                if len(intersection) > 0:
                    clique_graph.add_edge(i, j, weight=len(intersection))

    if clique_graph.number_of_nodes() == 0:
        return list(graph.nodes())

    tree_decomp = nx.maximum_spanning_tree(clique_graph)
    final_order = []
    visited = set()
    for tree_node in nx.dfs_preorder_nodes(tree_decomp):
        bag = tree_decomp.nodes[tree_node]['bag']
        for v in bag:
            if v not in visited:
                final_order.append(v)
                visited.add(v)

    # 注: 孤立点不在任何 clique bag 中, 自然不会进入 order, 也不需要进入。
    return final_order


# ============================================================
# 步骤 3: 解析 ZDD 文件 → 行 (完整枚举, 不截断)
# ============================================================
ZDD_SAFETY_LIMIT = 2_000_000  # 单块路径数硬上限 (仅作 OOM 兜底)


def parse_zdd_to_rows(zdd_file_path):
    """
    完整枚举 ZDD 中所有根→T 的路径作为稀疏矩阵的行。
    ZDD 的语义保证不同路径对应不同的变量子集 → 行天然不重复。
    """
    nodes = {}
    referenced = set()

    with open(zdd_file_path, "r") as f:
        for line in f:
            if not line.strip() or line.startswith('_'):
                continue
            parts = line.strip().split()
            if len(parts) == 4:
                nid, level, lo, hi = parts
                nodes[nid] = {"level": int(level), "lo": lo, "hi": hi}
                if lo not in ("T", "F"):
                    referenced.add(lo)
                if hi not in ("T", "F"):
                    referenced.add(hi)

    if not nodes:
        return [], False

    all_ids = set(nodes.keys())
    root_candidates = all_ids - referenced
    if not root_candidates:
        root = list(nodes.keys())[-1]
    else:
        root = sorted(root_candidates, key=lambda nid: -int(nid))[0]

    rows = []
    overflowed = [False]
    sys.setrecursionlimit(max(sys.getrecursionlimit(), len(nodes) + 1000))

    def dfs(nid, ones):
        if overflowed[0]:
            return
        if len(rows) >= ZDD_SAFETY_LIMIT:
            overflowed[0] = True
            return
        if nid == "T":
            rows.append(sorted(ones))
            return
        if nid == "F" or nid not in nodes:
            return
        node = nodes[nid]
        # 完整枚举: lo-first 固定顺序
        dfs(node["lo"], ones)
        dfs(node["hi"], ones + [node["level"]])

    dfs(root, [])
    return rows, overflowed[0]


# ============================================================
# 步骤 3.5: 分块内精确覆盖解构造 (增强行多样性)
# ============================================================
# 目标: 每个分块除了 ZDD 自身枚举出的路径行之外, 主动构造 10~100 组
# "精确覆盖解"(每组的若干行在该分块的列集合 U_b 上形成一个划分,
# 即每列恰好覆盖一次, 行之间列不相交)。把每组解中的每一行作为
# 独立矩阵行注入, 并做全局 frozenset 去重, 从而提升下游 DLX
# 求解器的搜索空间。
#
# 注意:
# 1) 新增行的局部列索引只来自 U_b (即本块 ZDD 行里出现过的列),
#    所以不会扩展 block_max_local_col, 分块列空间独立性保持不变。
# 2) 去重在全局 seen_frozensets 上做, 保证最终矩阵无重复行。

MIN_EXTRA_SOLUTIONS_PER_BLOCK = 10   # 每块最少目标构造组数
MAX_EXTRA_SOLUTIONS_PER_BLOCK = 100  # 每块最多目标构造组数
SOLUTION_BUILD_MAX_TRIES = 2000      # 单块构造尝试次数上限, 避免死循环


def _solution_from_zdd_rows(universe, zdd_rows_local, rng):
    """
    贪心地从 ZDD 行中挑出一组列不相交的行, 直到列用完; 剩余列用
    singleton 行(单列一行)补齐。返回一个 list[list[int]], 每个
    子 list 是该解的一行 (局部列索引, 排序)。
    """
    remaining = set(universe)
    pool = [r for r in zdd_rows_local if r]  # 非空行
    rng.shuffle(pool)

    chosen = []
    for row in pool:
        s = frozenset(row)
        if not s:
            continue
        # 整行必须落在 remaining 内, 才能保持"每列恰好一次"
        if s.issubset(remaining):
            chosen.append(sorted(s))
            remaining -= s
            if not remaining:
                break

    # 剩余列用 singleton 补齐, 保证列恰好被覆盖一次
    for c in sorted(remaining):
        chosen.append([c])

    return chosen


def _solution_from_partition(universe, rng):
    """
    把 universe 随机打散后切成若干段, 每段作为解的一行。
    天然满足"每列恰好覆盖一次"。返回 list[list[int]]。
    """
    cols = list(universe)
    if not cols:
        return []
    rng.shuffle(cols)
    n = len(cols)

    # 随机选划分块数 k ∈ [1, n], 偏向 2 ~ sqrt(n)*2 之间的中等粒度
    upper = max(2, min(n, int(n ** 0.5) * 2 + 1))
    k = rng.randint(1, upper) if n > 1 else 1

    # 随机生成 k-1 个切点, 得到 k 段
    if k == 1:
        parts_idx = [(0, n)]
    else:
        cuts = sorted(rng.sample(range(1, n), k - 1))
        parts_idx = []
        prev = 0
        for c in cuts:
            parts_idx.append((prev, c))
            prev = c
        parts_idx.append((prev, n))

    return [sorted(cols[a:b]) for (a, b) in parts_idx]


def build_extra_exact_cover_rows(zdd_rows_local, seen_frozensets, rng):
    """
    为一个分块构造额外的精确覆盖解, 把每组解的每一行作为独立行返回。

    参数:
        zdd_rows_local: 该分块 ZDD 解析出的行 (局部列索引, list[list[int]])
        seen_frozensets: 全局已出现的行集合 (用 frozenset 去重, 会被原地更新)
        rng: random.Random 实例, 便于复现
    返回:
        extra_local_rows: list[list[int]], 需要注入的新行 (局部列索引)
        stats: dict, 包含构造统计信息
    """
    stats = {
        "target_solutions": 0,
        "built_solutions": 0,
        "injected_rows": 0,
        "skipped_duplicate_rows": 0,
    }

    if not zdd_rows_local:
        return [], stats

    # 本块的列全集 = ZDD 行里出现过的所有局部列
    universe = set()
    for r in zdd_rows_local:
        universe.update(r)
    if not universe:
        return [], stats

    target = rng.randint(MIN_EXTRA_SOLUTIONS_PER_BLOCK,
                         MAX_EXTRA_SOLUTIONS_PER_BLOCK)
    stats["target_solutions"] = target

    extra_local_rows = []
    built = 0
    tries = 0

    # 两种构造方法交替使用, 提高多样性
    while built < target and tries < SOLUTION_BUILD_MAX_TRIES:
        tries += 1
        use_zdd_based = (tries % 2 == 0) and len(zdd_rows_local) > 0
        if use_zdd_based:
            solution = _solution_from_zdd_rows(universe, zdd_rows_local, rng)
        else:
            solution = _solution_from_partition(universe, rng)

        if not solution:
            continue

        # 正确性校验: 每列恰好覆盖一次 (行之间列不相交, 且并集 == universe)
        covered = []
        for row in solution:
            covered.extend(row)
        if len(covered) != len(universe) or set(covered) != universe:
            # 构造函数本应保证, 这里只是双保险
            continue

        # 把本组解的每一行作为独立行加入, 全局 frozenset 去重
        any_new = False
        for row in solution:
            key = frozenset(row)
            if not key:
                continue
            if key in seen_frozensets:
                stats["skipped_duplicate_rows"] += 1
                continue
            seen_frozensets.add(key)
            extra_local_rows.append(sorted(row))
            stats["injected_rows"] += 1
            any_new = True

        if any_new:
            built += 1
            stats["built_solutions"] = built

    return extra_local_rows, stats


# ============================================================
# 步骤 4: 导出导出子图给 ZDD 引擎
# ============================================================
def export_subgraph_for_zdd(sub_graph, sub_order, prefix, temp_dir):
    """
    导出 induced subgraph: 节点按 sub_order 重编号 0..k-1。
    只写两端都在 sub_order 中的边。
    """
    node_mapping = {n: i for i, n in enumerate(sub_order)}
    edges_file = os.path.abspath(os.path.join(temp_dir, f"{prefix}.edges"))
    sub_edges = list(sub_graph.edges())
    with open(edges_file, 'w') as f:
        f.write(f"{len(sub_order)} {len(sub_edges)}\n")
        for u, v in sub_edges:
            f.write(f"{node_mapping[u]} {node_mapping[v]}\n")
    return edges_file


# ============================================================
# 步骤 5: 分块 ZDD 处理 (C++ 引擎已自带多方法 fallback 链)
# ============================================================
def block_zdd_strategy(G, order, zdd_engine_bin, temp_dir, base_name):
    """
    把 min-fill 排序切成 K 段, 对每段对应的导出子图独立调用 C++ ZDD 引擎。
    每个块的列空间互不重叠, 拼接后的全局矩阵天然不重复。

    C++ 引擎自带 fallback 链 (InducedGraphsConnected -> Cycle -> S_T_Path),
    所以单个块失败的可能性已经很低; 仍然失败的块直接跳过, 不再做 Python 兜底。
    """
    print("[ZDD] 分块处理...")

    n = len(order)
    if n < 4:
        print("  图过小, 跳过")
        return None, None

    num_blocks = random.randint(4, 16)
    num_blocks = max(2, min(num_blocks, n // 4))

    base_size = n // num_blocks
    block_nodes_list = []
    cursor = 0
    for b in range(num_blocks):
        if b == num_blocks - 1:
            end = n
        else:
            offset = random.randint(-base_size // 5, base_size // 5)
            min_end = cursor + 2
            max_end = n - 2 * (num_blocks - b - 1)
            end = max(min_end, min(max_end, cursor + base_size + offset))
        block_nodes_list.append(order[cursor:end])
        cursor = end

    print(f"  共划分 {len(block_nodes_list)} 个块, 各块大小: {[len(b) for b in block_nodes_list]}")

    all_rows = []
    col_offset = 0
    success_count = 0
    failed_blocks = []

    # 全局行去重集合: key = frozenset(全局列索引), 保证最终矩阵无重复行
    seen_frozensets = set()
    # 复用一个 rng 便于复现 (保持和上层 random 状态一致即可, 这里直接用 module 级)
    rng = random.Random(random.randint(0, 2**31 - 1))

    for block_idx, block_nodes in enumerate(block_nodes_list):
        sub_G = G.subgraph(block_nodes).copy()

        if sub_G.number_of_edges() == 0:
            print(f"  [Block {block_idx + 1}] 内部无边, 跳过")
            failed_blocks.append(block_idx)
            continue

        prefix = f"block_{base_name}_{block_idx}"
        edges_file = export_subgraph_for_zdd(sub_G, block_nodes, prefix, temp_dir)

        zdd_dump = os.path.join(temp_dir, "sample.zdd")
        if os.path.exists(zdd_dump):
            os.remove(zdd_dump)

        # 调 C++ 引擎; 它内部有完整的 fallback 链:
        #   InducedGraphsConnected -> Cycle(true) -> S_T_Path × N对
        #   -> Cycle(false) -> InducedGraphsConnected on random spanning forest
        try:
            subprocess.run(
                [zdd_engine_bin, edges_file],
                cwd=temp_dir,
                check=True,
                capture_output=True,
                text=True,
                timeout=300     # C++ 端软预算 150s, 这里多留 150s 给 sparsify fallback 和 I/O
            )
        except subprocess.TimeoutExpired:
            print(f"  [Block {block_idx + 1}] C++ 引擎整体超时 (300s), 跳过")
            failed_blocks.append(block_idx)
            continue
        except subprocess.CalledProcessError as e:
            # C++ 返回非零: 所有 fallback 方法都失败时引擎会返回 2
            print(f"  [Block {block_idx + 1}] C++ 引擎返回 {e.returncode}, 所有方法失败, 跳过")
            failed_blocks.append(block_idx)
            continue
        except Exception as e:
            print(f"  [Block {block_idx + 1}] 未知错误: {e}, 跳过")
            failed_blocks.append(block_idx)
            continue

        if not os.path.exists(zdd_dump):
            print(f"  [Block {block_idx + 1}] 未生成 ZDD 输出文件, 跳过")
            failed_blocks.append(block_idx)
            continue

        rows, overflowed = parse_zdd_to_rows(zdd_dump)
        if overflowed:
            print(f"  [Block {block_idx + 1}] 警告: 路径数达到安全上限 {ZDD_SAFETY_LIMIT}, 提前停止")

        if not rows:
            print(f"  [Block {block_idx + 1}] ZDD 解析后无有效行, 跳过")
            failed_blocks.append(block_idx)
            continue

        block_max_local_col = max((c for row in rows for c in row), default=0)
        if block_max_local_col == 0:
            failed_blocks.append(block_idx)
            continue

        # ---- 1) 先把 ZDD 原始行做全局去重后映射进 all_rows ----
        zdd_rows_injected = 0
        zdd_rows_dup = 0
        for row in rows:
            key = frozenset(c + col_offset for c in row)
            if not key:
                continue
            if key in seen_frozensets:
                zdd_rows_dup += 1
                continue
            seen_frozensets.add(key)
            all_rows.append(sorted(key))
            zdd_rows_injected += 1

        # ---- 2) 构造额外的精确覆盖解以扩充行数 (每块 10~100 组) ----
        # 使用"全局 frozenset 视角"的去重集合, 需要把局部列映射为全局列后再查重
        #  --> 做法: 构造时先在局部列空间操作, 拿到局部行后再映射为全局列 frozenset 查重
        # 为减少构造阶段的无效 tries, 先把本块 ZDD 行的局部 frozenset 放进构造函数
        # 的内部去重集合, 避免反复构造出已有的行
        local_seen = {frozenset(r) for r in rows if r}
        extra_local_rows, extra_stats = build_extra_exact_cover_rows(
            rows,
            local_seen,
            rng,
        )

        # 再用全局去重集合过滤一次 (映射到 global 列)
        extra_injected = 0
        extra_dup = 0
        for lrow in extra_local_rows:
            key = frozenset(c + col_offset for c in lrow)
            if not key:
                continue
            if key in seen_frozensets:
                extra_dup += 1
                continue
            seen_frozensets.add(key)
            all_rows.append(sorted(key))
            extra_injected += 1

        col_lo = col_offset + 1
        col_hi = col_offset + block_max_local_col
        col_offset += block_max_local_col
        success_count += 1
        print(f"  [Block {block_idx + 1}] ZDD 行={len(rows)} "
              f"(注入 {zdd_rows_injected}, 去重 {zdd_rows_dup}), "
              f"构造解目标={extra_stats['target_solutions']} "
              f"完成={extra_stats['built_solutions']}, "
              f"额外行注入 {extra_injected} (去重 {extra_dup}), "
              f"全局列 {col_lo}~{col_hi}")

    if success_count == 0 or not all_rows:
        return None, None

    if failed_blocks:
        print(f"  注意: {len(failed_blocks)} 个块失败 (索引 {failed_blocks}), "
              f"{success_count} 个块成功")
    print(f"  汇总: {len(all_rows)} 行 x {col_offset} 列 (来自 {success_count} 个分块)")
    return all_rows, col_offset


# ============================================================
# 步骤 6: 写入与清理
# ============================================================
def write_matrix(rows, num_cols, output_path):
    with open(output_path, "w") as f:
        f.write(f"{num_cols} {len(rows)}\n")
        for row in rows:
            f.write(f"{len(row)} " + " ".join(map(str, row)) + "\n")


def clean_temp_dir(temp_dir):
    if not os.path.isdir(temp_dir):
        return
    for f in os.listdir(temp_dir):
        path = os.path.join(temp_dir, f)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass


# ============================================================
# 步骤 7: 单文件处理
# ============================================================
def process_single_task(graph_file, zdd_engine_bin, temp_dir, output_dir="."):
    base_name = os.path.splitext(os.path.basename(graph_file))[0]
    print(f"\n========== 开始处理: {base_name} ==========")

    G, total_nodes = read_graph(graph_file)
    print(f"  图大小 |V|={total_nodes}, |E|={G.number_of_edges()}")

    if total_nodes < 4 or G.number_of_edges() == 0:
        print("  图过小, 放弃")
        clean_temp_dir(temp_dir)
        return

    order = min_fill_tree_decomposition_order(G)

    output_matrix = os.path.abspath(os.path.join(output_dir, f"{base_name}.txt"))

    rows, num_cols = block_zdd_strategy(G, order, zdd_engine_bin, temp_dir, base_name)

    if not rows:
        print("[错误] 所有分块均失败 (C++ 引擎的 fallback 链已用尽), 放弃当前测例")
        clean_temp_dir(temp_dir)
        return

    write_matrix(rows, num_cols, output_matrix)
    print(f"[完成] {len(rows)} 行 x {num_cols} 列 -> {output_matrix}")

    clean_temp_dir(temp_dir)


# ============================================================
# 步骤 8: 入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='将图结构 (.in) 转换为精确覆盖矩阵实例 (D3X 改进版)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            使用示例:
            # 单文件
            python generate_exact_cover.py -i graph.in

            # 批量处理整个文件夹 (./graphs/*.in)
            python generate_exact_cover.py -d ./graphs
        """
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--input', help='输入文件路径 (单文件)')
    group.add_argument('-d', '--directory', help='输入文件夹 (批量)')
    parser.add_argument('-o', '--output', default="./output", help='输出目录')
    args = parser.parse_args()

    zdd_engine_bin = os.path.abspath("./build_zdd_bin/main")
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    if args.input:
        graph_file = os.path.abspath(args.input)
        if not os.path.isfile(graph_file):
            print(f"错误: 找不到输入文件 {graph_file}")
            sys.exit(1)
        process_single_task(graph_file, zdd_engine_bin, temp_dir, output_dir)
    else:
        folder = os.path.abspath(args.directory)
        if not os.path.isdir(folder):
            print(f"错误: 找不到文件夹 {folder}")
            sys.exit(1)
        targets = glob.glob(os.path.join(folder, "*.in"))
        if not targets:
            print(f"警告: {folder} 下未找到任何 .in 文件")
            sys.exit(0)
        print(f"找到 {len(targets)} 个 .in 文件, 开始批量处理...")
        for fp in targets:
            base_name = os.path.splitext(os.path.basename(fp))[0]
            expected = os.path.join(output_dir, f"{base_name}.txt")
            if os.path.exists(expected):
                print(f"[跳过] 输出 {expected} 已存在")
                continue
            process_single_task(fp, zdd_engine_bin, temp_dir, output_dir)

    print(f"\n--- 全部任务结束 ---")


if __name__ == "__main__":
    main()