# OmniAnomaly 论文复现实验报告

> **论文**：OmniAnomaly: Robust Anomaly Detection for Multivariate Time Series (KDD 2019)
> **复现场景**：Online Boutique 微服务系统（11 微服务，Kubernetes + Prometheus + ChaosMesh）
> **复现人**：tamotasmash
> **分支**：`release/v0.10.2`

---

## 1. 实验目标

在 Online Boutique 微服务系统上复现 OmniAnomaly（KDD 2019）异常检测算法，验证其在 Kubernetes 容器监控场景下对 **CPU 压力**、**网络延迟**、**Pod Kill** 三类故障的检测能力，并通过 9 组对照实验探索特征选择、数据质量和超参数对检测效果的影响。

---

## 2. 算法原理

OmniAnomaly 是一种基于随机递归神经网络（Stochastic RNN）和变分自编码器（VAE）的多元时间序列异常检测算法。其核心架构包括：

### 2.1 编码器-解码器框架

```
输入 x_t (22维指标)
  → GRU 编码 (rnn_num_hidden=128)
  → VAE 隐变量 z_t (z_dim=6)
  → Planar Normalizing Flow (nf_layers=10) 增强后验表达能力
  → GRU 解码
  → 重建 x'_t (22维)
```

### 2.2 核心组件

| 组件 | 作用 | 本实验配置 |
|------|------|:---:|
| **GRU RNN** | 对时间窗口内序列建模，捕捉时序依赖 | `rnn_num_hidden=128` |
| **VAE (Variational Autoencoder)** | 学习隐空间表示，用重建概率而非重建误差做异常检测 | `z_dim=6` |
| **Planar Normalizing Flow** | 增强 VAE 后验分布的灵活性，更好拟合复杂分布 | `nf_layers=10` |
| **Linear Gaussian State Space Model** | 对隐变量 `z` 的时间结构建模（`use_connected_z_q/p=True`） | 启用 |
| **Dense 解码层** | 从隐变量 `z` 重建原始指标 | `dense_dim=256` |

### 2.3 异常判定

1. **训练**：模型在 100% 纯净的正常数据上学习正常行为模式
2. **打分**：对测试数据计算每个时间点的**重建概率分数**（reconstruction probability score）
3. **阈值**：
   - **POT（Peaks Over Threshold）**：用极值理论自动确定阈值（仅在足够大的训练集上有效）
   - **Best-F1 搜索**：在 [-400, 400] 范围内以步长 1 搜索使 F1 最大化的阈值

---

## 3. 实验环境

| 组件 | 配置 |
|------|------|
| 操作系统 | Windows 10 |
| Kubernetes | Minikube（CPU=4, Memory=8192MB） |
| 微服务 | Online Boutique 11 个微服务（namespace: `boutique`） |
| 负载生成 | Locust (`loadgenerator`)，持续模拟用户购物流程 |
| 监控 | Prometheus（namespace: `monitoring`，端口转发 `19090:9090`） |
| 故障注入 | ChaosMesh（namespace: `chaos-testing`） |
| Python 环境 | conda env `omnianomaly`（Python 3.6, TensorFlow 1.12.0） |
| 依赖库 | tfsnippet, zhusuan（本地副本，非 git 安装） |

---

## 4. 数据采集

### 4.1 两种数据来源

| 数据源 | 实验使用 | 说明 |
|--------|:---:|------|
| **GDN 预处数据** | #6 | 使用 GDN 实验采集的 CSV（`experiment/GDN/data/`），由 `gdn_data/convert_to_omnianomaly.py` 转换 |
| **真实采集数据** | #1-#5, #7-#9 | 通过 `boutique__data/collect_metrics.py` 从 Prometheus 直接导出 |

### 4.2 真实采集管线

#### 第一步：正常数据采集（~6 小时）

```powershell
cd boutique__data
python collect_metrics.py --mode live --duration 360 --interval 30 `
    --metrics cpu_rate memory_working_set `
    --output ..\data\normal_train.csv --prometheus-url http://localhost:19090
```

输出格式（长表）：
```
metric,node,pod,namespace,container,timestamp,value
cpu_rate,minikube,frontend-xxx,boutique,,1780395480,0.00056
memory_working_set,minikube,frontend-xxx,boutique,,1780395480,5132288
```

#### 第二步：故障注入（9 组，~2 小时）

```powershell
.\run_fault.ps1 -All
```

每组实验自动完成：`后台采集启动 → 2 分钟基线 → 注入 ChaosMesh 故障 → 5 分钟故障 → 清理故障 → 2 分钟恢复 → 采集自动停止 → 记录时间窗口 → 5 分钟冷却`

**实验矩阵（3 故障类型 × 3 服务）**：

| 故障类型 | ChaosMesh 资源 | 目标服务 | 参数 |
|----------|---------------|----------|------|
| CPU Stress | StressChaos | frontend, cartservice, productcatalogservice | 2 核, 80% 负载 |
| Network Delay | NetworkChaos | frontend, cartservice, productcatalogservice | 500ms 延迟 + 100ms 抖动 |
| Pod Kill | PodChaos | frontend, cartservice, productcatalogservice | `pod-kill` action |

#### 第三步：数据转换

```powershell
conda activate omnianomaly
python convert_collected_data.py
```

`convert_collected_data.py` 自动完成：
1. 过滤 `boutique` namespace
2. Pod 名 → 服务名聚合（如 `frontend-abc-def` → `frontend`）
3. 长表 pivot → 宽表（22 列：11 服务 × cpu/mem）
4. 解析 `experiment_log.txt` 生成异常标签（故障段 + 2 分钟恢复期 = `attack=1`）
5. 划分训练/测试集，输出到 `processed/boutique_*.pkl`

**采集过程中修复的 3 个 bug**：
1. **CSV 无表头**：`collect_metrics.py` 输出的 CSV 无 header row，需用 `header=None, names=[...]` 读取
2. **时间戳类型**：pivot 后 index 为 Unix 时间戳（int），`pd.to_datetime()` 需指定 `unit='s'`
3. **时区不匹配**：`experiment_log.txt` 记录 CST 本地时间，Prometheus 时间戳为 UTC，差 8 小时导致标签全为 0；修复为直接数值比较

### 4.3 核心原则（来自 9 组实验教训）

| 原则 | 说明 | 违反后果 |
|------|------|----------|
| **训练集 100% 正常数据** | 正常采集和故障注入不能同时进行 | 训练数据被污染，模型无法学到正常基线 |
| **单服务故障** | 每次只注入一个服务故障 | 多服务同时故障导致连锁反应，模型区分不了正常/异常 |
| **精确时间标签** | 故障起止时间记录到秒级 | 标签错误直接污染评估结果 |
| **精选低维特征** | 仅用 11 服务 × cpu/mem = 22 维 | 494 维原始数据 F1=0.112，22 维精选 F1=0.968 |
| **足够长的训练集** | 正常期 ≥ 2 小时 | 61 行训练数据极易过拟合 |

---

## 5. 实验设计与结果

### 5.1 9 组实验总览

| # | 名称 | F1 | Precision | Recall | TP/FP/TN/FN | 特征维度 | 训练行数 | 关键变量 |
|---|------|:---:|:---:|:---:|:---:|:---:|:---:|---------|
| 1 | Baseline | 0.112 | 5.9% | 100% | 82/1298/0/0 | 494 | 3,223 | 默认参数, 全命名空间 |
| 2 | 降维 | 0.109 | 5.8% | 100% | 82/1338/25/0 | 234 | 3,220 | 仅 boutique 命名空间 |
| 3 | 强故障(短) | 0.553 | 38.3% | 100% | 44/71/0/0 | 234 | 201 | 2 核 CPU + 512MB |
| 4 | 服务聚合 | 0.496 | 33.0% | 100% | 539/1095/0/0 | 156 | 674 | Pod 聚合去重 |
| **5** | **精简特征** | **0.589** | **45.7%** | **83.2%** | **448/533/562/91** | **36** | **674** | ★ 首次出现 TN |
| **6** | **GDN 数据训练** | **0.968** | **93.7%** | **100%** | **45/3/26/0** | **22** | **61** | ★ 人造理想数据 |
| 7 | 降维优化 | 0.487 | 32.4% | 98.5% | 531/1110/280/8 | 36 | 379 | 方差过滤 663→36 |
| 8 | 去噪 | 0.472 | 30.9% | 100% | 539/1205/185/0 | 54 | 379 | 仅 boutique cpu/mem |
| **9** | **新管线+调参** | **0.786** | **70.4%** | **89.1%** | **114/48/137/14** | **22** | **637** | ★ 真实采集数据最佳 |

### 5.2 实验分阶段解读


  │
  ├─ 故障强度 ↑ → 实验 #3 (F1=0.553, +392%)
  │
  ├─ 特征精选 → 实验 #5 (F1=0.589, +6%)
  │    └─ 首次出现 TN，模型开始判别
  │
  ├─ 换成 GDN 理想数据 → 实验 #6 (F1=0.968, +64%)
  │    └─ 数据源决定天花板
  │
  └─ 重新采集 + 调参 → 实验 #9 (F9 组实验按优化方向可分为三个阶段：

#### 阶段一：特征探索（#1–#5）

实验从 494 维全量指标起步（所有命名空间、所有 Prometheus 指标），F1 仅 0.112，模型几乎将全部正常点误判为异常（FP=1298）。简单按命名空间过滤（#2, 234 维）没有改善。

第一个关键转折出现在 **#3（F1=0.553）**：将故障强度提高至 2 核 CPU + 512MB 内存压力后，F1 提升了 5 倍，证明**故障强度比特征工程更重要**。

第二个关键转折在 **#5（F1=0.589）**：人工精选 36 维高方差特征后，**首次出现 TN=562**——模型开始学会区分正常和异常，不再对所有时间点无差别报警。

#### 阶段二：数据源验证（#6–#8）

**#6（F1=0.968）** 改用 GDN 实验的设计数据集（22 维、61 行训练、78 行测试、3 段清晰故障），达到所有实验的绝对值最佳。与 GDN 轻量复现（F1=0.917）相比，OmniAnomaly 的 Precision 提升约 9 个百分点（93.7% vs 84.6%）。但该数据集为实验设计数据（正常段几乎无波动、故障信号瞬时强），不代表真实场景。

**#7（F1=0.487）** 和 **#8（F1=0.472）** 回到实验 #4 的原始数据（115 个同时故障事件），分别尝试方差过滤降维（663→36 维）和语义去噪（仅 boutique cpu/mem，54 维）。方差过滤优于语义去噪（+3% F1），但两者均止步于 F1≈0.48——因为数据源本身质量（多故障同时、正常段过短）是根本瓶颈。

#### 阶段三：重新采集 + 调参（#9, F1=0.786）

基于前 8 组教训，全新采集 6 小时正常数据（637 有效行 × 22 维）+ 9 组单服务故障，进行 9 轮网格调参。窗口长度 w30 达最佳 F1=0.786，w5（复刻 #6 配置）仅得 0.600——真实信号需要大窗口捕捉累积偏差。**POT 算法在 637 行小样本上完全失效**（level=0.01 时 TP=0），最终 F1 依赖 Best-F1 搜索确定阈值。

---

## 6. 9 组实验渐进优化路径

```
实验 #1 (F1=0.112)
  │ 全量指标+全命名空间 → 无法区分1=0.786)
       └─ 真实场景下最终结果
```

---

## 7. 核心结论

### 7.1 算法复现结论

OmniAnomaly 在 Online Boutique 微服务监控场景中成功复现。关键发现：

1. **数据质量 > 模型调参 > 特征工程**：从实验 #1 到 #9，最大的三次 F1 跳升分别来自：
   - 增强故障强度（#1→#3：0.112→0.553，+392%）
   - 换用高质量数据（#5→#6：0.589→0.968，+64%）
   - 真实数据 + 精心调参（→#9：0.786）

2. **真实场景 F1=0.786** 是人造理想数据（F1=0.968）和真实生产数据的合理差距，根本原因在于**信号噪声比**：GDN 数据集是实验设计数据，正常段"无波动"；真实采集数据含自然业务流量波动。

3. **特征维度与 F1 呈反比**：494 维（F1=0.112）→ 36 维（F1=0.589）→ 22 维（F1=0.968/0.786）。每一轮降维都带来改善，但**人工精选 22 维远超自动筛选 36-54 维**。

4. **POT 算法不可靠**：在 ≤ 637 行的小样本上，POT 几乎完全失效（level 调优极其困难，稍小则 TP=0，稍大则 FP 爆炸）。

5. **窗口长度 30 为最优点**：w5（F1=0.600）、w10（0.616）、w20（0.643）、w30（0.786）、w40（0.762）——窗口长度的选择取决于数据的信号特性，需通过网格搜索确定。

### 7.2 局限性

| 局限 | 说明 |
|------|------|
| **训练集规模** | 最大仅 637 行（~6 小时），远少于论文数万条样本；模型收敛不稳定（±0.1 F1 波动） |
| **特征维度** | 仅 cpu/mem 两类指标（22 维），缺少网络、磁盘 I/O、应用级指标 |
| **故障类型** | 仅 CPU Stress、Network Delay、Pod Kill 三种；未涵盖内存泄漏、磁盘 I/O 饱和等 |
| **单故障假设** | 每次仅注入一个服务故障；多服务同时故障的场景未覆盖 |
| **POT 失效** | 小样本上完全无法使用；所有报告的 F1 依赖 Best-F1 搜索（需要真实标签） |
| **TF 1.x 依赖** | 训练环境依赖 TensorFlow 1.12.0（EOL），迁移和维护成本较高 |

### 7.3 后续工作方向        

1. **延长训练集**：正常数据采集 12-24 小时，目标 ≥ 3000 行
2. **扩展指标**：接入 cAdvisor 网络指标（`container_network_receive_bytes_total` 等）、磁盘 I/O、应用级 QPS/延迟
3. **丰富故障类型**：内存泄漏、磁盘 I/O 饱和、级联故障
4. **模型升级**：迁移至 TensorFlow 2.x / PyTorch 版本，降低维护成本
5. **与 aiopsagent 集成**：通过 `aiops_agent/detectors/paper_adapter.py` 将训练好的模型接入 LangGraph 管道

---

## A. 附录：关键命令速查

### 环境搭建

```bash
# Minikube
minikube start --cpus=4 --memory=8192

# Prometheus 端口转发（保持终端打开）
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 19090:9090

# ChaosMesh
helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-testing --create-namespace

# 部署微服务
skaffold run
```

### 数据采集（PowerShell，非 bash）

```powershell
# 正常数据采集（6 小时）
cd boutique__data
python collect_metrics.py --mode live --duration 360 --interval 30 `
    --metrics cpu_rate memory_working_set `
    --output ..\data\normal_train.csv --prometheus-url http://localhost:19090

# 故障注入（9 组）
cd ..
.\run_fault.ps1 -All

# 或单组测试
.\run_fault.ps1 -Type cpu -Service frontend
```

### 训练与评估

```powershell
# 数据转换
conda activate omnianomaly
python convert_collected_data.py

# 清理旧模型
Remove-Item -Recurse -Force model, result -ErrorAction SilentlyContinue

# 训练
$env:PYTHONPATH = ".;./tfsnippet_repo;./zhusuan"
python main.py

# 查看结果
Get-Content result\result.json
```

### 关键超参数（在 main.py 中修改）

```python
# 实验 #6 配置（GDN 数据，F1=0.968）
window_length = 5
batch_size = 16
z_dim = 3
rnn_num_hidden = 64
dense_dim = 128
nf_layers = 5
max_epoch = 100

# 实验 #9 配置（真实数据，F1=0.786）
window_length = 30
batch_size = 50
z_dim = 6
rnn_num_hidden = 128
dense_dim = 256
nf_layers = 10
max_epoch = 150
```

---

## B. 附录：数据文件清单

```
paper_reproduce/omnianomaly_kdd19/
├── main.py                         # 训练入口
├── convert_collected_data.py       # 数据转换（长表→宽表+标签）
├── collect_data.sh                 # bash 自动化脚本
├── run_fault.ps1                   # PowerShell 故障注入脚本
├── DATA_COLLECTION_GUIDE.md        # 数据采集方案文档
├── omni_anomaly/                   # OmniAnomaly 核心算法
│   ├── model.py                    # VAE + NF + LGSSM 模型
│   ├── training.py                 # 训练循环
│   ├── prediction.py               # 异常分数计算
│   ├── eval_methods.py             # POT + Best-F1 评估
│   └── vae.py                      # VAE 基础组件
├── tfsnippet_repo/                 # tfsnippet 本地副本
├── zhusuan/                        # zhusuan 本地副本
├── data/                           # 已采集数据
│   ├── normal_train.csv            # 6 小时正常数据
│   └── fault_*.csv                 # 9 组故障数据
├── processed/                      # 预处理后数据（.pkl）
├── model/                          # 训练好的模型
├── result/                         # 评估结果
│   └── result.json
└── experiment_backups/             # 9 组实验备份
    ├── EXPERIMENT_LOG.md           # 完整实验记录
    ├── exp_v1_window20/ ~ exp_v7_window30_lr/
    ├── exp6_gdn_data/
    ├── exp7_dimreduce_optimized/
    ├── exp8_denoised/
    └── exp9_new_pipeline/
```
