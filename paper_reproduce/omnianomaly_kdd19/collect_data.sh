#!/bin/bash
# ============================================================
# Online Boutique OmniAnomaly 数据采集流水线 (v2)
# 使用已验证的 collect_metrics.py + boutique_preprocess.py
# 用法: bash collect_data.sh [start|stop|status|collect-normal|fault|all-faults|train]
# ============================================================

NS="boutique"
PROMETHEUS_URL="http://localhost:19090"
PROMETHEUS_NS="monitoring"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"
BOUTIQUE_DATA_DIR="$SCRIPT_DIR/boutique__data"
LOG_FILE="$DATA_DIR/experiment_log.txt"
INTERVAL=30  # 采样间隔（秒）

# 把 Anaconda 加入 PATH（解决从 PowerShell 启动 bash 时 PATH 不完整的问题）
for anaconda_dir in "/d/Anaconda" "/mnt/d/Anaconda" "D:/Anaconda"; do
    if [ -d "$anaconda_dir" ]; then
        export PATH="$anaconda_dir:$anaconda_dir/Scripts:$PATH"
        break
    fi
done

# 检测 Python — 与原 start_collection.sh 一致的方式
PYTHON=$(which python 2>/dev/null || which python3 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "错误: Python 未找到"
    exit 1
fi
echo "Python: $PYTHON"

mkdir -p "$DATA_DIR"

# ── 启动集群 ──────────────────────────────────
start() {
    echo "=== 1. 检查 Minikube ==="
    minikube status 2>/dev/null || minikube start --cpus=4 --memory=8192

    echo "=== 2. 部署 Online Boutique ==="
    kubectl apply -f "$SCRIPT_DIR/../../release/kubernetes-manifests.yaml"
    kubectl wait --for=condition=ready pod -l app=frontend -n $NS --timeout=300s

    echo "=== 3. 部署 loadgenerator ==="
    kubectl apply -f "$SCRIPT_DIR/../../kubernetes-manifests/loadgenerator.yaml"

    echo "✓ 集群已就绪"
    echo "  端口转发: kubectl port-forward -n $PROMETHEUS_NS svc/monitoring-kube-prometheus-prometheus $PROMETHEUS_PORT:9090"
}

# ── 采集正常训练数据 ──────────────────────────
collect_normal() {
    DURATION_MIN=${1:-360}  # 默认 360 分钟 = 6 小时
    echo "=== 采集正常训练数据 (${DURATION_MIN} 分钟 ≈ $(($DURATION_MIN/60)) 小时) ==="
    echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"

    cd "$BOUTIQUE_DATA_DIR"
    $PYTHON collect_metrics.py \
        --mode live \
        --duration "$DURATION_MIN" \
        --interval "$INTERVAL" \
        --output "$DATA_DIR/normal_train.csv" \
        --prometheus-url "$PROMETHEUS_URL" \
        --metrics cpu_rate memory_working_set

    LINES=$(wc -l < "$DATA_DIR/normal_train.csv" 2>/dev/null || echo 0)
    echo "采集完成: $LINES 行" | tee -a "$LOG_FILE"
    echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
    echo "输出: $DATA_DIR/normal_train.csv"
}

# ── 单个故障实验 ──────────────────────────────
run_fault() {
    FAULT_TYPE=$1    # cpu, delay, kill
    TARGET_SVC=$2    # frontend, cartservice, etc.
    NAME="fault_${FAULT_TYPE}_${TARGET_SVC}"

    echo ""
    echo "========================================"
    echo "  故障实验: $NAME"
    echo "========================================"

    # 1. 启动后台采集 (9 分钟 = 2基线 + 5故障 + 2恢复)
    OUTPUT="$DATA_DIR/${NAME}.csv"
    echo "[$(date '+%H:%M:%S')] 启动采集..." | tee -a "$LOG_FILE"
    cd "$BOUTIQUE_DATA_DIR"
    $PYTHON collect_metrics.py \
        --mode live \
        --duration 9 \
        --interval "$INTERVAL" \
        --output "$OUTPUT" \
        --prometheus-url "$PROMETHEUS_URL" \
        --metrics cpu_rate memory_working_set &
    COLLECT_PID=$!
    cd "$SCRIPT_DIR"
    sleep 5

    # 2. 基线采集 2 分钟
    echo "[$(date '+%H:%M:%S')] 采集正常基线 (2min)..." | tee -a "$LOG_FILE"
    sleep 115

    # 3. 注入故障
    FAULT_START=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$(date '+%H:%M:%S')] 注入故障: $FAULT_TYPE → $TARGET_SVC" | tee -a "$LOG_FILE"

    YAML_FILE="$DATA_DIR/.chaos_${NAME}.yaml"
    case $FAULT_TYPE in
        cpu)
            cat > "$YAML_FILE" << EOF
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: $NAME
  namespace: chaos-testing
spec:
  mode: one
  selector:
    namespaces: [$NS]
    labelSelectors: {app: $TARGET_SVC}
  stressors:
    cpu: {workers: 2, load: 80}
  duration: "5m"
EOF
            ;;
        delay)
            cat > "$YAML_FILE" << EOF
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: $NAME
  namespace: chaos-testing
spec:
  action: delay
  mode: one
  selector:
    namespaces: [$NS]
    labelSelectors: {app: $TARGET_SVC}
  delay: {latency: "500ms", jitter: "100ms"}
  duration: "5m"
EOF
            ;;
        kill)
            cat > "$YAML_FILE" << EOF
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: $NAME
  namespace: chaos-testing
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces: [$NS]
    labelSelectors: {app: $TARGET_SVC}
  duration: "5m"
EOF
            ;;
    esac

    kubectl apply -f "$YAML_FILE"
    echo "  故障开始: $FAULT_START" >> "$LOG_FILE"

    # 4. 等待故障结束 + 恢复期
    echo "[$(date '+%H:%M:%S')] 故障进行中 (5min)..." | tee -a "$LOG_FILE"
    sleep 300
    FAULT_END=$(date '+%Y-%m-%d %H:%M:%S')
    echo "  故障结束: $FAULT_END" >> "$LOG_FILE"
    kubectl delete -f "$YAML_FILE" 2>/dev/null || true

    echo "[$(date '+%H:%M:%S')] 恢复期 (2min)..." | tee -a "$LOG_FILE"
    sleep 120

    # 5. 等待采集自动结束（9 分钟 duration 应该已到）
    COLLECT_END=$(date '+%Y-%m-%d %H:%M:%S')
    wait $COLLECT_PID 2>/dev/null || true
    rm -f "$YAML_FILE" 2>/dev/null || true

    # 6. 记录日志
    echo "  采集结束: $COLLECT_END" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    echo "## $NAME" >> "$LOG_FILE"
    echo "- 故障开始: $FAULT_START" >> "$LOG_FILE"
    echo "- 故障结束: $FAULT_END" >> "$LOG_FILE"
    echo "- 采集结束: $COLLECT_END" >> "$LOG_FILE"
    echo "- 文件: data/${NAME}.csv" >> "$LOG_FILE"

    LINES=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
    echo "  采集完成: $LINES 行 → $OUTPUT"

    # 7. 冷却
    echo "[$(date '+%H:%M:%S')] 冷却 5 分钟..." | tee -a "$LOG_FILE"
    sleep 300

    return 0
}

# ── 运行完整实验矩阵 ──────────────────────────
run_all_faults() {
    echo "=== 开始故障实验矩阵 (9 组, 预计 ~2 小时) ==="

    SERVICES=(frontend cartservice productcatalogservice)
    FAILED=()

    for svc in "${SERVICES[@]}"; do
        if run_fault cpu "$svc"; then
            echo "  ✓ fault_cpu_$svc 完成"
        else
            echo "  ✗ fault_cpu_$svc 失败，继续下一个"
            FAILED+=("fault_cpu_$svc")
        fi
    done
    for svc in "${SERVICES[@]}"; do
        if run_fault delay "$svc"; then
            echo "  ✓ fault_delay_$svc 完成"
        else
            echo "  ✗ fault_delay_$svc 失败，继续下一个"
            FAILED+=("fault_delay_$svc")
        fi
    done
    for svc in "${SERVICES[@]}"; do
        if run_fault kill "$svc"; then
            echo "  ✓ fault_kill_$svc 完成"
        else
            echo "  ✗ fault_kill_$svc 失败，继续下一个"
            FAILED+=("fault_kill_$svc")
        fi
    done

    echo ""
    echo "========================================"
    echo "  全部故障实验结束"
    echo "  成功: $((9 - ${#FAILED[@]}))/9"
    if [ ${#FAILED[@]} -gt 0 ]; then
        echo "  失败: ${FAILED[*]}"
    fi
    echo "  日志: $LOG_FILE"
    echo "  数据: $DATA_DIR/"
    echo "========================================"
}

# ── 转换数据并训练 ───────────────────────────
train() {
    echo "=== 转换数据（长表 → 宽表 + 标签）==="
    cd "$SCRIPT_DIR"
    PYTHONPATH=".;./tfsnippet_repo;./zhusuan" conda run -n omnianomaly python convert_collected_data.py
    if [ $? -ne 0 ]; then
        echo "转换失败，请检查错误信息"
        return 1
    fi

    echo "=== 训练 OmniAnomaly ==="
    rm -rf model result
    PYTHONPATH=".;./tfsnippet_repo;./zhusuan" conda run -n omnianomaly python main.py

    echo "=== 结果 ==="
    if [ -f result/result.json ]; then
        cat result/result.json
    else
        echo "训练未产生结果文件"
    fi
}

# ── 状态检查 ─────────────────────────────────
status() {
    echo "=== 集群状态 ==="
    kubectl get pods -n $NS 2>/dev/null || echo "  集群不可达"
    echo ""
    echo "=== Prometheus ($PROMETHEUS_URL) ==="
    curl -s "$PROMETHEUS_URL/api/v1/query?query=up" 2>/dev/null | head -c 200 || echo "  不可达 - 请先启动端口转发:"
    echo "    kubectl port-forward -n $PROMETHEUS_NS svc/monitoring-kube-prometheus-prometheus $PROMETHEUS_PORT:9090"
    echo ""
    echo "=== 数据文件 ==="
    ls -la "$DATA_DIR/"*.csv 2>/dev/null || echo "  (暂无采集数据)"
    echo ""
    echo "=== 实验日志 ($LOG_FILE) ==="
    if [ -f "$LOG_FILE" ]; then
        tail -20 "$LOG_FILE"
    else
        echo "  (暂无)"
    fi
}

# ── 入口 ─────────────────────────────────────
case "${1:-}" in
    start)          start ;;
    stop)           minikube stop ;;
    status)         status ;;
    collect-normal) collect_normal "${2:-360}" ;;
    fault)          run_fault "${2:-cpu}" "${3:-frontend}" ;;
    all-faults)     run_all_faults ;;
    train)          train ;;
    *)
        echo "用法: bash collect_data.sh <命令>"
        echo ""
        echo "  start              启动 Minikube + Boutique + loadgenerator"
        echo "  status             查看集群/数据/日志状态"
        echo "  collect-normal [分] 采集正常训练数据（默认 360 分钟=6小时）"
        echo "  fault <类型> <服务>  运行单个故障实验（自动采集+注入）"
        echo "    类型: cpu | delay | kill"
        echo "    服务: frontend | cartservice | productcatalogservice | ..."
        echo "  all-faults         运行全部 9 组故障实验（约 2 小时）"
        echo "  train              转换数据 + 训练 OmniAnomaly"
        echo "  stop               停止集群"
        ;;
esac
