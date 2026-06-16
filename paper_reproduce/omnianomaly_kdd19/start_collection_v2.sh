#!/bin/bash
# ================================================================
# start_collection.sh — 一键启动 Prometheus 端口转发 + K8s 指标采集
#
# 用法:
#   ./start_collection.sh                    # 默认: 持续采集直到 Ctrl+C
#   ./start_collection.sh --hours 24         # 采集 24 小时后自动停止
#   ./start_collection.sh --hours 48 --interval 10  # 每10秒采样，持续48小时
#   ./start_collection.sh --mode backfill --hours 6  # 回填过去6小时
# ================================================================

set -e

# ---- 可配置参数 ----
PROMETHEUS_NS="${PROMETHEUS_NS:-monitoring}"
PROMETHEUS_SVC="${PROMETHEUS_SVC:-monitoring-kube-prometheus-prometheus}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
LOCAL_PORT="${LOCAL_PORT:-19090}"
DURATION_HOURS="${DURATION_HOURS:-}"
INTERVAL="${INTERVAL:-30}"
OUTPUT_FILE="${OUTPUT_FILE:-../data/normal_train.csv}"

# ---- 颜色输出 ----
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---- 获取脚本所在目录 ----
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATA_DIR="${SCRIPT_DIR}/boutique__data"

# ---- 1. 检查前置条件 ----
info "========== 检查环境 =========="

# minikube/kubectl 在 Windows 侧运行，WSL 内无法直接调用，跳过
info "minikube/kubectl: 跳过 (Windows 侧已运行)"

# 把 Anaconda 加入 PATH（解决 PowerShell→bash 时 PATH 不完整）
[ -d "/d/Anaconda" ] && export PATH="/d/Anaconda:/d/Anaconda/Scripts:$PATH"

# 检查 Python
PYTHON=$(which python 2>/dev/null || which python3 2>/dev/null)
if [ -z "$PYTHON" ]; then
    error "Python 未找到"
    exit 1
fi
info "Python: $PYTHON"

# ---- 2. 检查 Prometheus 连通性 ----
info ""
info "========== 检查 Prometheus =========="

if curl -s "http://localhost:${LOCAL_PORT}/api/v1/query?query=up" 2>/dev/null | grep -q success; then
    info "Prometheus 端口 ${LOCAL_PORT} 已可访问 ✓"
else
    error "Prometheus 端口 ${LOCAL_PORT} 不可达"
    error "请在另一个终端运行: kubectl port-forward -n ${PROMETHEUS_NS} svc/${PROMETHEUS_SVC} ${LOCAL_PORT}:${PROMETHEUS_PORT}"
    exit 1
fi

# ---- 3. 启动数据采集 ----
info ""
info "========== 启动数据采集 =========="
info "输出文件: ${DATA_DIR}/${OUTPUT_FILE}"

cd "$DATA_DIR"

# 构建采集命令
COLLECT_ARGS="--mode live --interval ${INTERVAL} --output ${OUTPUT_FILE} --prometheus-url http://localhost:${LOCAL_PORT} --metrics cpu_rate memory_working_set"
if [ -n "$DURATION_HOURS" ]; then
    DURATION_MIN=$((DURATION_HOURS * 60))
    COLLECT_ARGS="${COLLECT_ARGS} --duration ${DURATION_MIN}"
    info "模式: 实时采集, 持续 ${DURATION_HOURS} 小时, 间隔 ${INTERVAL}s"
else
    info "模式: 实时采集, 间隔 ${INTERVAL}s, 按 Ctrl+C 停止"
fi

info ""
info "=============================================="
info "  采集进行中..."
info "  按 Ctrl+C 安全停止 (数据已增量保存)"
info "=============================================="
echo ""

# 开始采集
$PYTHON collect_metrics.py $COLLECT_ARGS
EXIT_CODE=$?

# ---- 4. 完成 ----
info ""
if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 130 ]; then
    info "========== 采集结束 =========="

    # 显示采集结果
    if [ -f "$OUTPUT_FILE" ]; then
        ROWS=$(wc -l < "$OUTPUT_FILE")
        SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
        info "输出文件: ${DATA_DIR}/${OUTPUT_FILE}"
        info "数据行数: $((ROWS - 1))"
        info "文件大小: ${SIZE}"

        META="${OUTPUT_FILE%.csv}_metadata.json"
        if [ -f "$META" ]; then
            info "元数据:   ${DATA_DIR}/${META}"
        fi
    fi

    info ""
    info "下一步: 运行预处理"
    info "  cd ${SCRIPT_DIR}"
    info "  python boutique_preprocess.py --csv boutique__data/${OUTPUT_FILE}"
else
    error "采集异常退出 (code: $EXIT_CODE)"
fi

# 采集完成
if [ -n "$PF_PID" ]; then
    info "关闭端口转发 (PID: $PF_PID)..."
    kill $PF_PID 2>/dev/null || true
fi

exit $EXIT_CODE
