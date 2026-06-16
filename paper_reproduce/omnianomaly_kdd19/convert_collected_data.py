#!/usr/bin/env python3
"""
将 collect_metrics.py 采集的长表 CSV 转换为 OmniAnomaly pkl 格式。

collect_metrics.py 输出格式（长表）:
    metric,node,pod,namespace,container,timestamp,value

本脚本完成:
    1. 过滤 boutique namespace 的 cpu_rate + memory_working_set
    2. Pod 名 → 服务名聚合（sum: frontend-xxx-yyy → frontend）
    3. Pivot 长表 → 宽表（11服务 × 2指标 = 22维）
    4. 解析 experiment_log.txt 生成异常标签
    5. 划分训练集/测试集，保存为 pkl

用法:
    cd paper_reproduce/omnianomaly_kdd19
    python convert_collected_data.py
    python convert_collected_data.py --train-split 0.8 --recovery-min 2
"""

import argparse
import os
import pickle
import re
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ─── 路径配置 ──────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
LOG_FILE = os.path.join(DATA_DIR, "experiment_log.txt")
NORMAL_CSV = os.path.join(DATA_DIR, "normal_train.csv")

# 11 个标准微服务
SERVICES = [
    "frontend", "cartservice", "checkoutservice", "productcatalogservice",
    "recommendationservice", "paymentservice", "currencyservice",
    "shippingservice", "emailservice", "adservice", "redis-cart",
]

METRIC_RENAME = {
    "cpu_rate": "cpu",
    "memory_working_set": "mem",
}


def extract_service(pod_name):
    """从完整 Pod 名提取服务名: 'frontend-694b9f76cd-z2pk6' → 'frontend'"""
    # Pod 名格式: {service}-{replicaset_hash}-{pod_hash}
    # 去掉末尾两个哈希段
    parts = pod_name.rsplit("-", 2)
    return parts[0] if len(parts) >= 2 else pod_name


def load_long_csv(path, label=""):
    """读取 collect_metrics.py 输出的长表 CSV，转换为宽表。

    Returns:
        DataFrame: 宽表，index=timestamp, columns=service_metric (22列)
    """
    df = pd.read_csv(path, header=None, names=[
        "metric", "node", "pod", "namespace", "container", "timestamp", "value"
    ])

    # 过滤：只保留 boutique namespace + cpu_rate / memory_working_set
    df = df[df["namespace"] == "boutique"]
    df = df[df["metric"].isin(["cpu_rate", "memory_working_set"])]

    if df.empty:
        print(f"  [{label}] 警告: 过滤后无数据 (namespace=boutique, metrics=cpu_rate/memory_working_set)")
        return pd.DataFrame()

    # 提取服务名
    df["service"] = df["pod"].apply(extract_service)

    # 重命名 metric
    df["metric"] = df["metric"].map(METRIC_RENAME)

    # 按 (timestamp, service, metric) 聚合 (sum)
    pivot = df.pivot_table(
        index="timestamp",
        columns=["service", "metric"],
        values="value",
        aggfunc="sum",
    )

    # 展平列名: ('frontend', 'cpu') → 'frontend_cpu'
    pivot.columns = [f"{s}_{m}" for s, m in pivot.columns]

    # 确保 22 列齐全，缺失填 0
    expected_cols = []
    for svc in SERVICES:
        for m in ["cpu", "mem"]:
            expected_cols.append(f"{svc}_{m}")
    for col in expected_cols:
        if col not in pivot.columns:
            pivot[col] = 0.0
    pivot = pivot[expected_cols]

    pivot = pivot.sort_index()
    pivot = pivot.fillna(0)

    print(f"  [{label}] {pivot.shape[0]} 行 × {pivot.shape[1]} 列 (长表→宽表)")
    return pivot


def parse_experiment_log(log_path):
    """解析 experiment_log.txt，提取故障时间窗口。

    Returns:
        list of dict: [{"name", "fault_start", "fault_end", "csv"}, ...]
    """
    if not os.path.exists(log_path):
        print(f"⚠ 实验日志不存在: {log_path}")
        return []

    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()

    experiments = []
    blocks = re.split(r"\n## ", content)

    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().split("\n")
        name = lines[0].strip().lstrip("#").strip()
        if not name.startswith("fault_"):
            continue

        exp = {"name": name}
        for line in lines[1:]:
            line = line.strip().lstrip("-").strip()
            if line.startswith("故障开始:"):
                ts = line.replace("故障开始:", "").strip()
                try:
                    exp["fault_start"] = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            elif line.startswith("故障结束:"):
                ts = line.replace("故障结束:", "").strip()
                try:
                    exp["fault_end"] = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            elif line.startswith("文件:"):
                csv_rel = line.replace("文件:", "").strip()
                csv_path = os.path.join(BASE_DIR, csv_rel)
                if os.path.exists(csv_path):
                    exp["csv"] = csv_path
                else:
                    print(f"  ⚠ 文件不存在: {csv_path}")

        if "csv" in exp and "fault_start" in exp and "fault_end" in exp:
            experiments.append(exp)
        else:
            print(f"  ⚠ 跳过 {name}: 缺少时间窗口或CSV文件")

    print(f"解析到 {len(experiments)} 个故障实验:")
    for exp in experiments:
        print(f"  {exp['name']}: {exp['fault_start']} → {exp['fault_end']}")
    return experiments


def make_labels(timestamps,
                fault_start,
                fault_end,
                recovery_min):
    """故障窗口 + 恢复期 → 标签 (0=正常, 1=异常)。

    fault_start/end 来自 experiment_log.txt (本地时间 CST=UTC+8)，
    timestamps 是 Pandas DatetimeIndex (来自 Unix 时间戳，UTC)。
    转为 Unix 时间戳做数值比较以避免时区问题。
    """
    import calendar

    def _to_unix(dt):
        # dt 是 naive datetime (本地时间 CST)，转为 UTC unix timestamp
        return calendar.timegm(dt.timetuple()) - 8 * 3600

    start_ts = _to_unix(fault_start)
    end_ts = _to_unix(fault_end + timedelta(minutes=recovery_min))
    labels = np.zeros(len(timestamps), dtype=np.bool_)
    for i, ts in enumerate(timestamps):
        ts_val = ts.value // 10**9  # nanoseconds → seconds
        if start_ts <= ts_val <= end_ts:
            labels[i] = True
    return labels


def convert(train_split: float = 0.8, recovery_min: int = 2, dry_run: bool = False):
    """主转换流程。"""
    # ── 1. 检查输入 ──────────────────────────────────────────
    if not os.path.exists(NORMAL_CSV):
        print(f"✗ 错误: 正常数据不存在: {NORMAL_CSV}")
        print(f"  请先运行: bash collect_data.sh collect-normal")
        return 1

    experiments = parse_experiment_log(LOG_FILE)
    if not experiments:
        print(f"⚠ 警告: 没有故障实验记录，测试集将只含正常数据")

    # ── 2. 加载正常数据 ──────────────────────────────────────
    print("\n" + "=" * 55)
    print("1. 正常训练数据")
    df_normal = load_long_csv(NORMAL_CSV, "normal")
    if df_normal.empty:
        print("✗ 错误: 正常数据过滤后为空")
        return 1

    n_features = df_normal.shape[1]
    columns = list(df_normal.columns)
    ts_normal = pd.to_datetime(df_normal.index, unit='s')
    values = df_normal.values.astype(np.float32)

    # 拆分训练/验证
    split_idx = int(len(values) * train_split)
    train_data = values[:split_idx]
    val_normal = values[split_idx:]
    val_ts = ts_normal[split_idx:]

    print(f"  总: {len(values)} 行 × {n_features} 维")
    print(f"  训练: {len(train_data)} 行 | 验证正常段: {len(val_normal)} 行")
    print(f"  列: {', '.join(columns[:6])}... ({n_features} 列)")

    # ── 3. 加载故障数据 ──────────────────────────────────────
    print(f"\n2. 故障测试数据")
    test_parts = []
    test_labels_list = []

    if len(val_normal) > 0:
        test_parts.append(val_normal)
        test_labels_list.append(np.zeros(len(val_normal), dtype=np.bool_))
        print(f"  验证正常段: {len(val_normal)} 行, 标签=0")

    for exp in experiments:
        name = exp["name"]
        print(f"\n  故障段: {name}")
        df_fault = load_long_csv(exp["csv"], name)
        if df_fault.empty:
            print(f"    ⚠ 数据为空，跳过")
            continue

        # 确保列与训练集一致
        df_fault = df_fault.reindex(columns=columns, fill_value=0.0)
        fault_values = df_fault.values.astype(np.float32)
        fault_ts = pd.to_datetime(df_fault.index, unit='s')

        test_parts.append(fault_values)
        labels = make_labels(fault_ts, exp["fault_start"], exp["fault_end"], recovery_min)
        test_labels_list.append(labels)
        print(f"    {len(fault_values)} 行, 异常 {labels.sum()}/{len(fault_values)}")

    test_data = np.concatenate(test_parts, axis=0)
    test_label = np.concatenate(test_labels_list, axis=0)
    print(f"\n  测试集总计: {test_data.shape}, "
          f"异常: {test_label.sum()}/{len(test_label)} "
          f"({test_label.sum()/max(1,len(test_label))*100:.1f}%)")

    # ── 4. 保存 ────────────────────────────────────────────────
    if dry_run:
        print("\n[Dry Run] 跳过写入")
        return 0

    os.makedirs(PROCESSED_DIR, exist_ok=True)

    files = [
        ("boutique_train.pkl", train_data),
        ("boutique_test.pkl", test_data),
        ("boutique_test_label.pkl", test_label),
    ]
    for fname, arr in files:
        path = os.path.join(PROCESSED_DIR, fname)
        with open(path, "wb") as f:
            pickle.dump(arr, f)
        print(f"  ✓ {fname}  {arr.shape}")

    with open(os.path.join(PROCESSED_DIR, "boutique_dim.txt"), "w") as f:
        f.write(str(n_features))
    with open(os.path.join(PROCESSED_DIR, "columns.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(columns))

    print(f"\n输出: {PROCESSED_DIR}/")
    print(f"  特征: {n_features} 维")
    print(f"  训练: {train_data.shape[0]} 行")
    print(f"  测试: {test_data.shape[0]} 行 (异常 {test_label.sum()}/{len(test_label)})")

    # ── 5. 参数建议 ────────────────────────────────────────
    n_train = train_data.shape[0]
    print(f"\n{'='*55}")
    print(f"建议 main.py 参数 (当前 {n_train} 个训练点):")
    if n_train >= 400:
        print(f"  window_length = 30, batch_size = 50")
    elif n_train >= 120:
        print(f"  window_length = 10, batch_size = 35")
    else:
        print(f"  window_length = 5,  batch_size = 16")
    print(f"{'='*55}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="将 collect_metrics.py 长表 CSV 转换为 OmniAnomaly pkl",
    )
    parser.add_argument("--train-split", type=float, default=0.8)
    parser.add_argument("--recovery-min", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return convert(args.train_split, args.recovery_min, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
