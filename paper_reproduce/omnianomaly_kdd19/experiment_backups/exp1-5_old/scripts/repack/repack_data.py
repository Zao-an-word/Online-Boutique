import pickle, os, numpy as np, pandas as pd
from sklearn.preprocessing import MinMaxScaler

df = pd.read_csv('../../boutique__data/k8s_metrics.csv')
pivot = df.pivot_table(index='timestamp', columns=['metric','pod','namespace'], values='value', aggfunc='first')
pivot = pivot.sort_index()
pivot.columns = ['|'.join(str(l) for l in col) for col in pivot.columns.values]
pivot = pivot.ffill().fillna(0)
data = pivot.values.astype(np.float32)

labels_df = pd.read_csv('../../data/anomaly_labels.csv')
labels = labels_df['is_anomaly'].values
anomaly_idx = np.where(labels == 1)[0]
fault_end = anomaly_idx[-1] + 50

test_data = data[:fault_end]
train_data = data[fault_end:]
test_labels = labels[:fault_end].astype(np.int32)

scaler = MinMaxScaler()
train_norm = scaler.fit_transform(train_data).astype(np.float32)
test_norm = scaler.transform(test_data).astype(np.float32)

os.makedirs('processed', exist_ok=True)
with open('processed/boutique_train.pkl', 'wb') as f: pickle.dump(train_norm, f)
with open('processed/boutique_test.pkl', 'wb') as f: pickle.dump(test_norm, f)
with open('processed/boutique_test_label.pkl', 'wb') as f: pickle.dump(test_labels, f)
with open('processed/boutique_dim.txt', 'w') as f: f.write(str(data.shape[1]))

print(f'train={train_norm.shape}, test={test_norm.shape}, labels={test_labels.sum()}/{len(test_labels)}')
print('done')
