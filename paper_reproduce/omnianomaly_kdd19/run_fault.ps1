# ============================================================
# Online Boutique 故障注入脚本 (PowerShell 版)
# 用法:
#   .\run_fault.ps1 -Type cpu -Service frontend
#   .\run_fault.ps1 -Type delay -Service cartservice
#   .\run_fault.ps1 -Type kill -Service productcatalogservice
#   .\run_fault.ps1 -All     # 运行全部 9 组实验
# ============================================================

param(
    [ValidateSet("cpu","delay","kill")]
    [string]$Type = "cpu",
    [string]$Service = "frontend",
    [switch]$All
)

$NS = "boutique"
$CHAOS_NS = "chaos-testing"
$PROMETHEUS_URL = "http://localhost:19090"
$DATA_DIR = "$PSScriptRoot\data"
$LOG_FILE = "$DATA_DIR\experiment_log.txt"
$INTERVAL = 30
$COLLECT_SCRIPT = "$PSScriptRoot\boutique__data\collect_metrics.py"

# 确保数据目录存在
New-Item -ItemType Directory -Force -Path $DATA_DIR | Out-Null

function Run-SingleFault {
    param($FaultType, $TargetSvc)

    $Name = "fault_${FaultType}_${TargetSvc}"
    $Output = "$DATA_DIR\${Name}.csv"
    $YamlFile = "$DATA_DIR\.chaos_${Name}.yaml"

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  故障实验: $Name" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    # 1. 启动后台采集 (9 分钟 = 2基线 + 5故障 + 2恢复)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 启动采集..."
    $collectJob = Start-Job -ScriptBlock {
        param($script, $output, $url, $interval)
        python $script --mode live --duration 9 --interval $interval `
            --metrics cpu_rate memory_working_set `
            --output $output --prometheus-url $url 2>&1
    } -ArgumentList $COLLECT_SCRIPT, $Output, $PROMETHEUS_URL, $INTERVAL

    Start-Sleep -Seconds 5

    # 2. 基线采集 2 分钟
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 采集正常基线 (2min)..."
    Start-Sleep -Seconds 115

    # 3. 注入故障
    $FaultStart = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 注入故障: $FaultType -> $TargetSvc" -ForegroundColor Yellow

    switch ($FaultType) {
        "cpu" {
            @"
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: $Name
  namespace: $CHAOS_NS
spec:
  mode: one
  selector:
    namespaces: [$NS]
    labelSelectors: {app: $TargetSvc}
  stressors:
    cpu: {workers: 2, load: 80}
  duration: "5m"
"@ | Set-Content $YamlFile
        }
        "delay" {
            @"
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: $Name
  namespace: $CHAOS_NS
spec:
  action: delay
  mode: one
  selector:
    namespaces: [$NS]
    labelSelectors: {app: $TargetSvc}
  delay: {latency: "500ms", jitter: "100ms"}
  duration: "5m"
"@ | Set-Content $YamlFile
        }
        "kill" {
            @"
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: $Name
  namespace: $CHAOS_NS
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces: [$NS]
    labelSelectors: {app: $TargetSvc}
  duration: "5m"
"@ | Set-Content $YamlFile
        }
    }

    kubectl apply -f $YamlFile

    # 4. 故障持续 5 分钟
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 故障进行中 (5min)..."
    Start-Sleep -Seconds 300

    $FaultEnd = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    kubectl delete -f $YamlFile 2>$null
    Remove-Item $YamlFile -Force -ErrorAction SilentlyContinue

    # 5. 恢复期 2 分钟
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 恢复期 (2min)..."
    Start-Sleep -Seconds 120

    # 6. 等待采集自动结束
    $CollectEnd = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Wait-Job $collectJob | Out-Null
    Remove-Job $collectJob

    # 7. 记录日志
    Add-Content $LOG_FILE ""
    Add-Content $LOG_FILE "## $Name"
    Add-Content $LOG_FILE "- 故障开始: $FaultStart"
    Add-Content $LOG_FILE "- 故障结束: $FaultEnd"
    Add-Content $LOG_FILE "- 采集结束: $CollectEnd"
    Add-Content $LOG_FILE "- 文件: data/${Name}.csv"

    $lines = (Get-Content $Output -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
    Write-Host "  采集完成: $lines 行 -> $Output" -ForegroundColor Green

    # 8. 冷却 5 分钟
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 冷却 5 分钟..."
    Start-Sleep -Seconds 300
}

# ── 入口 ─────────────────────────────────────

if ($All) {
    Write-Host "=== 开始故障实验矩阵 (9 组, 预计 ~2 小时) ===" -ForegroundColor Cyan

    $services = @("frontend", "cartservice", "productcatalogservice")
    $failed = @()
    $total = 0
    $success = 0

    foreach ($svc in $services) {
        foreach ($type in @("cpu", "delay", "kill")) {
            $total++
            try {
                Run-SingleFault -FaultType $type -TargetSvc $svc
                $success++
                Write-Host "  [$success/$total] ✓ $type-$svc 完成" -ForegroundColor Green
            } catch {
                $failed += "$type-$svc"
                Write-Host "  [$success/$total] ✗ $type-$svc 失败" -ForegroundColor Red
            }
        }
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  全部故障实验结束" -ForegroundColor Cyan
    Write-Host "  成功: $success / $total" -ForegroundColor Green
    if ($failed.Count -gt 0) {
        Write-Host "  失败: $failed" -ForegroundColor Red
    }
    Write-Host "  日志: $LOG_FILE"
    Write-Host "  数据: $DATA_DIR\"
    Write-Host "========================================" -ForegroundColor Cyan

} else {
    Run-SingleFault -FaultType $Type -TargetSvc $Service
}
