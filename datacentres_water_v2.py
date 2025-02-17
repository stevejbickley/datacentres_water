##################################################
# 1) Import Packages
##################################################

import requests
import pandas as pd
import openpyxl
import json

##################################################
# 2) Define Functions
##################################################

def convert_data_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert columns in 'df' to appropriate data types before saving.
    Modify this function to match your real columns and data specs.
    """
    # 1) Numeric columns
    numeric_cols = ["coord_x", "coord_y", "gross_max_power", "m2"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # 2) List-like columns -> JSON string
    list_cols = ["cdns", "clouds", "fibres", "ixps", "networks"]
    for col in list_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: json.dumps(x) if isinstance(x, list)
                else json.dumps([]) if pd.isna(x)
                else json.dumps(x)
            )
    # 3) Boolean columns (TRUE/FALSE strings -> bool)
    bool_cols = [
        "certs_BREAAM", "certs_EUcoc", "certs_LEED",
        "certs_Other", "certs_UT_cert", "certs_UT_level"
    ]
    def parse_bool(x):
        if isinstance(x, str):
            if x.upper() == "TRUE":
                return True
            elif x.upper() == "FALSE":
                return False
        return None if not x else x
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].apply(parse_bool)
    # 4) Date/time columns (numeric timestamps in ms -> datetime)
    time_stamp_cols = ["readyForService", "construction_date"]
    for col in time_stamp_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = pd.to_datetime(df[col], unit="ms", errors="coerce")
    # 5) Date/time columns (string format -> datetime)
    #    (If you have columns like 'readyForService_dmy' or 'construction_date_dmy')
    date_str_cols = ["readyForService_dmy", "construction_date_dmy"]
    for i, col in enumerate(time_stamp_cols):
        if col in df.columns:
            col_name=date_str_cols[i]
            df[col_name] = df[col].dt.strftime("%d-%m-%Y")
    # 6) Categorical columns
    #    Adjust this list to match all text-based columns you want as categorical.
    categorical_cols = ["geometry_type", "feature_type", "company_name", "country", "name"]
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype("category")
    # 7) 'id' column as string
    if "id" in df.columns:
        df["id"] = df["id"].astype("string")
    return df

##################################################
# 3) Accessing Web Data
##################################################

url = "https://map.datacente.rs/api/geo/world"
# Note: Alternative dataset (n=5238) is available at: https://www.datacenters.com/locations

response = requests.get(url)

if response.status_code == 200:
    data = response.json()   # Parse JSON response
    print(data)
else:
    print(f"Request failed with status code {response.status_code}")

##################################################
# 3) Extracting Features/Data
##################################################

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

# 4) Convert columns to datetime (assuming milliseconds since epoch)
df["readyForService"] = pd.to_numeric(df["readyForService"], errors="coerce") # Convert from string to numeric (integers); non-numeric become NaN
df["construction_date"] = pd.to_numeric(df["construction_date"], errors="coerce")
df["readyForService_dt"] = pd.to_datetime(df["readyForService"], unit="ms", errors="coerce") # Now convert numeric values (ms since epoch) to datetime
df["construction_date_dt"] = pd.to_datetime(df["construction_date"], unit="ms", errors="coerce")

# 5) Format the date columns as dd-mm-yyyy strings
df["readyForService_dmy"] = df["readyForService_dt"].dt.strftime("%d-%m-%Y")
df["construction_date_dmy"] = df["construction_date_dt"].dt.strftime("%d-%m-%Y")

# 6) Convert all data types
df = convert_data_types(df)

# 7) Optionally, view a subset of the created DataFrame
print(df.head()) # Print top 10 rows

# 8) Optionally, save to CSV or XLSX
df.to_csv("datacenter_map_data.csv", index=False)
#df.to_excel("datacenter_map_data.xlsx", index=False)