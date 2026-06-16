#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""为 OmniAnomaly 实验报告生成 5 张图片"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pickle
import os

# 中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = 'images'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════
# 9 组实验数据 (来源: EXPERIMENT_LOG.md)
# ═══════════════════════════════════════════════════════
EXP = {
    'names':  ['#1\n基线', '#2\n降维', '#3\n强故障', '#4\n聚合', '#5\n精选特征',
               '#6\nGDN数据', '#7\n降维优化', '#8\n去噪', '#9\n新管线'],
    'f1':     [0.112, 0.109, 0.553, 0.496, 0.589, 0.968, 0.487, 0.472, 0.786],
    'prec':   [0.059, 0.058, 0.383, 0.330, 0.457, 0.937, 0.324, 0.309, 0.704],
    'recall': [1.000, 1.000, 1.000, 1.000, 0.832, 1.000, 0.985, 1.000, 0.891],
    'dims':   [494, 234, 234, 156, 36, 22, 36, 54, 22],
    'train':  [3223, 3220, 201, 674, 674, 61, 379, 379, 637],
}

# 窗口长度扫描 (实验 #9 子实验)
WINDOW_SWEEP = {
    'w5':  0.600,
    'w10': 0.616,
    'w20': 0.643,
    'w28': 0.692,
    'w30': 0.786,
    'w40': 0.762,
}

# 加载当前模型数据
TEST_SCORE = pickle.load(open('result/test_score.pkl', 'rb'))
TEST_LABEL = pickle.load(open('processed/boutique_test_label.pkl', 'rb'))
TRAIN_SCORE = pickle.load(open('result/train_score.pkl', 'rb'))

# 对齐 test_score 和 test_label (label 比 score 多 window_length 个)
MIN_LEN = min(len(TEST_SCORE), len(TEST_LABEL))
TEST_SCORE_ALIGNED = TEST_SCORE[:MIN_LEN]
TEST_LABEL_ALIGNED = TEST_LABEL[:MIN_LEN]

# 分离正常/异常分数
NORMAL_SCORES = TEST_SCORE_ALIGNED[TEST_LABEL_ALIGNED == 0]
ANOMALY_SCORES = TEST_SCORE_ALIGNED[TEST_LABEL_ALIGNED == 1]

print(f"数据加载完成: test_score={len(TEST_SCORE)}, test_label={len(TEST_LABEL)}, "
      f"aligned={MIN_LEN}, normal={len(NORMAL_SCORES)}, anomaly={len(ANOMALY_SCORES)}")

# ═══════════════════════════════════════════════════════
# 图 1: 9 组实验 F1/Precision/Recall 对比
# ═══════════════════════════════════════════════════════
print("生成图1...")
fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))

x = np.arange(len(EXP['names']))
colors_bar = ['#d4d4d4', '#d4d4d4', '#a8d8ea', '#7ec8e3', '#3b8ed0',
              '#e74c3c', '#f39c12', '#95a5a6', '#FFD700']  # #9 金色高亮

# 子图1: F1 变化趋势
bars = axes[0].bar(x, EXP['f1'], color=colors_bar, edgecolor='black', linewidth=0.5)
axes[0].set_xticks(x)
axes[0].set_xticklabels(EXP['names'], fontsize=8)
axes[0].set_ylabel('F1-Score', fontsize=12)
axes[0].set_title('9 组实验 F1 渐进变化趋势', fontsize=14, fontweight='bold')
axes[0].set_ylim(0, 1.12)
# 添加数值标签
for i, v in enumerate(EXP['f1']):
    color = 'black' if i != 8 else '#B8860B'
    weight = 'bold' if i in [5, 8] else 'normal'
    axes[0].text(i, v + 0.02, f'{v:.3f}', ha='center', fontsize=9, fontweight=weight, color=color)
# 添加箭头标注
axes[0].annotate('★ 最佳\n真实数据', xy=(8, 0.786), xytext=(7.2, 0.92),
                fontsize=8, color='#B8860B', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#B8860B', lw=1.5))
axes[0].annotate('★ 最佳\n理想数据', xy=(5, 0.968), xytext=(3.5, 1.02),
                fontsize=8, color='#c0392b', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#c0392b', lw=1.5))

# 子图2: Precision & Recall 分组柱状图
width = 0.35
colors_prec = ['#e74c3c'] * 9
colors_rec = ['#2ecc71'] * 9
axes[1].bar(x - width/2, EXP['prec'], width, label='Precision', color='#e74c3c',
            edgecolor='black', linewidth=0.5)
axes[1].bar(x + width/2, EXP['recall'], width, label='Recall', color='#2ecc71',
            edgecolor='black', linewidth=0.5)
axes[1].set_xticks(x)
axes[1].set_xticklabels(EXP['names'], fontsize=8)
axes[1].set_ylabel('Score', fontsize=12)
axes[1].set_title('9 组实验 Precision & Recall 对比', fontsize=14, fontweight='bold')
axes[1].set_ylim(0, 1.15)
axes[1].legend(fontsize=10, loc='lower left')
for i in range(len(x)):
    axes[1].text(i - width/2, EXP['prec'][i] + 0.02, f'{EXP["prec"][i]:.1%}',
                ha='center', fontsize=7, rotation=90)
    axes[1].text(i + width/2, EXP['recall'][i] + 0.02, f'{EXP["recall"][i]:.1%}',
                ha='center', fontsize=7, rotation=90)

plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/fig1_experiments_comparison.png', dpi=200, bbox_inches='tight')
plt.close()
print("  -> fig1_experiments_comparison.png")

# ═══════════════════════════════════════════════════════
# 图 2: 维度 vs F1 散点图
# ═══════════════════════════════════════════════════════
print("生成图2...")
fig, ax = plt.subplots(figsize=(9, 5.5))

scatter_colors = ['#d4d4d4', '#d4d4d4', '#a8d8ea', '#7ec8e3', '#3b8ed0',
                  '#e74c3c', '#f39c12', '#95a5a6', '#FFD700']
edge_colors = ['black'] * 8 + ['#B8860B']
linewidths = [0.8] * 8 + [2.0]
sizes = [150] * 8 + [280]

for i in range(9):
    ax.scatter(EXP['dims'][i], EXP['f1'][i], s=sizes[i], c=scatter_colors[i],
               edgecolors=edge_colors[i], linewidth=linewidths[i], zorder=5)

# 标注
offsets = [(5, 15), (5, 15), (5, -22), (5, 15), (5, 15), (-40, 12),
           (-15, -22), (20, -18), (12, -20)]
for i, (lbl, dim, f1) in enumerate(zip(EXP['names'], EXP['dims'], EXP['f1'])):
    name_clean = lbl.replace('\n', ' ')
    ax.annotate(f'{name_clean}\n({dim}维, F1={f1:.3f})',
                (dim, f1), textcoords="offset points", xytext=offsets[i],
                ha='center', fontsize=7.5,
                fontweight='bold' if i in [5, 8] else 'normal',
                color='#B8860B' if i == 8 else ('#c0392b' if i == 5 else 'black'))

# 趋势线（排除 #6 人造数据异常值）
real_idx = [i for i in range(9) if i != 5]
z = np.polyfit([EXP['dims'][i] for i in real_idx], [EXP['f1'][i] for i in real_idx], 2)
x_smooth = np.linspace(20, 520, 200)
y_smooth = np.polyval(z, x_smooth)
ax.plot(x_smooth, y_smooth, '--', color='#7f8c8d', alpha=0.6, linewidth=1.5, label='趋势线 (不含#6)')

ax.set_xlabel('特征维度数', fontsize=12)
ax.set_ylabel('F1-Score', fontsize=12)
ax.set_title('特征维度 vs F1 — 降维是提升检测效果的关键', fontsize=14, fontweight='bold')
ax.set_xlim(-30, 560)
ax.set_ylim(0, 1.08)
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# 添加区域标注
ax.axvspan(0, 50, alpha=0.06, color='green', label='_nolegend_')
ax.text(25, 0.04, '精选区\n(22-54维)', ha='center', fontsize=8, color='green', fontweight='bold')
ax.axvspan(100, 300, alpha=0.06, color='orange')
ax.text(200, 0.04, '过渡区\n(156-234维)', ha='center', fontsize=8, color='orange', fontweight='bold')
ax.axvspan(400, 520, alpha=0.06, color='red')
ax.text(460, 0.04, '原始区\n(494维)', ha='center', fontsize=8, color='red', fontweight='bold')

plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/fig2_dimension_vs_f1.png', dpi=200, bbox_inches='tight')
plt.close()
print("  -> fig2_dimension_vs_f1.png")

# ═══════════════════════════════════════════════════════
# 图 3: 异常分数分布 — 正常 vs 异常 (实验 #9)
# ═══════════════════════════════════════════════════════
print("生成图3...")
fig, ax = plt.subplots(figsize=(10, 5.5))

# 限制分数范围以看得更清楚 (裁剪极端值)
score_min = np.percentile(TEST_SCORE_ALIGNED, 1)
score_max = np.percentile(TEST_SCORE_ALIGNED, 99)
normal_clipped = NORMAL_SCORES[(NORMAL_SCORES >= score_min) & (NORMAL_SCORES <= score_max)]
anomaly_clipped = ANOMALY_SCORES[(ANOMALY_SCORES >= score_min) & (ANOMALY_SCORES <= score_max)]

bins = np.linspace(score_min, score_max, 60)
ax.hist(normal_clipped, bins=bins, alpha=0.65, label=f'正常窗口 (n={len(NORMAL_SCORES)})',
        color='#2ecc71', edgecolor='black', linewidth=0.3)
ax.hist(anomaly_clipped, bins=bins, alpha=0.75, label=f'异常窗口 (n={len(ANOMALY_SCORES)})',
        color='#e74c3c', edgecolor='black', linewidth=0.3)

# 标注阈值 (Best-F1 threshold from result.json)
threshold = 8.0  # from result.json
ax.axvline(x=threshold, color='#f39c12', linestyle='--', linewidth=2.5,
           label=f'Best-F1 阈值 ({threshold})')

ax.set_xlabel('Anomaly Score', fontsize=12)
ax.set_ylabel('频数', fontsize=12)
ax.set_title('异常分数分布 (实验 #9, F1=0.786): 正常 vs 异常', fontsize=14, fontweight='bold')
ax.legend(fontsize=10)

# 添加统计信息文本框
stats_text = (f'正常: mean={NORMAL_SCORES.mean():.1f}, std={NORMAL_SCORES.std():.1f}\n'
              f'异常: mean={ANOMALY_SCORES.mean():.1f}, std={ANOMALY_SCORES.std():.1f}\n'
              f'分离度 (Cohen\'s d) = {abs(NORMAL_SCORES.mean() - ANOMALY_SCORES.mean()) / np.sqrt((NORMAL_SCORES.var() + ANOMALY_SCORES.var())/2):.2f}')
ax.text(0.02, 0.95, stats_text, transform=ax.transAxes, fontsize=9,
        verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/fig3_score_distribution.png', dpi=200, bbox_inches='tight')
plt.close()
print("  -> fig3_score_distribution.png")

# ═══════════════════════════════════════════════════════
# 图 4: 异常分数时序图 (实验 #9)
# ═══════════════════════════════════════════════════════
print("生成图4...")
fig, ax = plt.subplots(figsize=(14, 5))

timesteps = np.arange(MIN_LEN)
is_anomaly = TEST_LABEL_ALIGNED

# 背景色标注故障时段
in_attack = False
attack_start = 0
for i in range(MIN_LEN):
    if is_anomaly[i] and not in_attack:
        attack_start = i
        in_attack = True
    elif not is_anomaly[i] and in_attack:
        ax.axvspan(attack_start, i, alpha=0.12, color='red')
        in_attack = False
if in_attack:
    ax.axvspan(attack_start, MIN_LEN, alpha=0.12, color='red')

# 正常点和异常点分别画
normal_idx = np.where(is_anomaly == 0)[0]
anomaly_idx = np.where(is_anomaly == 1)[0]

ax.scatter(normal_idx, TEST_SCORE_ALIGNED[normal_idx], c='#2ecc71', s=12, alpha=0.6,
           label=f'正常 (n={len(normal_idx)})', zorder=5)
ax.scatter(anomaly_idx, TEST_SCORE_ALIGNED[anomaly_idx], c='#e74c3c', s=20, alpha=0.8,
           label=f'异常 (n={len(anomaly_idx)})', zorder=5, marker='^')

# 阈值线
ax.axhline(y=threshold, color='#f39c12', linestyle='--', linewidth=2,
           label=f'阈值={threshold}')

# 标注训练集得分范围作为参考
train_mean = TRAIN_SCORE.mean()
train_std = TRAIN_SCORE.std()
ax.axhline(y=train_mean, color='#3498db', linestyle=':', linewidth=1.5, alpha=0.7,
           label=f'训练集均值={train_mean:.1f}')

ax.set_xlabel('测试窗口序号', fontsize=12)
ax.set_ylabel('Anomaly Score', fontsize=12)
ax.set_title('异常分数时序图 (实验 #9, 窗口长度=30)', fontsize=14, fontweight='bold')
ax.legend(fontsize=9, loc='upper left', ncol=2)

# 裁剪 Y 轴以看得更清楚
y_bottom = max(TEST_SCORE_ALIGNED.min(), np.percentile(TEST_SCORE_ALIGNED, 0.5))
y_top = min(TEST_SCORE_ALIGNED.max(), np.percentile(TEST_SCORE_ALIGNED, 99.5)) + 5
ax.set_ylim(y_bottom - 5, y_top)

ax.grid(True, alpha=0.25)

plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/fig4_score_timeline.png', dpi=200, bbox_inches='tight')
plt.close()
print("  -> fig4_score_timeline.png")

# ═══════════════════════════════════════════════════════
# 图 5: 窗口长度超参数搜索 (实验 #9)
# ═══════════════════════════════════════════════════════
print("生成图5...")
fig, ax = plt.subplots(figsize=(9, 5))

win_names = list(WINDOW_SWEEP.keys())
win_values = [int(w.replace('w', '')) for w in win_names]
win_f1 = [WINDOW_SWEEP[w] for w in win_names]

# 排序
sorted_idx = np.argsort(win_values)
win_names_sorted = [win_names[i] for i in sorted_idx]
win_values_sorted = [win_values[i] for i in sorted_idx]
win_f1_sorted = [win_f1[i] for i in sorted_idx]

# 颜色渐变
colors_win = ['#3498db' if f1 != max(win_f1_sorted) else '#FFD700' for f1 in win_f1_sorted]
edge_colors_win = ['#2980b9' if f1 != max(win_f1_sorted) else '#B8860B' for f1 in win_f1_sorted]

bars = ax.bar(win_names_sorted, win_f1_sorted, color=colors_win, edgecolor=edge_colors_win,
              linewidth=1.5, width=0.6)

# 数值标签
for bar, f1, wl in zip(bars, win_f1_sorted, win_values_sorted):
    height = bar.get_height()
    color = '#B8860B' if f1 == max(win_f1_sorted) else '#2c3e50'
    weight = 'bold' if f1 == max(win_f1_sorted) else 'normal'
    ax.text(bar.get_x() + bar.get_width()/2., height + 0.008,
            f'{f1:.3f}', ha='center', fontsize=11, fontweight=weight, color=color)

# 添加论文默认窗口标注
ax.axhline(y=0.600, color='#e74c3c', linestyle='--', linewidth=1.2, alpha=0.7)
ax.text(4.5, 0.608, '论文默认 w5 (F1=0.600)', fontsize=8, color='#e74c3c', ha='right')

ax.set_xlabel('窗口长度', fontsize=12)
ax.set_ylabel('F1-Score', fontsize=12)
ax.set_title('窗口长度超参数搜索 (实验 #9)', fontsize=14, fontweight='bold')
ax.set_ylim(0.55, 0.84)
ax.grid(True, alpha=0.25, axis='y')

# 添加箭头标注最佳
best_idx = win_f1_sorted.index(max(win_f1_sorted))
ax.annotate(f'最佳: w30\nF1={max(win_f1_sorted):.3f}\n(提升 +18.6pp vs w5)',
            xy=(best_idx, max(win_f1_sorted)),
            xytext=(best_idx + 0.8, max(win_f1_sorted) + 0.04),
            fontsize=9, color='#B8860B', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#B8860B', lw=1.5))

plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/fig5_window_sweep.png', dpi=200, bbox_inches='tight')
plt.close()
print("  -> fig5_window_sweep.png")

print("\n✅ 5 张图片全部生成完成! 输出目录: images/")
print("   fig1_experiments_comparison.png  — 9组实验 F1/Precision/Recall 对比")
print("   fig2_dimension_vs_f1.png         — 维度 vs F1 散点图")
print("   fig3_score_distribution.png      — 异常分数分布 (实验#9)")
print("   fig4_score_timeline.png          — 异常分数时序图 (实验#9)")
print("   fig5_window_sweep.png            — 窗口长度超参数搜索")
