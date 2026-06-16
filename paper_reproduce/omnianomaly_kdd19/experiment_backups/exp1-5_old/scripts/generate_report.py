#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OmniAnomaly 实验报告 — 精简版"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from datetime import datetime

doc = Document()

# ── 标题 ──
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run('OmniAnomaly 异常检测实验报告')
run.font.size = Pt(22)
run.bold = True

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub.add_run('基于 Online Boutique 微服务 + Chaos Mesh 故障注入').font.size = Pt(12)

doc.add_paragraph()
info = doc.add_paragraph()
info.alignment = WD_ALIGN_PARAGRAPH.CENTER
info.add_run(f'报告生成: {datetime.now().strftime("%Y-%m-%d %H:%M")} | KDD 2019 论文复现')

doc.add_paragraph()

# ── 实验环境 ──
doc.add_heading('实验环境', level=2)
doc.add_paragraph(
    '微服务系统: Online Boutique (11个服务 + Redis, gRPC通信), 部署于 Minikube\n'
    '监控: Prometheus (kube-prometheus-stack), 采集间隔 15s\n'
    '故障注入: Chaos Mesh 3.x (StressChaos / PodChaos)\n'
    '模型: OmniAnomaly (GRU + VAE), TensorFlow 1.15 / Python 3.6'
)

# ── 实验设计 ──
doc.add_heading('实验设计', level=2)
doc.add_paragraph(
    '通过五组对照实验逐步优化检测效果。变量包括: '
    '故障强度、数据维度、Pod聚合策略、特征选择。'
)

t1 = doc.add_table(rows=6, cols=5, style='Light Grid Accent 1')
t1.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, h in enumerate(['实验', '数据', '维度', '故障', '改进方向']):
    t1.rows[0].cells[i].text = h
for i, d in enumerate([
    ('#1 基线', '17.4h', '494 (4命名空间)', '弱 (1核/256MB/60s)', '默认参数+全量数据'),
    ('#2 降维', '17.4h', '234 (boutique)', '弱 (同上)', '仅保留boutique命名空间'),
    ('#3 强故障', '75min', '234 (boutique)', '强 (2核/512MB/90s)', '加大故障力度'),
    ('#4 服务聚合', '9h', '156 (12服务)', '强 (115次)', 'Pod聚合+合并正常数据'),
    ('#5 精简特征', '9h', '36 (3指标×12服务)', '强 (115次)', '只保留故障敏感指标'),
], 1):
    for j, v in enumerate(d): t1.rows[i].cells[j].text = v

doc.add_paragraph()

# ── 模型参数 ──
doc.add_heading('模型参数', level=2)

t2 = doc.add_table(rows=6, cols=6, style='Light Grid Accent 1')
t2.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, h in enumerate(['实验', 'z_dim', 'window', 'rnn', 'epoch', '训练/测试']):
    t2.rows[0].cells[i].text = h
for i, d in enumerate([
    ('#1', '3', '100', '500', '10', '3223 / 1479'),
    ('#2', '16', '60', '500', '30', '3220 / 1479'),
    ('#3', '8', '20', '256', '50', '201 / 134'),
    ('#4', '8', '20', '256', '100', '674 / 1653'),
    ('#5', '6', '20', '128', '60', '674 / 1653'),
], 1):
    for j, v in enumerate(d): t2.rows[i].cells[j].text = v

doc.add_paragraph()

# ── 实验结果 ──
doc.add_heading('检测结果对比', level=2)

t3 = doc.add_table(rows=9, cols=6, style='Light Grid Accent 1')
t3.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, h in enumerate(['指标', '#1', '#2', '#3', '#4', '#5 ★']):
    t3.rows[0].cells[i].text = h
for i, d in enumerate([
    ('F1-Score', '0.112', '0.109', '0.553', '0.496', '0.589'),
    ('Precision', '5.9%', '5.8%', '38.3%', '33.0%', '45.7%'),
    ('Recall', '100%', '100%', '100%', '100%', '83.2%'),
    ('TP', '82/82', '82/82', '44/44', '539/539', '448/539'),
    ('FP', '1,298', '1,338', '71', '1,095', '533'),
    ('TN', '0', '25', '0', '0', '562'),
    ('FN', '0', '0', '0', '0', '91'),
    ('维度', '494', '234', '234', '156', '36'),
], 1):
    for j, v in enumerate(d): t3.rows[i].cells[j].text = v

doc.add_paragraph()

# ── 分析 ──
doc.add_heading('对比分析', level=2)

doc.add_paragraph(
    '1. 故障强度主导 (#1→#3): 弱故障时模型完全无法区分正常与异常 (F1≈0.11, TN=0)。'
    '强化到 2核/512MB/90s 后, F1 跃升至 0.553。'
    '故障信号强度是最关键的变量。'
)
doc.add_paragraph(
    '2. 维度控制关键 (#3→#4→#5): Pod名漂移导致维度膨胀至663后 F1 降至 0.443; '
    '服务聚合 (156维) 恢复至 0.496; 特征精选 (36维) 达到最佳 0.589。'
    '精简指标去除了噪音维度 (fs_reads/writes、pod_status_phase 等), '
    '使异常信号更集中。'
)
doc.add_paragraph(
    '3. 精度与召回的权衡 (#1-#4 vs #5): 前四组实验 Recall=100% 但 Precision 最高仅 38%, '
    '模型过度敏感。实验 #5 首次出现 TN=562, FP 降至 533, 但漏报 91 个异常。'
    '这表明模型开始在精度和召回间建立合理的决策边界。'
)
doc.add_paragraph(
    '4. 训练数据质量: 674 个纯净训练点 + 36 维的效果优于 3223 点 + 494 维。'
    '维度质量 > 数据数量。'
)

# ── 指标说明 ──
doc.add_heading('评估指标说明', level=2)
doc.add_paragraph(
    'F1: Precision 和 Recall 的调和均值, 综合衡量检测能力\n'
    'Precision (精确率): 报警中真正异常的比例 (TP / (TP+FP))\n'
    'Recall (召回率): 真实异常中被检出的比例 (TP / (TP+FN))\n'
    'TP: 正确检出的异常点 | FP: 误报(正常被判异常)\n'
    'TN: 正确识别的正常点 | FN: 漏报(异常被判正常)'
)

# ── 结论 ──
doc.add_heading('结论', level=2)
doc.add_paragraph(
    'OmniAnomaly 在 Online Boutique 微服务环境中可有效检测强故障, '
    '最佳 F1=0.589 (Precision=45.7%, Recall=83.2%)。'
    '故障强度、特征选择、维度控制是影响检测效果的核心因素。'
    '未来可通过延长数据采集 (获得更多训练样本) '
    '和尝试更多特征工程进一步提升。'
)

# ── 保存 ──
path = 'OmniAnomaly_实验报告_v2.docx'
doc.save(path)
print(f'报告已生成: {path}')
