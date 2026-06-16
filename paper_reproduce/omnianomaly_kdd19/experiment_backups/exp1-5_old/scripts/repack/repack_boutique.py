import pickle, os, numpy as np, pandas as pd
from sklearn.preprocessing import MinMaxScaler

# 1. 只加载 boutique 命名空间
df = pd.read_csv('../../boutique__data/k8s_metrics.csv')
df = df[df['namespace'] == 'boutique']
print(f'boutique only: {len(df)} 行, pods: {sorted(df["pod"].unique())}')

# 2. Pivot
pivot = df.pivot_table(index='timestamp', columns=['metric','pod'], values='value', aggfunc='first')
pivot = pivot.sort_index()
pivot.columns = ['|'.join(str(l) for l in col) for col in pivot.columns.values]
pivot = pivot.ffill().fillna(0)
data = pivot.values.astype(np.float32)
n_dims = data.shape[1]

# 3. 标签（需要对齐时间戳）
labels_df = pd.read_csv('../../data/anomaly_labels.csv')
# 只取 pivot 中有对应的时间戳
common_ts = set(pivot.index) & set(labels_df['timestamp'])
pivot_filtered = pivot[pivot.index.isin(common_ts)]
data = pivot_filtered.values.astype(np.float32)
labels_df = labels_df[labels_df['timestamp'].isin(common_ts)].sort_values('timestamp')
labels = labels_df['is_anomaly'].values

# 4. 智能分割（异常放测试集）
anomaly_idx = np.where(labels == 1)[0]
fault_end = anomaly_idx[-1] + 50
test_data = data[:fault_end]; train_data = data[fault_end:]
test_labels = labels[:fault_end].astype(np.int32)

# 5. 归一化
scaler = MinMaxScaler()
train_norm = scaler.fit_transform(train_data).astype(np.float32)
test_norm = scaler.transform(test_data).astype(np.float32)

# 6. 保存
os.makedirs('processed', exist_ok=True)
with open('processed/boutique_train.pkl', 'wb') as f: pickle.dump(train_norm, f)
with open('processed/boutique_test.pkl', 'wb') as f: pickle.dump(test_norm, f)
with open('processed/boutique_test_label.pkl', 'wb') as f: pickle.dump(test_labels, f)
with open('processed/boutique_dim.txt', 'w') as f: f.write(str(n_dims))

print(f'维度: {n_dims}, train={train_norm.shape}, test={test_norm.shape}')
print(f'测试集异常: {test_labels.sum()}/{len(test_labels)} ({test_labels.sum()/len(test_labels)*100:.2f}%)')
print('done')
