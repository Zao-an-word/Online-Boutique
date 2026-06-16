import pickle, os, numpy as np, pandas as pd
from sklearn.preprocessing import MinMaxScaler

# 1. boutique only
df = pd.read_csv('../../boutique__data/k8s_metrics_round2.csv')
df = df[df['namespace'] == 'boutique']
print(f'boutique: {len(df):,} rows, {df["pod"].nunique()} pods')

# 2. Pivot
pivot = df.pivot_table(index='timestamp', columns=['metric','pod'], values='value', aggfunc='first')
pivot = pivot.sort_index()
pivot.columns = ['|'.join(str(l) for l in col) for col in pivot.columns.values]
pivot = pivot.ffill().fillna(0)
data = pivot.values.astype(np.float32)

# 3. Labels
labels_df = pd.read_csv('../../data/anomaly_labels.csv')
common = set(pivot.index) & set(labels_df['timestamp'])
pivot = pivot[pivot.index.isin(common)]
data = pivot.values.astype(np.float32)
labels_df = labels_df[labels_df['timestamp'].isin(common)].sort_values('timestamp')
labels = labels_df['is_anomaly'].values

anomaly_idx = np.where(labels == 1)[0]
print(f'Total: {len(data)}, anomalous: {len(anomaly_idx)} ({len(anomaly_idx)/len(data)*100:.1f}%)')

# 4. Smart split: train on post-fault normals, test on fault window
fault_end = anomaly_idx[-1] + 30
if fault_end >= len(data) - 200:
    fault_end = int(len(data) * 0.45)  # fallback

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
with open('processed/boutique_dim.txt', 'w') as f: f.write(str(data.shape[1]))

print(f'dim={data.shape[1]}, train={train_norm.shape}, test={test_norm.shape}')
train_anomalies = np.sum(labels[fault_end:])
print(f'train anomalies: {train_anomalies} (should be near 0)')
print(f'test anomalies: {test_labels.sum()}/{len(test_labels)} ({test_labels.sum()/len(test_labels)*100:.2f}%)')
print('done')
