import os
import json
import pandas as pd

os.makedirs('data', exist_ok=True)

df = pd.read_csv('rawdata/Dinesafe.csv', encoding='utf-8', low_memory=False)

# One row per unique inspection event (estId + date + status)
unique_inspections = df[['estId', 'inspectionDate', 'inspectionStatus']].drop_duplicates()

status_counts = unique_inspections.groupby('estId').agg(
    pass_count=('inspectionStatus', lambda x: (x == 'Pass').sum()),
    conditional_count=('inspectionStatus', lambda x: (x == 'Conditional Pass').sum()),
    closed_count=('inspectionStatus', lambda x: (x == 'Closed').sum()),
)

est_info = df.groupby('estId').agg(
    estName=('estName', 'first'),
    address=('address', 'first'),
    latitude=('latitude', 'first'),
    longitude=('longitude', 'first'),
    lastInspection=('inspectionDate', 'max'),
).reset_index()

result = est_info.merge(status_counts, on='estId')
result['worstStatus'] = result.apply(
    lambda r: 'Closed' if r['closed_count'] > 0
    else ('Conditional Pass' if r['conditional_count'] > 0 else 'Pass'),
    axis=1,
)

result['latitude'] = pd.to_numeric(result['latitude'], errors='coerce')
result['longitude'] = pd.to_numeric(result['longitude'], errors='coerce')
result = result.dropna(subset=['latitude', 'longitude'])

features = []
for _, row in result.iterrows():
    features.append({
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [row['longitude'], row['latitude']]},
        'properties': {
            'estName': row['estName'],
            'address': row['address'],
            'worstStatus': row['worstStatus'],
            'pass_count': int(row['pass_count']),
            'conditional_count': int(row['conditional_count']),
            'closed_count': int(row['closed_count']),
            'lastInspection': str(row['lastInspection']),
        }
    })

geojson = {'type': 'FeatureCollection', 'features': features}
with open('data/establishments.json', 'w', encoding='utf-8') as f:
    json.dump(geojson, f, separators=(',', ':'), ensure_ascii=False)

print(f"Written {len(features)} establishments to data/establishments.json")
worst_counts = result['worstStatus'].value_counts()
print(worst_counts.to_string())
