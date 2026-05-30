import io
import json
import os
import requests
import pandas as pd

os.makedirs('data', exist_ok=True)

BASE_URL = "https://ckan0.cf.opendata.inter.prod-toronto.ca"

package = requests.get(
    BASE_URL + "/api/3/action/package_show",
    params={"id": "dinesafe"},
    timeout=30,
).json()

resource_id = next(
    r["id"] for r in package["result"]["resources"] if r["datastore_active"]
)

print(f"Fetching resource {resource_id}...")
response = requests.get(
    BASE_URL + "/datastore/dump/" + resource_id,
    timeout=120,
)
response.raise_for_status()

df = pd.read_csv(io.BytesIO(response.content), low_memory=False)

df = df.rename(columns={
    "Establishment ID": "estId",
    "Establishment Name": "estName",
    "Address": "address",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Inspection Date": "inspectionDate",
    "Establishment Status": "inspectionStatus",
})

print(f"Loaded {len(df)} rows")

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
