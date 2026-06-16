import pickle, os, numpy as np, pandas as pd
from sklearn.preprocessing import MinMaxScaler

# boutique + 服务聚合降维
df = pd.read_csv('../../boutique__data/k8s_metrics_round2.csv')
df = df[df['namespace'] == 'boutique']
df['service'] = df['pod'].apply(lambda x: '-'.join(x.split('-')[:-2]))

pivot = df.pivot_table(index='timestamp', columns=['metric','service'], values='value', aggfunc='mean')
pivot = pivot.sort_index()
pivot.columns = ['|'.join(str(l) for l in col) for col in pivot.columns.values]
pivot = pivot.ffill().fillna(0)
data = pivot.values.astype(np.float32)

labels_df = pd.read_csv('../../data/anomaly_labels.csv')
common = set(pivot.index) & set(labels_df['timestamp'])
pivot = pivot[pivot.index.isin(common)]
data = pivot.values.astype(np.float32)
labels_df = labels_df[labels_df['timestamp'].isin(common)].sort_values('timestamp')
labels = labels_df['is_anomaly'].values

anomaly_idx = np.where(labels == 1)[0]
n = len(data)

# 训练 = 故障前正常 + 故障后正常 合并
pre_start, pre_end = 0, anomaly_idx[0] - 50
post_start, post_end = anomaly_idx[-1] + 50, n
pre_norm = data[pre_start:pre_end]   # ~315 点
post_norm = data[post_start:post_end] # ~359 点
train_data = np.vstack([pre_norm, post_norm])

# 测试 = 故障窗口 (含前后缓冲区)
test_data = data[pre_end:post_start]
test_labels = labels[pre_end:post_start].astype(np.int32)

scaler = MinMaxScaler()
train_norm = scaler.fit_transform(train_data).astype(np.float32)
test_norm = scaler.transform(test_data).astype(np.float32)

os.makedirs('processed', exist_ok=True)
with open('processed/boutique_train.pkl', 'wb') as f: pickle.dump(train_norm, f)
with open('processed/boutique_test.pkl', 'wb') as f: pickle.dump(test_norm, f)
with open('processed/boutique_test_label.pkl', 'wb') as f: pickle.dump(test_labels, f)
with open('processed/boutique_dim.txt', 'w') as f: f.write(str(data.shape[1]))

print(f'维度: {data.shape[1]}')
print(f'训练集: {train_norm.shape} = 故障前{pre_norm.shape[0]} + 故障后{post_norm.shape[0]} (全部正常)')
print(f'测试集: {test_norm.shape}, 异常 {test_labels.sum()}/{len(test_labels)} ({test_labels.sum()/len(test_labels)*100:.1f}%)')
print('done')
