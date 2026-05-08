# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import sys
import os
import glob
import re
from collections import defaultdict

def natural_sort_key(s):
    """
    用于自然排序的辅助函数。
    例如确保 'n2' 排在 'n10' 前面，而不是标准的字符串排序 'n10' 在 'n2' 前面。
    """
    # 将字符串分割成数字部分和非数字部分，并将数字部分转为整数进行比较
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

def debug_graphml_structure(graphml_file):
    """
    调试GraphML文件结构，使用流式解析以防大文件卡死
    """
    try:
        print(f"调试信息 - {graphml_file}")
        print("=" * 50)
        
        nodes_count = 0
        edges_count = 0
        graph_attrib = {}
        
        # 使用 iterparse 抓取基本信息
        context = ET.iterparse(graphml_file, events=("start", "end"))
        for event, elem in context:
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if event == "start" and tag == "graph":
                graph_attrib = elem.attrib
            elif event == "end":
                if tag == "node":
                    nodes_count += 1
                elif tag == "edge":
                    edges_count += 1
                elem.clear()

        print(f"Graph 属性: {graph_attrib}")
        print(f"节点总数: {nodes_count}")
        print(f"边总数: {edges_count}")

    except Exception as e:
        print(f"调试失败: {e}")

def parse_graphml_to_in(graphml_file, output_file, debug=False):
    """
    将GraphML格式的图文件转换为.in格式
    自动兼容带命名空间（Topo）和无命名空间（Rome）的文件
    """
    if debug:
        debug_graphml_structure(graphml_file)

    try:
        nodes = set()
        raw_edges = []
        is_undirected = True # 默认视为无向图
        
        # 使用 iterparse 流式解析，完美解决各种命名空间问题且节省内存
        context = ET.iterparse(graphml_file, events=("start", "end"))
        
        for event, elem in context:
            # 剥离可能存在的命名空间前缀，兼容 Topo 和 Rome 格式
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if event == "start":
                # 获取图的默认方向属性
                if tag == "graph":
                    edgedefault = elem.get('edgedefault')
                    if edgedefault == 'directed':
                        is_undirected = False
            elif event == "end":
                if tag == "node":
                    node_id = elem.get('id')
                    if node_id is not None:
                        nodes.add(node_id)
                
                elif tag == "edge":
                    source = elem.get('source')
                    target = elem.get('target')
                    if source is not None and target is not None:
                        raw_edges.append((source, target))
                
                # 关键：释放内存，防止大文件吃光内存
                elem.clear()

        if not nodes:
            raise ValueError("未在文件中找到任何有效节点")

        # 对节点进行自然排序（确保 n2 在 n10 前面）
        sorted_nodes = sorted(list(nodes), key=natural_sort_key)
        
        # 创建原始ID到连续整数(0到N-1)的映射
        node_mapping = {node_id: i for i, node_id in enumerate(sorted_nodes)}
        
        edges = []
        for source, target in raw_edges:
            if source in node_mapping and target in node_mapping:
                u = node_mapping[source]
                v = node_mapping[target]
                
                if is_undirected:
                    # 对于无向图，始终把较小的节点ID放前面以方便去重
                    edges.append((min(u, v), max(u, v)))
                else:
                    edges.append((u, v))
                    
        # 去除重复边并排序
        edges = sorted(list(set(edges)))

        # 输出到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            # 第一行：节点数 边数
            f.write(f"{len(nodes)} {len(edges)}\n")
            # 后续行：边 u v
            for u, v in edges:
                f.write(f"{u} {v}\n")

        print(f"节点数: {len(nodes)}, 边数: {len(edges)} | 类型: {'无向图' if is_undirected else '有向图'}")
        
    except FileNotFoundError:
        print(f"文件未找到: {graphml_file}")
    except Exception as e:
        print(f"转换过程中出现错误: {e}")
        raise e # 在批量处理中捕获

def batch_convert_folder(input_folder, output_folder, debug=False):
    """批量转换文件夹中的所有GraphML文件"""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"创建输出文件夹: {output_folder}")
    
    graphml_pattern = os.path.join(input_folder, "*.graphml")
    graphml_files = glob.glob(graphml_pattern)
    
    if not graphml_files:
        print(f"在文件夹 {input_folder} 中未找到任何.graphml文件")
        return
    
    print(f"找到 {len(graphml_files)} 个GraphML文件")
    print("-" * 50)
    
    successful_conversions = 0
    failed_conversions = 0
    
    # 修复原始脚本的逻辑错误，Python 没有 ++i
    for i, graphml_file in enumerate(graphml_files, 1):
        base_name = os.path.splitext(os.path.basename(graphml_file))[0]
        output_file = os.path.join(output_folder, base_name + ".in")
        
        print(f"[{i}/{min(len(graphml_files), 500)}] 转换: {os.path.basename(graphml_file)}")
        
        try:
            parse_graphml_to_in(graphml_file, output_file, debug)
            successful_conversions += 1
            print(f"  ✓ 成功 -> {base_name}.in")
        except Exception as e:
            failed_conversions += 1
            print(f"  ✗ 失败 -> {str(e)}")
            
        if i == 500:
            print("达到 500 个文件的转换上限，提前终止。")
            break 
    
    print("=" * 50)
    print("批量转换完成!")
    print(f"成功转换: {successful_conversions} 个文件")
    print(f"转换失败: {failed_conversions} 个文件")

def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  单文件转换:")
        print(f"    python {os.path.basename(sys.argv[0])} <graphml_file> [output_file]")
        print("  批量文件夹转换:")
        print(f"    python {os.path.basename(sys.argv[0])} --batch <input_folder> <output_folder>")
        print("  调试模式:")
        print(f"    python {os.path.basename(sys.argv[0])} --debug <graphml_file>")
        sys.exit(1)
    
    if sys.argv[1] == "--debug":
        if len(sys.argv) != 3:
            print(f"使用方法: python {os.path.basename(sys.argv[0])} --debug <graphml_file>")
            sys.exit(1)
        debug_graphml_structure(sys.argv[2])
        
    elif sys.argv[1] == "--batch":
        if len(sys.argv) != 4:
            print(f"使用方法: python {os.path.basename(sys.argv[0])} --batch <input_folder> <output_folder>")
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
            output_file = os.path.splitext(graphml_file)[0] + ".in"
        parse_graphml_to_in(graphml_file, output_file)

if __name__ == "__main__":
    main()