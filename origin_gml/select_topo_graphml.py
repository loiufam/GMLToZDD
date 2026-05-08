import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

def count_edges_in_graphml(file_path):
    """
    解析 GraphML 文件并统计边数（edge 标签的数量）
    优化版：使用 iterparse 避免大文件撑爆内存（专门针对包含大量 yFiles 几何数据的图）
    """
    try:
        edge_count = 0
        # 使用 iterparse 逐事件/逐节点解析，避免一次性把整个庞大的 DOM 树加载到内存中
        context = ET.iterparse(file_path, events=("end",))
        
        for event, elem in context:
            # GraphML 通常有默认命名空间，所以 tag 会变成 {http://...}edge
            if elem.tag.endswith('}edge') or elem.tag == 'edge':
                edge_count += 1
            
            # 关键：处理完一个元素后立即释放内存。
            # 尤其是面对您数据中包含大量冗长 <y:ShapeNode> 等视图标签时，这步能极大加快速度并节省内存。
            elem.clear()
                
        return edge_count
    except Exception as e:
        print(f"❌ 解析文件出错 {file_path.name}: {e}")
        return -1 # 返回 -1 表示解析失败

def filter_and_copy_graphs(src_folder, dest_folder, threshold=50):
    """
    从源文件夹挑选边数大于 threshold 的 .graphml 文件并复制到目标文件夹
    """
    src_path = Path(src_folder)
    dest_path = Path(dest_folder)

    # 检查源文件夹是否存在
    if not src_path.exists() or not src_path.is_dir():
        print(f"❌ 错误: 源文件夹不存在 -> {src_folder}")
        return

    # 确保目标文件夹存在，如果不存在则自动创建
    dest_path.mkdir(parents=True, exist_ok=True)
    print(f"📁 源文件夹: {src_path.resolve()}")
    print(f"📁 目标文件夹: {dest_path.resolve()}")
    print("-" * 50)

    # 查找所有 .graphml 文件 (如果你需要包含子文件夹，可以将 glob 换成 rglob)
    graphml_files = list(src_path.glob('*.graphml'))
    
    if not graphml_files:
        print("⚠️ 源文件夹中没有找到 .graphml 文件。")
        return

    copied_count = 0
    total_count = len(graphml_files)

    for i, file_path in enumerate(graphml_files, 1):
        edge_count = count_edges_in_graphml(file_path)
        
        # 判断边数是否大于指定阈值 (50)
        if edge_count > threshold:
            print(f"[{i}/{total_count}] ✅ 复制: {file_path.name} (边数: {edge_count})")
            
            # 复制文件到目标文件夹 (copy2 会保留文件的元数据，如创建时间等)
            destination_file = dest_path / file_path.name
            shutil.copy2(file_path, destination_file)
            copied_count += 1
        elif edge_count >= 0:
            print(f"[{i}/{total_count}] ⏭️ 跳过: {file_path.name} (边数: {edge_count})")

    print("-" * 50)
    print(f"🎉 任务完成! 共检查了 {total_count} 个文件，成功挑选并复制了 {copied_count} 个文件。")

if __name__ == "__main__":

    SOURCE_DIRECTORY = r"./topologyzoo/sources"      # 替换为你的源文件夹路径
    DESTINATION_DIRECTORY = r"../graphs/topo" # 替换为你要存放结果的目标文件夹路径
    EDGE_THRESHOLD = 50                        # 筛选条件：边数大于 50
    
    filter_and_copy_graphs(SOURCE_DIRECTORY, DESTINATION_DIRECTORY, EDGE_THRESHOLD)