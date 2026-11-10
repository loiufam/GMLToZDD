import os
import shutil
import csv
import xml.etree.ElementTree as ET
from pathlib import Path

def analyze_graphs_to_csv(src_folder, csv_path):
    """
    遍历文件夹中的所有 GraphML 文件，统计节点和边数，
    并按边数、节点数从大到小排序，最后保存到 CSV 文件中。
    """
    src_path = Path(src_folder)
    if not src_path.exists() or not src_path.is_dir():
        print(f"❌ 错误: 源文件夹不存在 -> {src_folder}")
        return

    graphml_files = list(src_path.glob('*.graphml'))
    if not graphml_files:
        print(f"⚠️ 警告: {src_folder} 中没有找到 .graphml 文件。")
        return

    print(f"🔍 阶段 1/2: 开始分析 {len(graphml_files)} 个 GraphML 文件...")
    results = []

    for i, file_path in enumerate(graphml_files, 1):
        nodes, edges = 0, 0
        try:
            # 使用 iterparse 流式解析，高效且节省内存
            context = ET.iterparse(file_path, events=("end",))
            for event, elem in context:
                # Rome 数据集的 graphml 没有 XML 命名空间，标签直接是 'node' 和 'edge'
                # 这里通过去掉可能存在的 '{}' 命名空间前缀，完美兼容您的 Rome 格式及其他格式
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                
                if tag == 'node':
                    nodes += 1
                elif tag == 'edge':
                    edges += 1
                    
                # 释放节点内存，防止内存泄漏
                elem.clear()
            
            results.append({
                "filename": file_path.name,
                "edges": edges,
                "nodes": nodes
            })
            
            # 每分析 100 个文件打印一次日志，避免日志刷屏
            if i % 100 == 0 or i == len(graphml_files):
                print(f"  ... 已分析 {i}/{len(graphml_files)} 个文件")
                
        except Exception as e:
            print(f"❌ 解析文件出错 {file_path.name}: {e}")

    print("📊 阶段 2/2: 正在对结果进行排序并写入 CSV...")
    # 按边数从大到小排序，如果边数相同，则按节点数从大到小排序
    results.sort(key=lambda x: (x['edges'], x['nodes']), reverse=True)

    try:
        with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["filename", "edges", "nodes"])
            writer.writeheader()
            writer.writerows(results)
        print(f"✅ 分析完成！已将排序后的数据保存至 -> {csv_path}")
    except Exception as e:
        print(f"❌ 写入 CSV 失败: {e}")

def filter_graphs_from_csv(csv_path, src_folder, dest_folder, 
                           min_edges=0, max_edges=float('inf'), 
                           min_nodes=0, max_nodes=float('inf'), 
                           top_n=10):
    """
    直接读取 CSV 文件，根据边数和节点数范围筛选出满足条件的图，
    并复制前 top_n 个文件到指定文件夹。
    """
    if not os.path.exists(csv_path):
        print(f"❌ 错误: 找不到 CSV 文件 {csv_path}。请先运行分析功能！")
        return

    src_path = Path(src_folder)
    dest_path = Path(dest_folder)
    dest_path.mkdir(parents=True, exist_ok=True)

    print(f"📂 正在从 {csv_path} 中读取并筛选数据...")
    print(f"   [筛选条件]: 边数 {min_edges}~{max_edges}, 节点数 {min_nodes}~{max_nodes}, 需要提取 {top_n} 个")

    selected_files = []
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            edges = int(row['edges'])
            nodes = int(row['nodes'])
            
            # 判断是否在指定范围内
            if (min_edges <= edges <= max_edges) and (min_nodes <= nodes <= max_nodes):
                selected_files.append(row['filename'])
                if len(selected_files) >= top_n:
                    break  # 达到所需数量，提前结束读取

    if not selected_files:
        print("⚠️ 未找到符合要求的图文件。")
        return

    print(f"🚀 筛选完毕，开始从 {src_folder} 复制 {len(selected_files)} 个文件到 {dest_folder}...")
    
    success_count = 0
    skip_count = 0

    for file_name in selected_files:
        src_file = src_path / file_name
        dest_file = dest_path / file_name
        
        if not src_file.exists():
            print(f"  [!] 文件丢失 (CSV中有记录但文件夹中未找到): {file_name}")
            continue

        if dest_file.exists():
            print(f"  [=] 跳过已有文件: {file_name}")
            skip_count += 1
            continue

        shutil.copy2(src_file, dest_file)
        print(f"  [+] 复制成功: {file_name}")
        success_count += 1

    print(f"🎉 任务完成！成功挑选并复制了 {success_count} 个图文件。")

def select_graphs_from_csv(csv_path, src_folder, dest_folder, top_n=10, exclude_folder=None):
    """
    从 CSV 中按顺序选择前 top_n 个图文件，并复制到目标文件夹。
    如果 exclude_folder 不为 None，则会排除掉已经存在于该文件夹中的图文件。
    """
    if not os.path.exists(csv_path):
        print(f"❌ 错误: 找不到 CSV 文件 {csv_path}。请先运行分析功能！")
        return

    src_path = Path(src_folder)
    dest_path = Path(dest_folder)
    dest_path.mkdir(parents=True, exist_ok=True)

    exclude_files = set()
    if exclude_folder:
        exclude_path = Path(exclude_folder)
        if exclude_path.exists() and exclude_path.is_dir():
            exclude_files = {f.name for f in exclude_path.glob('*.graphml')}
            print(f"📂 将排除 {len(exclude_files)} 个已存在于 {exclude_folder} 中的图文件。")
        else:
            print(f"⚠️ 警告: 排除文件夹不存在或不是目录 -> {exclude_folder}")

    print(f"📂 正在从 {csv_path} 中读取并选择前 {top_n} 个图文件...")
    
    selected_files = []
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            file_name = row['filename']
            if file_name not in exclude_files:
                selected_files.append(file_name)
                if len(selected_files) >= top_n:
                    break  # 达到所需数量，提前结束读取

    if not selected_files:
        print("⚠️ 未找到符合要求的图文件。")
        return

    print(f"🚀 开始从 {src_folder} 复制 {len(selected_files)} 个文件到 {dest_folder}...")
    
    success_count = 0
    skip_count = 0

    for file_name in selected_files:
        src_file = src_path / file_name
        dest_file = dest_path / file_name
        
        if not src_file.exists():
            print(f"  [!] 文件丢失 (CSV中有记录但文件夹中未找到): {file_name}")
            continue

        if dest_file.exists():
            print(f"  [=] 跳过已有文件: {file_name}")
            skip_count += 1
            continue
        shutil.copy2(src_file, dest_file)
        print(f"  [+] 复制成功: {file_name}")
        success_count += 1

    print(f"🎉 任务完成！成功挑选并复制了 {success_count} 个图文件。")

if __name__ == "__main__":
    # ==================== 配置区 ====================
    # 你的 rome 文件夹路径
    ROME_FOLDER = r"./rome" 
    # 分析结果保存的 CSV 文件名
    CSV_FILE_PATH = r"rome_analysis.csv" 
    # 筛选后存放图的目标文件夹
    TARGET_FOLDER = r"../graphs_graphml/rome_2"

    CHOSEN_ROME = r"../graphs_graphml/rome_1"

    # ==================== 操作一：分析所有文件 ====================
    # 第一次使用，或者 rome 文件夹里有新图加入时，请取消注释运行下面这行
    
    # analyze_graphs_to_csv(ROME_FOLDER, CSV_FILE_PATH)

    # ==================== 操作二：按条件查表筛选 ====================
    # 有了 CSV 后，就可以使用这行代码进行“秒筛选”了。不需要分析时，可把上方那行注释掉。
    # 如果没有上限，可以使用 float('inf')。

    # 第一次筛选范围： 130 > edges > 100 and 80 > nodes > 60，挑选 50 个
    
    # filter_graphs_from_csv(
    #     csv_path=CSV_FILE_PATH,
    #     src_folder=ROME_FOLDER,
    #     dest_folder=TARGET_FOLDER,
    #     min_edges=100,   # 最小边数
    #     max_edges=130,  # 最大边数
    #     min_nodes=60,   # 最小节点数
    #     max_nodes=80,   # 最大节点数
    #     top_n=5         # 挑选 N 个图
    # )

    # 按照csv从前往后找 N 个图到目标文件夹，要求不能在 CHOSEN_ROME 文件夹中已存在
    select_graphs_from_csv(
        csv_path=CSV_FILE_PATH,
        src_folder=ROME_FOLDER,
        dest_folder=TARGET_FOLDER,
        top_n=300,  # 挑选前 N 个图
        exclude_folder=CHOSEN_ROME  # 排除已存在于这个文件夹中的图
    )