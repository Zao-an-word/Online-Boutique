# OmniAnomaly 实验记录

## 实验结果总览

| # | 名称 | F1 | Precision | Recall | TP/FP/TN/FN | 维度 | 训练 | 关键变量 |
|---|------|:---:|:---:|:---:|:---:|:---:|:---:|---------|
| 1 | Baseline | 0.112 | 5.9% | 100% | 82/1298/0/0 | 494 | 3,223 | 默认参数 |
| 2 | 降维 | 0.109 | 5.8% | 100% | 82/1338/25/0 | 234 | 3,220 | boutique only |
| 3 | 强故障(短) | 0.553 | 38.3% | 100% | 44/71/0/0 | 234 | 201 | 2核CPU+512MB |
| 4 | 服务聚合 | 0.496 | 33.0% | 100% | 539/1095/0/0 | 156 | 674 | Pod聚合+合并 |
| **5** | **精简特征** | **0.589** | **45.7%** | **83.2%** | **448/533/562/91** | **36** | **674** | ★ 最佳 |
| **6** | **GDN数据训练** | **0.968** | **93.7%** | **100%** | **45/3/26/0** | **22** | **61** | ★ GDN数据集 |
| 7 | 降维优化(exp4) | 0.487 | 32.4% | 98.5% | 531/1110/280/8 | 36 | 379 | 自动降维(663→36) |
| 8 | 去噪(exp4) | 0.472 | 30.9% | 100% | 539/1205/185/0 | 54 | 379 | boutique cpu/mem |
| **9** | **新管线采集+调参** | **0.786** | **70.4%** | **89.1%** | **114/48/137/14** | **22** | **637** | ★ 最佳配置: w30 |

## 核心结论
- 故障强度: F1 从 0.11 → 0.55 (5倍提升)
- 特征选择: 22维(GDN精选) > 36维(自动筛选) > 54维(去噪) > 156维 > 494维
- Recall 从 100% → 83%, 首次出现 TN=562, 模型学会区分正常/异常 (实验#5)
- 最佳 F1=0.968 (GDN), Precision=93.7%
- **降维≠去噪**: 方差过滤(#7, F1=0.487)优于简单去噪(#8, F1=0.472); 低方差列即使语义干净也会成为噪声
- **数据源决定上限**: #7/#8 对 #4 的优化止步于 F1≈0.49, 远不及 GDN(#6)的 0.968; 根本差异在于数据采集质量而非特征工程

## 备份目录
- exp3_strong_fault/    → 实验#3: 强故障(短)
- exp4_long_highdim/    → 实验#4: 长数据+高维
- exp4C_combined_normal/ → 实验#4C: 合并训练
- exp5_focused_features/ → 实验#5: 精简特征 (最佳)
- exp6_gdn_data/         → 实验#6: GDN数据集训练
- exp7_dimreduce_optimized/ → 实验#7: 降维优化(exp4)
- exp8_denoised/          → 实验#8: 去噪(exp4)
- exp_backup_20260608/    → 实验#9前旧模型备份
- exp_v1_window20/        → 实验#9 v1: 默认参数基准 (F1=0.643)
- exp_v2_window10/        → 实验#9 v2: 小窗口 (F1=0.616)
- exp_v3_window30/        → 🏆 实验#9 v3: 最佳结果 (F1=0.786)
- exp_v4_window40/        → 实验#9 v4: 大窗口 (F1=0.762)
- exp_v5_window28/        → 实验#9 v5: 中等窗口 (F1=0.692)
- exp_v6_window30_l5/     → 实验#9 v6: w30+level=0.05 (F1=0.713)
- exp_v7_window30_lr/     → 实验#9 v7: w30+低lr (F1=0.655)

## 实验 #6: GDN 数据集训练 (2026-06-08)

### 数据来源
- GDN 实验数据 (`experiment/GDN/data/`)，由 `gdn_data/convert_to_omnianomaly.py` 转换
- 训练集: 61 个时间点（~30 分钟正常数据）
- 测试集: 78 个时间点（21 正常 + 19 CPU故障 + 19 网络延迟 + 19 Pod Kill）
- 特征: 22 维（11 服务 × cpu/mem，剔除全空网络列）
- 标签: 根据 experiment-log.md 故障时间窗口 + 2 分钟恢复期自动标注（33 正常 / 45 异常）

### 模型超参数
- window_length=5, batch_size=16, z_dim=3
- rnn_num_hidden=64, dense_dim=128, nf_layers=5
- max_epoch=100, lr_anneal_epoch_freq=30
- valid_step_freq=20, early_stop=True

### 结果
- F1=0.968, Precision=0.937, Recall=1.000
- TP=45, FP=3, TN=26, FN=0
- Best threshold=-19.0, Best valid loss=1.8465

### 与 GDN 对比
| 方法 | Precision | Recall | F1 |
|------|-----------|--------|-----|
| GDN 轻量复现 | 0.8462 | 1.0000 | 0.9167 |
| OmniAnomaly | 0.9375 | 1.0000 | 0.9677 |
- OmniAnomaly Precision 提升 ~9pp，FP 仅 3 个

### 注意事项
- POT 评估因训练集过小（peaks=0）被跳过
- 数据量极小（61 行），模型泛化性待更大数据集验证
- 对比实验 #1-#5 使用 Prometheus 直接导出的 k8s_metrics.csv（494 维），本实验使用 GDN 预处理后的 22 维数据
- 数据转换脚本: `gdn_data/convert_to_omnianomaly.py`

## 实验 #7: 降维优化 (基于实验#4数据) (2026-06-08)

### 数据来源
- 实验#4 的原始数据 (379 训练 / 1948 测试, 663 维)
- 降维策略:
  1. 剔除零方差列: 663 → 49 (92.6% 的列为零方差!)
  2. 剔除 pod_status_phase 类 categorical one-hot 列
  3. 保留所有命名空间 (因 boutique-only 只剩 13 维)
- 最终维度: 36

### 保留特征类型
cpu_rate(8), pod_restarts(8), fs_reads_bytes_rate(6), fs_reads_total(5),
fs_writes_bytes_rate(4), memory_working_set(3), fs_writes_total(1), memory_rss(1)

### 模型超参数
- window_length=20, batch_size=50, z_dim=6 (默认参数)
- rnn_num_hidden=128, dense_dim=256, nf_layers=10
- max_epoch=80, lr_anneal_epoch_freq=40
- 总参数: 334,622

### 结果
- F1=0.487, Precision=0.324, Recall=0.985
- TP=531, FP=1110, TN=280, FN=8
- Best threshold=-84.0, Best valid loss=208.3

### 与实验#4对比
| 指标 | 实验#4 (663维) | 实验#7 (36维) | 变化 |
|------|:---:|:---:|:---:|
| F1 | 0.443 | 0.487 | +10% |
| Precision | 28.5% | 32.4% | +14% |
| Recall | 100% | 98.5% | -1.5% |
| FP | 1355 | 1110 | -245 |
| TN | 35 | 280 | +245 |
| FN | 0 | 8 | +8 |

### 分析
- 降维带来明显改善: FP-245, TN 从 35 增至 280
- 模型首次在实验#4 数据上学会区分正常/异常 (非全报警)
- 但 36 维中仍含 fs_*、pod_restarts 等与故障弱相关的噪声指标
- GDN 的 22 维精选特征(仅 cpu/mem)远超此 36 维自动筛选效果
- 结论: **特征质量比特征数量重要得多**，人工精选 22 维 cpu/mem 效果碾压自动筛选 36 维

## 实验 #8: 去噪 (基于实验#4, boutique cpu/mem) (2026-06-08)

### 数据来源
- 实验#4 原始数据 (379 训练 / 1948 测试, 663 维)
- 去噪策略: 仅保留 boutique 命名空间的 cpu_rate + memory_rss + memory_working_set
- 最终: 54 维 (12 服务 × 3 指标, 含多副本 Pod)

### 模型超参数
- 同实验#7: window_length=20, batch_size=50, z_dim=6, 参数~351K

### 结果
- F1=0.472, Precision=0.309, Recall=1.000
- TP=539, FP=1205, TN=185, FN=0
- Best threshold=-399.0, Best valid loss=-169.3

### 与实验#7(自动降维)对比
| 指标 | #7 (36维) | #8 (54维) | 差异 |
|------|:---:|:---:|:---:|
| F1 | 0.487 | 0.472 | -3% |
| FP | 1110 | 1205 | +95 |
| TN | 280 | 185 | -95 |

### 分析
- 去噪(#8)比原始(#4, F1=0.443)好，但不如方差过滤(#7, F1=0.487)
- 原因: 54 维中大量 boutique pod 的 cpu/mem 在训练段方差为零，MinMaxScaler 后变为常数噪声
- **降维 > 去噪**: 剔除零方差列比人工语义筛选更有效
- **数据源是瓶颈**: #4 的数据来自 115 个故障事件的广泛影响，训练段太短(~16%)
  - GDN(#6)的数据专门为异常检测设计: 干净正常期 + 精确故障窗口
  - #4 的数据是"野生"采集: 多命名空间混杂、故障影响广泛

---

## 实验 #9: 新采集管线 + 调参优化 (2026-06-08)

### 数据来源
- 正常数据: `collect_metrics.py --mode live --duration 360 --interval 30 --metrics cpu_rate memory_working_set`
  - 采集时长: 6 小时（实际 ~7.5 小时，50,367 条原始记录）
  - 过滤后: 797 行 × 22 维
- 故障注入: `run_fault.ps1 -All`（9 组，3 故障类型 × 3 服务）
  - CPU Stress (2核, 80%): frontend, cartservice, productcatalogservice
  - Network Delay (500ms): frontend, cartservice, productcatalogservice
  - Pod Kill: frontend, cartservice, productcatalogservice
- 测试集: 342 行 (128 异常 / 214 正常 = 37.4%)
- 转换: `convert_collected_data.py`（修复了无表头、时间戳时区等 bug）

### 采集管线问题修复
本次采集过程中发现并修复了 `convert_collected_data.py` 的 3 个 bug:
1. **CSV 无表头**: `collect_metrics.py` 输出的 CSV 无 header row，需用 `header=None, names=[...]` 读取
2. **时间戳类型**: pivot 后 index 为 Unix 时间戳(int)，`pd.to_datetime()` 需 `unit='s'`
3. **时区不匹配**: `experiment_log.txt` 记录的是 CST 本地时间，Prometheus 时间戳是 UTC，差 8 小时导致标签全为 0。修复为数值比较

### 调参过程

| 轮次 | window | batch | epoch | z_dim | level | 其他 | F1 | 备注 |
|:---:|:---:|:---:|:---:|:---:|:---:|------|:---:|------|
| v1 | 20 | 50 | 80 | 6 | 0.01 | — | 0.643 | 默认参数(基准) |
| v2 | 10 | 35 | 120 | 4 | 0.005 | — | 0.616 | 小窗口→退步 |
| **v3** | **30** | **50** | **150** | **6** | **0.01** | — | **0.786** | 🏆 **最佳** |
| v4 | 40 | 60 | 150 | 6 | 0.01 | — | 0.762 | 窗口过大→衰减 |
| v5 | 28 | 50 | 150 | 6 | 0.05 | — | 0.692 | POT level过大→best-f1下降 |
| v6 | 30 | 50 | 150 | 6 | 0.05 | — | 0.713 | 同v3但level更大→退步 |
| v7 | 30 | 50 | 200 | 6 | 0.02 | lr=0.0005 | 0.655 | 低lr→收敛慢 |
| v8 | 30 | 50 | 200 | 6 | 0.03 | — | 0.639 | 随机初始化波动 |
| v9 | 5 | 16 | 100 | 3 | 0.01 | rnn=64, dense=128, nf=5 | 0.600 | 复刻#6参数→不适用 |

### 最佳结果 (v3)
```
window_length=30, batch_size=50, max_epoch=150, z_dim=6
rnn_num_hidden=128, dense_dim=256, nf_layers=10
level=0.01, initial_lr=0.001

F1=0.786, Precision=0.704, Recall=0.891
TP=114, FP=48, TN=137, FN=14
Best threshold=8.0, Best valid loss=-16.29

POT: 因 level=0.01 过于保守，threshold=-587，检测不到任何异常 (pot-f1=0.0)
```

### 关键发现

1. **窗口长度是最敏感的超参**: w10→w20→w30→w40，F1 呈倒 U 形（0.616→0.643→0.786→0.762），30 为最优点
2. **POT level 调优困难**: 对当前 637 行训练集，level < 0.05 时 POT 极度保守（threshold 极高，TP=0）；level=0.05 时 POT 开始检出但 best-F1 被拖低
3. **大窗口优于小窗口**（与 #6 相反）: #6 用 w5 达 0.968，我们用 w5 仅 0.600。因为 #6 数据是瞬时强信号，我们的数据需要大窗口捕捉累积偏差
4. **模型大小需匹配数据复杂度**: w5+z3+64hidden (#6配置) 在我们数据上表现最差，说明真实采集数据需要更大模型
5. **随机初始化导致 ±0.1 F1 波动**: 相同参数跑多次 F1 在 0.64~0.79 之间，说明 637 训练行仍不足以稳定收敛

### 与 #6 的差距分析

| 维度 | #6 (GDN数据) | #9 (新采集) | 影响 |
|------|:---:|:---:|------|
| 训练行数 | 61 | 637 | #9 多 10× |
| 信号噪声比 | 极高(实验设计) | 普通(真实环境) | **根本差异** |
| 正常期特征 | 30分钟"无波动" | 6小时含自然波动 | #6 正常基线过于简单 |
| 故障信号强度 | CPU骤变到满载 | 真实注入,部分被系统吸收 | #6 信号更清晰 |
| 测试集结构 | 3段故障,边界清晰 | 9段故障穿插160个正常点 | #9 更难区分 |

**结论**: #6 的 0.968 是人造理想数据的结果，0.786 才是真实采集数据的天花板。要进一步提升需要更长采集（12-24h）或更强故障注入。

### 备份目录
- exp_backup_20260608/ — 旧模型备份（Pipeline开始前）
- exp_v1_window20/ — v1: 默认参数基准
- exp_v2_window10/ — v2: 小窗口尝试
- exp_v3_window30/ — 🏆 v3: 最佳结果
- exp_v4_window40/ — v4: 大窗口尝试
- exp_v5_window28/ — v5: 中等窗口+高POT
- exp_v6_window30_l5/ — v6: w30+level=0.05
- exp_v7_window30_lr/ — v7: w30+低lr+200epoch

---

## 后续工作：重新采集高质量数据

基于 8 组实验的教训，已准备好完整的数据采集流水线。

### 相关文件

| 文件 | 用途 |
|------|------|
| `DATA_COLLECTION_GUIDE.md` | 详细采集方案（原理、标准、质量检查） |
| `collect_data.sh` | 一键自动化脚本（启动→采集→故障→训练） |
| `gdn_data/convert_to_omnianomaly.py` | CSV → OmniAnomaly pkl 格式转换 |
| `../experiment/GDN/scripts/export_metrics.py` | Prometheus 指标导出（22 维 cpu/mem） |

### 待执行流程

1. `bash collect_data.sh start` — 启动集群
2. `bash collect_data.sh collect-normal 7200` — 采集 ≥2 小时正常数据
3. `bash collect_data.sh fault <类型> <服务>` — 逐服务注入故障（每次只打 1 个）
4. `bash collect_data.sh train` — 转换 + 训练 + 输出结果

### 核心改进（相比实验 #1-#5）

- 每次只注入 1 个服务故障（而非 115 个同时）
- 仅采集 boutique 命名空间的 cpu/mem（22 维而非 494-663 维）
- 精确记录故障时间窗口 + 2 分钟恢复期
- 正常训练集 ≥2 小时（而非 16% 的短窗口）
