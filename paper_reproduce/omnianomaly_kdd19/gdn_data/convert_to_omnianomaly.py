# -*- coding: utf-8 -*-
"""
将 GDN 实验 CSV 数据转换为 OmniAnomaly 可读取的 .pkl 格式。

输入: gdn_data/ 目录下的 GDN CSV 文件（宽表格式）
输出: gdn_data/omnianomaly/ 目录下的 .pkl 文件

用法:
    cd paper_reproduce/omnianomaly_kdd19
    python gdn_data/convert_to_omnianomaly.py
"""

import os
import pickle
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ─── 路径配置 ───────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # gdn_data/
OUTPUT_DIR = os.path.join(BASE_DIR, "omnianomaly")

# GDN CSV 文件（相对于 gdn_data/）
TRAIN_CSV = os.path.join(BASE_DIR, "gdn_normal_train.csv")
VALID_CSV = os.path.join(BASE_DIR, "gdn_normal_valid.csv")
FAULT_CSV_CPU    = os.path.join(BASE_DIR, "gdn_fault_cpu_frontend.csv")
FAULT_CSV_DELAY  = os.path.join(BASE_DIR, "gdn_fault_delay_cart.csv")
FAULT_CSV_KILL   = os.path.join(BASE_DIR, "gdn_fault_kill_product.csv")

# ─── 故障时间窗口（来自 experiment/GDN/experiment-log.md）────
# (csv路径, 故障开始, 故障结束, 恢复期分钟数)
# attack=1 范围 = [fault_start, fault_end + recovery_minutes]
FAULT_WINDOWS = [
    (FAULT_CSV_CPU,   "2026-06-06 18:22:56", "2026-06-06 18:27:57", 2),
    (FAULT_CSV_DELAY, "2026-06-06 18:37:40", "2026-06-06 18:42:41", 2),
    (FAULT_CSV_KILL,  "2026-06-06 19:23:41", "2026-06-06 19:28:42", 2),
]

# 网络特征后缀（全空列，自动剔除）
DROP_SUFFIXES = ["_net_rx", "_net_tx"]


def load_and_clean(path, label=""):
    """读取 GDN CSV，剔除时间戳列和全空列。返回 (timestamps, DataFrame)。"""
    df = pd.read_csv(path)
    ts = pd.to_datetime(df["timestamp"])
    df = df.drop(columns=["timestamp"])

    # 剔除全空网络列
    drop = [c for c in df.columns if any(c.endswith(s) for s in DROP_SUFFIXES)]
    if drop:
        df = df.drop(columns=drop)
        print(f"  [{label}] 剔除 {len(drop)} 个空列")

    df = df.fillna(0)
    print(f"  [{label}] {df.shape[0]} 行 × {df.shape[1]} 列")
    return ts, df


def make_labels(timestamps, fault_start_str, fault_end_str, recovery_min):
    """根据故障窗口生成标签: 0=正常, 1=异常。"""
    t0 = datetime.strptime(fault_start_str, "%Y-%m-%d %H:%M:%S")
    t1 = datetime.strptime(fault_end_str,   "%Y-%m-%d %H:%M:%S")
    t_end = t1 + timedelta(minutes=recovery_min)

    labels = np.zeros(len(timestamps), dtype=np.bool_)
    for i, ts in enumerate(timestamps):
        if t0 <= ts.to_pydatetime() <= t_end:
            labels[i] = True
    return labels


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── 1. 训练集 ──────────────────────────────────────────
    print("1. 训练集")
    train_ts, train_df = load_and_clean(TRAIN_CSV, "train")
    train_data = train_df.values.astype(np.float32)
    n_feat = train_data.shape[1]
    columns = list(train_df.columns)

    # ── 2. 测试集（正常验证 + 三类故障）────────────────────
    print("\n2. 测试集")

    # 正常段
    val_ts, val_df = load_and_clean(VALID_CSV, "valid")
    val_df = val_df[columns]
    test_parts = [val_df.values.astype(np.float32)]
    test_labels = [np.zeros(len(val_df), dtype=np.bool_)]
    print(f"    正常段: {len(val_df)} 行, 标签=0")

    # 故障段
    for csv_path, t_start, t_end, rec in FAULT_WINDOWS:
        name = os.path.basename(csv_path).replace("gdn_fault_", "").replace(".csv", "")
        print(f"\n    故障段: {name}")
        f_ts, f_df = load_and_clean(csv_path, name)
        f_df = f_df[columns]
        test_parts.append(f_df.values.astype(np.float32))
        labels = make_labels(f_ts, t_start, t_end, rec)
        test_labels.append(labels)
        print(f"    异常 {labels.sum()}/{len(labels)} 行")

    test_data = np.concatenate(test_parts, axis=0)
    test_label = np.concatenate(test_labels, axis=0)
    print(f"\n  测试集总计: {test_data.shape}, 异常占比: {test_label.sum()}/{len(test_label)}")

    # ── 3. 保存 ────────────────────────────────────────────
    print("\n3. 保存")
    for name, arr in [("train.pkl", train_data), ("test.pkl", test_data),
                       ("test_label.pkl", test_label)]:
        path = os.path.join(OUTPUT_DIR, name)
        with open(path, "wb") as f:
            pickle.dump(arr, f)
        print(f"  ✓ {path}  {arr.shape}")

    with open(os.path.join(OUTPUT_DIR, "dim.txt"), "w") as f:
        f.write(str(n_feat))
    print(f"  ✓ dim.txt  (dim={n_feat})")

    with open(os.path.join(OUTPUT_DIR, "columns.txt"), "w") as f:
        f.write("\n".join(columns))
    print(f"  ✓ columns.txt")

    # ── 4. 摘要 ────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"转换完成: {n_feat} 特征, 训练 {train_data.shape[0]} 行, 测试 {test_data.shape[0]} 行")
    print(f"输出: {OUTPUT_DIR}")
    print(f"\n使用方式: 将 omnianomaly/ 软链接为 processed/")
    print(f"  cd paper_reproduce/omnianomaly_kdd19")
    print(f"  ln -s gdn_data/omnianomaly processed   # Linux/Mac")
    print(f"  mklink /D processed gdn_data\\omnianomaly   # Windows")
    print(f"\n然后修改 main.py 参数:")
    print(f"  window_length = 5    # 原值 20, 训练集较小")
    print(f"  batch_size = 16      # 原值 50")
    print(f"  max_epoch = 100      # 原值 60, 小数据集需更多迭代")


if __name__ == "__main__":
    main()
