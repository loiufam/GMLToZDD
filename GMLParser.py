
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import sys
import os
import glob
from collections import defaultdict

def debug_graphml_structure(graphml_file):
    """
    调试GraphML文件结构，帮助诊断解析问题
    
    Args:
        graphml_file (str): GraphML文件路径
    """
    try:
        tree = ET.parse(graphml_file)
        root = tree.getroot()
        
        print(f"调试信息 - {graphml_file}")
        print("=" * 50)
        print(f"根元素: {root.tag}")
        print(f"命名空间: {root.attrib}")
        
        print("\n文档结构:")
        for i, elem in enumerate(root.iter()):
            if i < 20:  # 只显示前20个元素
                print(f"  {elem.tag} - 属性: {elem.attrib}")
            elif i == 20:
                print("  ... (更多元素)")
        
        # 查找graph元素
        graphs = []
        for elem in root.iter():
            if elem.tag.endswith('graph'):
                graphs.append(elem)
        
        print(f"\n找到 {len(graphs)} 个graph元素")
        
        for i, graph in enumerate(graphs):
            print(f"\nGraph {i+1}:")
            print(f"  标签: {graph.tag}")
            print(f"  属性: {graph.attrib}")
            
            # 统计子元素
            nodes = [elem for elem in graph.iter() if elem.tag.endswith('node')]
            edges = [elem for elem in graph.iter() if elem.tag.endswith('edge')]
            
            print(f"  节点数: {len(nodes)}")
            print(f"  边数: {len(edges)}")
            
            if nodes:
                print(f"  示例节点: {nodes[0].tag}, 属性: {nodes[0].attrib}")
            if edges:
                print(f"  示例边: {edges[0].tag}, 属性: {edges[0].attrib}")
    
    except Exception as e:
        print(f"调试失败: {e}")

def parse_graphml_to_in(graphml_file, output_file, debug=False):
    """
    将GraphML格式的图文件转换为.in格式
    
    Args:
        graphml_file (str): 输入的GraphML文件路径
        output_file (str): 输出的.in文件路径
        debug (bool): 是否启用调试模式
    """
    try:
        if debug:
            debug_graphml_structure(graphml_file)
        
        # 解析XML文件
        tree = ET.parse(graphml_file)
        root = tree.getroot()
        
        # 定义命名空间
        ns = {'gml': 'http://graphml.graphdrawing.org/xmlns'}
        
        # 查找graph元素，尝试多种方法
        graph = root.find('.//gml:graph', ns)
        if graph is None:
            # 如果没有命名空间，尝试不带命名空间查找
            graph = root.find('.//graph')
        if graph is None:
            # 尝试直接从根元素找
            for elem in root.iter():
                if elem.tag.endswith('graph'):
                    graph = elem
                    break
        
        if graph is None:
            raise ValueError("未找到graph元素")
        
        # 收集所有节点
        nodes = set()
        node_mapping = {}  # 原始ID到连续整数的映射
        
        # 解析节点 - 尝试多种方法
        node_elements = []
        
        # 方法1: 使用命名空间查找
        if ns:
            node_elements = graph.findall('.//gml:node', ns)
        
        # 方法2: 不使用命名空间查找
        if not node_elements:
            node_elements = graph.findall('.//node')
        
        # 方法3: 直接在graph下查找
        if not node_elements:
            node_elements = graph.findall('node')
        
        # 方法4: 遍历所有子元素
        if not node_elements:
            for elem in graph.iter():
                if elem.tag.endswith('node'):
                    node_elements.append(elem)
        
        print(f"找到 {len(node_elements)} 个节点元素")  # 调试信息
        
        for node in node_elements:
            node_id = node.get('id')
            if node_id is not None:
                # 尝试转换为整数，如果失败则使用字符串
                try:
                    node_id = int(node_id)
                except ValueError:
                    pass
                nodes.add(node_id)
        
        # 创建节点ID到连续整数的映射
        sorted_nodes = sorted(nodes, key=lambda x: (isinstance(x, str), x))
        for i, node_id in enumerate(sorted_nodes):
            node_mapping[node_id] = i
        
        # 解析边 - 尝试多种方法
        edge_elements = []
        edges = []  # 初始化边的列表
        
        # 方法1: 使用命名空间查找
        if ns:
            edge_elements = graph.findall('.//gml:edge', ns)
        
        # 方法2: 不使用命名空间查找
        if not edge_elements:
            edge_elements = graph.findall('.//edge')
        
        # 方法3: 直接在graph下查找
        if not edge_elements:
            edge_elements = graph.findall('edge')
        
        # 方法4: 遍历所有子元素
        if not edge_elements:
            for elem in graph.iter():
                if elem.tag.endswith('edge'):
                    edge_elements.append(elem)
        
        print(f"找到 {len(edge_elements)} 个边元素")  # 调试信息
        
        for edge in edge_elements:
            source = edge.get('source')
            target = edge.get('target')
            
            if source is not None and target is not None:
                # 尝试转换为整数
                try:
                    source = int(source)
                except ValueError:
                    pass
                try:
                    target = int(target)
                except ValueError:
                    pass
                
                # 映射到连续整数
                if source in node_mapping and target in node_mapping:
                    u = node_mapping[source]
                    v = node_mapping[target]
                    edges.append((u, v))
        
        # 检查是否为无向图，去除重复边
        is_undirected = graph.get('edgedefault') == 'undirected'
        if is_undirected:
            # 对于无向图，确保边的表示是一致的（较小的节点ID在前）
            unique_edges = set()
            for u, v in edges:
                edge = (min(u, v), max(u, v))
                unique_edges.add(edge)
            edges = list(unique_edges)
        else:
            # 对于有向图，去除完全重复的边
            edges = list(set(edges))
        
        # 排序边（可选，但让输出更整齐）
        edges.sort()
        
        # 输出到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"{len(nodes)} {len(edges)}\n")
            for u, v in edges:
                f.write(f"{u} {v}\n")
        
        print(f"转换完成！")
        print(f"节点数: {len(nodes)}")
        print(f"边数: {len(edges)}")
        print(f"图类型: {'无向图' if is_undirected else '有向图'}")
        
        # 显示节点映射信息（如果原始ID不是连续的整数）
        if not all(isinstance(node_id, int) and node_id == node_mapping[node_id] for node_id in nodes):
            print("节点ID映射:")
            for original_id in sorted_nodes:
                print(f"  {original_id} -> {node_mapping[original_id]}")
    
    except ET.ParseError as e:
        print(f"XML解析错误: {e}")
    except FileNotFoundError:
        print(f"文件未找到: {graphml_file}")
    except Exception as e:
        print(f"转换过程中出现错误: {e}")

def batch_convert_folder(input_folder, output_folder, debug=False):
    """
    批量转换文件夹中的所有GraphML文件
    
    Args:
        input_folder (str): 输入文件夹路径
        output_folder (str): 输出文件夹路径
    """
    # 确保输出文件夹存在
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"创建输出文件夹: {output_folder}")
    
    # 查找所有GraphML文件
    graphml_pattern = os.path.join(input_folder, "*.graphml")
    graphml_files = glob.glob(graphml_pattern)
    
    if not graphml_files:
        print(f"在文件夹 {input_folder} 中未找到任何.graphml文件")
        return
    
    print(f"找到 {len(graphml_files)} 个GraphML文件")
    print("-" * 50)
    
    successful_conversions = 0
    failed_conversions = 0
    
    i = 0
    for i, graphml_file in enumerate(graphml_files, 1):
        # 获取文件名（不含扩展名）
        base_name = os.path.splitext(os.path.basename(graphml_file))[0]
        output_file = os.path.join(output_folder, base_name + ".in")
        
        print(f"[{i}/{len(graphml_files)}] 转换: {os.path.basename(graphml_file)}")
        
        try:
            parse_graphml_to_in(graphml_file, output_file, debug)
            successful_conversions += 1
            print(f"✓ 成功: {base_name}.in")
        except Exception as e:
            failed_conversions += 1
            print(f"✗ 失败: {os.path.basename(graphml_file)} - {str(e)}")
        
        print()  # 空行分隔

        if ++i == 500:
            break # 最多转换500个文件
    
    print("=" * 50)
    print("批量转换完成!")
    print(f"成功转换: {successful_conversions} 个文件")
    print(f"转换失败: {failed_conversions} 个文件")
    print(f"输出文件夹: {output_folder}")

# graphml to in format
def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  单文件转换:")
        print(f"    {sys.argv[0]} <graphml_file> [output_file]")
        print(f"    例如: {sys.argv[0]} network.graphml network.in")
        print()
        print("  批量文件夹转换:")
        print(f"    {sys.argv[0]} --batch <input_folder> <output_folder>")
        print(f"    例如: {sys.argv[0]} --batch ./data/graphml ./data/in")
        print()
        print("  调试模式:")
        print(f"    {sys.argv[0]} --debug <graphml_file>")
        print(f"    例如: {sys.argv[0]} --debug network.graphml")
        print()
        print("  如果单文件转换时不指定输出文件，将使用输入文件名但扩展名改为.in")
        sys.exit(1)
    
    # 检查是否为调试模式
    if sys.argv[1] == "--debug":
        if len(sys.argv) != 3:
            print("调试模式需要指定GraphML文件")
            print(f"使用方法: {sys.argv[0]} --debug <graphml_file>")
            sys.exit(1)
        
        graphml_file = sys.argv[2]
        debug_graphml_structure(graphml_file)
        return
    
    # 检查是否为批量处理模式
    elif sys.argv[1] == "--batch":
        if len(sys.argv) != 4:
            print("批量转换模式需要指定输入文件夹和输出文件夹")
            print(f"使用方法: {sys.argv[0]} --batch <input_folder> <output_folder>")
            sys.exit(1)
        
        input_folder = sys.argv[2]
        output_folder = sys.argv[3]
        
        if not os.path.exists(input_folder):
            print(f"输入文件夹不存在: {input_folder}")
            sys.exit(1)
        
        batch_convert_folder(input_folder, output_folder)
    else:
        # 单文件转换模式
        graphml_file = sys.argv[1]
        
        if len(sys.argv) == 3:
            output_file = sys.argv[2]
        else:
            # 自动生成输出文件名
            base_name = os.path.splitext(graphml_file)[0]
            output_file = base_name + ".in"
        
        parse_graphml_to_in(graphml_file, output_file)

if __name__ == "__main__":
    main()