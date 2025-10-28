import numpy as np
from typing import List, Set, Tuple, Dict, Optional
from collections import defaultdict, deque
from dataclasses import dataclass

# ===================== ZDD 数据结构 =====================

@dataclass(frozen=True)
class ZDDNode:
    """ZDD节点"""
    node_id: int
    level: int  # 对应的顶点/变量
    lo: int     # low边指向的节点ID (0表示⊥终端节点)
    hi: int     # high边指向的节点ID (1表示⊤终端节点)
    
    def is_terminal(self) -> bool:
        return self.node_id in (0, 1)

class ZDD:
    """Zero-suppressed Binary Decision Diagram"""
    
    def __init__(self):
        self.nodes: Dict[int, ZDDNode] = {}
        # 终端节点
        self.nodes[0] = ZDDNode(0, -1, 0, 0)  # ⊥ (FALSE)
        self.nodes[1] = ZDDNode(1, -1, 1, 1)  # ⊤ (TRUE)
        self.next_id = 2
        
        # 唯一性表：(level, lo, hi) -> node_id
        self.unique_table: Dict[Tuple[int, int, int], int] = {}
        
    def make_node(self, level: int, lo: int, hi: int) -> int:
        """创建或获取ZDD节点（带唯一性检查）"""
        # ZDD规约规则1: 如果hi边指向⊥，则删除该节点
        if hi == 0:
            return lo
        
        # 检查是否已存在
        key = (level, lo, hi)
        if key in self.unique_table:
            return self.unique_table[key]
        
        # 创建新节点
        node_id = self.next_id
        self.next_id += 1
        self.nodes[node_id] = ZDDNode(node_id, level, lo, hi)
        self.unique_table[key] = node_id
        return node_id
    
    def enumerate_paths(self, root_id: int) -> List[Set[int]]:
        """枚举从根到⊤的所有路径，返回high边经过的level集合"""
        paths = []
        
        def dfs(node_id: int, current_set: Set[int]):
            if node_id == 0:  # ⊥终端
                return
            if node_id == 1:  # ⊤终端
                paths.append(current_set.copy())
                return
            
            node = self.nodes[node_id]
            
            # 走low边（不选择当前level）
            dfs(node.lo, current_set)
            
            # 走high边（选择当前level）
            current_set.add(node.level)
            dfs(node.hi, current_set)
            current_set.remove(node.level)
        
        dfs(root_id, set())
        return paths
    
    def export_to_text(self, root_id: int) -> str:
        """导出ZDD为文本格式"""
        lines = []
        visited = set()
        
        def dfs(node_id: int):
            if node_id in visited or node_id in (0, 1):
                return
            visited.add(node_id)
            
            node = self.nodes[node_id]
            lines.append(f"{node.node_id} {node.level} {node.lo} {node.hi}")
            
            dfs(node.lo)
            dfs(node.hi)
        
        dfs(root_id)
        return "\n".join(lines)
    
    def get_node_count(self, root_id: int) -> int:
        """获取ZDD中的节点数（不含终端节点）"""
        visited = set()
        
        def dfs(node_id: int):
            if node_id in visited or node_id in (0, 1):
                return
            visited.add(node_id)
            node = self.nodes[node_id]
            dfs(node.lo)
            dfs(node.hi)
        
        dfs(root_id)
        return len(visited)

# ===================== Frontier-based Search =====================

@dataclass(frozen=True)
class FrontierState:
    """
    Frontier状态：用于跟踪连通子图枚举过程中的状态
    
    frontier: 当前边界顶点集合（已处理但有未处理邻居的顶点）
    comp: 连通分量的等价类表示（使用并查集思想）
    """
    frontier: frozenset  # 当前frontier中的顶点
    comp: tuple  # 连通分量的父节点映射 (顶点 -> 代表元)
    
    def __hash__(self):
        return hash((self.frontier, self.comp))

class UnionFind:
    """轻量级并查集，用于跟踪frontier中的连通性"""
    
    def __init__(self, vertices: Set[int] | frozenset[int]):
        self.parent = {v: v for v in vertices}
    
    def find(self, x: int) -> int:
        """查找代表元（带路径压缩）"""
        if x not in self.parent:
            return x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    
    def union(self, x: int, y: int) -> bool:
        """合并两个集合"""
        px, py = self.find(x), self.find(y)
        if px == py:
            return False
        self.parent[px] = py
        return True
    
    def num_components(self) -> int:
        """返回连通分量数"""
        return len(set(self.find(v) for v in self.parent))
    
    def get_normalized_tuple(self) -> tuple:
        """返回规范化的元组表示（用于哈希）"""
        # 将每个顶点映射到其代表元
        mapping = {}
        next_id = 0
        result = []
        
        for v in sorted(self.parent.keys()):
            root = self.find(v)
            if root not in mapping:
                mapping[root] = next_id
                next_id += 1
            result.append((v, mapping[root]))
        
        return tuple(result)

class FrontierBasedZDDConstructor:
    """
    使用Frontier-based Search构造表示所有连通子图的ZDD
    
    核心思想：
    1. 按顶点编号顺序处理（0, 1, 2, ...）
    2. 维护frontier：已选择且有未处理邻居的顶点集合
    3. 使用并查集跟踪frontier内的连通性
    4. 剪枝：如果frontier中有多个连通分量，则无效
    """
    
    def __init__(self, n_vertices: int, edges: List[Tuple[int, int]]):
        self.n = n_vertices
        self.edges = edges
        
        # 构建邻接表
        self.neighbors = [set() for _ in range(n_vertices)]
        for u, v in edges:
            self.neighbors[u].add(v)
            self.neighbors[v].add(u)
        
        self.zdd = ZDD()
        # 状态: (vertex_index, frontier_set, ever_selected) -> node_id
        self.cache = {}
        
    def build_connected_subgraphs_zdd(self) -> int:
        """构造ZDD主函数"""
        print(f"开始构造ZDD...")
        
        # 初始状态：空frontier，未选择任何顶点
        root = self._build(0, frozenset(), False)
        
        print(f"ZDD构造完成！")
        print(f"  ZDD节点数: {self.zdd.get_node_count(root)}")
        print(f"  缓存大小: {len(self.cache)}")
        
        return root
        
    def _build(self, v: int, frontier: frozenset, ever_selected: bool) -> int:
        """
        递归构造ZDD
        
        Args:
            v: 当前要决策的顶点编号
            frontier: 当前frontier集合（已选择但有未处理邻居的顶点）
            ever_selected: 是否曾经选择过至少一个顶点（用于排除空集）
        
        Returns:
            ZDD节点ID（0表示⊥，1表示⊤）
        """
        # 终止条件：所有顶点都已处理
        if v == self.n:
            # 合法的连通子图：frontier为空 且 至少选了一个顶点
            if len(frontier) == 0 and ever_selected:
                return 1
            return 0
        
        # 检查缓存
        key = (v, frontier, ever_selected)
        if key in self.cache:
            return self.cache[key]
        
        # Low分支：不选择顶点v
        if v in frontier:
            # v在frontier中但不选择，需要从frontier移除
            new_frontier = frontier - {v}
            # 检查移除v后frontier是否仍然连通
            if len(new_frontier) > 0 and not self._is_connected_frontier(new_frontier):
                lo_child = 0  # 不连通，剪枝
            else:
                lo_child = self._build(v + 1, new_frontier, ever_selected)
        else:
            # v不在frontier中，状态不变
            lo_child = self._build(v + 1, frontier, ever_selected)
        
        # High分支：选择顶点v
        hi_child = self._select_vertex(v, frontier, ever_selected)
        
        # 创建ZDD节点
        result = self.zdd.make_node(v, lo_child, hi_child)
        self.cache[key] = result
        return result
    
    def _select_vertex(self, v: int, frontier: frozenset, ever_selected: bool) -> int:
        """选择顶点v并继续构造"""
        # 找出v的邻居中：
        # 1. 在frontier中的（past_neighbors）
        # 2. 未来要处理的（future_neighbors）
        past_neighbors = {u for u in self.neighbors[v] if u < v} & frontier
        future_neighbors = {u for u in self.neighbors[v] if u > v}
        
        # 更新frontier
        new_frontier = set(frontier)
        
        # 情况分析
        if len(past_neighbors) == 0:
            # v不连接任何frontier中的顶点
            if len(frontier) > 0:
                # 如果frontier已有顶点，添加v会形成第二个连通分量
                return 0  # 剪枝
            # frontier为空，v开启新的连通分量
        
        # 将v加入frontier（如果v有未处理的邻居）
        if len(future_neighbors) > 0:
            new_frontier.add(v)
        # 如果v没有未处理的邻居，v不进入frontier（直接完成）
        
        # 添加v的未处理邻居到frontier
        new_frontier.update(future_neighbors)
        
        # 检查新frontier的连通性
        if len(new_frontier) > 1 and not self._is_connected_frontier(new_frontier):
            return 0  # 不连通，剪枝
        
        return self._build(v + 1, frozenset(new_frontier), True)
    
    def _is_connected_frontier(self, frontier: set[int] | frozenset[int]) -> bool:
        """
        检查frontier中的顶点是否连通
        
        注意：这里检查的是"已选择的顶点"之间的连通性
        由于我们是增量式构造，frontier中的顶点应该始终连通
        但在移除顶点时可能断开连通性
        """
        if len(frontier) <= 1:
            return True
        
        # BFS检查连通性（只考虑frontier内的边）
        start = next(iter(frontier))
        visited = {start}
        queue = deque([start])
        
        while queue:
            u = queue.popleft()
            for neighbor in self.neighbors[u]:
                if neighbor in frontier and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return len(visited) == len(frontier)

# ===================== 简化版实现（更高效） =====================

class SimpleConnectedSubgraphZDD:
    """
    简化版连通子图ZDD构造
    使用更直接的方法：枚举所有子集，检查连通性
    对于小图（<15个顶点）非常高效
    """
    
    def __init__(self, n_vertices: int, edges: List[Tuple[int, int]]):
        self.n = n_vertices
        self.edges = edges
        
        # 构建邻接表
        self.adj = defaultdict(list)
        for u, v in edges:
            self.adj[u].append(v)
            self.adj[v].append(u)
        
        # 预计算所有连通子图
        self.connected_subgraphs = self._enumerate_connected_subgraphs()
        
    def _enumerate_connected_subgraphs(self) -> List[Set[int]]:
        """枚举所有连通子图"""
        result = []
        
        # 枚举所有非空子集
        for mask in range(1, 2**self.n):
            subset = {i for i in range(self.n) if mask & (1 << i)}
            if self._is_connected(subset):
                result.append(subset)
        
        return result
    
    def _is_connected(self, vertices: Set[int]) -> bool:
        """BFS检查连通性"""
        if not vertices:
            return False
        
        start = next(iter(vertices))
        visited = {start}
        queue = deque([start])
        
        while queue:
            u = queue.popleft()
            for v in self.adj[u]:
                if v in vertices and v not in visited:
                    visited.add(v)
                    queue.append(v)
        
        return len(visited) == len(vertices)
    
    def build_zdd(self) -> Tuple[ZDD, int]:
        """从连通子图列表构造ZDD"""
        zdd = ZDD()
        
        # 构造ZDD的递归函数
        memo = {}
        
        def construct(level: int, remaining: Set[int]) -> int:
            """
            level: 当前处理的顶点
            remaining: 剩余需要表示的子图索引集合
            """
            if level == self.n:
                # 所有顶点都已处理
                return 1 if len(remaining) > 0 else 0
            
            cache_key = (level, frozenset(remaining))
            if cache_key in memo:
                return memo[cache_key]
            
            # 分割：包含level的子图 vs 不包含level的子图
            with_level = {i for i in remaining if level in self.connected_subgraphs[i]}
            without_level = remaining - with_level
            
            # Low边：不选择当前顶点
            lo_child = construct(level + 1, without_level)
            
            # High边：选择当前顶点
            hi_child = construct(level + 1, with_level)
            
            result = zdd.make_node(level, lo_child, hi_child)
            memo[cache_key] = result
            return result
        
        # 初始调用
        all_indices = set(range(len(self.connected_subgraphs)))
        root_id = construct(0, all_indices)
        
        return zdd, root_id


# ===================== 主转换类 =====================

class GraphToExactCover:
    """将图结构转换为Exact Cover问题"""
    
    def __init__(self, 
                graph_file: str | None = None,
                vertices: list[int] | None = None,
                edges: list[tuple[int, int]] | None = None):
        """
        初始化
        
        Args:
            graph_file: 图文件路径（第一行：n m，后续每行：u v）
            vertices: 顶点列表（如果不提供graph_file）
            edges: 边列表（如果不提供graph_file）
        """
        if graph_file:
            self.vertices, self.edges = self._read_graph_file(graph_file)
        else:
            self.vertices = sorted(vertices) if vertices else []
            self.edges = edges if edges else []
        
        self.n = len(self.vertices)
        self.vertex_to_idx = {v: i for i, v in enumerate(self.vertices)}
    
    def _read_graph_file(self, filepath: str) -> Tuple[List[int], List[Tuple[int, int]]]:
        """读取图文件"""
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        # 第一行：顶点数和边数
        n, m = map(int, lines[0].strip().split())
        vertices = list(range(n))
        
        # 后续行：边
        edges = []
        for i in range(1, m + 1):
            u, v = map(int, lines[i].strip().split())
            edges.append((u, v))
        
        return vertices, edges
    
    def build_zdd_simple(self) -> Tuple[ZDD, int, List[Set[int]]]:
        """构造ZDD（简化方法，适合小图）"""
        print(f"使用简化方法构造ZDD (n={self.n})...")
        
        constructor = SimpleConnectedSubgraphZDD(self.n, self.edges)
        zdd, root_id = constructor.build_zdd()
        
        return zdd, root_id, constructor.connected_subgraphs
    
    def build_zdd_frontier(self) -> Tuple[ZDD, int, List[Set[int]]]:
        """
        构造ZDD（Frontier-based方法，适合大图）
        
        Returns:
            (zdd, root_id, connected_subgraphs)
        """
        print(f"使用Frontier-based方法构造ZDD (n={self.n}, m={len(self.edges)})...")
        
        constructor = FrontierBasedZDDConstructor(self.n, self.edges)
        zdd = constructor.zdd
        root_id = constructor.build_connected_subgraphs_zdd()
        
        # 从ZDD枚举所有连通子图
        print("从ZDD枚举连通子图...")
        connected_subgraphs = zdd.enumerate_paths(root_id)
        print(f"枚举完成，共 {len(connected_subgraphs)} 个连通子图")
        
        return zdd, root_id, connected_subgraphs
    
    def build_zdd_auto(self, threshold: int = 15) -> Tuple[ZDD, int, List[Set[int]]]:
        """
        自动选择ZDD构造方法
        
        Args:
            threshold: 顶点数阈值，小于等于此值使用简单方法，否则使用frontier方法
        
        Returns:
            (zdd, root_id, connected_subgraphs)
        """
        if self.n <= threshold:
            print(f"图较小 (n={self.n} ≤ {threshold})，使用简单方法")
            return self.build_zdd_simple()
        else:
            print(f"图较大 (n={self.n} > {threshold})，使用Frontier-based方法")
            return self.build_zdd_frontier()
    
    def build_exact_cover_matrix(self, connected_subgraphs: List[Set[int]]) -> Tuple[np.ndarray, List[int], List[Set[int]]]:
        """构建Exact Cover矩阵"""
        num_options = len(connected_subgraphs)
        num_elements = self.n
        
        matrix = np.zeros((num_options, num_elements), dtype=int)
        
        for i, subgraph in enumerate(connected_subgraphs):
            for vertex in subgraph:
                j = self.vertex_to_idx[vertex]
                matrix[i][j] = 1
        
        return matrix, self.vertices, connected_subgraphs
    
    def export_zdd_to_file(self, zdd: ZDD, root_id: int, output_file: str):
        """导出ZDD到文件"""
        content = zdd.export_to_text(root_id)
        with open(output_file, 'w') as f:
            f.write(f"# Root node: {root_id}\n")
            f.write(f"# Format: <node_id> <level> <lo> <hi>\n")
            f.write(f"# Terminal nodes: 0 (FALSE), 1 (TRUE)\n")
            f.write(content)
        print(f"ZDD exported to {output_file}")

    def export_matrix_to_file(self, matrix: np.ndarray, output_file: str):
        """导出矩阵到文件"""
        with open(output_file, 'w') as f:
            f.write(f"{matrix.shape[1]} {matrix.shape[0]}\n")

            for _, row in enumerate(matrix):

                # 找出当前行中所有为 1 的列索引（1-based）
                ones_indices = [str(j + 1) for j, value in enumerate(row) if value == 1]

                # 行首写入 1 的数量，然后写出这些索引
                f.write(f"{len(ones_indices)} ")
                f.write(" ".join(ones_indices))
                f.write("\n")
                
        print(f"Matrix exported to {output_file}")
    
    def print_summary(self, zdd: ZDD, root_id: int, connected_subgraphs: List[Set[int]], 
                     matrix: np.ndarray):
        """打印摘要信息"""
        print("\n" + "="*70)
        print("图到ZDD到Exact Cover转换完成")
        print("="*70)
        print(f"图信息:")
        print(f"  顶点数: {self.n}")
        print(f"  边数: {len(self.edges)}")
        print(f"\nZDD信息:")
        print(f"  根节点ID: {root_id}")
        print(f"  ZDD节点数: {zdd.get_node_count(root_id)} (不含终端节点)")
        print(f"  连通子图数量: {len(connected_subgraphs)}")
        print(f"\nExact Cover矩阵:")
        print(f"  维度: {matrix.shape[0]} × {matrix.shape[1]}")
        print(f"  行（选项/连通子图）: {matrix.shape[0]}")
        print(f"  列（元素/节点）: {matrix.shape[1]}")


# ===================== 使用示例 =====================

def example_complete_pipeline():
    """完整流程示例"""
    print("="*70)
    print("示例：线性图 0-1-2-3-4")
    print("="*70)
    
    # 方式1: 直接提供顶点和边
    vertices = [0, 1, 2, 3, 4]
    edges = [(0, 1), (1, 2), (2, 3), (3, 4)]
    
    converter = GraphToExactCover(vertices=vertices, edges=edges)
    
    # 步骤1: 构造ZDD
    zdd, root_id, connected_subgraphs = converter.build_zdd_auto()
    
    # 步骤2: 构造Exact Cover矩阵
    matrix, _, row_labels = converter.build_exact_cover_matrix(connected_subgraphs)
    
    # 步骤3: 打印信息
    converter.print_summary(zdd, root_id, connected_subgraphs, matrix)
    
    # 步骤4: 显示部分连通子图
    print(f"\n前10个连通子图:")
    for i, subgraph in enumerate(connected_subgraphs[:10]):
        print(f"  {i}: {sorted(subgraph)}")
    
    # 步骤5: 显示矩阵前几行
    print(f"\nExact Cover矩阵前10行:")
    print(f"{'索引':<6} {'连通子图':<20} {'二元向量'}")
    print("-" * 50)
    for i in range(min(10, len(row_labels))):
        subgraph_str = str(sorted(row_labels[i]))
        row_str = ''.join(map(str, matrix[i]))
        print(f"{i:<6} {subgraph_str:<20} {row_str}")
    
    # 步骤6: 导出ZDD
    converter.export_zdd_to_file(zdd, root_id, "output_zdd.txt")
    
    print(f"\n可以验证ZDD的路径数 = 连通子图数: {len(connected_subgraphs)}")
    paths = zdd.enumerate_paths(root_id)
    print(f"ZDD枚举路径数: {len(paths)}")


def example_large_graph():
    """大图示例 - 使用Frontier-based方法"""
    print("\n" + "="*70)
    print("较大的网格图 (使用Frontier-based方法)")
    print("="*70)
    
    # 创建一个 4x4 网格图
    n = 16  # 4x4 = 16 个顶点
    edges = []
    
    # 添加水平边
    for i in range(4):
        for j in range(3):
            u = i * 4 + j
            v = i * 4 + j + 1
            edges.append((u, v))
    
    # 添加垂直边
    for i in range(3):
        for j in range(4):
            u = i * 4 + j
            v = (i + 1) * 4 + j
            edges.append((u, v))
    
    vertices = list(range(n))
    
    print(f"网格图: {n} 个顶点, {len(edges)} 条边")
    
    converter = GraphToExactCover(vertices=vertices, edges=edges)
    
    # 使用Frontier-based方法
    zdd, root_id, connected_subgraphs = converter.build_zdd_frontier()
    
    # 构造Exact Cover矩阵
    matrix, _, _ = converter.build_exact_cover_matrix(connected_subgraphs)
    
    # 打印摘要
    converter.print_summary(zdd, root_id, connected_subgraphs, matrix)
    
    # 导出ZDD
    converter.export_zdd_to_file(zdd, root_id, "output_zdd_large.txt")

    # 导出矩阵
    converter.export_matrix_to_file(matrix, "output_matrix_large.txt")  
    
    print(f"\n连通子图统计:")
    print(f"  单顶点子图: {sum(1 for s in connected_subgraphs if len(s) == 1)}")
    print(f"  两顶点子图: {sum(1 for s in connected_subgraphs if len(s) == 2)}")
    print(f"  三顶点子图: {sum(1 for s in connected_subgraphs if len(s) == 3)}")
    print(f"  大于三顶点: {sum(1 for s in connected_subgraphs if len(s) > 3)}")


def example_from_file():
    """从文件读取图的示例"""
    # 创建测试文件
    test_graph = """8 10
                    0 1
                    1 2
                    2 3
                    3 0
                    4 5
                    5 6
                    6 7
                    7 4
                    0 4
                    2 6"""
    
    with open("test_graph.txt", "w") as f:
        f.write(test_graph)
    
    print("\n" + "="*70)
    print("从文件读取图（两个正方形连接）")
    print("="*70)
    
    converter = GraphToExactCover(graph_file="test_graph.txt")
    
    # 自动选择方法
    zdd, root_id, connected_subgraphs = converter.build_zdd_auto()
    matrix, _, _ = converter.build_exact_cover_matrix(connected_subgraphs)
    converter.print_summary(zdd, root_id, connected_subgraphs, matrix)


if __name__ == "__main__":
    # example_complete_pipeline()
    # example_from_file()
    example_large_graph()