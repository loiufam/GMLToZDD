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

        mapped = [[c + col_offset for c in row] for row in rows]
        all_rows.extend(mapped)
        col_lo = col_offset + 1
        col_hi = col_offset + block_max_local_col
        col_offset += block_max_local_col
        success_count += 1
        print(f"  [Block {block_idx + 1}] 提取 {len(rows)} 行, 全局列 {col_lo}~{col_hi}")

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