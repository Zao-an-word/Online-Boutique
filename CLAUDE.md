# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

本项目 fork 自 Google Cloud 的 [Online Boutique (microservices-demo)](https://github.com/GoogleCloudPlatform/microservices-demo)，是一个基于 gRPC 的云原生微服务演示应用（11 个标准微服务）。在此基础上新增了 AIOps 智能运维 Agent、集群监控服务和论文复现实验代码。当前分支 `release/v0.10.2`。

## 环境搭建速查

大部分实验和开发工作依赖以下基础设施，按需启动：

```bash
# MiniKube 集群（如使用 minikube）
minikube start --cpus=4 --memory=8192

# Prometheus 端口转发（几乎所有实验的前置条件）
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 19090:9090

# ChaosMesh 部署（故障注入实验需要）
# 安装: helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-testing --create-namespace
# 验证: kubectl get pods -n chaos-testing
```

## 构建与运行

### 本地开发（推荐使用 Skaffold）

```bash
# 前置条件：Docker Desktop + Kubernetes 集群 (minikube/kind/docker-desktop)
# 一次构建所有镜像并部署到集群
skaffold run

# 开发模式（代码变更自动重新构建）
skaffold dev

# 清理
skaffold delete

# 使用 GCP Cloud Build 构建（不需要本地 Docker）
skaffold run -p gcb --default-repo=<YOUR_AR_REPO>

# 仅构建单个服务的镜像（不部署）
skaffold build --build-image=aiopsagent
```

**Skaffold 结构说明**：`skaffold.yaml` 包含两个独立的 Config — `app`（11 个微服务 + aiopsagent + shoppingassistantservice）和 `loadgenerator`（压测服务，通过 `requires` 依赖 `app`）。loadgenerator 不在 kustomization.yaml 中（被注释掉），由 Skaffold 单独管理其部署。

**可用 Profile**：
- `gcb`：通过 Google Cloud Build 构建，不需本地 Docker
- `debug`：将 cartservice 切换为 debug 镜像（`skaffold debug` 时自动激活）
- `network-policies`：叠加 kustomize 网络策略组件

### 端口转发访问前端

```bash
kubectl port-forward deployment/frontend 8080:8080
# 浏览器访问 http://localhost:8080
```

### 单独构建 Docker 镜像

```bash
# 单个服务
docker build -t aiopsagent src/aiopsagent/
docker build -t frontend src/frontend/
docker build -t cartservice src/cartservice/src/

# 或通过 Skaffold 构建指定服务
skaffold build --build-image=aiopsagent
```

### 单独构建/运行某个服务

- **aiopsagent** (Python): 
  - **HTTP 服务模式**: `cd src/aiopsagent && pip install -r requirements.txt && python service.py`
    - 默认加载 `config/online_boutique.yaml`，可通过 `AIOPS_CONFIG` 环境变量切换
    - 本地调试时使用 mock 数据源：`AIOPS_CONFIG=config/local_mock.yaml python service.py`
    - 内置 HTTP 服务器基于 Python stdlib `ThreadingHTTPServer`（非 Flask/FastAPI），监听 `AIOPS_HOST:AIOPS_PORT`（默认 `0.0.0.0:8080`）
  - **CLI 模式**: `python main.py diagnose --config <path>` 运行单次诊断，`python main.py check --config <path>` 校验配置和数据源连通性（输出 JSON 到 `config.output.dir`）
- **oversee** (Java/Spring Boot): `cd src/oversee && mvn spring-boot:run`
- **shoppingassistantservice** (Python/Flask): `cd src/shoppingassistantservice && pip install -r requirements.txt && python shoppingassistantservice.py`（依赖 GCP Secret Manager + AlloyDB，本地开发需配置凭证）
- 其余 10 个标准微服务见各自目录下的 Dockerfile，可通过 Skaffold 统一管理

### 测试

本项目没有统一的测试框架。各语言服务按自身约定：
- Go 服务: `go test ./...`（CI 中具体测试 `shippingservice`, `productcatalogservice`, `frontend/validator`）
- C#（cartservice）: `dotnet test src/cartservice/`
- Java（adservice, oversee）: `mvn test`
- Python（aiopsagent 等）: `pytest`（如存在）

### CI/CD

GitHub Actions 工作流（`.github/workflows/`）：
- **ci-pr.yaml** — PR 触发：Go/C# 单元测试 → Skaffold 部署到 GKE → 冒烟测试（验证 loadgenerator 无错误），结果通过 PR comment 回显
- **ci-main.yaml** — main 分支 CI
- **kustomize-build-ci.yaml** / **terraform-validate-ci.yaml** / **helm-chart-ci.yaml** — 各部署方式的校验
- **cleanup.yaml** — PR 合并后清理 GKE 命名空间

GCP Cloud Build（`cloudbuild.yaml`）：替代 CI 方案，直接在 GCP 上构建所有镜像。

### 论文实验脚本

**OmniAnomaly (KDD 2019)：**
```bash
cd paper_reproduce/omnianomaly_kdd19
conda activate omnianomaly
PYTHONPATH=".;./tfsnippet_repo;./zhusuan" python main.py
```

**GDN (AAAI 2021)：**
```bash
cd experiment/GDN
python scripts/export_metrics.py --probe-only
python scripts/prepare_gdn_data.py
python scripts/run_gdn_reproduction.py --epochs 120

# 或使用官方 GDN 实现（需单独克隆官方仓库到 gdn-reproduce/）
# 见 scripts/run_gdn.ps1（PowerShell）
```

**OmniAnomaly 数据采集（详细指南见 `DATA_COLLECTION_GUIDE.md`）：**
```powershell
# 所有采集命令必须在 PowerShell 中执行，不能用 bash
# （bash 无法访问 Anaconda Python 和 localhost 端口转发）

# 第一步：正常数据采集（6 小时）
cd boutique__data
python collect_metrics.py --mode live --duration 360 --interval 30 `
    --metrics cpu_rate memory_working_set `
    --output ..\data\normal_train.csv --prometheus-url http://localhost:19090

# 第二步：故障注入（9 组，~2 小时）
cd ..
.\run_fault.ps1 -All

# 第三步：转换 + 训练
conda activate omnianomaly
python convert_collected_data.py
$env:PYTHONPATH = ".;./tfsnippet_repo;./zhusuan"
python main.py
```

## 架构概览

### 标准微服务（上游 Online Boutique）

| 服务 | 语言 | 职责 |
|------|------|------|
| frontend | Go | Web 前端，无登录 |
| cartservice | C# | 购物车，Redis 存储 |
| productcatalogservice | Go | 产品目录 JSON |
| currencyservice | Node.js | 货币转换（QPS 最高） |
| paymentservice | Node.js | 模拟支付 |
| shippingservice | Go | 模拟运费/发货 |
| emailservice | Python | 模拟邮件 |
| checkoutservice | Go | 订单编排 |
| recommendationservice | Python | 产品推荐 |
| adservice | Java | 文字广告 |
| loadgenerator | Python/Locust | 压测负载生成（ENV: `USERS` 控制并发数，`FRONTEND_ADDR` 指定前端地址） |

loadgenerator 含一个 busybox init container，启动时会轮询前端（最多 12 次 × 10s），确认前端就绪后才启动 Locust。`USERS` 默认值为 `10`（可通过 K8s Deployment 环境变量调整）。所有标准微服务通过 gRPC 相互通信，Kubernetes 清单在 `kubernetes-manifests/`，Skaffold 配置在 `skaffold.yaml`。

### 新增自定义服务

**aiopsagent** (`src/aiopsagent/`) — 基于 LangGraph 的智能运维 Agent：

模块结构：
```
aiops_agent/
├── config.py          # AppConfig 及所有子配置 (Pydantic BaseModel)
├── types.py           # AgentState, MetricPoint, Anomaly, RootCause, Action (TypedDict)
├── checks.py          # 启动前预检（Prometheus 连通性、文件存在性、数据源可用性）
├── agent/graph.py     # LangGraph StateGraph 管道定义
├── datasource/        # 数据源：base → factory → mock/prometheus/csv
├── detectors/         # 异常检测：rule_based (阈值) + paper_adapter (论文算法适配器)
├── diagnosis/         # 根因分析：按异常分数排序，输出 Top-K 候选服务
├── remediation/       # 修复：planner (生成建议) + executor (dry-run/execute)
└── reports/           # 报告生成（可选接入 LLM）
```

核心流程（StateGraph 管道）：`collect_metrics` → `detect_anomalies` → `analyze_root_cause` → `plan_remediation` → `execute_actions` → `generate_report`
- **条件分支**：若无异常则从 `detect_anomalies` 直接跳至 `generate_report`，跳过根因分析和修复步骤

关键类型定义（`types.py`）：
- `AgentState`：整个管道的状态对象，包含 config、metrics、anomalies、root_causes、actions、executed_actions、report、errors
- `MetricPoint`：`{timestamp, service, namespace, metrics: {cpu_usage, memory_usage, ...}}`
- `Anomaly`：`{service, metric, value, threshold, score, reason}`
- `RootCause`：`{service, score, evidence[]}`
- `Action`：`{action_type, target_service, namespace, command, risk, require_confirm, status, rationale}`

配置体系（`config.py`）：
- `AppConfig` 是顶层配置类，包含所有子配置：`DataSourceConfig`, `PrometheusConfig`, `KubernetesConfig`, `ChaosMeshConfig`, `LLMConfig`, `DetectorConfig`, `RemediationConfig`, `OutputConfig`
- 通过 `load_config(path)` 从 YAML 加载并校验
- **运行时覆盖**：`POST /api/v1/diagnose` 接受 `config_overrides` 字段，递归深度合并到当前配置（见 `service.py:_merge_dict`）

支持三种数据源：Prometheus、Mock、CSV（通过 `datasource/factory.py` 工厂创建，由 `datasource.type` 配置控制）
- 可用配置文件：`online_boutique.yaml`（生产/Prometheus）、`local_mock.yaml`（本地 mock）、`ark_mock.yaml`（mock+LLM）、`from_csv.yaml`（CSV 回放）

异常检测支持 `rule`（规则阈值）和 `paper`（论文算法适配器）两种模式：
- `rule` 模式：`RuleBasedDetector` 直接使用阈值比较（`cpu_usage > 0.8`, `memory_usage > 0.8` 等）
- `paper` 模式：`PaperAlgorithmAdapter` 包装 `RuleBasedDetector`，当前 fallback 到规则检测，替换 `detect()` 即可接入论文算法

修复模式：`dry-run`（仅建议）和 `execute`（实际执行，受 `require_confirm` 控制）

可选接入火山方舟 LLM 生成诊断报告（`llm.enabled: true`，需 `ARK_API_KEY`）

对外 REST 接口：`GET /healthz`, `GET /readyz`, `GET /api/v1/capabilities`, `GET /api/v1/config`, `POST /api/v1/preflight`, `POST /api/v1/diagnose`, `POST /api/v1/events`（`events` 端点接收 oversee/压测/外部测试模块的运行时事件）

**PromQL 指标映射** (`config/metric_mapping.yaml`)：使用 `$namespace` 和 `$service` 占位符，运行时动态替换。已定义指标：`cpu_usage`, `memory_usage`, `pod_ready`, `request_latency_p95`, `error_rate`。新增检测指标只需在此文件中添加一条 PromQL 查询即可。

**oversee** (`src/oversee/`) — Spring Boot 集群监控服务：
- 定期探测所有微服务（支持 HTTP、gRPC Health Check、Redis PING 三种协议）
- 暴露 Prometheus 指标（`online_boutique_requests_total`, `online_boutique_errors_total`, `online_boutique_request_latency`）
- 服务列表通过 `application.properties` 中的 `online.boutique.services` 配置
- 使用 Maven + Java 8 + Spring Boot 2.7

**shoppingassistantservice** (`src/shoppingassistantservice/`) — 购物助手：
- Flask Web 服务，使用 Gemini 1.5 Flash 视觉模型分析房间图片风格
- 通过 AlloyDB 向量存储做 RAG 检索相似产品
- 依赖 Google Cloud 服务（Secret Manager、AlloyDB）

### 论文复现

#### OmniAnomaly (KDD 2019) — `paper_reproduce/omnianomaly_kdd19/`

- 核心算法在 `omni_anomaly/` 目录
- `main.py` 为训练/测试入口，数据从 `processed/boutique_*.pkl` 读取
- **数据采集引擎**: `boutique__data/collect_metrics.py`（已验证，可靠）
  - 输出长表格式: `metric,node,pod,namespace,container,timestamp,value`
  - 必须用 `--metrics cpu_rate memory_working_set`（空格分隔，放在参数最后）
- **故障注入**: `run_fault.ps1`（PowerShell 脚本，自动采集+注入+日志）
- **数据转换**: `convert_collected_data.py`（长表→宽表+标签，输出到 `processed/`）
- **旧脚本已删除**：原 `repack_*.py`, `chaos_injection.py`, `plot_results.py` 等已被清理（见 git status），不再使用
- **一键采集脚本**: `collect_data.sh`（bash，自动化全流程）和 `manual_collect.py`（手动交互式采集）
- **详细采集流程**: `DATA_COLLECTION_GUIDE.md`
- 9 组实验记录: `experiment_backups/EXPERIMENT_LOG.md`
- **已采集的真实数据**: `data/`（9 组故障 CSV + normal_train.csv，~7.5h 正常 + 9 段故障）
- 依赖 `tfsnippet` 和 `zhusuan`（已在目录内），omnianomaly conda 环境 (Python 3.6 + TensorFlow 1.x)
- OmnAnomaly 实验 #6 最佳 F1=0.968（22维 GDN 数据），关键教训：**单服务故障 + 精选22维 + 纯净训练集**

#### GDN (AAAI 2021) — `experiment/GDN/`

- 基于图神经网络的多元时间序列异常检测，学习指标间依赖图，通过预测偏差检测异常
- 实验目录结构：
  - `scripts/` — `export_metrics.py`（从 Prometheus 导出 CSV）、`prepare_gdn_data.py`（数据预处理）、`run_gdn_reproduction.py`（轻量复现）、`run_partner_gdn.py`（官方实现）、`validate_exp124.py`
  - `data/` — 正常训练/验证数据（`normal_train.csv`, `normal_valid.csv`）和故障注入数据（`fault_cpu_frontend.csv`, `fault_delay_cart.csv`, `fault_kill_product.csv`）
  - `chaos/` — ChaosMesh 故障注入 YAML（CPU Stress、Network Delay、Pod Kill）
  - `results/` — GDN 输出（异常分数 CSV、Top 异常特征 CSV）
  - `tests/selenium/` — Selenium 功能测试（`test_checkout_flow.py`）
  - `partner_data/` — 官方 GDN 格式数据（`.pkl`）
- 实验配置：22 维特征（11 服务 × cpu/mem），窗口 5，embedding 64，TopK 15
- 实验结果：Precision 0.8462, Recall 1.0000, F1 0.9167
- 当前限制：离线批处理、训练集短（~30min）、仅 cpu/mem 特征（无 pod 级网络指标）
- 故障注入时间记录：`experiment-log.md`（精确到秒的故障起止时间）

### aiopsagent 与论文复现的集成点

1. **OmniAnomaly 集成**：`aiops_agent/detectors/paper_adapter.py` 中的 `PaperAlgorithmAdapter` 是预留适配器，替换 `detect()` 方法即可将 OmniAnomaly 模型接入 LangGraph 诊断管道。

2. **GDN 集成**（详见 `experiment/GDN/GDN-AGENT-INTERFACE.md`）：GDN 输出文件接口，Agent 可直接读取：
   - `results/gdn_lightweight_scores.csv` — 判断当前窗口是否异常（`prediction=1` 且 `score > threshold`）
   - `results/gdn_lightweight_top_features.csv` — 获取异常贡献最高的指标（格式 `{service}_{metric}`），据此定位候选服务
   - 推荐集成流程：GDN 检测异常 → Agent 读取 Top features → 调用 Prometheus/kubectl 进一步确认 → 输出诊断结论

## 关键配置文件

| 文件 | 用途 |
|------|------|
| `skaffold.yaml` | 定义所有服务的构建/部署配置 |
| `kubernetes-manifests/kustomization.yaml` | Kustomize 清单入口 |
| `src/aiopsagent/config/online_boutique.yaml` | AIOps Agent 主配置（生产/Prometheus 数据源） |
| `src/aiopsagent/config/local_mock.yaml` | 本地 mock 数据源配置 |
| `src/aiopsagent/config/ark_mock.yaml` | Mock + LLM 配置 |
| `src/aiopsagent/config/from_csv.yaml` | CSV 回放数据源配置 |
| `src/aiopsagent/config/metric_mapping.yaml` | Prometheus 指标映射 |
| `src/oversee/pom.xml` | Oversee Maven 构建配置 |
| `cloudbuild.yaml` | GCP Cloud Build CI/CD 配置 |
| `experiment/GDN/GDN-AGENT-INTERFACE.md` | GDN 与 Agent 集成接口文档 |
| `experiment/GDN/scripts/` | GDN 数据预处理与复现脚本 |

## Kubernetes 部署方式

项目支持多种部署方式：
- **kubectl apply**: 直接应用 `release/kubernetes-manifests.yaml`（单文件合并版）或 `release/istio-manifests.yaml`
- **Skaffold**: `skaffold run` 或 `skaffold dev`（推荐开发方式）
- **Kustomize**: `kubernetes-manifests/` + `kustomize/`（Skaffold 内部使用此方式）
- **Helm**: `helm-chart/`
- **Istio**: `istio-manifests/` 含 Gateway 和网络策略
- **Terraform**: `terraform/` 目录

### Kustomize 组件 (`kustomize/components/`)

`kubernetes-manifests/kustomization.yaml` 中注释掉了多个可选 Kustomize 叠加组件，按需启用：

| 组件 | 用途 |
|------|------|
| `cymbal-branding` | Cymbal 品牌定制 |
| `google-cloud-operations` | GCP Cloud Monitoring 集成 |
| `memorystore` | GCP Memorystore (Redis) |
| `network-policies` | Kubernetes 网络策略 |
| `alloydb` | AlloyDB 数据库（配合 shoppingassistantservice） |
| `shopping-assistant` | 购物助手服务完整部署 |
| `spanner` | Cloud Spanner 替代本地存储 |
| `container-images-tag/registry` | 镜像 tag/registry 覆盖 |
| `single-shared-session` | 单一共享会话（替换随机生成会话） |
| `non-public-frontend` | 内网前端（移除外部 IP） |
| `without-loadgenerator` | 不含压测的部署 |

启用方式：取消注释 `kustomization.yaml` 中对应的 components 行，或用 Skaffold profile：`skaffold run -p network-policies`。

### gRPC 协议定义 (`protos/`)

`protos/demo.proto` 定义了所有微服务间的 gRPC 协议（`CartService`, `CheckoutService`, `CurrencyService`, `ProductCatalogService`, `ShippingService`, `AdService`, `RecommendationService`, `PaymentService`, `EmailService`）。各语言服务通过 `protos/grpc/` 下的生成代码使用，修改 proto 后需重新生成各语言的 gRPC stub。

### oversee 部署

`kubernetes-manifests/deployment.yaml` 和 `service.yaml` 专门部署 `oversee` Spring Boot 监控服务（非标准微服务），包含 Prometheus 注解（`prometheus.io/scrape: "true"`），由 `/actuator/prometheus` 端点暴露 JVM + 自定义业务指标。

## Namespace 约定（注意不一致）

项目中不同配置文件使用了不同的 namespace，这是已知的历史遗留问题，排查问题时要留意：

| 位置 | namespace 值 | 说明 |
|------|-------------|------|
| CLAUDE.md（本文档） | `boutique` | 推荐使用的微服务 namespace |
| `src/aiopsagent/config/online_boutique.yaml` | `default` | aiopsagent 生产配置使用的值 |
| GDN 文档 / 脚本 | `onlineboutique` | GDN 实验中使用的值 |
| ChaosMesh（安装文档） | `chaos-testing` | 故障注入官方推荐的 namespace |
| ChaosMesh（aiopsagent 配置） | `chaos-mesh` | `online_boutique.yaml` 中实际使用的值，注意与 `chaos-testing` 不同 |
| Prometheus | `monitoring` | Prometheus 栈的固定 namespace |

**建议**：在同一个实验/部署中统一使用一个 namespace，避免跨 namespace 导致的连接问题。

## 注意事项

- 当前分支 `release/v0.10.2`，PR 目标分支也是此分支
- **微服务 namespace 是 `boutique`**，ChaosMesh namespace 推荐 `chaos-testing`（注意 aiopsagent 配置中为 `chaos-mesh`，可能需手动对齐）
- **Prometheus 端口转发**: `kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 19090:9090`
- **数据采集必须在 PowerShell 中执行，不能用 bash/WSL**。bash 无法访问 Anaconda Python 和 localhost 端口转发。如果看到 `wsl: 检测到 localhost 代理配置` 警告，说明用错了终端
- `omnianomaly` conda 环境是 Python 3.6 + TensorFlow 1.x（`requirements.txt` 指定 `tensorflow-gpu==1.12.0`），仅用于训练阶段。数据采集用 base Anaconda Python 即可（需要 `requests` + `pandas`）
  - 实际部署环境可能为 TF 1.15.5 + Python 3.7（以 `conda list` 为准），`zhusuan` 和 `tfsnippet` 使用目录内本地副本（非 git 安装）
- `collect_data.sh` 是 bash 脚本（自动化全流程），`run_fault.ps1` 是 PowerShell 脚本（仅故障注入），两者互补。`collect_data.sh` 会自动检测 Anaconda Python 路径
- `aiopsagent` 基于 Python stdlib `ThreadingHTTPServer`（非 Flask/FastAPI）
- `aiopsagent` 的 LLM 功能需要 K8s Secret `aiopsagent-ark` 设置 `ARK_API_KEY`
- `loadgenerator` 的 busybox init container 镜像拉取策略已改为 `IfNotPresent`（避免网络问题时拉取失败）
- OmniAnomaly 数据采集时 `collect_metrics.py --metrics` 参数必须用空格分隔且放在所有参数最后：`--metrics cpu_rate memory_working_set`
- OmniAnomaly 训练数据必须是 100% 纯净的正常数据，故障注入和正常采集**不能同时进行**
- **`loadgenerator` 的 Skaffold 管理**：loadgenerator 在 `skaffold.yaml` 中是独立的 Config（名为 `loadgenerator`），通过 `requires: [app]` 依赖主应用。同时它在 `kustomization.yaml` 中被注释掉（`# - loadgenerator.yaml`），由 Skaffold 的 `rawYaml` 直接部署。如需单独部署 loadgenerator：`kubectl apply -f kubernetes-manifests/loadgenerator.yaml`

## `.claude/` 持久化配置

`.claude/settings.local.json` 包含项目级权限预设（预授权的 bash/kubectl/curl 命令），减少交互式权限弹窗。`.claude/` 目录不会被 git 追踪。用户级持久记忆存储在 `~/.claude/projects/D--online-boutique-temp/memory/`，包含实验流程经验（如 [[omnianomaly-data-collection]]），Claude Code 启动时会自动加载。

## 常见问题排查

| 症状 | 可能原因 | 排查命令 |
|------|---------|---------|
| `skaffold dev` 构建失败 | Docker 未启动或磁盘不足 | `docker info`, `docker system df` |
| loadgenerator 一直 CrashLoopBackOff | busybox init container 镜像拉取失败（网络问题） | `kubectl describe pod -l app=loadgenerator`，检查 image pull 错误 |
| Prometheus 端口转发拒绝连接 | monitoring namespace 的 Prometheus Pod 未运行 | `kubectl get pods -n monitoring` |
| OmniAnomaly 训练结果极差 | 训练数据包含故障时段的数据 | 检查正常数据采集和故障注入的时间是否重叠 |
| `conda activate omnianomaly` 失败 | 环境未创建或路径不对 | `conda info --envs`，确认环境名和 Anaconda 安装路径 |
| 数据采集时 CSV 为空 | `--metrics` 参数格式错误或 namespace 不匹配 | 确认参数格式：`--metrics cpu_rate memory_working_set`（空格分隔，放最后） |
| `PYTHONPATH` 警告 | Windows 路径分隔符问题 | 使用 PowerShell: `$env:PYTHONPATH = ".;./tfsnippet_repo;./zhusuan"`，bash: `PYTHONPATH=".:./tfsnippet_repo:./zhusuan"` |
| 论文实验找不到 conda Python | 用错了终端 | 数据采集/故障注入必须用 PowerShell（能访问 Anaconda），训练可用 bash + `conda run` |

## 关键参考文档

| 文档 | 路径 | 内容 |
|------|------|------|
| 上游开发指南 | `docs/development-guide.md` | Skaffold 完整部署指南（GKE + 本地） |
| 项目定位 | `docs/purpose.md` | 项目目标与范围 |
| GDN 完整实验报告 | `experiment/GDN/EXPERIMENT-GDN.md` | 四阶段实验细节、JMeter/Selenium 测试结果 |
| GDN 实验时间记录 | `experiment/GDN/experiment-log.md` | 所有故障注入精确起止时间 |
| GDN-Agent 接口 | `experiment/GDN/GDN-AGENT-INTERFACE.md` | GDN 输出如何对接 aiopsagent |
| OmniAnomaly 采集指南 | `paper_reproduce/omnianomaly_kdd19/DATA_COLLECTION_GUIDE.md` | 完整数据采集流程 |
| OmniAnomaly 实验日志 | `paper_reproduce/omnianomaly_kdd19/experiment_backups/EXPERIMENT_LOG.md` | 9+ 组实验记录与教训
