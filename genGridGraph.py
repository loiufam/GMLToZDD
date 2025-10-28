import os

def generate_grid_graph(rows, cols, output_file):
    """生成一个 rows x cols 的网格图数据文件。"""
    edges = []

    def node_id(r, c):
        return r * cols + c

    for r in range(rows):
        for c in range(cols):
            current = node_id(r, c)
            # 右邻居
            if c + 1 < cols:
                right = node_id(r, c + 1)
                edges.append((current, right))
            # 下邻居
            if r + 1 < rows:
                down = node_id(r + 1, c)
                edges.append((current, down))

    vertex_count = rows * cols
    edge_count = len(edges)

    # 输出文件
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(f"{vertex_count} {edge_count}\n")
        for u, v in edges:
            f.write(f"{u} {v}\n")

    print(f"✅ 已生成 {rows}x{cols} 网格图: {output_file}")


if __name__ == "__main__":
    output_dir = "./graph_dataset/grid"
    os.makedirs(output_dir, exist_ok=True)

    sizes = [(3, 3), (3, 4), (4, 3), (4, 4)]
    for r, c in sizes:
        filename = os.path.join(output_dir, f"grid_{r}x{c}.in")
        generate_grid_graph(r, c, filename)
