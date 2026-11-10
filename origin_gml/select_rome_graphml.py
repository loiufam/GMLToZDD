#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按边数阈值随机挑选 GraphML 图脚本

功能：
  1. analyze_graphs_to_csv : 遍历文件夹中所有 .graphml 文件，统计节点/边数，
     按边数(再按节点数)从大到小排序，保存为 CSV。
  2. select_random_graphs_from_csv : 基于 CSV，在「边数 > 阈值」的范围内遍历候选，
     随机挑选 top_n 个图复制到目标文件夹，保证随机性；
     可选排除已存在于指定文件夹中的图，可选设置随机种子以便复现。

用法：
  python3 select_rome_graphml.py --help
  python3 select_rome_graphml.py --analysis-only --refresh-analysis
  python3 select_rome_graphml.py --min-edges 109 --max-edges 140 \
      --dest ../graphs_graphml/selected --top-n 12 --seed 20261106

所有路径、阈值、数量、排除目录和随机种子均通过命令行参数设置。
"""

import os
import shutil
import csv
import random
import argparse
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
                # 这里通过去掉可能存在的 '{}' 命名空间前缀，兼容 Rome 格式及其他格式
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


def select_random_graphs_from_csv(csv_path, src_folder, dest_folder,
                                  min_edges=0, max_edges=float('inf'),
                                  min_nodes=0, max_nodes=float('inf'),
                                  top_n=10, exclude_folder=None, seed=None):
    """
    从 CSV 中筛选满足条件的图文件（默认核心条件：边数 > min_edges），
    再随机挑选 top_n 个复制到目标文件夹，保证随机性。

    参数:
        csv_path     : 分析得到的 CSV 文件路径
        src_folder   : 图源文件夹
        dest_folder  : 目标文件夹（不存在会自动创建）
        min_edges    : 边数下界（不含），即只挑选边数严格大于该值的图
        max_edges    : 最大边数（含），无上限时用 float('inf')
        min_nodes    : 最小节点数（含），不限制填 0
        max_nodes    : 最大节点数（含），不限制用 float('inf')
        top_n        : 需要随机挑选的图数量
        exclude_folder : 排除已存在于此文件夹（或文件夹列表）中的图文件
        seed         : 随机种子；传固定数字可复现结果，None 则每次随机
    """
    if not os.path.exists(csv_path):
        print(f"❌ 错误: 找不到 CSV 文件 {csv_path}。请先运行分析功能！")
        return

    src_path = Path(src_folder)
    dest_path = Path(dest_folder)
    dest_path.mkdir(parents=True, exist_ok=True)

    # 收集需要排除的文件名
    exclude_files = set()
    if exclude_folder:
        exclude_folders = (
            [exclude_folder]
            if isinstance(exclude_folder, (str, os.PathLike))
            else exclude_folder
        )
        for folder in exclude_folders:
            exclude_path = Path(folder)
            if exclude_path.exists() and exclude_path.is_dir():
                found = {f.name for f in exclude_path.glob('*.graphml')}
                exclude_files.update(found)
                print(f"📂 将从候选中排除 {len(found)} 个已存在于 {folder} 中的图文件。")
            else:
                print(f"⚠️ 警告: 排除文件夹不存在或不是目录 -> {folder}")
        print(f"📂 排除文件去重后共 {len(exclude_files)} 个。")

    print(f"📂 正在读取 {csv_path} 并遍历筛选满足条件的图...")
    print(f"   [筛选条件]: 边数 > {min_edges} 且 <= {max_edges}, "
          f"节点数 {min_nodes}~{max_nodes}")

    # 先遍历 CSV，把满足阈值范围（且未被排除）的文件全部收进候选池
    candidates = []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            edges = int(row['edges'])
            nodes = int(row['nodes'])

            if (min_edges < edges <= max_edges) and (min_nodes <= nodes <= max_nodes):
                if row['filename'] not in exclude_files:
                    candidates.append(row['filename'])

    if not candidates:
        print("⚠️ 未找到满足条件的图文件，请检查阈值设置。")
        return

    # 设置随机种子（可选），保证随机性且可复现
    if seed is not None:
        random.seed(seed)

    if len(candidates) < top_n:
        print(f"⚠️ 满足条件的图只有 {len(candidates)} 个，少于要求的 {top_n} 个，将全部选取。")
        selected_files = candidates[:]
        random.shuffle(selected_files)
    else:
        # random.sample 无放回随机抽取，保证不重复且完全随机
        selected_files = random.sample(candidates, top_n)

    print(f"🚀 从 {len(candidates)} 个候选中随机挑选 {len(selected_files)} 个，开始复制到 {dest_folder}...")

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

    print(f"🎉 任务完成！成功挑选并复制了 {success_count} 个图文件（跳过已存在 {skip_count} 个）。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze and reproducibly sample Rome GraphML files."
    )
    parser.add_argument("--source", default="./rome", help="GraphML source folder")
    parser.add_argument(
        "--csv",
        default="rome_analysis.csv",
        help="Node/edge inventory CSV",
    )
    parser.add_argument(
        "--dest",
        default="../graphs_graphml/rome_3",
        help="Destination folder for selected GraphML files",
    )
    parser.add_argument("--min-edges", type=int, default=50)
    parser.add_argument("--max-edges", type=int, default=None)
    parser.add_argument("--min-nodes", type=int, default=0)
    parser.add_argument("--max-nodes", type=int, default=None)
    parser.add_argument("--top-n", type=int, default=350)
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Folder whose GraphML files must be excluded; repeat for multiple folders",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for a reproducible sample",
    )
    parser.add_argument(
        "--refresh-analysis",
        action="store_true",
        help="Rebuild the inventory CSV before selecting",
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="Only build the inventory CSV",
    )
    args = parser.parse_args()

    if args.refresh_analysis or args.analysis_only:
        analyze_graphs_to_csv(args.source, args.csv)
    if args.analysis_only:
        raise SystemExit(0)

    exclude = args.exclude
    if exclude is None:
        exclude = [
            "../graphs_graphml/rome_1",
            "../graphs_graphml/rome_2",
        ]

    select_random_graphs_from_csv(
        csv_path=args.csv,
        src_folder=args.source,
        dest_folder=args.dest,
        min_edges=args.min_edges,
        max_edges=args.max_edges if args.max_edges is not None else float("inf"),
        min_nodes=args.min_nodes,
        max_nodes=args.max_nodes if args.max_nodes is not None else float("inf"),
        top_n=args.top_n,
        exclude_folder=exclude,
        seed=args.seed,
    )
