import os
import random

# ===== 参数 =====
output_dir = "./graph_dataset/rome_dataset"
file_count = 2500
id_range = (100, 10000)   # 编号随机范围
mid_range = (10, 100)  # 中间标识随机范围
random.seed(42)        # 可删
# =================

os.makedirs(output_dir, exist_ok=True)

ids = random.sample(range(id_range[0], id_range[1] + 1), file_count)

for i in ids:
    mid = random.randint(mid_range[0], mid_range[1])
    filename = f"grafo{i}.{mid}.in"
    open(os.path.join(output_dir, filename), "w").close()
