import pickle, os, numpy as np, pandas as pd
from sklearn.preprocessing import MinMaxScaler

# 1. boutique only
df = pd.read_csv('../../boutique__data/k8s_metrics_round2.csv')
df = df[df['namespace'] == 'boutique']

# 2. 降维: 把 Pod 名聚合成服务名 (去除 ReplicaSet+Pod hash)
#    cartservice-546c548494-cb4lb → cartservice
#    redis-cart-6899b65948-ms767 → redis-cart
df['service'] = df['pod'].apply(lambda x: '-'.join(x.split('-')[:-2]))

before_pods = df['pod'].nunique()
after_svcs = df['service'].nunique()
print(f'Pod降维: {before_pods} pods → {after_svcs} services')

# 3. Pivot by (metric, service) — 均值聚合同一服务的多个副本
pivot = df.pivot_table(
    index='timestamp',
    columns=['metric', 'service'],
    values='value',
    aggfunc='mean'
)
pivot = pivot.sort_index()
pivot.columns = ['|'.join(str(l) for l in col) for col in pivot.columns.values]
pivot = pivot.ffill().fillna(0)
data = pivot.values.astype(np.float32)
n_dims = data.shape[1]

# 4. Labels
labels_df = pd.read_csv('../../data/anomaly_labels.csv')
common = set(pivot.index) & set(labels_df['timestamp'])
pivot = pivot[pivot.index.isin(common)]
data = pivot.values.astype(np.float32)
labels_df = labels_df[labels_df['timestamp'].isin(common)].sort_values('timestamp')
labels = labels_df['is_anomaly'].values
anomaly_idx = np.where(labels == 1)[0]

print(f'总: {len(data)}, 异常: {len(anomaly_idx)} ({len(anomaly_idx)/len(data)*100:.1f}%)')
print(f'维度: {n_dims}')

# 5. Smart split
fault_end = anomaly_idx[-1] + 30
if fault_end >= len(data) - 200:
    fault_end = int(len(data) * 0.4)

train_data = data[fault_end:]
test_data = data[:fault_end]
test_labels = labels[:fault_end].astype(np.int32)

scaler = MinMaxScaler()
train_norm = scaler.fit_transform(train_data).astype(np.float32)
test_norm = scaler.transform(test_data).astype(np.float32)

os.makedirs('processed', exist_ok=True)
with open('processed/boutique_train.pkl', 'wb') as f: pickle.dump(train_norm, f)
with open('processed/boutique_test.pkl', 'wb') as f: pickle.dump(test_norm, f)
with open('processed/boutique_test_label.pkl', 'wb') as f: pickle.dump(test_labels, f)
with open('processed/boutique_dim.txt', 'w') as f: f.write(str(n_dims))

print(f'train={train_norm.shape}, test={test_norm.shape}')
print(f'test anomalies: {test_labels.sum()}/{len(test_labels)} ({test_labels.sum()/len(test_labels)*100:.2f}%)')
print('done')
