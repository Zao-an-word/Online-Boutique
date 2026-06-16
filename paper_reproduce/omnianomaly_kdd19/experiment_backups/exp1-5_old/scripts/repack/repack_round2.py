import pickle, os, numpy as np, pandas as pd
from sklearn.preprocessing import MinMaxScaler

# 1. 只加载 boutique 命名空间
df = pd.read_csv('../../boutique__data/k8s_metrics_round2.csv')
df = df[df['namespace'] == 'boutique']
print(f'boutique: {len(df)} 行, {df["pod"].nunique()} pods')

# 2. Pivot
pivot = df.pivot_table(index='timestamp', columns=['metric','pod'], values='value', aggfunc='first')
pivot = pivot.sort_index()
pivot.columns = ['|'.join(str(l) for l in col) for col in pivot.columns.values]
pivot = pivot.ffill().fillna(0)
data = pivot.values.astype(np.float32)

# 3. 标签对齐
labels_df = pd.read_csv('../../data/anomaly_labels.csv')
common_ts = set(pivot.index) & set(labels_df['timestamp'])
pivot = pivot[pivot.index.isin(common_ts)]
data = pivot.values.astype(np.float32)
labels_df = labels_df[labels_df['timestamp'].isin(common_ts)].sort_values('timestamp')
labels = labels_df['is_anomaly'].values

anomaly_idx = np.where(labels == 1)[0]
print(f'总点: {len(data)}, 异常: {len(anomaly_idx)} ({len(anomaly_idx)/len(data)*100:.1f}%)')

# 4. 分割: 训练 = 故障结束后 → 末尾 (纯正常)
#         测试 = 开头 → 故障结束 (含全部异常)
fault_end = anomaly_idx[-1] + 15
if fault_end >= len(data) - 30:
    # 故障覆盖到末尾，取前60%训练，后40%测试
    fault_end = int(len(data) * 0.4)

train_data = data[fault_end:]
test_data = data[:fault_end]
test_labels = labels[:fault_end].astype(np.int32)

print(f'train: {train_data.shape}, test: {test_data.shape}')
print(f'test内异常: {test_labels.sum()}/{len(test_labels)}')

scaler = MinMaxScaler()
train_norm = scaler.fit_transform(train_data).astype(np.float32)
test_norm = scaler.transform(test_data).astype(np.float32)

os.makedirs('processed', exist_ok=True)
with open('processed/boutique_train.pkl', 'wb') as f: pickle.dump(train_norm, f)
with open('processed/boutique_test.pkl', 'wb') as f: pickle.dump(test_norm, f)
with open('processed/boutique_test_label.pkl', 'wb') as f: pickle.dump(test_labels, f)
with open('processed/boutique_dim.txt', 'w') as f: f.write(str(data.shape[1]))
print(f'dim={data.shape[1]}, done')
