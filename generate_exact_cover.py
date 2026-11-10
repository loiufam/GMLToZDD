import networkx as nx
import os
import sys
import subprocess
import argparse
import random
import glob
import csv
import hashlib
import json
from functools import lru_cache
import math
import shutil
from pathlib import Path

from GMLParser import parse_graphml_to_in

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
        for node in sorted(G.nodes):
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
    cliques = sorted(
        (frozenset(clique) for clique in nx.chordal_graph_cliques(chordal_G)),
        key=lambda clique: (min(clique), len(clique)),
    )

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
        for v in sorted(bag):
            if v not in visited:
                final_order.append(v)
                visited.add(v)

    # 注: 孤立点不在任何 clique bag 中, 自然不会进入 order, 也不需要进入。
    return final_order


def graph_topology_metrics(graph):
    """Return graph-level topology metrics used by the calibrated selector."""
    G = nx.Graph(graph)
    G.remove_edges_from(nx.selfloop_edges(G))
    nodes = G.number_of_nodes()
    edges = G.number_of_edges()
    degrees = [degree for _, degree in G.degree()]
    mean_degree = sum(degrees) / len(degrees) if degrees else 0.0
    degree_std = (
        math.sqrt(sum((degree - mean_degree) ** 2 for degree in degrees) / len(degrees))
        if degrees
        else 0.0
    )

    # Compute the same greedy elimination pressure used by the decomposition
    # order. The total fill and maximum eliminated degree describe how much
    # chordal structure the graph creates.
    H = G.copy()
    fill_edges = 0
    elimination_width = 0
    while H:
        best_node = None
        best_key = None
        for node in H:
            neighbors = list(H[node])
            fill_count = sum(
                not H.has_edge(left, right)
                for index, left in enumerate(neighbors)
                for right in neighbors[index + 1 :]
            )
            key = (fill_count, H.degree(node), str(node))
            if best_key is None or key < best_key:
                best_key = key
                best_node = node

        neighbors = list(H[best_node])
        fill_edges += sum(
            not H.has_edge(left, right)
            for index, left in enumerate(neighbors)
            for right in neighbors[index + 1 :]
        )
        elimination_width = max(elimination_width, len(neighbors))
        for index, left in enumerate(neighbors):
            for right in neighbors[index + 1 :]:
                H.add_edge(left, right)
        H.remove_node(best_node)

    articulation_count = len(list(nx.articulation_points(G))) if nodes else 0
    bridge_count = len(list(nx.bridges(G))) if edges else 0
    core_number = max(nx.core_number(G).values(), default=0)
    metrics = {
        "nodes": nodes,
        "edges": edges,
        "density": nx.density(G) if nodes > 1 else 0.0,
        "degree_std": degree_std,
        "max_degree": max(degrees, default=0),
        "clustering": nx.average_clustering(G) if nodes else 0.0,
        "core_number": core_number,
        "articulation_ratio": articulation_count / nodes if nodes else 0.0,
        "bridge_ratio": bridge_count / edges if edges else 0.0,
        "min_fill_edges": fill_edges,
        "elimination_width": elimination_width,
    }
    metrics["topology_score"] = (
        0.45 * fill_edges
        + 3.0 * elimination_width
        + 15.0 * degree_std
        + 20.0 * metrics["articulation_ratio"]
    )
    return metrics


# ============================================================
# 步骤 3: 解析 ZDD 文件 → 行 (完整枚举, 不截断)
# ============================================================
ZDD_SAFETY_LIMIT = 150_000  # 单块路径数硬上限 (仅作 OOM 兜底)


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
# 目标: 每个分块除了 ZDD 自身枚举出的路径行之外, 主动构造 51~100 组
# "精确覆盖解"(每组的若干行在该分块的列集合 U_b 上形成一个划分,
# 即每列恰好覆盖一次, 行之间列不相交)。把每组解中的每一行作为
# 独立矩阵行注入, 并做全局 frozenset 去重, 从而提升下游 DLX
# 求解器的搜索空间。
#
# 注意:
# 1) 新增行的局部列索引只来自 U_b (即本块 ZDD 行里出现过的列),
#    所以不会扩展 block_max_local_col, 分块列空间独立性保持不变。
# 2) 去重在全局 seen_frozensets 上做, 保证最终矩阵无重复行。

MIN_EXTRA_SOLUTIONS_PER_BLOCK = 51   # 每块最少目标构造组数 (>50)
MAX_EXTRA_SOLUTIONS_PER_BLOCK = 100  # 每块最多目标构造组数
SOLUTION_BUILD_MAX_TRIES = 5000      # 单块构造尝试次数上限, 避免死循环

# 初始分块数范围
MIN_BLOCKS = 6
MAX_BLOCKS = 10
MAX_MATRIX_ROWS = 150_000
TARGET_BLOCK_NODES = 0


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


def _iter_set_partitions(universe):
    """
    枚举 universe 的全部集合划分。每个划分是一组列不相交、并集为
    universe 的行，因此对应一个 exact cover 解。
    """
    columns = sorted(universe)
    if not columns:
        return

    def visit(remaining, groups):
        if not remaining:
            yield [sorted(group) for group in groups]
            return

        first = min(remaining)
        rest = remaining - {first}

        # first 单独成组
        yield from visit(rest, groups + [{first}])

        # first 加入当前已有的某个组
        for group in groups:
            group.add(first)
            yield from visit(rest, groups)
            group.remove(first)

    yield from visit(set(columns), [])


def _solution_key(solution):
    """把一组解规范化为可哈希、与行顺序无关的 key。"""
    return tuple(sorted(tuple(sorted(row)) for row in solution if row))


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
        "universe_size": 0,
    }

    if not zdd_rows_local:
        return [], stats

    # 本块的列全集 = ZDD 行里出现过的所有局部列
    universe = set()
    for r in zdd_rows_local:
        universe.update(r)
    if not universe:
        return [], stats
    stats["universe_size"] = len(universe)

    target = rng.randint(MIN_EXTRA_SOLUTIONS_PER_BLOCK,
                         MAX_EXTRA_SOLUTIONS_PER_BLOCK)
    stats["target_solutions"] = target

    extra_local_rows = []
    seen_solutions = set()
    tries = 0

    def add_solution(solution):
        """校验并记录一个与之前不同的 exact cover 解。"""
        if not solution:
            return False
        # 正确性校验: 每列恰好覆盖一次 (行之间列不相交, 且并集 == universe)
        covered = []
        for row in solution:
            covered.extend(row)
        if len(covered) != len(universe) or set(covered) != universe:
            return False

        solution_key = _solution_key(solution)
        if solution_key in seen_solutions:
            return False
        seen_solutions.add(solution_key)

        # 把本组解的每一行作为独立行加入, 全局 frozenset 去重
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
        return True

    # 两种随机构造方法交替使用, 提高行列分布多样性
    while len(seen_solutions) < target and tries < SOLUTION_BUILD_MAX_TRIES:
        tries += 1
        use_zdd_based = (tries % 2 == 0) and len(zdd_rows_local) > 0
        if use_zdd_based:
            solution = _solution_from_zdd_rows(universe, zdd_rows_local, rng)
        else:
            solution = _solution_from_partition(universe, rng)
        add_solution(solution)

    # 随机构造对小 universe 可能长期重复。枚举集合划分作为确定性兜底,
    # 从而在可行范围内稳定达到每块至少 51 个不同解。
    if len(seen_solutions) < target:
        for solution in _iter_set_partitions(universe):
            add_solution(solution)
            if len(seen_solutions) >= target:
                break

    stats["built_solutions"] = len(seen_solutions)

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
def block_zdd_strategy(
    G,
    order,
    zdd_engine_bin,
    temp_dir,
    base_name,
    zdd_seed=None,
):
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

    if TARGET_BLOCK_NODES:
        num_blocks = round(n / TARGET_BLOCK_NODES)
    else:
        num_blocks = random.randint(MIN_BLOCKS, MAX_BLOCKS)
    num_blocks = min(max(2, num_blocks), max(2, n // 2))

    # 顺序切分 min-fill 排序，同时让块大小最多相差 1。
    base_size, remainder = divmod(n, num_blocks)
    block_nodes_list = []
    cursor = 0
    for b in range(num_blocks):
        block_size = base_size + (1 if b < remainder else 0)
        end = cursor + block_size
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
    zdd_environment = os.environ.copy()
    if zdd_seed is not None:
        zdd_environment["ZDD_SEED"] = str(zdd_seed)

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
                timeout=300,    # C++ 端软预算 150s, 这里多留 150s 给 sparsify fallback 和 I/O
                env=zdd_environment,
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

        # ---- 2) 构造额外的精确覆盖解以扩充行数 ----
        extra_injected = 0
        extra_dup = 0
        extra_stats = {"target_solutions": 0, "built_solutions": 0}

        # 使用"全局 frozenset 视角"的去重集合
        local_seen = {frozenset(r) for r in rows if r}
        extra_local_rows, extra_stats = build_extra_exact_cover_rows(
            rows,
            local_seen,
            rng,
        )
        if extra_stats["built_solutions"] <= MIN_EXTRA_SOLUTIONS_PER_BLOCK - 1:
            print(
                f"  [Block {block_idx + 1}] 警告: 仅构造出 "
                f"{extra_stats['built_solutions']} 个不同的 exact cover 解 "
                f"(局部列数={extra_stats['universe_size']})，未达到 >50；"
                "请增大图规模或减少分块数"
            )

        # 再用全局去重集合过滤一次 (映射到 global 列)
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

        # ---- 3) 永远执行：更新当前块的状态和列偏移量 ----
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

        # ---- 4) 提前跳出机制 ----
        if len(all_rows) > MAX_MATRIX_ROWS:
            print(
                f"  [提前跳出] 当前总行数 {len(all_rows)} 已超过上限 "
                f"{MAX_MATRIX_ROWS}，停止处理后续分块。"
            )
            break  # 跳出 for 循环，直接执行后面的 return all_rows, col_offset

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


class _DisjointSet:
    def __init__(self, size):
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value):
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left, right):
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if self.rank[root_left] < self.rank[root_right]:
            root_left, root_right = root_right, root_left
        self.parent[root_right] = root_left
        if self.rank[root_left] == self.rank[root_right]:
            self.rank[root_left] += 1


def analyze_matrix_structure(matrix_path):
    """Measure the connected components relevant to DXZ/DynDXD."""
    with open(matrix_path, "r", encoding="utf-8") as stream:
        header = stream.readline().split()
        if len(header) < 2:
            raise ValueError(f"{matrix_path}: invalid matrix header")
        num_cols, num_rows = int(header[0]), int(header[1])
        row_cols = []
        column_rows = {}
        for row_id, line in enumerate(stream):
            values = [int(value) for value in line.split()]
            if not values:
                row_cols.append([])
                continue
            count = values[0]
            columns = values[1:]
            if len(columns) != count:
                raise ValueError(
                    f"{matrix_path}:{row_id + 2}: expected {count} columns"
                )
            row_cols.append(columns)
            for column in columns:
                column_rows.setdefault(column, []).append(row_id)

    if len(row_cols) < num_rows:
        row_cols.extend([] for _ in range(num_rows - len(row_cols)))
    row_cols = row_cols[:num_rows]

    dsu = _DisjointSet(num_rows)
    for row_ids in column_rows.values():
        if not row_ids:
            continue
        first = row_ids[0]
        for row_id in row_ids[1:]:
            dsu.union(first, row_id)

    component_rows = {}
    component_cols = {}
    component_row_ids = {}
    for row_id, columns in enumerate(row_cols):
        if not columns:
            continue
        root = dsu.find(row_id)
        component_rows[root] = component_rows.get(root, 0) + 1
        component_cols.setdefault(root, set()).update(columns)
        component_row_ids.setdefault(root, []).append(row_id)

    areas = sorted(
        (
            component_rows[root] * len(columns)
            for root, columns in component_cols.items()
        ),
        reverse=True,
    )
    total_area = sum(areas)
    return {
        "matrix_rows": num_rows,
        "matrix_cols": num_cols,
        "valid_components": len(areas),
        "largest_component_area": areas[0] if areas else 0,
        "largest_component_area_share": areas[0] / total_area if total_area else 0.0,
        "component_areas": areas,
        "unique_rows": num_rows == len({tuple(row) for row in row_cols}),
        "_row_cols": row_cols,
        "_component_row_ids": component_row_ids,
        "_component_cols": component_cols,
    }


def count_exact_cover_solutions(
    row_cols,
    component_row_ids,
    component_cols,
):
    """
    按独立分量精确计数精确覆盖解。

    单个分量的列数通常只有 13~22。把列编码成位掩码后，对剩余列状态
    做记忆化递归即可精确得到解数，再对各分量的解数求积。
    """
    component_counts = []
    total = 1

    for root in sorted(
        component_row_ids,
        key=lambda key: (
            len(component_cols[key]) * len(component_row_ids[key]),
            key,
        ),
        reverse=True,
    ):
        columns = sorted(component_cols[root])
        if not columns:
            component_counts.append(0)
            total = 0
            continue

        # 把较少出现的列放在低位，优先围绕低分支列做状态转移。
        frequencies = {
            column: sum(column in row_cols[row_id]
                        for row_id in component_row_ids[root])
            for column in columns
        }
        columns.sort(key=lambda column: (frequencies[column], column))
        column_bit = {column: index for index, column in enumerate(columns)}

        row_masks = {
            sum(1 << column_bit[column] for column in row_cols[row_id])
            for row_id in component_row_ids[root]
        }

        rows_by_column = [[] for _ in columns]
        for mask in row_masks:
            bits = mask
            while bits:
                bit = bits & -bits
                rows_by_column[bit.bit_length() - 1].append(mask)
                bits -= bit

        @lru_cache(maxsize=None)
        def count(mask):
            if mask == 0:
                return 1
            first_bit = mask & -mask
            first_column = first_bit.bit_length() - 1
            return sum(
                count(mask ^ row_mask)
                for row_mask in rows_by_column[first_column]
                if row_mask & mask == row_mask
            )

        component_count = count((1 << len(columns)) - 1)
        component_counts.append(component_count)
        total *= component_count

    return total, component_counts


def add_exact_solution_count(stats, min_solution_count):
    """Add exact solution statistics used as a hard matrix-profile gate."""
    solution_count, component_counts = count_exact_cover_solutions(
        stats["_row_cols"],
        stats["_component_row_ids"],
        stats["_component_cols"],
    )
    stats["solution_count"] = solution_count
    stats["solution_log10"] = (
        math.log10(solution_count) if solution_count else float("-inf")
    )
    stats["component_solution_counts"] = component_counts
    stats["meets_solution_target"] = solution_count >= min_solution_count
    return stats


def matrix_replication_count(args, stats):
    """
    返回达到目标规模所需的矩阵复制次数。

    复制矩阵等价于加入若干个互不共享列的分量：行数和列数按 k 倍增长，
    精确覆盖解数按 base_solution_count ** k 增长。矩阵内部的行结构、
    每个分量的规模和列模式保持不变。
    """
    if stats["solution_count"] <= 0:
        return None

    for copies in range(args.min_replications, args.max_replications + 1):
        matrix_rows = stats["matrix_rows"] * copies
        matrix_cols = stats["matrix_cols"] * copies
        if matrix_rows > args.matrix_rows_max:
            return None
        if matrix_cols > args.matrix_cols_max:
            return None
        if (
            matrix_rows >= args.matrix_rows_min
            and matrix_cols >= args.matrix_cols_min
            and stats["solution_count"] ** copies >= args.min_solution_count
        ):
            return copies

    return None


def replicate_matrix_file(matrix_path, copies):
    """把一个稀疏矩阵以互不重叠的新列空间复制 copies 次。"""
    if copies <= 0:
        raise ValueError("matrix replication count must be positive")
    if copies == 1:
        return

    with open(matrix_path, "r", encoding="utf-8") as stream:
        header = stream.readline().split()
        num_cols, num_rows = int(header[0]), int(header[1])
        rows = []
        for line in stream:
            values = [int(value) for value in line.split()]
            if values:
                rows.append(values[1:])

    if len(rows) != num_rows:
        raise ValueError(
            f"{matrix_path}: header declares {num_rows} rows, read {len(rows)}"
        )

    replicated_rows = []
    for copy_index in range(copies):
        column_offset = copy_index * num_cols
        replicated_rows.extend(
            [column + column_offset for column in row]
            for row in rows
        )

    write_matrix(replicated_rows, num_cols * copies, matrix_path)


def _matrix_profile_score(
    stats,
    target_rows,
    target_cols,
    target_area_share,
    target_solution_log10,
):
    row_distance = abs(
        math.log(max(stats["matrix_rows"], 1) / max(target_rows, 1))
    )
    col_distance = abs(
        math.log(max(stats["matrix_cols"], 1) / max(target_cols, 1))
    )
    area_distance = abs(
        stats["largest_component_area_share"] - target_area_share
    )
    component_distance = abs(stats["valid_components"] - 9) / 9.0
    solution_distance = abs(
        stats["solution_log10"] - target_solution_log10
    )
    return (
        row_distance
        + col_distance
        + 4.0 * area_distance
        + 0.05 * component_distance
        + 0.1 * solution_distance
    )


def _matrix_meets_shape_profile(args, stats):
    return (
        args.matrix_rows_min <= stats["matrix_rows"] <= args.matrix_rows_max
        and args.matrix_cols_min <= stats["matrix_cols"] <= args.matrix_cols_max
        and args.min_components <= stats["valid_components"] <= args.max_components
        and args.min_largest_area_share
        <= stats["largest_component_area_share"]
        <= args.max_largest_area_share
        and stats["unique_rows"]
    )


def _matrix_meets_profile(args, stats):
    return (
        _matrix_meets_shape_profile(args, stats)
        and stats["meets_solution_target"]
    )


def _public_matrix_stats(stats):
    return {
        key: value
        for key, value in stats.items()
        if not key.startswith("_")
    }


def _graphml_candidates(args):
    source = Path(args.select_rome_dir).resolve()
    if not source.is_dir():
        raise ValueError(f"GraphML directory not found: {source}")

    excluded_names = set(args.exclude_name)
    for excluded_dir in args.exclude_matrix_dir:
        excluded_path = Path(excluded_dir).resolve()
        if excluded_path.is_dir():
            excluded_names.update(
                path.stem for path in excluded_path.glob("*.txt")
            )

    candidates = []
    for graphml_path in sorted(source.glob("*.graphml")):
        if graphml_path.stem in excluded_names:
            continue
        graph = nx.Graph(nx.read_graphml(graphml_path))
        graph.remove_edges_from(nx.selfloop_edges(graph))
        metrics = graph_topology_metrics(graph)
        if not (
            args.min_edges <= metrics["edges"] <= args.max_edges
            and args.min_nodes <= metrics["nodes"] <= args.max_nodes
            and metrics["min_fill_edges"] >= args.min_fill_edges
            and metrics["elimination_width"] >= args.min_elimination_width
            and metrics["degree_std"] >= args.min_degree_std
            and metrics["articulation_ratio"] <= args.max_articulation_ratio
        ):
            continue
        candidates.append(
            {
                "graphml": str(graphml_path),
                "name": graphml_path.stem,
                **metrics,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["topology_score"],
            item["min_fill_edges"],
            item["elimination_width"],
            item["name"],
        ),
        reverse=True,
    )
    if args.randomize_candidates:
        random.Random(args.seed).shuffle(candidates)
    return candidates


def select_and_generate_topology_cases(args, zdd_engine_bin):
    """Select topology-qualified Rome graphs and retain one profile-matched seed."""
    output_dir = Path(args.output).resolve()
    input_dir = output_dir / "inputs"
    selected_dir = output_dir / "matrices"
    candidate_dir = output_dir / "candidates"
    temp_root = output_dir / "temp"
    for directory in (input_dir, selected_dir, candidate_dir, temp_root):
        directory.mkdir(parents=True, exist_ok=True)

    candidates = _graphml_candidates(args)
    print(
        f"[auto-select] topology filter matched {len(candidates)} graphs "
        f"from {Path(args.select_rome_dir).resolve()}"
    )
    if not candidates:
        print("[auto-select] no graph matched the topology standard", file=sys.stderr)
        return 2

    seeds = [args.seed + offset for offset in range(args.search_seeds)]
    selected = []
    for graph_index, candidate in enumerate(candidates, start=1):
        if len(selected) >= args.select_count:
            break

        graphml_path = Path(candidate["graphml"])
        graph_candidate_dir = candidate_dir / candidate["name"]
        graph_candidate_dir.mkdir(parents=True, exist_ok=True)
        working_input_path = graph_candidate_dir / f"{candidate['name']}.in"
        parse_graphml_to_in(str(graphml_path), str(working_input_path))

        seed_results = []
        for seed in seeds:
            seed_output = graph_candidate_dir / f"seed_{seed}"
            seed_output.mkdir(parents=True, exist_ok=True)
            seed_temp = temp_root / f"{candidate['name']}_seed_{seed}"
            seed_temp.mkdir(parents=True, exist_ok=True)
            random.seed(seed)
            matrix_path = process_single_task(
                str(working_input_path),
                zdd_engine_bin,
                str(seed_temp),
                str(seed_output),
                zdd_seed=seed,
            )
            if not matrix_path:
                continue
            stats = analyze_matrix_structure(matrix_path)
            if stats["matrix_cols"] < args.base_matrix_cols_min:
                print(
                    f"[auto-select] {candidate['name']} seed={seed} "
                    f"base cols={stats['matrix_cols']} < "
                    f"{args.base_matrix_cols_min}; skip",
                    file=sys.stderr,
                )
                stats.update(
                    {
                        "solution_count": 0,
                        "solution_log10": float("-inf"),
                        "component_solution_counts": [],
                        "meets_solution_target": False,
                        "replications": 0,
                    }
                )
                seed_results.append(
                    {
                        "seed": seed,
                        "matrix_path": matrix_path,
                        "profile_score": float("inf"),
                        "meets_profile": False,
                        **stats,
                    }
                )
                continue
            print(
                f"[auto-select] {candidate['name']} seed={seed} "
                "counting exact covers in the base matrix..."
            )
            add_exact_solution_count(stats, args.min_solution_count)
            base_stats = _public_matrix_stats(stats)
            copies = matrix_replication_count(args, stats)
            if copies is None:
                stats.update(
                    {
                        "meets_solution_target": False,
                        "replications": 0,
                    }
                )
                meets_profile = False
                profile_score = float("inf")
            else:
                replicate_matrix_file(matrix_path, copies)
                final_stats = analyze_matrix_structure(matrix_path)
                final_stats.update(
                    {
                        "solution_count": stats["solution_count"] ** copies,
                        "component_solution_counts": [
                            count
                            for _ in range(copies)
                            for count in stats["component_solution_counts"]
                        ],
                        "meets_solution_target": True,
                        "replications": copies,
                        "base_matrix_rows": base_stats["matrix_rows"],
                        "base_matrix_cols": base_stats["matrix_cols"],
                        "base_solution_count": base_stats["solution_count"],
                        "base_solution_log10": base_stats["solution_log10"],
                    }
                )
                final_stats["solution_log10"] = math.log10(
                    final_stats["solution_count"]
                )
                meets_profile = _matrix_meets_profile(args, final_stats)
                profile_score = _matrix_profile_score(
                    final_stats,
                    args.target_matrix_rows,
                    args.target_matrix_cols,
                    args.target_area_share,
                    args.min_solution_log10,
                )
                stats = final_stats
            seed_results.append(
                {
                    "seed": seed,
                    "matrix_path": matrix_path,
                    "profile_score": profile_score,
                    "meets_profile": meets_profile,
                    **stats,
                }
            )

        if not seed_results:
            print(
                f"[auto-select] {candidate['name']} produced no valid matrix; skip",
                file=sys.stderr,
            )
            continue

        eligible = [result for result in seed_results if result["meets_profile"]]
        if not eligible:
            print(
                f"[auto-select] {candidate['name']} produced no seed satisfying "
                "the hard matrix profile; skip",
                file=sys.stderr,
            )
            continue
        best = min(
            eligible,
            key=lambda result: result["profile_score"],
        )
        public_best = _public_matrix_stats(best)
        selected_path = selected_dir / f"{candidate['name']}.txt"
        selected_input = input_dir / f"{candidate['name']}.in"
        shutil.copy2(best["matrix_path"], selected_path)
        shutil.copy2(working_input_path, selected_input)
        selected.append(
            {
                **candidate,
                **public_best,
                "topology_rank": graph_index,
                "selected_seed": best["seed"],
                "selected_matrix": str(selected_path),
                "selected_input": str(selected_input),
                "seed_candidates": len(seed_results),
            }
        )
        print(
            f"[auto-select] {graph_index}/{len(candidates)} {candidate['name']}: "
            f"seed={best['seed']} rows={best['matrix_rows']} "
            f"cols={best['matrix_cols']} components={best['valid_components']} "
            f"max_share={best['largest_component_area_share']:.4f} "
            f"log10_solutions={best['solution_log10']:.3f} "
            f"replications={best['replications']} "
            "profile=pass"
        )

    if len(selected) < args.select_count:
        print(
            f"[auto-select] warning: selected {len(selected)} of "
            f"{args.select_count} requested matrices",
            file=sys.stderr,
        )

    report_path = output_dir / "selection_report.csv"
    report_fields = [
        "topology_rank",
        "name",
        "graphml",
        "selected_input",
        "selected_matrix",
        "nodes",
        "edges",
        "density",
        "degree_std",
        "max_degree",
        "clustering",
        "core_number",
        "articulation_ratio",
        "bridge_ratio",
        "min_fill_edges",
        "elimination_width",
        "topology_score",
        "selected_seed",
        "seed_candidates",
        "matrix_rows",
        "matrix_cols",
        "valid_components",
        "largest_component_area_share",
        "component_areas",
        "solution_count",
        "solution_log10",
        "component_solution_counts",
        "base_matrix_rows",
        "base_matrix_cols",
        "base_solution_count",
        "base_solution_log10",
        "replications",
        "meets_solution_target",
        "profile_score",
        "within_profile",
    ]
    with report_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=report_fields)
        writer.writeheader()
        for item in selected:
            writer.writerow(
                {
                    "topology_rank": item["topology_rank"],
                    "name": item["name"],
                    "graphml": item["graphml"],
                    "selected_input": item["selected_input"],
                    "selected_matrix": item["selected_matrix"],
                    "nodes": item["nodes"],
                    "edges": item["edges"],
                    "density": item["density"],
                    "degree_std": item["degree_std"],
                    "max_degree": item["max_degree"],
                    "clustering": item["clustering"],
                    "core_number": item["core_number"],
                    "articulation_ratio": item["articulation_ratio"],
                    "bridge_ratio": item["bridge_ratio"],
                    "min_fill_edges": item["min_fill_edges"],
                    "elimination_width": item["elimination_width"],
                    "topology_score": item["topology_score"],
                    "selected_seed": item["selected_seed"],
                    "seed_candidates": item["seed_candidates"],
                    "matrix_rows": item["matrix_rows"],
                    "matrix_cols": item["matrix_cols"],
                    "valid_components": item["valid_components"],
                    "largest_component_area_share": item[
                        "largest_component_area_share"
                    ],
                    "component_areas": "|".join(
                        str(value) for value in item["component_areas"]
                    ),
                    "solution_count": item["solution_count"],
                    "solution_log10": item["solution_log10"],
                    "component_solution_counts": "|".join(
                        str(value) for value in item["component_solution_counts"]
                    ),
                    "base_matrix_rows": item["base_matrix_rows"],
                    "base_matrix_cols": item["base_matrix_cols"],
                    "base_solution_count": item["base_solution_count"],
                    "base_solution_log10": item["base_solution_log10"],
                    "replications": item["replications"],
                    "meets_solution_target": item["meets_solution_target"],
                    "profile_score": item["profile_score"],
                    "within_profile": item["meets_profile"],
                }
            )

    manifest = {
        "source_graphml_dir": str(Path(args.select_rome_dir).resolve()),
        "output_dir": str(output_dir),
        "zdd_engine": str(Path(zdd_engine_bin).resolve()),
        "zdd_engine_sha256": hashlib.sha256(
            Path(zdd_engine_bin).read_bytes()
        ).hexdigest(),
        "topology_candidates": len(candidates),
        "selected_count": len(selected),
        "selection_report": str(report_path),
        "criteria": {
            "edges": [args.min_edges, args.max_edges],
            "nodes": [args.min_nodes, args.max_nodes],
            "min_fill_edges": args.min_fill_edges,
            "elimination_width": args.min_elimination_width,
            "degree_std": args.min_degree_std,
            "max_articulation_ratio": args.max_articulation_ratio,
            "blocks": [args.min_blocks, args.max_blocks],
            "extra_solutions": [
                args.min_extra_solutions,
                args.max_extra_solutions,
            ],
            "matrix_rows": [args.matrix_rows_min, args.matrix_rows_max],
            "matrix_cols": [args.matrix_cols_min, args.matrix_cols_max],
            "components": [args.min_components, args.max_components],
            "largest_area_share": [
                args.min_largest_area_share,
                args.max_largest_area_share,
            ],
            "target_matrix_rows": args.target_matrix_rows,
            "target_matrix_cols": args.target_matrix_cols,
            "target_area_share": args.target_area_share,
            "randomize_candidates": args.randomize_candidates,
            "min_replications": args.min_replications,
            "max_replications": args.max_replications,
            "base_matrix_cols_min": args.base_matrix_cols_min,
            "min_solution_count": str(args.min_solution_count),
            "min_solution_log10": args.min_solution_log10,
            "base_seed": args.seed,
            "search_seeds": args.search_seeds,
        },
        "selected": selected,
    }
    with (output_dir / "selection_manifest.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)

    print(f"[auto-select] selection report: {report_path}")
    print(f"[auto-select] selected matrices: {selected_dir}")
    return 0 if len(selected) == args.select_count else 2


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
def process_single_task(
    graph_file,
    zdd_engine_bin,
    temp_dir,
    output_dir=".",
    zdd_seed=None,
):
    base_name = os.path.splitext(os.path.basename(graph_file))[0]
    print(f"\n========== 开始处理: {base_name} ==========")

    G, total_nodes = read_graph(graph_file)
    print(f"  图大小 |V|={total_nodes}, |E|={G.number_of_edges()}")

    if total_nodes < 4 or G.number_of_edges() == 0:
        print("  图过小, 放弃")
        clean_temp_dir(temp_dir)
        return None

    order = min_fill_tree_decomposition_order(G)

    output_matrix = os.path.abspath(os.path.join(output_dir, f"{base_name}.txt"))

    rows, num_cols = block_zdd_strategy(
        G,
        order,
        zdd_engine_bin,
        temp_dir,
        base_name,
        zdd_seed=zdd_seed,
    )

    if not rows:
        print("[错误] 所有分块均失败 (C++ 引擎的 fallback 链已用尽), 放弃当前测例")
        clean_temp_dir(temp_dir)
        return None

    write_matrix(rows, num_cols, output_matrix)
    print(f"[完成] {len(rows)} 行 x {num_cols} 列 -> {output_matrix}")

    clean_temp_dir(temp_dir)
    return output_matrix


# ============================================================
# 步骤 8: 入口
# ============================================================
def main():
    global MIN_BLOCKS, MAX_BLOCKS
    global MIN_EXTRA_SOLUTIONS_PER_BLOCK, MAX_EXTRA_SOLUTIONS_PER_BLOCK
    global ZDD_SAFETY_LIMIT, MAX_MATRIX_ROWS
    global TARGET_BLOCK_NODES

    parser = argparse.ArgumentParser(
        description='将图结构 (.in) 转换为精确覆盖矩阵实例 (基于ZDD枚举)',
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
    group.add_argument(
        '--select-rome-dir',
        metavar='DIR',
        help=(
            '从包含 GraphML 的 Rome 目录中按拓扑标准选图，并为每张图搜索多个种子'
        ),
    )
    parser.add_argument('-o', '--output', default="./output", help='输出目录')
    parser.add_argument('--seed', type=int, default=None, help='随机种子，固定后便于复现')
    parser.add_argument('--min-blocks', type=int, default=None)
    parser.add_argument('--max-blocks', type=int, default=None)
    parser.add_argument(
        '--target-block-size',
        type=int,
        default=None,
        help='按每个分块的目标节点数自动决定分块数',
    )
    parser.add_argument(
        '--min-extra-solutions',
        type=int,
        default=None,
        help='每块至少构造多少个不同的精确覆盖解',
    )
    parser.add_argument(
        '--max-extra-solutions',
        type=int,
        default=None,
    )
    parser.add_argument(
        '--zdd-safety-limit',
        type=int,
        default=ZDD_SAFETY_LIMIT,
        help='单块 ZDD 路径枚举上限',
    )
    parser.add_argument(
        '--max-rows',
        type=int,
        default=MAX_MATRIX_ROWS,
        help='最终矩阵总行数上限',
    )
    parser.add_argument(
        '--zdd-engine',
        default=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'build_zdd_bin',
            'main',
        ),
        help='ZDD 分块引擎路径',
    )
    parser.add_argument(
        '--temp-dir',
        default=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'temp',
        ),
        help='ZDD 中间文件目录',
    )
    parser.add_argument(
        '--select-count',
        type=int,
        default=10,
        help='自动模式最终保留的矩阵数',
    )
    parser.add_argument(
        '--search-seeds',
        type=int,
        default=3,
        help='自动模式每张图尝试的连续种子数',
    )
    parser.add_argument(
        '--randomize-candidates',
        action='store_true',
        help='随机打乱通过图级筛选的候选，而不是按拓扑分数排序',
    )
    parser.add_argument(
        '--max-replications',
        type=int,
        default=16,
        help=(
            '为达到矩阵硬门槛，最多把候选矩阵复制为多少个互列独立分量'
        ),
    )
    parser.add_argument(
        '--min-replications',
        type=int,
        default=1,
        help='即使基础矩阵达标，也至少复制为多少个互列独立分量',
    )
    parser.add_argument(
        '--base-matrix-cols-min',
        type=int,
        default=0,
        help='复制前基础矩阵允许进入计数的列数下限',
    )
    parser.add_argument(
        '--exclude-name',
        action='append',
        default=[],
        help='自动选图时排除的图名，可重复指定',
    )
    parser.add_argument(
        '--exclude-matrix-dir',
        action='append',
        default=[],
        help='排除该目录中同名矩阵对应的图，可重复指定',
    )
    parser.add_argument('--min-edges', type=int, default=135)
    parser.add_argument('--max-edges', type=int, default=140)
    parser.add_argument('--min-nodes', type=int, default=95)
    parser.add_argument('--max-nodes', type=int, default=100)
    parser.add_argument('--min-fill-edges', type=int, default=140)
    parser.add_argument('--min-elimination-width', type=int, default=9)
    parser.add_argument('--min-degree-std', type=float, default=1.30)
    parser.add_argument('--max-articulation-ratio', type=float, default=0.25)
    parser.add_argument('--matrix-rows-min', type=int, default=37001)
    parser.add_argument('--matrix-rows-max', type=int, default=60000)
    parser.add_argument('--matrix-cols-min', type=int, default=161)
    parser.add_argument('--matrix-cols-max', type=int, default=240)
    parser.add_argument('--min-components', type=int, default=10)
    parser.add_argument('--max-components', type=int, default=10)
    parser.add_argument('--min-largest-area-share', type=float, default=0.14)
    parser.add_argument('--max-largest-area-share', type=float, default=0.24)
    parser.add_argument('--min-solution-log10', type=int, default=95)
    parser.add_argument('--target-matrix-rows', type=int, default=40000)
    parser.add_argument('--target-matrix-cols', type=int, default=175)
    parser.add_argument('--target-area-share', type=float, default=0.18)
    args = parser.parse_args()

    auto_select = args.select_rome_dir is not None
    if args.seed is None:
        args.seed = 20261114
    if args.min_blocks is None:
        args.min_blocks = 10 if auto_select else MIN_BLOCKS
    if args.max_blocks is None:
        args.max_blocks = 10 if auto_select else MAX_BLOCKS
    if args.min_extra_solutions is None:
        args.min_extra_solutions = 3600 if auto_select else MIN_EXTRA_SOLUTIONS_PER_BLOCK
    if args.max_extra_solutions is None:
        args.max_extra_solutions = 4000 if auto_select else MAX_EXTRA_SOLUTIONS_PER_BLOCK

    if args.min_blocks < 2 or args.max_blocks < args.min_blocks:
        parser.error('require 2 <= --min-blocks <= --max-blocks')
    if args.target_block_size is not None and args.target_block_size < 3:
        parser.error('--target-block-size must be at least 3')
    if (
        args.min_extra_solutions < 1
        or args.max_extra_solutions < args.min_extra_solutions
    ):
        parser.error(
            'require 1 <= --min-extra-solutions <= --max-extra-solutions'
        )
    if args.zdd_safety_limit < 1 or args.max_rows < 1:
        parser.error('--zdd-safety-limit and --max-rows must be positive')
    if args.select_count < 1 or args.search_seeds < 1:
        parser.error('--select-count and --search-seeds must be positive')
    if args.max_replications < 1:
        parser.error('--max-replications must be positive')
    if args.min_replications < 1 or args.min_replications > args.max_replications:
        parser.error('require 1 <= --min-replications <= --max-replications')
    if args.base_matrix_cols_min < 0:
        parser.error('--base-matrix-cols-min must be non-negative')
    if (
        args.matrix_rows_min < 1
        or args.matrix_rows_max < args.matrix_rows_min
        or args.matrix_cols_min < 1
        or args.matrix_cols_max < args.matrix_cols_min
        or args.min_components < 1
        or args.max_components < args.min_components
        or args.min_largest_area_share < 0
        or args.max_largest_area_share < args.min_largest_area_share
        or args.min_solution_log10 < 0
    ):
        parser.error('invalid matrix profile bounds')
    args.min_solution_count = 10 ** args.min_solution_log10
    random.seed(args.seed)

    MIN_BLOCKS = args.min_blocks
    MAX_BLOCKS = args.max_blocks
    MIN_EXTRA_SOLUTIONS_PER_BLOCK = args.min_extra_solutions
    MAX_EXTRA_SOLUTIONS_PER_BLOCK = args.max_extra_solutions
    ZDD_SAFETY_LIMIT = args.zdd_safety_limit
    MAX_MATRIX_ROWS = args.max_rows
    TARGET_BLOCK_NODES = args.target_block_size

    zdd_engine_bin = os.path.abspath(args.zdd_engine)
    if not os.path.isfile(zdd_engine_bin):
        print(f"错误: 找不到 ZDD 引擎 {zdd_engine_bin}", file=sys.stderr)
        sys.exit(1)
    temp_dir = os.path.abspath(args.temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    if args.select_rome_dir:
        try:
            return select_and_generate_topology_cases(args, zdd_engine_bin)
        except ValueError as exc:
            print(f"错误: {exc}", file=sys.stderr)
            return 2
    if args.input:
        graph_file = os.path.abspath(args.input)
        if not os.path.isfile(graph_file):
            print(f"错误: 找不到输入文件 {graph_file}")
            sys.exit(1)
        process_single_task(
            graph_file,
            zdd_engine_bin,
            temp_dir,
            output_dir,
            zdd_seed=args.seed,
        )
    else:
        folder = os.path.abspath(args.directory)
        if not os.path.isdir(folder):
            print(f"错误: 找不到文件夹 {folder}")
            sys.exit(1)
        targets = sorted(glob.glob(os.path.join(folder, "*.in")))
        if not targets:
            print(f"警告: {folder} 下未找到任何 .in 文件")
            sys.exit(0)
        print(f"找到 {len(targets)} 个 .in 文件, 开始批量处理...")
        for fp in targets:
            base_name = os.path.splitext(os.path.basename(fp))[0]
            expected = os.path.join(output_dir, f"{base_name}.txt")
            # if os.path.exists(expected):
            #     print(f"[跳过] 输出 {expected} 已存在")
            #     continue
            process_single_task(
                fp,
                zdd_engine_bin,
                temp_dir,
                output_dir,
                zdd_seed=args.seed,
            )

    print(f"\n--- 全部任务结束 ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
