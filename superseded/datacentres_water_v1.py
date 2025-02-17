import requests

url = "https://map.datacente.rs/api/geo/world"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()   # Parse JSON response
    print(data)
else:
    print(f"Request failed with status code {response.status_code}")

# We know the top-level JSON has a list at data['features'].
features = data["features"]

# 1) Figure out all possible top-level property keys (including certs) across all features
all_property_keys = set()
for feat in features:
    prop_dict = feat.get("properties", {})
    for key, val in prop_dict.items():
        if key == "certs" and isinstance(val, dict):
            # Flatten out the 'certs' dict keys as separate columns
            all_property_keys.update(f"certs_{k}" for k in val.keys())
        else:
            all_property_keys.add(key)

# We’ll also collect columns for geometry info
geo_cols = ["geometry_type", "coord_x", "coord_y", "feature_type"]
all_columns = list(geo_cols) + sorted(all_property_keys)

# 2) Build a "row" for each feature
rows = []
for feat in features:
    row = {}

    # Geometry data
    geom = feat.get("geometry", {})
    row["geometry_type"] = geom.get("type")  # e.g., "Point"
    coords = geom.get("coordinates", [None, None])
    # You can rename these to latitude/longitude if you prefer
    row["coord_x"] = coords[0]
    row["coord_y"] = coords[1]

    # The "type" key of the Feature itself
    row["feature_type"] = feat.get("type")

    # Properties
    prop_dict = feat.get("properties", {})
    for key, val in prop_dict.items():
        if key == "certs" and isinstance(val, dict):
            # Flatten each certificate key
            for cert_key, cert_val in val.items():
                row[f"certs_{cert_key}"] = cert_val
        else:
            row[key] = val

    # Fill missing columns with None
    for col in all_columns:
        row.setdefault(col, None)

    rows.append(row)

# 3) Create a DataFrame with every column
df = pd.DataFrame(rows, columns=all_columns)

print(df.head())

# Optionally, save to CSV
df.to_csv("datacenter_map_data.csv", index=False)