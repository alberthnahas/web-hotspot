# =========================================================================
# FIRMS Hotspot Processor for Indonesia (Single CSV Output)
#
# This script performs the following actions:
# 1. Determines yesterday's date to download the relevant hotspot data.
# 2. Downloads active fire data (MODIS, VIIRS) to the local directory.
# 3. Filters the data to retain only high-confidence hotspots.
# 4. Uses Indonesian provincial boundaries from a single GeoJSON file to
#    spatially filter for hotspots located within Indonesia.
# 5. Formats the filtered data into the specified columns.
# 6. Appends the new data to a master archive file: archived_hotspot_idn.csv
# 7. Removes the temporary downloaded source files after processing.
# =========================================================================

import os
import glob
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import datetime
import warnings

# Suppress irrelevant warnings for a cleaner output
warnings.simplefilter("ignore")

# =========================================================================
# SECTION A: Downloading Yesterday's Hotspot Data
# =========================================================================

# 1. NASA Earthdata Authorization Token
# IMPORTANT: Replace with your own valid token from https://urs.earthdata.nasa.gov/
token = ("Authorization: Bearer eyJ0eXAiOiJKV1QiLCJvcmlnaW4iOiJFYXJ0aGRhdGEgTG9naW4iLCJzaWciOiJlZGxqd3RwdWJrZXlfb3BzIiwiYWxnIjoiUlMyNTYifQ.eyJ0eXBlIjoiVXNlciIsInVpZCI6ImFsYmVydGgubmFoYXMiLCJleHAiOjE3NTg3MDA4NzUsImlhdCI6MTc1MzUxNjg3NSwiaXNzIjoiaHR0cHM6Ly91cnMuZWFydGhkYXRhLm5hc2EuZ292IiwiaWRlbnRpdHlfcHJvdmlkZXIiOiJlZGxfb3BzIiwiYWNyIjoiZWRsIiwiYXNzdXJhbmNlX2xldmVsIjozfQ.MxUjNKRKRQciNXQGJeZu8gcQEWpxcrqXzVYrFV7jOsgDbmWlqzXUsvDBnuYeSOzmMRGtG1YA19z-jS5oPK5uBwI-NCgS1Dn3xrK-Gu97aPJE0XBCw4Z06KPoQYe1YLIof8meAOislwPPqmH-WYjlYjVKJHLKD_X3rWH4_QS0HqhWmr8y_HSCcgu-Be3DvMBUvLft70Jf96YiPrQJSChY5-cJpbWIV3QCamni4oIErnZVU-glvtCZApdAIYgDy0eZr4QoG-SIeIDN_NEMF4HUoIv37wV05koAkV5It0jcIM2CjPG2zWHyGRs6-AuET1UiQbtDWJAJ0c5qfRp5QiNaGQ")

# 2. Define Date for Download (Yesterday)
yesterday = datetime.date.today() - datetime.timedelta(days=1)
year = yesterday.strftime("%Y")
julianday = yesterday.strftime("%j")  # Day of the year (001-366)

print(f"Preparing to download data for yesterday: {yesterday} (Year: {year}, Julian Day: {julianday})")

# 3. Define Data Sources and URL Templates
sources = {
    "modis": f"https://nrt3.modaps.eosdis.nasa.gov/archive/FIRMS/modis-c6.1/Global/MODIS_C6_1_Global_MCD14DL_NRT_{year}{julianday}.txt",
    "noaa20": f"https://nrt3.modaps.eosdis.nasa.gov/archive/FIRMS/noaa-20-viirs-c2/Global/J1_VIIRS_C2_Global_VJ114IMGTDL_NRT_{year}{julianday}.txt",
    "noaa21": f"https://nrt3.modaps.eosdis.nasa.gov/archive/FIRMS/noaa-21-viirs-c2/Global/J2_VIIRS_C2_Global_VJ214IMGTDL_NRT_{year}{julianday}.txt",
    "suomi": f"https://nrt3.modaps.eosdis.nasa.gov/archive/FIRMS/suomi-npp-viirs-c2/Global/SUOMI_VIIRS_C2_Global_VNP14IMGTDL_NRT_{year}{julianday}.txt"
}

# 4. Download Data to the Local Directory
downloaded_files = []
for src, file_url in sources.items():
    print(f"\n--- Downloading file for source: {src} ---")
    print(f"URL: {file_url}")
    # Download to the current directory (no -P option)
    os.system(f'wget -e robots=off -np -R .html,.tmp -nH --cut-dirs=3 "{file_url}" --header "{token}"')
    # Keep track of the downloaded filename for processing and later cleanup
    local_filename = os.path.basename(file_url)
    downloaded_files.append(local_filename)

print(f"\n--- Download process completed for {yesterday} ---")


# =========================================================================
# SECTION B: Data Loading and Filtering for High Confidence Hotspots
# =========================================================================

print(f"\nProcessing {len(downloaded_files)} downloaded files.")

dataframes = []
for file in downloaded_files:
    if not os.path.exists(file) or os.path.getsize(file) == 0:
        print(f"Skipping empty or non-existent file: {file}")
        continue
    try:
        df = pd.read_csv(file)
        print(f"Processing file: {file} with {len(df)} rows.")
    except Exception as e:
        print(f"Error reading {file}: {e}")
        continue

    filename = os.path.basename(file).upper()
    df_high = pd.DataFrame()

    if "MODIS" in filename:
        df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce')
        df_high = df[df['confidence'] > 80].copy()
    elif "J1_VIIRS" in filename or "J2_VIIRS" in filename or "SUOMI" in filename:
        df['confidence'] = df['confidence'].astype(str)
        df_high = df[df['confidence'].str.strip().str.lower() == 'high'].copy()

    if not df_high.empty:
        print(f"  -> Found {df_high.shape[0]} high confidence rows.")
        dataframes.append(df_high)

if dataframes:
    df_all = pd.concat(dataframes, ignore_index=True)
    print(f"\nTotal high confidence rows compiled: {len(df_all)}")
else:
    print("\nNo high confidence hotspots found in any of the downloaded files.")
    df_all = pd.DataFrame()


# =========================================================================
# SECTION C: Geospatial Filtering for Indonesia
# =========================================================================

if not df_all.empty:
    # Convert date column and create GeoDataFrame
    df_all['acq_date'] = pd.to_datetime(df_all['acq_date'])
    geometry = [Point(xy) for xy in zip(df_all['longitude'], df_all['latitude'])]
    gdf_hotspots = gpd.GeoDataFrame(df_all, geometry=geometry, crs="EPSG:4326")
    print(f"Created GeoDataFrame with {len(gdf_hotspots)} high-confidence hotspots.")

    # Load Indonesian provincial boundaries
    prov_geojson_path = 'indonesia_38prov.geojson'
    try:
        gdf_prov = gpd.read_file(prov_geojson_path)
        print("Successfully loaded Indonesian province GeoJSON file.")
        
        # Ensure CRS match for spatial operations
        gdf_prov = gdf_prov.to_crs(gdf_hotspots.crs)
        
        # Spatially join hotspots with provinces to filter for Indonesia
        print("Filtering hotspots within Indonesian provincial boundaries...")
        gdf_hotspots_idn = gpd.sjoin(gdf_hotspots, gdf_prov, how="inner", predicate='within')
        print(f"Found {len(gdf_hotspots_idn)} hotspots within Indonesia.")

    except Exception as e:
        print(f"\nERROR loading GeoJSON file: {e}")
        print(f"Please ensure '{prov_geojson_path}' is present in the script's directory.")
        gdf_hotspots_idn = gpd.GeoDataFrame() # Create empty dataframe to prevent further errors
else:
    gdf_hotspots_idn = gpd.GeoDataFrame()


# =========================================================================
# SECTION D: Formatting and Appending to Master Archive
# =========================================================================

if not gdf_hotspots_idn.empty:
    print("\nFormatting data for final output...")
    
    # Create a new DataFrame with the specified columns
    output_df = pd.DataFrame()
    output_df['lat'] = gdf_hotspots_idn['latitude']
    output_df['lon'] = gdf_hotspots_idn['longitude']
    output_df['month'] = gdf_hotspots_idn['acq_date'].dt.month
    output_df['day'] = gdf_hotspots_idn['acq_date'].dt.day
    output_df['year'] = gdf_hotspots_idn['acq_date'].dt.year
    output_df['confidence'] = 1 # Set confidence to 1 for all rows

    # Define the path for the master archive file
    archive_csv_path = 'archived_hotspot_idn.csv'

    # Check if the archive file already exists to decide whether to write a header
    file_exists = os.path.exists(archive_csv_path)

    # Append the new data to the master archive file
    # Use mode='a' for append, and write header only if the file is new
    output_df.to_csv(archive_csv_path, mode='a', header=not file_exists, index=False)
    
    if file_exists:
        print(f"\nSuccessfully appended {len(output_df)} new hotspots to '{archive_csv_path}'")
    else:
        print(f"\nCreated new archive and saved {len(output_df)} hotspots to '{archive_csv_path}'")
    
    print("Preview of the new data that was added:")
    print(output_df.head())

else:
    print("\nProcessing finished. No hotspots were found within Indonesia for yesterday.")

# =========================================================================
# SECTION E: Cleaning Up Downloaded Files
# =========================================================================

print("\n--- Cleaning up downloaded source files ---")
for file_to_delete in downloaded_files:
    try:
        if os.path.exists(file_to_delete):
            os.remove(file_to_delete)
            print(f"Removed: {file_to_delete}")
    except OSError as e:
        print(f"Error removing file {file_to_delete}: {e}")

print("\n--- Script finished ---")

