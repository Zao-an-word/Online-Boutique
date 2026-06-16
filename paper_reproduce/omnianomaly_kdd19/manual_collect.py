#!/usr/bin/env python3
"""
实时 Prometheus 指标采集脚本（备选方案）。

当 export_metrics.py 不支持 --duration 参数时使用此脚本。
直接从 Prometheus 实时查询指标，按固定间隔写入 CSV。

用法:
    # 采集 2 小时正常数据
    python manual_collect.py data/normal_train.csv 7200

    # 无限采集（Ctrl+C 停止）
    python manual_collect.py data/live_metrics.csv

    # 指定 Prometheus 地址和命名空间
    python manual_collect.py data/output.csv 3600 --prometheus http://localhost:19090 --namespace boutique --interval 30
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

# ─── 配置 ──────────────────────────────────────────────────
SERVICES = [
    "frontend",
    "cartservice",
    "checkoutservice",
    "productcatalogservice",
    "recommendationservice",
    "paymentservice",
    "currencyservice",
    "shippingservice",
    "emailservice",
    "adservice",
    "redis-cart",
]

CORE_METRICS = {
    "cpu": 'sum(rate(container_cpu_usage_seconds_total{{namespace="{ns}", pod=~"{svc}.*"}}[1m]))',
    "mem": 'sum(container_memory_working_set_bytes{{namespace="{ns}", pod=~"{svc}.*"}})',
}

_shutdown = False


def on_shutdown(signum, frame):
    global _shutdown
    _shutdown = True
    print("\n收到停止信号，正在结束采集...")


_first_error_printed = False

def prom_instant_query(base_url: str, query: str):
    """执行 Prometheus 即时查询，返回标量值。"""
    global _first_error_printed
    params = urllib.parse.urlencode({"query": query})
    url = f"{base_url.rstrip('/')}/api/v1/query?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("status") != "success":
            if not _first_error_printed:
                print(f"  [ERROR] Prometheus 返回错误: {payload.get('error', 'unknown')}", file=sys.stderr)
                _first_error_printed = True
            return 0.0
        result = payload["data"]["result"]
        if result:
            return float(result[0]["value"][1])
        # 指标名不存在或无数据 — 正常情况，不报错
        return 0.0
    except Exception as e:
        if not _first_error_printed:
            print(f"  [ERROR] Prometheus 查询失败: {e}", file=sys.stderr)
            print(f"  URL: {url[:120]}...", file=sys.stderr)
            _first_error_printed = True
        return 0.0


def collect(output_path: str, duration_sec: int | None, prometheus: str, namespace: str, interval: int):
    """实时采集指标到 CSV。

    Args:
        output_path: 输出 CSV 路径
        duration_sec: 采集时长（秒），None 表示无限采集
        prometheus: Prometheus 基础 URL
        namespace: Kubernetes 命名空间
        interval: 采样间隔（秒）
    """
    # 构建列名
    columns = ["timestamp"]
    queries = {}
    for svc in SERVICES:
        for metric_name, template in CORE_METRICS.items():
            col = f"{svc}_{metric_name}"
            queries[col] = template.format(ns=namespace, svc=svc)
    columns += list(queries.keys())

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    start_time = datetime.now()
    row_count = 0

    print(f"采集开始: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  输出: {output_path}")
    print(f"  Prometheus: {prometheus}")
    print(f"  命名空间: {namespace}")
    print(f"  间隔: {interval}s")
    print(f"  特征数: {len(queries)}（{len(SERVICES)} 服务 × {len(CORE_METRICS)} 指标）")
    if duration_sec:
        print(f"  时长: {duration_sec}s ≈ {duration_sec // 60} 分钟")
    else:
        print(f"  时长: 无限（Ctrl+C 停止）")
    print()

    # 启动自检：测试第一个查询是否返回非零值
    test_col, test_query = next(iter(queries.items()))
    test_val = prom_instant_query(prometheus, test_query)
    if test_val == 0.0:
        print(f"⚠ 警告: 启动自检失败 — {test_col} 返回 0.0")
        print(f"  查询: {test_query}")
        print(f"  请检查: 1) Prometheus 是否可达  2) namespace='{namespace}' 是否正确")
        print(f"  将尝试继续采集...")
    else:
        print(f"✓ 连通性检查通过 ({test_col}={test_val:.4f})")
    print()

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)

        try:
            while not _shutdown:
                # 检查是否超时
                if duration_sec:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed >= duration_sec:
                        print(f"已达到目标时长 {duration_sec}s，停止采集")
                        break

                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row = [ts]
                for col_name, query in queries.items():
                    val = prom_instant_query(prometheus, query)
                    row.append(val)

                writer.writerow(row)
                f.flush()  # 确保数据落盘
                row_count += 1

                if row_count % 20 == 0:
                    remaining = ""
                    if duration_sec:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        remaining = f"  剩余 {max(0, duration_sec - elapsed):.0f}s"
                    print(f"[{ts}] {row_count} 行已采集 ({len(SERVICES)}×{len(CORE_METRICS)}={len(queries)} 维){remaining}")

                # 分段 sleep，以便快速响应 shutdown 信号
                for _ in range(interval):
                    if _shutdown:
                        break
                    time.sleep(1)

        except KeyboardInterrupt:
            print("\n用户中断")
        except Exception as e:
            print(f"\n采集出错: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1

    end_time = datetime.now()
    total_minutes = (end_time - start_time).total_seconds() / 60
    print(f"\n采集结束: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总时长: {total_minutes:.1f} 分钟")
    print(f"总行数: {row_count}")
    print(f"输出: {output_path}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="实时 Prometheus 指标采集脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python manual_collect.py data/normal_train.csv 7200
  python manual_collect.py data/live.csv              # 无限采集
  python manual_collect.py data/output.csv 3600 --interval 15
        """,
    )
    parser.add_argument("output", help="输出 CSV 文件路径")
    parser.add_argument("duration", nargs="?", type=int, default=None,
                        help="采集时长（秒），不指定则无限采集至 Ctrl+C")
    parser.add_argument("--prometheus", default="http://localhost:19090",
                        help="Prometheus 基础 URL（默认 http://localhost:19090）")
    parser.add_argument("--namespace", default="boutique",
                        help="Kubernetes 命名空间（默认 boutique）")
    parser.add_argument("--interval", type=int, default=30,
                        help="采样间隔秒数（默认 30）")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, on_shutdown)
    signal.signal(signal.SIGTERM, on_shutdown)

    return collect(
        output_path=args.output,
        duration_sec=args.duration,
        prometheus=args.prometheus,
        namespace=args.namespace,
        interval=args.interval,
    )


if __name__ == "__main__":
    sys.exit(main())
