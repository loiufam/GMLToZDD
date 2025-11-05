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
        self.blocks_solutions = []  # 记录每个块的解
    
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
        
    def generate_blocks(self, 
                       num_blocks: int = 20,
                       min_rows_per_block: int = 100,
                       max_rows_per_block: int = 300,
                       min_cols_per_block: int = 15,
                       max_cols_per_block: int = 50,
                       solution_diversity: str = 'medium' ) -> Tuple[List[int], List[List[int]]]:
        """
        生成指定数量的独立矩阵块
        
        参数:
            num_blocks: 目标块数量 (默认20)
            min_rows_per_block: 每块最小行数 (默认100)
            max_rows_per_block: 每块最大行数 (默认300)
            min_cols_per_block: 每块最小列数 (默认15)
            max_cols_per_block: 每块最大列数 (默认50)
        """
        print(f"生成 {num_blocks} 个独立矩阵块")
        
        self.items = []
        self.options = []
        self.blocks_solutions = []
        blocks_info = []
        
        col_id = 1
        
        for block_idx in range(num_blocks):
            # 随机化每个块的尺寸
            num_cols = random.randint(min_cols_per_block, max_cols_per_block)
            num_rows = random.randint(min_rows_per_block, max_rows_per_block)
            
            # 记录这个块的列范围
            block_cols = list(range(col_id, col_id + num_cols))

            # 生成该块的矩阵和解
            block_rows, block_solutions = self._generate_block_with_solution(
                block_cols, num_rows, solution_diversity
            )

            blocks_info.append({
                'id': block_idx,
                'cols': block_cols,
                'rows': block_rows,
                'solutions': block_solutions
            })
            
            # 添加items（列）
            self.items.extend(block_cols)
            self.blocks_solutions.append(block_solutions)

            # 更新列id
            col_id += num_cols
        
        # 打乱行顺序，使矩阵看起来不是块状的
        all_rows = []
        for block in blocks_info:
            all_rows.extend(block['rows'])
        
        random.shuffle(all_rows)
        self.options = all_rows
        
        print(f"生成完成：{len(self.items)} 列，{len(self.options)} 行")
        
        return self.items, self.options
       
    def _generate_block_with_solution(self, cols: List[int], num_rows: int, 
                                      diversity: str) -> Tuple[List[List[int]], List[List[List[int]]]]:
        """
        为一个块生成包含精确覆盖解的行集合
        
        策略：
        1. 先构造1个或多个精确覆盖解
        2. 基于解添加兼容的额外行
        3. 添加一些"干扰行"增加难度
        """
        num_cols = len(cols)
        
        # 确定要生成的解的数量
        if diversity == 'low':
            num_solutions = random.randint(1, 2)
        elif diversity == 'medium':
            num_solutions = random.randint(2, 5)
        else:  # high
            num_solutions = random.randint(5, 15)
        
        solutions = []
        solution_rows = set()  # 所有解中使用的行
        
        # 生成多个不同的解
        for sol_idx in range(num_solutions):
            solution = self._generate_one_solution(cols)
            solutions.append(solution)
            for row in solution:
                solution_rows.add(tuple(row))
        
        # 所有解的行作为基础
        rows = [list(row) for row in solution_rows]
        
        # 计算还需要多少额外行
        remaining_rows = num_rows - len(rows)
        
        # 策略1：生成与解兼容的部分覆盖行（40%）
        num_compatible = int(remaining_rows * 0.4)
        compatible_rows = self._generate_compatible_rows(cols, solutions, num_compatible)
        rows.extend(compatible_rows)
        
        # 策略2：生成冲突行（与解中某些行有列重叠，但不是完全相同）（30%）
        num_conflict = int(remaining_rows * 0.3)
        conflict_rows = self._generate_conflict_rows(cols, solution_rows, num_conflict)
        rows.extend(conflict_rows)
        
        # 策略3：生成完全随机的行（30%）
        num_random = remaining_rows - num_compatible - num_conflict
        random_rows = self._generate_random_rows(cols, num_random)
        rows.extend(random_rows)
        
        return rows, solutions

    def _generate_one_solution(self, cols: List[int]) -> List[List[int]]:
        """
        生成一个精确覆盖解
        使用贪心策略：随机划分列到不相交的子集
        """
        num_cols = len(cols)
        remaining_cols = set(cols)
        solution = []
        
        while remaining_cols:
            # 随机选择行的大小（偏向中等大小）
            max_size = len(remaining_cols)
            if max_size == 1:
                size = 1
            elif max_size == 2:
                size = random.choices([1, 2], weights=[0.3, 0.7])[0]
            else:
                # 使用正态分布，偏向 num_cols / 5 左右的大小
                mean_size = max(2, min(num_cols // 5, max_size // 2))
                size = max(1, min(max_size, int(random.gauss(mean_size, mean_size / 2))))
            
            # 从剩余列中随机选择
            selected = random.sample(list(remaining_cols), size)
            solution.append(sorted(selected))
            remaining_cols -= set(selected)
        
        return solution
    
    def _generate_compatible_rows(self, cols: List[int], solutions: List[List[List[int]]], 
                                  num_rows: int) -> List[List[int]]:
        """
        生成与解兼容的行（即这些行可以和解共存，不会破坏精确覆盖性质）
        策略：选择解中某些行的子集
        """
        rows = []
        all_solution_rows = []
        for sol in solutions:
            all_solution_rows.extend(sol)
        
        for _ in range(num_rows):
            if not all_solution_rows:
                break
            
            # 随机选择一个解中的行
            base_row = random.choice(all_solution_rows)
            
            # 生成该行的子集
            if len(base_row) <= 1:
                continue
            
            subset_size = random.randint(1, len(base_row) - 1)
            subset = sorted(random.sample(base_row, subset_size))
            rows.append(subset)
        
        return rows
    
    def _generate_conflict_rows(self, cols: List[int], solution_rows: Set[Tuple], 
                               num_rows: int) -> List[List[int]]:
        """
        生成与解有部分重叠的冲突行
        这些行不能出现在任何解中，因为它们会与解的某些行冲突
        """
        rows = []
        solution_rows_list = [list(row) for row in solution_rows]
        
        for _ in range(num_rows):
            if not solution_rows_list:
                break
            
            # 选择一个解中的行作为基础
            base_row = random.choice(solution_rows_list)
            
            # 保留该行的一部分，并添加新的列
            if len(base_row) > 0:
                # 保留 30%-70% 的列
                keep_ratio = random.uniform(0.3, 0.7)
                keep_size = max(1, int(len(base_row) * keep_ratio))
                kept_cols = set(random.sample(base_row, keep_size))
                
                # 添加不在base_row中的新列
                available_cols = [c for c in cols if c not in base_row]
                if available_cols:
                    add_size = random.randint(1, min(5, len(available_cols)))
                    new_cols = set(random.sample(available_cols, add_size))
                    
                    conflict_row = sorted(list(kept_cols | new_cols))
                    if tuple(conflict_row) not in solution_rows:
                        rows.append(conflict_row)
        
        return rows
    
    def _generate_random_rows(self, cols: List[int], num_rows: int) -> List[List[int]]:
        """生成完全随机的行"""
        rows = []
        num_cols = len(cols)
        
        for _ in range(num_rows):
            # 多样化的行长度分布
            size = random.choices(
                range(1, min(11, num_cols + 1)),
                weights=[3, 5, 4, 3, 2, 2, 1, 1, 1, 1][:min(10, num_cols)]
            )[0]
            size = min(size, num_cols)
            
            row = sorted(random.sample(cols, size))
            rows.append(row)
        
        return rows

    def generate_from_graph(self,
                           target_blocks: int = 20,
                           min_rows_per_block: int = 100,
                           min_cols_per_block: int = 15,
                           solution_diversity: str = 'medium') -> Tuple[List[int], List[List[int]]]:
        """
        基于图结构生成块，每个块包含精确覆盖解
        """
        if self.graph is None:
            raise ValueError("需要提供图对象")
        
        print(f"基于图生成 {target_blocks} 个带解的块")
        
        all_nodes = list(self.graph.nodes())
        random.shuffle(all_nodes)
        
        total_nodes = len(all_nodes)
        base_nodes_per_block = max(min_cols_per_block, total_nodes // target_blocks)
        
        blocks_info = []
        col_id = 1
        node_idx = 0
        
        for block_idx in range(target_blocks):
            if block_idx == target_blocks - 1:
                block_nodes = all_nodes[node_idx:]
            else:
                variation = random.randint(-5, 10)
                block_size = max(min_cols_per_block, 
                               min(base_nodes_per_block + variation, 
                                   total_nodes - node_idx - (target_blocks - block_idx - 1) * min_cols_per_block))
                block_nodes = all_nodes[node_idx:node_idx + block_size]
                node_idx += block_size
            
            if not block_nodes:
                continue
            
            node_to_col = {node: col_id + i for i, node in enumerate(block_nodes)}
            block_cols = list(node_to_col.values())
            
            # 生成带解的矩阵块
            num_rows = random.randint(min_rows_per_block, min_rows_per_block + 200)
            block_rows, block_solutions = self._generate_block_with_solution(
                block_cols, num_rows, solution_diversity
            )
            
            blocks_info.append({
                'id': block_idx,
                'cols': block_cols,
                'nodes': block_nodes,
                'rows': block_rows,
                'solutions': block_solutions
            })
            
            self.items.extend(block_cols)
            self.blocks_solutions.append(block_solutions)
            col_id += len(block_nodes)
        
        # 打乱所有行
        all_rows = []
        for block in blocks_info:
            all_rows.extend(block['rows'])
        
        random.shuffle(all_rows)
        self.options = all_rows
        
        print(f"生成完成：{len(self.items)} 列，{len(self.options)} 行")
        
        return self.items, self.options


    def cycle_to_exact_cover(self, target_ratio: float = 0.4, 
                            min_options: int = 500,
                            num_blocks: int = None) -> Tuple[List[int], List[List[int]]]:
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

        # 指定分块数量为4-6个
        if num_blocks is None:
            num_blocks = random.randint(4, 6)

        # 将目标点分成多个组，创建独立分块
        target_groups = self._create_target_groups(target_vertices, num_groups=num_blocks )
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

        # 计算每个分块应生成的options数量
        total_target = 10000
        per_block_options = total_target // (len(target_groups) + 2)  # 留一些给跨分块
            
        # 为每个分块独立生成options
        for group_idx, target_group in enumerate(target_groups):
            print(f"为分块{group_idx + 1}生成options...")
            group_options = self._generate_options_for_group(
                start_vertex, target_group, vertex_to_col, 
                min_options=per_block_options,
                min_length=5  # 新增：最小长度要求
            )
            print(f"  生成 {len(group_options)} 个options")
            
            for option in group_options:
                option_tuple = tuple(sorted(option))
                if option_tuple not in seen_options:
                    seen_options.add(option_tuple)
                    self.options.append(list(option))
        
        cross_block_target = total_target // 3  # 约1/3是跨分块的
        print(f"生成 {cross_block_target} 个跨分块options...")
        cross_count = self._generate_cross_block_options(
            start_vertex, target_groups, vertex_to_col, 
            seen_options, cross_block_target
        )
        print(f"  实际生成 {cross_count} 个跨分块options")

        print(f"最终options总数: {len(self.options)}")
        print(f"平均长度: {sum(len(opt) for opt in self.options) / len(self.options):.2f}")
        
        # 统计长度分布
        length_dist = {}
        for opt in self.options:
            length_dist[len(opt)] = length_dist.get(len(opt), 0) + 1
        print(f"长度分布: {dict(sorted(length_dist.items()))}")
     
        return self.items, self.options
    
    def _create_target_groups(self, target_vertices: Set[int], num_groups: int = 5) -> List[Set[int]]:
        """
        将目标点分成多个组，每组形成一个独立分块
        """
        targets_list = list(target_vertices)
        num_targets = len(targets_list)
        
        # 确定分组数量
        num_groups = min(num_groups, num_targets // 2)
        num_groups = max(2, num_groups)  # 至少2组
        
        # 随机打乱并分组
        random.shuffle(targets_list)
        
        groups = []
        group_size = num_targets // num_groups
        remainder = num_targets % num_groups
        
        start_idx = 0
        for i in range(num_groups):
            # 将余数平均分配到前几组
            size = group_size + (1 if i < remainder else 0)
            group = set(targets_list[start_idx:start_idx + size])
            groups.append(group)
            start_idx += size
        
        return groups
    
    def _generate_options_for_group(self, start_vertex: int, target_group: Set[int], 
                                 vertex_to_col: Dict[int, int], min_options: int,
                                 min_length: int = 5) -> List[List[int]]:
        """
        为特定目标组生成大量options，优先生成长度>=min_length的
        """
        options = []
        seen = set()
        target_list = list(target_group)
        group_size = len(target_group)
        
        print(f"   分块包含 {group_size} 个目标点")
        
        # ✅ 根据分组大小调整长度分布
        max_length = min(10, group_size)
        actual_min_length = min(min_length, group_size)
        
        # 动态生成长度目标
        length_targets = {}
        for length in range(actual_min_length, max_length + 1):
            if length <= group_size:
                # 长度越接近分组大小，生成越多
                weight = (length - actual_min_length + 1) / (max_length - actual_min_length + 1)
                length_targets[length] = int(min_options * weight * 0.15)
        
        for length, count in length_targets.items():
            for _ in range(count):
                subset = random.sample(target_list, length)
                option = sorted([vertex_to_col[v] for v in subset])
                option_tuple = tuple(option)
                if option_tuple not in seen:
                    options.append(option)
                    seen.add(option_tuple)
        
        print(f"   策略1(固定长度组合): {len(options)} 个")
        
        # 策略2：基于路径生成（扩大搜索范围）
        path_options = self._generate_path_based_options(
            start_vertex, target_list, vertex_to_col, seen, 
            max_targets=min(30, len(target_list)),  # 增加搜索目标数
            cutoff=10  # 增加路径长度限制
        )
        options.extend(path_options)
        print(f"   策略2(路径): +{len(path_options)} 个，累计 {len(options)}")
        
        # 策略3：组合策略 - 生成大量中等长度的组合
        if len(target_group) >= 5:
            combo_count = 0
            for length in range(5, min(11, len(target_group) + 1)):
                combos = list(itertools.combinations(target_group, length))
                # ✅ 根据组合数量智能采样
                if len(combos) > 1000:
                    sample_size = min(1000, min_options // 5)
                elif len(combos) > 100:
                    sample_size = len(combos)  # 全部使用
                else:
                    # 组合太少，多次使用（打乱顺序）
                    sampled = combos * (100 // len(combos) + 1)
                    sample_size = min(100, len(sampled))
                    
                for combo in sampled:
                    option = sorted([vertex_to_col[v] for v in combo])
                    option_tuple = tuple(option)
                    if option_tuple not in seen:
                        options.append(option)
                        seen.add(option_tuple)
                        combo_count += 1
            
            print(f"   策略3(组合): +{combo_count} 个，累计 {len(options)}")
        
        # 策略4：随机长度组合（填充到目标数量）
        attempt = 0
        max_attempts = min_options * 3
        while len(options) < min_options and attempt < max_attempts:
            attempt += 1
            if len(target_group) >= min_length:
                # 优先生成长度>=5的
                subset_size = random.choices(
                    range(min_length, min(11, len(target_group) + 1)),
                    weights=[3, 3, 2, 2, 1, 1][:min(11, len(target_group) + 1) - min_length]
                )[0]
                subset = random.sample(target_list, subset_size)
                option = sorted([vertex_to_col[v] for v in subset])
                option_tuple = tuple(option)
                if option_tuple not in seen:
                    options.append(option)
                    seen.add(option_tuple)
        
        print(f"   策略4(随机填充): 最终 {len(options)} 个")
        
        return options
    
    def _generate_path_based_options(self, start_vertex: int, target_list: List[int],
                                    vertex_to_col: Dict[int, int], seen: Set,
                                    max_targets: int = 30, cutoff: int = 10) -> List[List[int]]:
        """
        基于路径生成options
        """
        options = []
        target_set = set(target_list)
        
        for target in target_list[:max_targets]:
            try:
                # 增加路径数量
                paths = list(nx.all_simple_paths(
                    self.graph, start_vertex, target, cutoff=cutoff
                ))[:50]  # 增加到50条路径
                
                for path in paths:
                    # 从路径中提取目标点
                    targets_in_path = [v for v in path if v in target_set]
                    
                    if len(targets_in_path) >= 3:
                        # 生成不同子集
                        for subset_size in range(3, min(len(targets_in_path) + 1, 11)):
                            if subset_size <= len(targets_in_path):
                                # 每个长度采样几个
                                for _ in range(min(3, len(targets_in_path) - subset_size + 1)):
                                    subset = random.sample(targets_in_path, subset_size)
                                    option = sorted([vertex_to_col[v] for v in subset])
                                    option_tuple = tuple(option)
                                    if option_tuple not in seen:
                                        options.append(option)
                                        seen.add(option_tuple)
            except Exception as e:
                continue
        
        return options

    def _generate_cross_block_options(self, start_vertex: int, 
                                   target_groups: List[Set[int]],
                                   vertex_to_col: Dict[int, int],
                                   seen_options: Set,
                                   target_count: int) -> int:
        """
        生成大量跨分块的options
        """
        count = 0
        attempts = 0
        max_attempts = target_count * 10
        
        while count < target_count and attempts < max_attempts:
            attempts += 1
            
            # 随机选择2-4个分块
            num_groups = random.randint(2, min(4, len(target_groups)))
            selected_groups = random.sample(target_groups, num_groups)
            
            # 从每个分块中选择顶点
            mixed_targets = []
            for group in selected_groups:
                # 每个分块选择2-4个顶点
                num_from_group = random.randint(1, min(3, len(group)))
                mixed_targets.extend(random.sample(list(group), num_from_group))
            
            # 确保总长度合适
            if 3 <= len(mixed_targets) <= 15:
                option = tuple(sorted([vertex_to_col[v] for v in mixed_targets]))
                if option not in seen_options:
                    seen_options.add(option)
                    self.options.append(list(option))
                    count += 1
            elif len(mixed_targets) > 12:
                # 如果太长，随机选择一个子集
                subset = random.sample(mixed_targets, random.randint(5, 10))
                option = tuple(sorted([vertex_to_col[v] for v in subset]))
                if option not in seen_options:
                    seen_options.add(option)
                    self.options.append(list(option))
                    count += 1
        
        return count

    def convert(self, graph_file: str, output_file: str, mode: int = 1):
        """
        转换单个图文件
        
        Args:
            graph_file: 输入图文件路径
            output_file: 输出矩阵文件路径
        """
        print(f"\n{'='*60}")
        print(f"转换文件: {graph_file}")
        print(f"{'='*60}")
        
        # 加载图
        self.load_graph(graph_file)
        print(f"加载图: {self.graph.number_of_nodes()} 个顶点, "
              f"{self.graph.number_of_edges()} 条边")
        
        print(f"采用模式 {mode} 进行转换\n")
        if mode == 1:
            self.generate_blocks( num_blocks=25, min_rows_per_block=300, max_rows_per_block=500, min_cols_per_block=25, max_cols_per_block=50)
        else:
            self.generate_from_graph( target_blocks=20, min_rows_per_block=300, min_cols_per_block=25 )

        # 保存矩阵
        self.save_matrix(output_file)
        print(f"矩阵已保存到: {output_file}")
        
    
    def batch_convert(self, input_dir: str, output_dir: str, mode: int = 1, max_count: int = 500):
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
        
        pattern = "*.in"
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
                self.convert(graph_file, output_file, mode)
                success_count += 1
                if success_count > max_count:
                    break
                
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

  # 单文件转换（指定模式）
  python script.py -i graph.txt -o matrix.txt -m 1
  
  # 批量转换
  python script.py -b -i ./graphs -o ./matrices -m 1
  
        """)
    
    parser.add_argument('-i', '--input', required=True,
                       help='输入文件路径（单文件）或输入目录（批量）')
    parser.add_argument('-o', '--output', required=True,
                       help='输出文件路径（单文件）或输出目录（批量）')
    parser.add_argument('-m', '--mode', type=int, default=1, choices=[1, 2],
                       help='转换模式 (default: 1)')
    parser.add_argument('-b', '--batch', action='store_true',
                       help='批量转换模式')
    parser.add_argument('-maxConvert', type=int, default=500,
                       help='最大批量转换数量 (default: 500)')

    
    args = parser.parse_args()
    
    converter = GraphToExactCover()
    
    if args.batch:
        # 批量转换
        converter.batch_convert(
            args.input, 
            args.output, 
            args.mode,
            args.maxConvert
        )
    else:
        # 单文件转换
        converter.convert(
            args.input, 
            args.output, 
            args.mode
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