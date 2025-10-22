def matrix_to_zdd(input_file_path, output_file_path):

    # 读取矩阵(按不同格式读取)
    with open(input_file_path, "r") as f:
        max_level, num_rows = map(int, f.readline().strip().split())
        
        paths = []
        for line in f:
            parts = list(map(int, line.strip().split()))
            if parts[0] > 0:
                paths.append(set(parts[1:parts[0]+1]))
            else:
                paths.append(set())
    
    # 构建ZDD（从高level到低level）
    node_counter = 0
    all_nodes = []
    
    # 使用动态规划构建
    def build_level(level, remaining_sets):
        nonlocal node_counter
        
        if level > max_level:
            return "T" if set() in remaining_sets else "B"
        
        # 分组：包含当前level的集合 vs 不包含的集合
        lo_sets = []
        hi_sets = []
        
        for s in remaining_sets:
            if level in s:
                hi_sets.append(s - {level})
            else:
                lo_sets.append(s)
        
        # 递归构建子节点
        lo_child = build_level(level + 1, lo_sets) if lo_sets else "B"
        hi_child = build_level(level + 1, hi_sets) if hi_sets else "B"
        
        # 创建节点
        node_counter += 1
        node_id = str(node_counter)
        all_nodes.append((node_id, level, lo_child, hi_child))
        return node_id
    
    # 开始构建
    root = build_level(1, paths)
    
    # 写入文件
    with open(output_file_path, "w") as f:
        for node_id, level, lo, hi in all_nodes:
            f.write(f"{node_id} {level} {lo} {hi}\n")

# 使用示例
matrix_to_zdd("Missouri.txt", "Missouri_test.zdd")