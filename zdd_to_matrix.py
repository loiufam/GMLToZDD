def zbdd_to_sparse_matrix_file(input_file_path, output_file_path):
    # Step 1: 解析节点
    nodes = {}
    referenced_nodes = set()
    with open(input_file_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4:
                node_id, level, lo, hi = parts
                nodes[node_id] = {
                    "level": int(level),
                    "lo": lo,
                    "hi": hi
                }
                if lo not in ("T", "B"):
                    referenced_nodes.add(lo)
                if hi not in ("T", "B"):
                    referenced_nodes.add(hi)

    # Step 2: 找根节点（未被引用的节点）
    all_nodes = set(nodes.keys())
    root_candidates = all_nodes - referenced_nodes
    if not root_candidates:
        raise ValueError("未找到根节点")
    root_node = sorted(root_candidates, key=lambda nid: -int(nid))[0]

    # Step 3: 最大变量编号（列数）
    max_level = max(node["level"] for node in nodes.values())

    # Step 4: 提取路径并构造稀疏矩阵
    sparse_matrix = []

    def dfs_sparse(node_id, ones):
        if node_id == "T":
            # 直接使用收集到的level值，不需要转换
            row = sorted(ones)
            sparse_matrix.append(row)
            return
        if node_id == "B":
            return
        if node_id in nodes:
            node = nodes[node_id]
            # 先处理lo分支（不选择当前变量）
            dfs_sparse(node["lo"], ones)
            # 再处理hi分支（选择当前变量）
            dfs_sparse(node["hi"], ones + [node["level"]])

    dfs_sparse(root_node, [])

    # Step 5: 写入输出文件
    with open(output_file_path, "w") as f:
        f.write(f"{max_level} {len(sparse_matrix)}\n")
        for row in sparse_matrix:
            f.write(f"{len(row)} " + " ".join(map(str, row)) + "\n")

# 转换
zbdd_to_sparse_matrix_file("att48.zdd", "att48_t.txt")