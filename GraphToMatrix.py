import random
import networkx as nx
from collections import defaultdict, deque
from typing import List, Set, Tuple, Dict
import itertools
import os
import sys

class GraphToExactCover:
    """将图结构转换为精确覆盖问题（矩阵形式）"""
    
    def __init__(self):
        self.graph = None
        self.items = []  # 列（items）
        self.options = []  # 行（options）
        self.conversion_type = None
    
    def load_graph(self, filename: str) -> nx.Graph:
        """
        从文件加载图
        文件格式：
        第一行：<顶点数> <边数>
        其余行：<源点> <目标点>
        """
        with open(filename, 'r') as f:
            lines = f.readlines()
            
        first_line = lines[0].strip().split()
        num_vertices = int(first_line[0])
        num_edges = int(first_line[1])
        
        # 使用普通的无向图
        G = nx.Graph()
        G.add_nodes_from(range(num_vertices))
        
        for line in lines[1:]:
            if line.strip():
                parts = line.strip().split()
                u, v = int(parts[0]), int(parts[1])
                G.add_edge(u, v)
        
        self.graph = G
        return G
    
    def detect_graph_type(self) -> str:
        """
        检测图的类型，判断应该使用哪种转换策略
        """
        # 检查是否是多个连通分量（Partition类型）
        num_components = nx.number_connected_components(self.graph)
        if num_components > 1:
            return "partition"
        
        # 检查是否是欧拉图或近似欧拉图（Cycle类型）
        odd_degree_count = 0
        degree_dict = dict(self.graph.degree())  # 转换为字典
        for v in self.graph.nodes():
            if degree_dict[v] % 2 == 1:
                odd_degree_count += 1
        
        if odd_degree_count <= 2:  # 欧拉图或半欧拉图
            return "cycle"
        
        # 默认判断：如果边数较多且连通，可能是cycle类型
        if self.graph.number_of_edges() >= self.graph.number_of_nodes():
            return "cycle"
        
        return "partition"
    
    def partition_to_exact_cover(self, min_options: int = 500) -> Tuple[List[int], List[List[int]]]:
        """
        Partition类型：基于连通分量转换，生成多样化的option长度
        """
        print("使用 Partition 转换策略")
        
        # 找到所有连通分量
        components = list(nx.connected_components(self.graph))
        
        # 如果只有1个连通分量，需要人工创建分块
        if len(components) == 1:
            print("检测到单一连通分量，将人工创建独立分块")
            components = self._split_component_into_blocks(components[0])
        
        print(f"发现/创建 {len(components)} 个独立分块")
        
        self.items = []
        self.options = []
        item_to_col = {}
        col_id = 1
        
        # 记录已添加的options，避免重复
        seen_options = set()
        
        for comp_idx, comp_verts in enumerate(components):
            comp_verts = sorted(list(comp_verts))
            comp_size = len(comp_verts)
            
            # 将该分量的顶点作为items
            for v in comp_verts:
                item_to_col[v] = col_id
                self.items.append(v)
                col_id += 1
            
            # 策略1：每条边作为一个option（长度=2）
            for u, v in self.graph.edges():
                if u in comp_verts and v in comp_verts:
                    option = tuple(sorted([item_to_col[u], item_to_col[v]]))
                    if option not in seen_options:
                        seen_options.add(option)
                        self.options.append(list(option))
            
            # 策略2：为每个顶点创建单独的option（长度=1）
            for v in comp_verts:
                option = tuple([item_to_col[v]])
                if option not in seen_options:
                    seen_options.add(option)
                    self.options.append(list(option))
            
            # 策略3：生成不同长度的顶点组合
            # 长度2的组合
            if comp_size >= 2:
                for combo in itertools.combinations(comp_verts, 2):
                    option = tuple(sorted([item_to_col[v] for v in combo]))
                    if option not in seen_options:
                        seen_options.add(option)
                        self.options.append(list(option))
            
            # 长度3的组合（部分采样）
            if comp_size >= 3:
                combos_3 = list(itertools.combinations(comp_verts, 3))
                sample_size = min(len(combos_3), max(10, comp_size * 2))
                for combo in random.sample(combos_3, sample_size):
                    option = tuple(sorted([item_to_col[v] for v in combo]))
                    if option not in seen_options:
                        seen_options.add(option)
                        self.options.append(list(option))
            
            # 长度4的组合（少量采样）
            if comp_size >= 4:
                combos_4 = list(itertools.combinations(comp_verts, 4))
                sample_size = min(len(combos_4), max(5, comp_size))
                for combo in random.sample(combos_4, sample_size):
                    option = tuple(sorted([item_to_col[v] for v in combo]))
                    if option not in seen_options:
                        seen_options.add(option)
                        self.options.append(list(option))
            
            # 策略4：生成随机长度的子集（长度从2到min(6, comp_size)）
            if comp_size >= 2:
                num_random = max(20, comp_size * 5)
                for _ in range(num_random):
                    # 多样化长度分布
                    length_weights = {
                        2: 0.25,  # 25%长度为2
                        3: 0.30,  # 30%长度为3
                        4: 0.20,  # 20%长度为4
                        5: 0.15,  # 15%长度为5
                        6: 0.10   # 10%长度为6或更多
                    }
                    max_len = min(6, comp_size)
                    subset_size = random.choices(
                        range(2, max_len + 1),
                        weights=[length_weights.get(i, 0.05) for i in range(2, max_len + 1)]
                    )[0]
                    
                    subset = random.sample(comp_verts, subset_size)
                    option = tuple(sorted([item_to_col[v] for v in subset]))
                    if option not in seen_options:
                        seen_options.add(option)
                        self.options.append(list(option))
            
            # 策略5：基于邻居关系生成连续的顶点子集
            if comp_size >= 3:
                for start_v in comp_verts[:min(5, comp_size)]:
                    # BFS生成以start_v为中心的邻域
                    for radius in range(1, min(4, comp_size)):
                        neighborhood = set([start_v])
                        frontier = set([start_v])
                        for _ in range(radius):
                            new_frontier = set()
                            for v in frontier:
                                neighbors = [n for n in self.graph.neighbors(v) if n in comp_verts]
                                new_frontier.update(neighbors)
                            neighborhood.update(new_frontier)
                            frontier = new_frontier
                        
                        if len(neighborhood) >= 2:
                            option = tuple(sorted([item_to_col[v] for v in neighborhood]))
                            if option not in seen_options and len(option) <= 8:
                                seen_options.add(option)
                                self.options.append(list(option))
        
        # 如果options不够，继续生成更多样化的options
        attempt = 0
        while len(self.options) < min_options and attempt < 2000:
            for comp_verts in components:
                comp_verts = list(comp_verts)
                if len(comp_verts) >= 2:
                    # 随机选择长度，偏向中等长度
                    max_len = min(7, len(comp_verts))
                    subset_size = random.choices(
                        range(2, max_len + 1),
                        weights=[3, 4, 3, 2, 1, 1][:max_len - 1]
                    )[0]
                    
                    subset = random.sample(comp_verts, subset_size)
                    option = tuple(sorted([item_to_col[v] for v in subset]))
                    if option not in seen_options:
                        seen_options.add(option)
                        self.options.append(list(option))
            attempt += 1
        
        print(f"生成了 {len(self.options)} 个 options")
        return self.items, self.options
    
    def _split_component_into_blocks(self, component: Set[int], min_blocks: int = 3) -> List[Set[int]]:
        """
        将一个连通分量分割成多个独立分块
        使用社区检测或简单的度数分割
        """
        comp_verts = list(component)
        comp_size = len(comp_verts)
        
        # 如果分量太小，直接分成小块
        if comp_size <= 10:
            blocks = []
            block_size = max(2, comp_size // min_blocks)
            for i in range(0, comp_size, block_size):
                blocks.append(set(comp_verts[i:i + block_size]))
            return blocks
        
        # 使用贪心社区检测方法
        try:
            # 创建子图
            subgraph = self.graph.subgraph(comp_verts)
            
            # 使用Louvain社区检测
            import networkx.algorithms.community as nx_comm
            communities = list(nx_comm.greedy_modularity_communities(subgraph))
            
            # 如果社区数量少于min_blocks，进一步分割
            if len(communities) < min_blocks:
                blocks = []
                for comm in communities:
                    comm_list = list(comm)
                    if len(comm_list) <= 5:
                        blocks.append(set(comm_list))
                    else:
                        # 进一步分割大社区
                        block_size = max(3, len(comm_list) // 2)
                        for i in range(0, len(comm_list), block_size):
                            blocks.append(set(comm_list[i:i + block_size]))
                return blocks
            else:
                return [set(comm) for comm in communities]
        except:
            # 如果社区检测失败，使用简单的基于度数的分割
            degree_dict = dict(self.graph.degree())
            sorted_verts = sorted(comp_verts, key=lambda v: degree_dict[v])
            
            blocks = []
            block_size = max(3, comp_size // min_blocks)
            for i in range(0, comp_size, block_size):
                blocks.append(set(sorted_verts[i:i + block_size]))
            return blocks

    def find_euler_paths(self, start_vertex: int, max_paths: int = 2000) -> List[List[int]]:
        """
        使用DFS找多条路径（简化版）
        """
        paths = []
        
        for attempt in range(max_paths):
            G_copy = self.graph.copy()
            stack = [start_vertex]
            path = []
            
            while stack:
                v = stack[-1]
                neighbors = list(G_copy.neighbors(v))
                if neighbors:
                    u = random.choice(neighbors)
                    stack.append(u)
                    G_copy.remove_edge(v, u)
                else:
                    path.append(stack.pop())
            
            path = path[::-1]
            
            # 验证路径有效性
            if len(path) >= 3:
                paths.append(path)
            
            if len(paths) >= max_paths // 3:
                break
        
        return paths
    
    def cycle_to_exact_cover(self, target_ratio: float = 0.4, 
                            min_options: int = 500) -> Tuple[List[int], List[List[int]]]:
        """
        Cycle类型：基于路径/回路转换，生成多样化长度的options
        """
        print("使用 Cycle 转换策略")
        
        num_vertices = self.graph.number_of_nodes()
        degree_dict = dict(self.graph.degree())
        
        # 选择起点（度数最大的点）
        start_vertex = max(self.graph.nodes(), key=lambda v: degree_dict[v])
        print(f"起点: {start_vertex}")
        
        # 选择目标点集合（40%的顶点）
        num_targets = max(2, int(num_vertices * target_ratio))
        remaining = [v for v in self.graph.nodes() if v != start_vertex]
        
        if len(remaining) < num_targets:
            num_targets = len(remaining)
        
        target_vertices = set(random.sample(remaining, num_targets))
        print(f"选择了 {len(target_vertices)} 个目标顶点")

        # 将目标点分成多个组，创建独立分块
        target_groups = self._create_target_groups(target_vertices, min_groups=3)
        print(f"目标点分为 {len(target_groups)} 组（独立分块）")
        
        # 目标点作为items，重编号
        self.items = sorted(list(target_vertices))
        vertex_to_col = {v: i + 1 for i, v in enumerate(self.items)}

        # 记录每个分块的列ID
        block_columns = []
        for group in target_groups:
            block_cols = [vertex_to_col[v] for v in group]
            block_columns.append(set(block_cols))
            print(f"  分块包含列: {sorted(block_cols)}")
        
        self.options = []
        seen_options = set()
        
        # 为每个分块独立生成options
        for group_idx, target_group in enumerate(target_groups):
            print(f"为分块{group_idx + 1}生成options...")
            group_options = self._generate_options_for_group(
                start_vertex, target_group, vertex_to_col, 50
            )
            print(f"  生成 {len(group_options)} 个options")
            
            for option in group_options:
                option_tuple = tuple(sorted(option))
                if option_tuple not in seen_options:
                    seen_options.add(option_tuple)
                    self.options.append(list(option))
        
        # 生成一些跨分块的options（少量，增加难度）
        cross_block_options = min(50, len(self.options) // 10)
        print(f"生成 {cross_block_options} 个跨分块options...")
        for _ in range(cross_block_options):
            # 从不同分块中选择目标点
            num_groups_to_mix = random.randint(2, min(3, len(target_groups)))
            selected_groups = random.sample(target_groups, num_groups_to_mix)
            
            mixed_targets = []
            for group in selected_groups:
                num_from_group = random.randint(1, min(2, len(group)))
                mixed_targets.extend(random.sample(list(group), num_from_group))
            
            if mixed_targets:
                option = tuple(sorted([vertex_to_col[v] for v in mixed_targets]))
                if option not in seen_options and len(option) <= 10:
                    seen_options.add(option)
                    self.options.append(list(option))
        
        # 确保每个item至少被覆盖一次
        # covered = set()
        # for option in self.options:
        #     covered.update(option)
        
        # uncovered = set(range(len(self.items))) - covered
        # for col_id in uncovered:
        #     self.options.append([col_id + 1]) # 单独覆盖该item
        
        print(f"生成了 {len(self.options)} 个 options")
        return self.items, self.options
    
    def _create_target_groups(self, target_vertices: Set[int], min_groups: int = 3) -> List[Set[int]]:
        """
        将目标点分成多个组，每组形成一个独立分块
        """
        targets_list = list(target_vertices)
        num_targets = len(targets_list)
        
        # 确定分组数量
        num_groups = max(min_groups, num_targets // 5)  # 每组至少5个目标点
        num_groups = min(num_groups, num_targets // 2)  # 每组至少2个目标点
        
        # 随机打乱并分组
        random.shuffle(targets_list)
        
        groups = []
        group_size = num_targets // num_groups
        
        for i in range(num_groups):
            if i == num_groups - 1:
                # 最后一组包含剩余所有
                group = set(targets_list[i * group_size:])
            else:
                group = set(targets_list[i * group_size:(i + 1) * group_size])
            groups.append(group)
        
        return groups
    
    def _generate_options_for_group(self, start_vertex: int, target_group: Set[int], 
                                     vertex_to_col: Dict[int, int], min_options: int) -> List[List[int]]:
        """
        为特定目标组生成options
        """
        options = []
        seen = set()
        
        # 策略1：单个目标点
        for target in target_group:
            option = [vertex_to_col[target]]
            options.append(option)
            seen.add(tuple(option))
        
        # 策略3：三个组合（采样）
        if len(target_group) >= 3:
            combos = list(itertools.combinations(target_group, 3))
            sample_size = min(len(combos), max(20, len(target_group) * 2))
            for combo in random.sample(combos, sample_size):
                option = sorted([vertex_to_col[v] for v in combo])
                option_tuple = tuple(option)
                if option_tuple not in seen:
                    options.append(option)
                    seen.add(option_tuple)
        
        # 策略4：找路径并提取该组的目标点
        for target in list(target_group)[:min(10, len(target_group))]:
            try:
                paths = list(nx.all_simple_paths(self.graph, start_vertex, target, cutoff=8))[:20]
                for path in paths:
                    targets_in_path = [v for v in path if v in target_group]
                    if len(targets_in_path) >= 2:
                        option = sorted([vertex_to_col[v] for v in targets_in_path])
                        option_tuple = tuple(option)
                        if option_tuple not in seen and len(option) <= 8:
                            options.append(option)
                            seen.add(option_tuple)
            except:
                pass
        
        print(f"   最小options数量: {min_options}, 当前生成: {len(options)}")
        # 策略5：随机组合不同长度
        while len(options) < min_options:
            if len(target_group) >= 2:
                subset_size = random.randint(2, min(6, len(target_group)))
                subset = random.sample(list(target_group), subset_size)
                option = sorted([vertex_to_col[v] for v in subset])
                option_tuple = tuple(option)
                options.append(option)

            else:
                break
        
        return options

    def convert(self, graph_file: str, output_file: str, 
                conversion_type: str = "auto", min_options: int = 500):
        """
        转换单个图文件
        
        Args:
            graph_file: 输入图文件路径
            output_file: 输出矩阵文件路径
            conversion_type: 转换类型 ("auto", "partition", "cycle")
            min_options: 最小options数量
        """
        print(f"\n{'='*60}")
        print(f"转换文件: {graph_file}")
        print(f"{'='*60}")
        
        # 加载图
        self.load_graph(graph_file)
        print(f"加载图: {self.graph.number_of_nodes()} 个顶点, "
              f"{self.graph.number_of_edges()} 条边")
        
        # 确定转换类型
        if conversion_type == "auto":
            conversion_type = self.detect_graph_type()
            print(f"自动检测类型: {conversion_type}")
        else:
            print(f"使用指定类型: {conversion_type}")
        
        self.conversion_type = conversion_type
        
        # 执行转换
        if conversion_type == "partition":
            self.partition_to_exact_cover(min_options)
        elif conversion_type == "cycle":
            self.cycle_to_exact_cover(min_options=min_options)
        else:
            raise ValueError(f"未知的转换类型: {conversion_type}")
        
        # 保存矩阵
        self.save_matrix(output_file)
        print(f"矩阵已保存到: {output_file}")
        
        # 打印统计信息
        self.print_stats()
    
    def batch_convert(self, input_dir: str, output_dir: str, 
                     conversion_type: str = "auto", 
                     min_options: int = 500,
                     pattern: str = "*.in"):
        """
        批量转换目录中的所有图文件
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            conversion_type: 转换类型
            min_options: 最小options数量
            pattern: 文件匹配模式
        """
        import glob
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 查找所有图文件
        search_pattern = os.path.join(input_dir, pattern)
        graph_files = glob.glob(search_pattern)
        
        if not graph_files:
            print(f"在 {input_dir} 中没有找到匹配 {pattern} 的文件")
            return
        
        print(f"\n找到 {len(graph_files)} 个文件待转换")
        print(f"输出目录: {output_dir}")
        print(f"{'='*60}\n")
        
        # 转换每个文件
        success_count = 0
        for i, graph_file in enumerate(graph_files, 1):
            try:
                # 生成输出文件名
                base_name = os.path.basename(graph_file)
                name_without_ext = os.path.splitext(base_name)[0]
                output_file = os.path.join(output_dir, f"{name_without_ext}.txt")
                
                print(f"[{i}/{len(graph_files)}] 处理: {base_name}")
                
                # 转换
                self.convert(graph_file, output_file, conversion_type, min_options)
                success_count += 1
                
            except Exception as e:
                print(f"错误: 转换 {graph_file} 时失败: {str(e)}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{'='*60}")
        print(f"批量转换完成!")
        print(f"成功: {success_count}/{len(graph_files)}")
        print(f"{'='*60}")
    
    def save_matrix(self, filename: str):
        """保存矩阵到文件"""
        with open(filename, 'w') as f:
            num_cols = len(self.items)
            num_rows = len(self.options)
            f.write(f"{num_cols} {num_rows}\n")
            
            for option in self.options:
                f.write(f"{len(option)} " + " ".join(map(str, option)) + "\n")
    
    def print_stats(self):
        """打印统计信息"""
        print(f"\n--- 统计信息 ---")
        print(f"Items (列数): {len(self.items)}")
        print(f"Options (行数): {len(self.options)}")
        print(f"图的顶点数: {self.graph.number_of_nodes()}")
        print(f"图的边数: {self.graph.number_of_edges()}")
        
        # 分析覆盖情况
        coverage = defaultdict(int)
        for option in self.options:
            for item in option:
                coverage[item] += 1
        
        if coverage:
            avg_coverage = sum(coverage.values()) / len(self.items)
            print(f"平均每个item被覆盖次数: {avg_coverage:.2f}")
            print(f"最少覆盖次数: {min(coverage.values())}")
            print(f"最多覆盖次数: {max(coverage.values())}")
        
        # Options大小分布（更详细的统计）
        option_sizes = [len(opt) for opt in self.options]
        if option_sizes:
            print(f"Option大小范围: {min(option_sizes)} - {max(option_sizes)}")
            print(f"平均Option大小: {sum(option_sizes)/len(option_sizes):.2f}")
            
            # 统计各个长度的option数量
            size_distribution = defaultdict(int)
            for size in option_sizes:
                size_distribution[size] += 1
            
            print(f"Option长度分布:")
            for size in sorted(size_distribution.keys()):
                count = size_distribution[size]
                percentage = count / len(self.options) * 100
                print(f"  长度{size}: {count}个 ({percentage:.1f}%)")
        
        # 分析分块情况（针对partition类型）
        if self.conversion_type == "partition":
            components = list(nx.connected_components(self.graph))
            print(f"\n分块信息:")
            print(f"  连通分量数: {len(components)}")
            comp_sizes = [len(c) for c in components]
            print(f"  分量大小范围: {min(comp_sizes)} - {max(comp_sizes)}")
            print(f"  平均分量大小: {sum(comp_sizes)/len(comp_sizes):.2f}")


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='将图结构转换为精确覆盖问题矩阵',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 单文件转换（自动检测类型）
  python script.py -i graph.txt -o matrix.txt
  
  # 单文件转换（指定类型）
  python script.py -i graph.txt -o matrix.txt -t partition
  
  # 批量转换
  python script.py -b -i ./graphs -o ./matrices
  
  # 批量转换，指定最小options数
  python script.py -b -i ./graphs -o ./matrices --min-options 800
        """)
    
    parser.add_argument('-i', '--input', required=True,
                       help='输入文件路径（单文件）或输入目录（批量）')
    parser.add_argument('-o', '--output', required=True,
                       help='输出文件路径（单文件）或输出目录（批量）')
    parser.add_argument('-t', '--type', default='auto',
                       choices=['auto', 'partition', 'cycle'],
                       help='转换类型 (default: auto)')
    parser.add_argument('-b', '--batch', action='store_true',
                       help='批量转换模式')
    parser.add_argument('--min-options', type=int, default=500,
                       help='最小options数量 (default: 500)')
    parser.add_argument('--pattern', default='*.in',
                       help='批量模式下的文件匹配模式 (default: *.in)')
    
    args = parser.parse_args()
    
    converter = GraphToExactCover()
    
    if args.batch:
        # 批量转换
        converter.batch_convert(
            args.input, 
            args.output, 
            args.type, 
            args.min_options,
            args.pattern
        )
    else:
        # 单文件转换
        converter.convert(
            args.input, 
            args.output, 
            args.type, 
            args.min_options
        )


if __name__ == "__main__":
    # 如果有命令行参数，使用命令行模式
    if len(sys.argv) > 1:
        main()
    else:
        # 否则显示使用说明
        print("图结构转精确覆盖问题转换器")
        print("="*60)
        print("\n使用方法:")
        print("\n1. 单文件转换:")
        print("   python script.py -i graph.txt -o matrix.txt")
        print("\n2. 批量转换:")
        print("   python script.py -b -i ./graphs -o ./matrices")
        print("\n3. 查看更多选项:")
        print("   python script.py --help")
        print("\n" + "="*60)
        
        # 如果当前目录有示例文件，也可以直接运行示例
        print("\n提示: 直接运行 python script.py --help 查看完整使用说明")