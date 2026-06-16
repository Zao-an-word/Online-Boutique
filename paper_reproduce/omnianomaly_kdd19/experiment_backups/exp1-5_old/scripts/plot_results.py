#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成实验图表: 对比柱状图 + 异常分数分布"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pickle

# 中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ═════════════════════════════════════════════
# 图1: 五组实验 F1/Precision/Recall 对比
# ═════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 子图1: F1 趋势
exp_names = ['#1\n基线', '#2\n降维', '#3\n强故障(短)', '#4\n服务聚合', '#5\n精简特征',
              '#6\nGDN数据', '#7\n降维优化', '#8\n去噪']
f1_scores = [0.112, 0.109, 0.553, 0.496, 0.589, 0.968, 0.487, 0.472]
precision_scores = [0.059, 0.058, 0.383, 0.330, 0.457, 0.937, 0.324, 0.309]
recall_scores = [1.0, 1.0, 1.0, 1.0, 0.832, 1.0, 0.985, 1.0]

colors = ['#d4d4d4', '#d4d4d4', '#a8d8ea', '#7ec8e3', '#3b8ed0', '#e74c3c', '#f39c12', '#95a5a6']
x = np.arange(len(exp_names))

axes[0].bar(x, f1_scores, color=colors, edgecolor='black', linewidth=0.5)
axes[0].set_xticks(x)
axes[0].set_xticklabels(exp_names, fontsize=9)
axes[0].set_ylabel('F1-Score', fontsize=12)
axes[0].set_title('F1 变化趋势 (6组对照实验)', fontsize=13, fontweight='bold')
axes[0].set_ylim(0, 1.1)
for i, v in enumerate(f1_scores):
    axes[0].text(i, v + 0.015, f'{v:.3f}', ha='center', fontsize=9, fontweight='bold')

# 子图2: Precision/Recall 堆叠
width = 0.35
axes[1].bar(x - width/2, precision_scores, width, label='Precision', color='#e74c3c', edgecolor='black', linewidth=0.5)
axes[1].bar(x + width/2, recall_scores, width, label='Recall', color='#2ecc71', edgecolor='black', linewidth=0.5)
axes[1].set_xticks(x)
axes[1].set_xticklabels(exp_names, fontsize=9)
axes[1].set_ylabel('Score', fontsize=12)
axes[1].set_title('Precision & Recall 对比', fontsize=13, fontweight='bold')
axes[1].set_ylim(0, 1.15)
axes[1].legend(fontsize=10)
for i in range(len(x)):
    axes[1].text(i - width/2, precision_scores[i] + 0.03, f'{precision_scores[i]:.1%}', ha='center', fontsize=8)
    axes[1].text(i + width/2, recall_scores[i] + 0.03, f'{recall_scores[i]:.1%}', ha='center', fontsize=8)

plt.tight_layout()
plt.savefig('images/results_comparison.png', dpi=150, bbox_inches='tight')
print('图1: images/results_comparison.png')

# ═════════════════════════════════════════════
# 图2: 实验#5 异常分数分布 (正常 vs 异常)
# ═════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(10, 5))

test_score = pickle.load(open('result/test_score.pkl', 'rb'))
test_label = pickle.load(open('processed/boutique_test_label.pkl', 'rb'))

# 确保长度匹配
min_len = min(len(test_score), len(test_label))
test_score = test_score[:min_len]
test_label = test_label[:min_len]

normal_scores = test_score[test_label == 0]
anomaly_scores = test_score[test_label == 1]

ax.hist(normal_scores, bins=50, alpha=0.6, label=f'正常 (n={len(normal_scores)})', color='#2ecc71', edgecolor='black', linewidth=0.3)
ax.hist(anomaly_scores, bins=50, alpha=0.7, label=f'异常 (n={len(anomaly_scores)})', color='#e74c3c', edgecolor='black', linewidth=0.3)
ax.set_xlabel('Anomaly Score', fontsize=12)
ax.set_ylabel('频数', fontsize=12)
ax.set_title('异常分数分布: 正常 vs 异常 (实验#6 GDN数据)', fontsize=13, fontweight='bold')
ax.legend(fontsize=10)

plt.tight_layout()
plt.savefig('images/anomaly_score_distribution.png', dpi=150, bbox_inches='tight')
print('图2: images/anomaly_score_distribution.png')

# ═════════════════════════════════════════════
# 图3: 维度 vs F1 关系
# ═════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(7, 4))
dims = [494, 234, 234, 156, 36, 22, 36, 54]
labels = ['#1', '#2', '#3', '#4', '#5', '#6', '#7', '#8']

ax.scatter(dims, f1_scores, s=200, c=colors, edgecolors='black', linewidth=1, zorder=5)
annotate_offsets = [(0, 15), (0, 15), (0, -25), (0, 15), (0, 15), (25, 5), (-15, -25), (25, -15)]
for i, l in enumerate(labels):
    ax.annotate(f'{l}\n({dims[i]}维, F1={f1_scores[i]:.3f})',
                (dims[i], f1_scores[i]),
                textcoords="offset points",
                xytext=annotate_offsets[i],
                ha='center', fontsize=8)
ax.set_xlabel('维度数', fontsize=12)
ax.set_ylabel('F1-Score', fontsize=12)
ax.set_title('维度数 vs F1', fontsize=13, fontweight='bold')
ax.set_xlim(-50, 550)
ax.set_ylim(0, 1.1)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('images/dimension_vs_f1.png', dpi=150, bbox_inches='tight')
print('图3: images/dimension_vs_f1.png')
print('\n三张图全部生成完成!')
