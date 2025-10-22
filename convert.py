import networkx as nx
import numpy as np
import os

def gml_to_adjacency_matrix(file_path):
    # 读取.gml文件并创建图形对象
    graph = nx.read_gml(file_path, label='id', destringizer=int)

    print("Number of nodes:", graph.number_of_nodes())
    print("Number of edges:", graph.number_of_edges())

    # 获取节点列表，将图对象中的所有节点转换为一个Python列表
    nodes = list(graph.nodes())

    # 创建空的邻接矩阵
    num_nodes = len(nodes)
    adjacency_matrix = np.zeros((num_nodes, num_nodes), dtype=int)

    # 遍历边并在邻接矩阵中标记连接关系
    for edge in graph.edges():
        source = nodes.index(edge[0])
        target = nodes.index(edge[1])
        adjacency_matrix[source][target] = 1
        adjacency_matrix[target][source] = 1

    return adjacency_matrix, nodes

def validate_edge_file(file_path, max_vertex):
    vertices_set = set()    # 创建一个集合用于存储出现的顶点编号

    with open(file_path, "r") as file:
        for line in file:
            vertex_pair = line.strip().split()  # 移除首尾空白，然后将行按空格分割
            if len(vertex_pair) == 2:
                vertex1, vertex2 = int(vertex_pair[0]), int(vertex_pair[1])
                vertices_set.add(vertex1)
                vertices_set.add(vertex2)

    num_vertices = len(vertices_set)    # 集合中的元素数量即为顶点数量

    # 检查顶点数量是否与最大顶点编号一致
    if num_vertices == max_vertex:
        print(f"边信息验证通过！顶点数量等于最大顶点编号 {max_vertex}。")
        return True
    else:
        print(f"边信息验证未通过！顶点数量为 {num_vertices}，不等于最大顶点编号 {max_vertex}。")
        return False

# 处理所有gml文件
input_dir = "input_graph"
output_dir = "output_graph"

# 如果输出文件夹不存在，则创建
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

for file_name in os.listdir(input_dir):
    if file_name.endswith(".gml"):  # 只处理以.gml结尾的文件
        input_file = os.path.join(input_dir, file_name)
        output_file = os.path.join(output_dir, file_name.replace(".gml", ".txt"))

        adj_matrix, nodes = gml_to_adjacency_matrix(input_file)

        # 获取最大顶点编号
        max_vertex = 0

        # 写入边的信息到txt文件
        with open(output_file, "w") as file:
            for i in range(adj_matrix.shape[0]):
                for j in range(i + 1, adj_matrix.shape[1]):
                    if adj_matrix[i][j] == 1:
                        max_vertex = max(max_vertex, max(nodes[i] + 1, nodes[j] + 1))
                        file.write(f"{nodes[i] + 1} {nodes[j] + 1}\n")

        print(f"文件 {file_name} 处理完成，生成 {output_file}")

        # 验证边信息
        if not validate_edge_file(output_file, max_vertex):
            # 边信息验证未通过，删除文件
            os.remove(output_file)
            print(f"文件 {output_file} 删除成功。")

print("批量处理完成。")