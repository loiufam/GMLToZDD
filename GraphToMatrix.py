"""
GraphToMatrix: 将图结构 (.in) 转换为精确覆盖矩阵实例

三步转换策略
------------
Step 1  基于原图结构生成图块 (graph blocks)
        - 对每个连通分量，选 1 个 special 顶点 + 30% element 顶点
        - 枚举所有经过 special 且至少含一个 element 的 simple cycle
        - element 集合构成该块的全集 U，每个 cycle ∩ elements 是一行

Step 2  额外生成若干独立子矩阵 (extra blocks)，保证可解、规模多样
        - unique:    单解 (1 个全覆盖行 + 冲突干扰行)
        - partition: 多解 (列集合的多种划分)
        - nqueens:   N-皇后风格 (行/列约束 + 格子选项)
        - tiling:    分块铺砌风格 (单格 / 骨牌 / 三格)
        - nested:    嵌套块 (内部含桥接行，可再分为 2 个子块)

Step 3  拼成大矩阵 + 打乱行列
        - 列号重新随机映射，行顺序随机 shuffle
"""

import argparse
import glob
import os
import random
import sys
from typing import Dict, List, Set, Tuple

import networkx as nx


# =============================================================================
# 主类
# =============================================================================

class GraphToMatrix:
    """把图转成精确覆盖矩阵实例的三步法转换器"""

    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)
        self.graph: nx.Graph = None
        self.items: List[int] = []       # 列
        self.options: List[List[int]] = []  # 行

    # ----------------------------------------------------------------------
    # 图加载
    # ----------------------------------------------------------------------
    def load_graph(self, filename: str) -> nx.Graph:
        with open(filename) as f:
            lines = f.readlines()

        n, m = map(int, lines[0].split()[:2])
        G = nx.Graph()
        G.add_nodes_from(range(n))

        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            u, v = int(parts[0]), int(parts[1])
            if u != v:
                G.add_edge(u, v)

        self.graph = G
        return G

    # ======================================================================
    # Step 1: 图结构 -> 图块
    # ======================================================================
    def step1_graph_to_blocks(
        self,
        element_ratio: float = 0.3,
        max_cycle_length: int = 8,
        max_cycles_per_block: int = 600,
    ) -> List[Dict]:
        """
        对每个连通分量:
          1. 选 degree 最大的顶点作为 special
          2. 从剩余顶点随机抽 30% 作为 element
          3. DFS 枚举经过 special 的 simple cycle (长度 ≤ max_cycle_length)
          4. 每个 cycle 与 element 的交集即一行
          5. 附加一个全覆盖行以保证子块有解
        """
        blocks = []
        components = list(nx.connected_components(self.graph))

        for idx, comp in enumerate(components):
            comp = list(comp)
            if len(comp) < 3:
                continue

            subg = self.graph.subgraph(comp).copy()
            special = max(comp, key=lambda v: subg.degree(v))

            others = [v for v in comp if v != special]
            num_elem = max(1, int(len(others) * element_ratio))
            elements = set(random.sample(others, num_elem))

            cycles = self._enumerate_cycles(
                subg, special, max_cycle_length, max_cycles_per_block
            )

            # 每行 = cycle 与 element 的交集 (必须非空)
            row_set: Set[Tuple[int, ...]] = set()
            for cyc in cycles:
                inter = tuple(sorted(set(cyc) & elements))
                if inter:
                    row_set.add(inter)

            if not row_set:
                continue

            cols = sorted(elements)
            rows = [list(r) for r in row_set]

            # 保证子块可解: 附加一个全覆盖行 (兜底解)
            full = tuple(cols)
            if full not in row_set:
                rows.append(list(cols))

            blocks.append({
                'columns': cols,
                'rows': rows,
                'type': f'graph_comp{idx}',
            })

        return blocks

    @staticmethod
    def _enumerate_cycles(
        G: nx.Graph,
        special: int,
        max_length: int,
        max_cycles: int,
    ) -> List[List[int]]:
        """
        DFS 枚举经过 special 的 simple cycle。
        用 frozenset 做去重 (同一个 cycle 顺/逆序只保留一次)。
        """
        cycles: List[List[int]] = []
        seen: Set[frozenset] = set()

        def dfs(current: int, path: List[int], visited: Set[int]):
            if len(cycles) >= max_cycles:
                return
            if len(path) > max_length:
                return
            for nb in G.neighbors(current):
                if len(cycles) >= max_cycles:
                    return
                if nb == special and len(path) >= 3:
                    key = frozenset(path)
                    if key not in seen:
                        seen.add(key)
                        cycles.append(list(path))
                elif nb != special and nb not in visited:
                    visited.add(nb)
                    path.append(nb)
                    dfs(nb, path, visited)
                    path.pop()
                    visited.remove(nb)

        dfs(special, [special], {special})
        return cycles

    # ======================================================================
    # Step 2: 额外子矩阵
    # ======================================================================
    def step2_generate_extra_blocks(
        self,
        num_extra: int = None,
    ) -> List[Dict]:
        if num_extra is None:
            num_extra = random.randint(4, 8)

        generators = [
            ('unique',    self._gen_unique_solution_block),
            ('partition', self._gen_partition_block),
            ('partition', self._gen_partition_block),   # 稍微倾向 partition
            ('nqueens',   self._gen_nqueens_style_block),
            ('tiling',    self._gen_tiling_style_block),
            ('nested',    self._gen_nested_block),
        ]

        blocks = []
        for _ in range(num_extra):
            kind, gen = random.choice(generators)
            try:
                b = gen()
                b['type'] = kind
                blocks.append(b)
            except Exception as e:
                print(f"  [warn] 生成 {kind} 块失败: {e}")
        return blocks

    # ---- 子生成器 ---------------------------------------------------------

    def _gen_unique_solution_block(self) -> Dict:
        """唯一解: 1 全覆盖行 + 若干冲突的部分覆盖行"""
        n = random.randint(8, 14)
        cols = list(range(n))
        rows = [cols[:]]  # 唯一解行
        seen = {tuple(cols)}
        for _ in range(random.randint(12, 25)):
            size = random.randint(max(1, n // 3), max(2, n * 3 // 4))
            r = tuple(sorted(random.sample(cols, size)))
            if r not in seen:
                seen.add(r)
                rows.append(list(r))
        return {'columns': cols, 'rows': rows}

    def _gen_partition_block(self) -> Dict:
        """多解: 列集合的若干种划分 + 干扰行"""
        n = random.randint(10, 18)
        cols = list(range(n))
        row_set: Set[Tuple[int, ...]] = set()

        for _ in range(random.randint(3, 6)):
            shuf = cols[:]
            random.shuffle(shuf)
            k = random.randint(2, min(5, max(2, n // 3)))
            sizes = self._random_partition(n, k)
            i = 0
            for s in sizes:
                row_set.add(tuple(sorted(shuf[i:i + s])))
                i += s

        # 干扰行 (不是完整覆盖)
        for _ in range(random.randint(10, 20)):
            size = random.randint(1, max(2, n // 2))
            row_set.add(tuple(sorted(random.sample(cols, size))))

        return {'columns': cols, 'rows': [list(r) for r in row_set]}

    def _gen_nqueens_style_block(self) -> Dict:
        """
        N 皇后风格: 2n 列 (n 个行约束 + n 个列约束)。
        每个 (r, c) 位置对应一个选项, 覆盖 row_r 和 col_c 两列。
        有 n! 个解 (完美匹配 = 置换)。
        """
        n = random.randint(4, 6)
        row_items = list(range(n))
        col_items = list(range(n, 2 * n))
        cols = row_items + col_items

        rows = []
        for r in range(n):
            for c in range(n):
                rows.append(sorted([row_items[r], col_items[c]]))
        return {'columns': cols, 'rows': rows}

    def _gen_tiling_style_block(self) -> Dict:
        """
        铺砌风格: 在 R×C 小网格上, 候选瓦片是单格 / 水平/竖直骨牌 / 三格条。
        单格瓦片保证一定有解 (全单格), 整体解数巨多。
        """
        R = random.randint(2, 3)
        C = random.randint(3, 5)
        cols = list(range(R * C))
        row_set: Set[Tuple[int, ...]] = set()

        # 单格
        for c in cols:
            row_set.add((c,))
        # 水平骨牌
        for r in range(R):
            for c in range(C - 1):
                row_set.add(tuple(sorted([r * C + c, r * C + c + 1])))
        # 竖直骨牌
        for r in range(R - 1):
            for c in range(C):
                row_set.add(tuple(sorted([r * C + c, (r + 1) * C + c])))
        # 水平三格
        for r in range(R):
            for c in range(C - 2):
                row_set.add(tuple(sorted([r * C + c, r * C + c + 1, r * C + c + 2])))

        return {'columns': cols, 'rows': [list(r) for r in row_set]}

    def _gen_nested_block(self) -> Dict:
        """
        嵌套块: 内部本身由两个子块 + 少量内部桥接行构成。
        整体仍是一个独立块, 但 BFS 能把它分两半则需要先识别并排除桥接行。
        """
        a = random.randint(5, 8)
        b = random.randint(5, 8)
        sub1 = list(range(a))
        sub2 = list(range(a, a + b))
        all_cols = sub1 + sub2
        row_set: Set[Tuple[int, ...]] = set()

        # sub1 的若干划分
        for _ in range(random.randint(2, 3)):
            shuf = sub1[:]
            random.shuffle(shuf)
            sizes = self._random_partition(a, random.randint(2, 3))
            i = 0
            for s in sizes:
                row_set.add(tuple(sorted(shuf[i:i + s])))
                i += s
        # sub2 的若干划分
        for _ in range(random.randint(2, 3)):
            shuf = sub2[:]
            random.shuffle(shuf)
            sizes = self._random_partition(b, random.randint(2, 3))
            i = 0
            for s in sizes:
                row_set.add(tuple(sorted(shuf[i:i + s])))
                i += s

        # 内部桥接行 (连接 sub1 与 sub2, 不参与解)
        for _ in range(random.randint(2, 4)):
            t1 = random.randint(1, min(2, a))
            t2 = random.randint(1, min(2, b))
            br = tuple(sorted(random.sample(sub1, t1) + random.sample(sub2, t2)))
            row_set.add(br)

        return {'columns': all_cols, 'rows': [list(r) for r in row_set]}

    @staticmethod
    def _random_partition(n: int, k: int) -> List[int]:
        """把整数 n 拆成 k 个正整数之和 (随机)"""
        if k <= 1:
            return [n]
        if k >= n:
            return [1] * n
        cuts = sorted(random.sample(range(1, n), k - 1))
        sizes = []
        prev = 0
        for c in cuts:
            sizes.append(c - prev)
            prev = c
        sizes.append(n - prev)
        return sizes

    # ======================================================================
    # Step 3: 拼接 + 打乱
    # ======================================================================
    def step3_combine_and_shuffle(
        self,
        blocks: List[Dict],
        num_global_bridges: int = None,
    ):
        """
        - 为所有块统一编号 (全局列 ID, 1-indexed)
        - 重新随机映射列 ID、随机 shuffle 行顺序
        """
        # 1) 分配全局列 ID
        cursor = 1
        for blk in blocks:
            local = blk['columns']
            mp = {lc: cursor + i for i, lc in enumerate(local)}
            blk['global_cols'] = [mp[c] for c in local]
            blk['global_rows'] = [sorted(mp[c] for c in r) for r in blk['rows']]
            cursor += len(local)
        total_cols = cursor - 1

        # 2) 收集行
        all_rows: List[List[int]] = []
        for blk in blocks:
            all_rows.extend(blk['global_rows'])

        # 3) 全局桥接行 (防 BFS 分块识别)
        # if num_global_bridges is None:
        #     num_global_bridges = max(4, min(20, total_cols // 6))
        # if len(blocks) >= 2:
        #     all_rows.extend(self._generate_global_bridges(blocks, num_global_bridges))

        # 4) 去重
        dedup = {tuple(r) for r in all_rows if r}
        all_rows = [list(r) for r in dedup]

        # 5) 列 ID 重映射
        perm = list(range(1, total_cols + 1))
        random.shuffle(perm)
        col_map = {old: perm[old - 1] for old in range(1, total_cols + 1)}
        remapped = [sorted(col_map[c] for c in r) for r in all_rows]

        # 6) 行顺序打乱
        random.shuffle(remapped)

        self.items = list(range(1, total_cols + 1))
        self.options = remapped

    @staticmethod
    def _generate_global_bridges(blocks: List[Dict], num_bridges: int) -> List[List[int]]:
        """每条桥接行从 2~3 个块各取 1~2 列"""
        bridges = []
        for _ in range(num_bridges):
            k = random.randint(2, min(3, len(blocks)))
            chosen = random.sample(blocks, k)
            row = []
            for b in chosen:
                if not b['global_cols']:
                    continue
                t = random.randint(1, min(2, len(b['global_cols'])))
                row.extend(random.sample(b['global_cols'], t))
            row = sorted(set(row))
            if len(row) >= 2:
                bridges.append(row)
        return bridges

    # ======================================================================
    # 统计 / 输出
    # ======================================================================
    def _density(self) -> float:
        if not self.items or not self.options:
            return 0.0
        filled = sum(len(r) for r in self.options)
        return filled / (len(self.items) * len(self.options))

    def save_matrix(self, filename: str):
        with open(filename, 'w') as f:
            f.write(f"{len(self.items)} {len(self.options)}\n")
            for opt in self.options:
                f.write(f"{len(opt)} " + " ".join(map(str, opt)) + "\n")

    # ======================================================================
    # 调度
    # ======================================================================
    def convert(self, graph_file: str, output_file: str, verbose: bool = True):
        self.load_graph(graph_file)
        if verbose:
            print(f"\n{'='*66}")
            print(f"输入: {graph_file}")
            print(f"图: {self.graph.number_of_nodes()} 顶点, "
                  f"{self.graph.number_of_edges()} 边, "
                  f"{nx.number_connected_components(self.graph)} 个连通分量")
            print('-' * 66)

        # Step 1
        gb = self.step1_graph_to_blocks()
        if verbose:
            print(f"[Step 1] 图块: {len(gb)} 个")
            for i, b in enumerate(gb):
                print(f"    - 块{i} [{b['type']}]: "
                      f"{len(b['columns'])} 列 × {len(b['rows'])} 行")

        # Step 2
        eb = self.step2_generate_extra_blocks()
        if verbose:
            print(f"[Step 2] 合成块: {len(eb)} 个")
            for i, b in enumerate(eb):
                print(f"    - 块{i} [{b['type']}]: "
                      f"{len(b['columns'])} 列 × {len(b['rows'])} 行")

        all_blocks = gb + eb
        if not all_blocks:
            raise ValueError("没有生成任何块, 检查图是否过小或过稀疏")

        # Step 3
        self.step3_combine_and_shuffle(all_blocks)
        if verbose:
            print(f"[Step 3] 拼接 & 打乱完成")
            print(f"    最终矩阵: {len(self.items)} 列 × {len(self.options)} 行, "
                  f"密度 {self._density():.2%}")

        self.save_matrix(output_file)
        if verbose:
            print(f"✓ 保存 → {output_file}")
            print('=' * 66)

    def batch_convert(
        self,
        input_dir: str,
        output_dir: str,
        max_count: int = 129,
        pattern: str = '*.in',
    ):
        os.makedirs(output_dir, exist_ok=True)
        files = sorted(glob.glob(os.path.join(input_dir, pattern)))
        if not files:
            print(f"在 {input_dir} 中未找到 {pattern}")
            return

        print(f"发现 {len(files)} 个文件, 最多转换 {max_count} 个")
        success = 0
        for i, gf in enumerate(files, 1):
            if success >= max_count:
                break
            try:
                name = os.path.splitext(os.path.basename(gf))[0]
                of = os.path.join(output_dir, f"{name}.txt")
                print(f"\n[{i}/{len(files)}] {os.path.basename(gf)}")
                self.convert(gf, of, verbose=True)
                success += 1
            except Exception as e:
                print(f"  ✗ 错误: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n{'='*66}")
        print(f"批量完成: {success}/{len(files)} 成功")
        print('=' * 66)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='将图结构 (.in) 转换为精确覆盖矩阵实例 (三步法)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 单文件
  python GraphToMatrix.py -i graph.in -o matrix.txt

  # 批量
  python GraphToMatrix.py -b -i ./graphs -o ./matrices

  # 固定随机种子以复现
  python GraphToMatrix.py -i g.in -o m.txt --seed 42
        """
    )
    parser.add_argument('-i', '--input', required=True,
                        help='输入文件 (单文件) 或目录 (配合 -b)')
    parser.add_argument('-o', '--output', required=True,
                        help='输出文件 (单文件) 或目录 (配合 -b)')
    parser.add_argument('-b', '--batch', action='store_true',
                        help='批量模式')
    parser.add_argument('--seed', type=int, default=None,
                        help='随机种子')
    parser.add_argument('-maxConvert', type=int, default=129,
                        help='批量模式下最大转换数量 (默认 129)')
    args = parser.parse_args()

    conv = GraphToMatrix(seed=args.seed)
    if args.batch:
        conv.batch_convert(args.input, args.output, args.maxConvert)
    else:
        conv.convert(args.input, args.output)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main()
    else:
        print("Graph → Exact Cover Matrix 转换器 (三步法)")
        print("=" * 60)
        print("用法:")
        print("  单文件: python graph_to_matrix.py -i graph.in -o matrix.txt")
        print("  批量:   python graph_to_matrix.py -b -i ./graphs -o ./matrices")
        print("  帮助:   python graph_to_matrix.py --help")