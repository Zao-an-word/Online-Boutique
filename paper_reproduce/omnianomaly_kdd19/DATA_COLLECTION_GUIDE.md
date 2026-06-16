# Online Boutique + OmniAnomaly 数据采集方案（PowerShell 版）

基于 8 组对照实验的经验教训：GDN 数据集（F1=0.968）vs 原始混沌工程数据（F1≤0.487）。

**⚠️ 所有命令在 PowerShell 中执行，不要用 Git Bash/WSL bash。**（bash 无法访问 Anaconda Python 和 localhost 端口转发。）

## 核心原则

| 原则 | 说明 | 证据 |
|------|------|------|
| 正常数据训练 | 训练集必须 100% 正常 | 论文要求 + 实验验证 |
| 单服务故障 | 每次只注入一个服务，避免连锁影响 | 115 个故障事件 → 无法区分 |
| 精确时间标签 | 记录故障开始/结束到秒级 | POT 算法依赖精确标签 |
| 只采集有效特征 | 11 服务 × cpu/mem = 22 维 | 54 维自动筛选 F1=0.47 vs 22 维精选 F1=0.97 |
| 足够长时间 | 正常期 ≥ 2 小时（推荐 6 小时），故障期 5-10 分钟/次 | 61 行太短，模型易过拟合 |
| **先后顺序** | **正常采集和故障注入不能同时跑** | 训练数据被污染会导致模型学不到正常基线 |

---

## 前置条件

在 PowerShell 中确认：

```powershell
# 1. Kubernetes 集群 + Online Boutique 已部署
kubectl get pods -n boutique

# 2. Prometheus 端口转发（保持此终端开着）
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 19090:9090

# 3. ChaosMesh 已部署
kubectl get pods -n chaos-testing

# 4. loadgenerator 运行中（产生正常流量）
kubectl get pods -n boutique -l app=loadgenerator

# 5. Python 环境（Anaconda base 或 omnianomaly 均可）
python -c "import requests, pandas; print('OK')"
```

---

## 第一步：采集正常训练数据（6 小时）

### 1.1 确认系统处于正常状态

```powershell
# 确认所有 Pod Running
kubectl get pods -n boutique | Select-String -Pattern "Running" -NotMatch

# 确认 loadgenerator 在产生流量
kubectl get pods -n boutique -l app=loadgenerator
```

### 1.2 启动采集

```powershell
cd D:\online-boutique-temp\paper_reproduce\omnianomaly_kdd19\boutique__data

python collect_metrics.py `
    --mode live `
    --duration 360 `
    --interval 30 `
    --metrics cpu_rate memory_working_set `
    --output ..\data\normal_train.csv `
    --prometheus-url http://localhost:19090
```

**参数说明：**
- `--duration 360`：采集 360 分钟 = 6 小时
- `--interval 30`：每 30 秒采样一次（6 小时 ≈ 720 行）
- `--metrics cpu_rate memory_working_set`：只采集 CPU 和内存（11 服务 × 2 = 22 维）
- 如需快速测试，将 `--duration 360` 改为 `--duration 120`（2 小时）

### 1.3 验证训练数据

```powershell
python -c "
import pandas as pd
df = pd.read_csv('../data/normal_train.csv')
print(f'行数: {len(df)} (建议≥240)')
print(f'唯一指标: {df[\"metric\"].nunique()}')
print(f'唯一 Pod: {df[\"pod\"].nunique()}')
"
```

**质量标准**: ≥240 行（2 小时），指标仅含 `cpu_rate` + `memory_working_set`，只含 `boutique` namespace。

---

## 第二步：故障注入 + 测试数据采集（~2 小时）

**⚠️ 必须在第一步完成后再执行。**

### 2.1 一键运行全部 9 组实验

```powershell
cd D:\online-boutique-temp\paper_reproduce\omnianomaly_kdd19
.\run_fault.ps1 -All
```

### 2.2 单组实验（测试用）

```powershell
.\run_fault.ps1 -Type cpu -Service frontend
.\run_fault.ps1 -Type delay -Service cartservice
.\run_fault.ps1 -Type kill -Service productcatalogservice
```

### 2.3 每组实验自动完成以下流程

```
后台采集启动 → 2分钟基线 → 注入 ChaosMesh 故障 → 5分钟故障
→ 清理故障 → 2分钟恢复 → 采集自动停止 → 记录时间窗口 → 5分钟冷却
```

### 2.4 实验矩阵

| 故障类型 | 目标服务 |
|----------|---------|
| CPU Stress (2核, 80%) | frontend, cartservice, productcatalogservice |
| Network Delay (500ms) | frontend, cartservice, productcatalogservice |
| Pod Kill | frontend, cartservice, productcatalogservice |

### 2.5 验证故障注入结果

```powershell
# 查看实验日志
Get-Content data\experiment_log.txt

# 查看故障数据文件
Get-ChildItem data\fault_*.csv | Select-Object Name, Length
```

---

## 第三步：转换数据 + 训练

### 3.1 转换（长表 → 宽表 + 标签）

```powershell
cd D:\online-boutique-temp\paper_reproduce\omnianomaly_kdd19
conda activate omnianomaly
python convert_collected_data.py
```

`convert_collected_data.py` 自动完成：
1. 过滤 `boutique` namespace
2. Pod 名 → 服务名聚合（如 `frontend-xxx-yyy` → `frontend`）
3. 长表 pivot → 宽表（22 列）
4. 解析 `experiment_log.txt` 生成异常标签
5. 划分训练/测试集，输出到 `processed/`

### 3.2 训练 OmniAnomaly

```powershell
Remove-Item -Recurse -Force model, result -ErrorAction SilentlyContinue
$env:PYTHONPATH = ".;./tfsnippet_repo;./zhusuan"
python main.py
```

根据 `convert_collected_data.py` 输出的参数建议，修改 `main.py` 中的 `window_length` 和 `batch_size`。

### 3.3 查看结果

```powershell
Get-Content result\result.json
```

---

## 数据格式说明

### 采集输出（长表格式）

`collect_metrics.py` 输出：
```
metric,node,pod,namespace,container,timestamp,value
cpu_rate,minikube,frontend-xxx,boutique,,1780395480,0.00056
memory_working_set,minikube,frontend-xxx,boutique,,1780395480,5132288
```

### 转换后（OmniAnomaly 输入）

`convert_collected_data.py` 输出 `processed/boutique_*.pkl`：
- 训练: (n_train, 22) float32
- 测试: (n_test, 22) float32（正常验证段 + 故障段拼接）
- 标签: (n_test,) bool（0=正常, 1=异常）
- 22 列: `frontend_cpu, frontend_mem, cartservice_cpu, cartservice_mem, ...`

---

## 质量检查清单

| 检查项 | 标准 | 方法 |
|--------|------|------|
| 训练集纯净 | 0 个异常点 | 确认采集时无故障 |
| 训练集长度 | ≥ 240 行 | `(Get-Content data\normal_train.csv).Count` |
| 采集指标数 | = 2（cpu_rate + memory_working_set） | `python -c "import pandas; df=pandas.read_csv('data/normal_train.csv'); print(df['metric'].unique())"` |
| 故障日志 | 每个故障有时间窗口 | `Get-Content data\experiment_log.txt` |
| 故障数据文件 | = 9 个（或 1 个如只测单组） | `(Get-ChildItem data\fault_*.csv).Count` |
| 转换后维度 | = 22 | `Get-Content processed\boutique_dim.txt` |

---

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: pandas` | 用了 bash 里的 WSL Python | 用 PowerShell 直接 `python`，不要经过 `bash` |
| `Connection refused` | Prometheus 端口转发未启动 | `kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 19090:9090` |
| 采集 0 条数据 | `--metrics` 参数格式错误 | 确保是空格分隔：`--metrics cpu_rate memory_working_set` |
| ChaosMesh 资源未找到 | YAML namespace 不对 | ChaosMesh 资源在 `chaos-testing`，selector 指向 `boutique` |
