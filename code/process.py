import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
from matplotlib.patches import Rectangle
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg
import datetime
import os
import sys

# === Set working directory ===
# Ensures the script looks for files in its own directory
os.chdir(os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.path.expanduser("./"))

# =======================================================
# === Automated Data Download (New Section) ===
# =======================================================

# 1. Calculate yesterday's date
yesterday = datetime.date.today() - datetime.timedelta(days=1)
url_date_path = yesterday.strftime("%Y/%m/%d")
file_date_part = yesterday.strftime("%Y%m%d")

# 2. Construct the FTP URL and wget command
ftp_url = f"ftp://202.90.199.64/himawari6/Hotspot/data/{url_date_path}/Hotspot_{file_date_part}.txt"
# IMPORTANT: The password contains special characters. Enclosing it in single quotes is crucial for shell command execution.
wget_command = f"wget --ftp-user=pusyanklim --ftp-password='zS?42G3K^h' {ftp_url}"

print(f"INFO: Attempting to download data for {yesterday.strftime('%Y-%m-%d')}...")
print(f"Executing command: {wget_command}")

# 3. Execute the download command
download_status = os.system(wget_command)

# 4. Check download status and rename the file
downloaded_filename = f"Hotspot_{file_date_part}.txt"
target_filename = "hotspot.txt"

# Check if the download was successful (os.system returns 0 on success)
if download_status == 0 and os.path.exists(downloaded_filename):
    print(f"INFO: Successfully downloaded {downloaded_filename}.")
    # If an old version of the target file exists, remove it first
    if os.path.exists(target_filename):
        os.remove(target_filename)
    # Rename the newly downloaded file
    os.rename(downloaded_filename, target_filename)
    print(f"INFO: File renamed to {target_filename}.")
else:
    print(f"ERROR: Failed to download data for {yesterday.strftime('%Y-%m-%d')}.")
    print("Please check FTP server status, credentials, and network connection.")
    # If the download fails, check if an old file exists to proceed.
    # If not, exit the script as no data is available.
    if not os.path.exists(target_filename):
        print(f"FATAL: No data file found ('{target_filename}'). Cannot generate map. Exiting.")
        sys.exit(1) # Exit the script with an error code
    else:
        print(f"WARNING: Using existing (old) data from '{target_filename}' to generate the map.")

# =======================================================
# === Original Map Generation Code (Unchanged) ===
# =======================================================

# === Load and clean data from TXT ===
txt_file = "hotspot.txt"
csv_file = "hotspot.csv"

try:
    with open(txt_file, 'r') as file:
        lines = file.readlines()
except FileNotFoundError:
    print(f"FATAL: The file {txt_file} was not found. Exiting.")
    sys.exit(1)

# Handle potential empty file
if not lines:
    print("WARNING: The data file is empty. An empty map will be generated.")
    df = pd.DataFrame(columns=['BUJUR', 'LINTANG', 'KEPERCAYAAN', 'REGION']) # Create empty dataframe
else:
    header = lines[0].strip().split('\t')
    # Ensure rows have the correct number of columns before creating DataFrame
    valid_rows = [line.strip().split('\t') for line in lines[1:] if len(line.strip().split('\t')) == len(header)]
    df = pd.DataFrame(valid_rows, columns=header)

# Convert types only if DataFrame is not empty
if not df.empty:
    df["BUJUR"] = pd.to_numeric(df["BUJUR"], errors='coerce')
    df["LINTANG"] = pd.to_numeric(df["LINTANG"], errors='coerce')
    df["KEPERCAYAAN"] = pd.to_numeric(df["KEPERCAYAAN"], errors='coerce')
    df.dropna(subset=['BUJUR', 'LINTANG', 'KEPERCAYAAN'], inplace=True)
    df["KEPERCAYAAN"] = df["KEPERCAYAAN"].astype(int)

    # Save cleaned CSV
    df.to_csv(csv_file, index=False)

# === Filter by confidence ===
low = df[df['KEPERCAYAAN'] == 7] if not df.empty else pd.DataFrame()
med = df[df['KEPERCAYAAN'] == 8] if not df.empty else pd.DataFrame()
high = df[df['KEPERCAYAAN'] == 9] if not df.empty else pd.DataFrame()

# === Create GeoDataFrames ===
def to_gdf(df_in):
    if not df_in.empty:
        geometry = [Point(xy) for xy in zip(df_in['BUJUR'], df_in['LINTANG'])]
        return gpd.GeoDataFrame(df_in, geometry=geometry, crs="EPSG:4326")
    return gpd.GeoDataFrame()

lo_gdf = to_gdf(low)
md_gdf = to_gdf(med)
hi_gdf = to_gdf(high)

# === Region-wise counts ===
regions = ['SUMATERA', 'JAWA', 'KEPULAUAN NUSA TENGGARA', 'KALIMANTAN', 'SULAWESI', 'KEPULAUAN MALUKU', 'PAPUA']
region_counts = {
    r: {
        'low': len(low[low['REGION'] == r]) if not low.empty else 0,
        'med': len(med[med['REGION'] == r]) if not med.empty else 0,
        'high': len(high[high['REGION'] == r]) if not high.empty else 0
    }
    for r in regions
}

# === Load shapefiles ===
try:
    shp_indonesia = gpd.read_file("shp/Indonesia_38_Provinsi.shp")
    shp_others = gpd.read_file("shp/world_without_idn.shp")
except Exception as e:
    print(f"FATAL: Could not read shapefiles. Error: {e}. Exiting.")
    sys.exit(1)

# === Create map ===
fig, ax = plt.subplots(figsize=(10, 7.5))
shp_others.plot(ax=ax, color='white', edgecolor='black')
shp_indonesia.plot(ax=ax, color='lightgrey', edgecolor='black')

# Plot hotspots
if not lo_gdf.empty: lo_gdf.plot(ax=ax, color='green', markersize=10, zorder=3)
if not md_gdf.empty: md_gdf.plot(ax=ax, color='yellow', markersize=10, zorder=3)
if not hi_gdf.empty: hi_gdf.plot(ax=ax, color='red', markersize=10, zorder=3)

# === Gridlines (no axis labels) ===
ax.set_xlim(95, 143)
ax.set_ylim(-19, 14)
ax.set_xticks(range(95, 145, 5))
ax.set_yticks(range(-15, 20, 5))
ax.grid(True, linestyle='--', linewidth=0.5, color='gray')
ax.tick_params(axis='both', labelsize=8)
ax.set_xlabel("")
ax.set_ylabel("")

# === Confidence level legend (lower left) ===
legend_x, legend_y = 96, -13
ax.add_patch(Rectangle((legend_x, legend_y), 9, 5, color='moccasin', zorder=1, ec='black'))
ax.text(legend_x + 4.5, legend_y + 4.3, 'Tingkat Kepercayaan', weight='bold', fontsize=9, family='monospace', ha='center')
ax.scatter(legend_x + 1, legend_y + 3.2, color='green', s=30, edgecolor='black', zorder=3)
ax.text(legend_x + 2, legend_y + 3.2, 'Rendah', fontsize=9, va='center', family='monospace')
ax.scatter(legend_x + 1, legend_y + 2.0, color='yellow', s=30, edgecolor='black', zorder=3)
ax.text(legend_x + 2, legend_y + 2.0, 'Sedang', fontsize=9, va='center', family='monospace')
ax.scatter(legend_x + 1, legend_y + 0.8, color='red', s=30, edgecolor='black', zorder=3)
ax.text(legend_x + 2, legend_y + 0.8, 'Tinggi', fontsize=9, va='center', family='monospace')

# === Region count box (top right) ===
box_x, box_y = 127.5, 14.5
row_height = 0.6
box_width = 15
box_height = (len(regions) + 2) * row_height + 0.5

ax.add_patch(Rectangle((box_x, box_y - box_height), box_width, box_height, color='moccasin', zorder=1, ec='black'))

# Header with colored markers
ax.text(box_x + 0.2, box_y - 0.5, f"{'Wilayah':<24}", fontsize=8, family='monospace', weight='bold')
ax.scatter(box_x + 10.1, box_y - 0.3, color='green', s=30, edgecolor='black', zorder=3)
ax.scatter(box_x + 11.9, box_y - 0.3, color='yellow', s=30, edgecolor='black', zorder=3)
ax.scatter(box_x + 14, box_y - 0.3, color='red', s=30, edgecolor='black', zorder=3)


# Region rows
for i, region in enumerate(regions):
    low_c = region_counts[region]['low']
    med_c = region_counts[region]['med']
    high_c = region_counts[region]['high']
    label = f"{region.title():<24} {low_c:>4} {med_c:>4} {high_c:>5}"
    ax.text(box_x + 0.2, box_y - (i + 1.2) * row_height - 0.5, label, fontsize=8, family='monospace')

# Separator line
#ax.plot([box_x, box_x + box_width], [box_y - (len(regions) + 1) * row_height, box_y - (len(regions) + 1) * row_height], color='black', linewidth=0.5)

# Indonesia total row
total_low = len(low) if not low.empty else 0
total_med = len(med) if not med.empty else 0
total_high = len(high) if not high.empty else 0
total_label = f"{'INDONESIA':<24} {total_low:>4} {total_med:>4} {total_high:>5}"
ax.text(box_x + 0.2, box_y - (len(regions) + 1.6) * row_height - 0.5, total_label, fontsize=8, weight='bold', family='monospace')

# === Title and logo ===
title_date = yesterday.strftime("%d-%m-%Y") # Use the same 'yesterday' variable
ax.text(98.8, -15.2, 'PETA SEBARAN HOTSPOT', weight='bold', fontsize=11, family='monospace')
ax.text(98.8, -16.2, f'Tanggal: {title_date}', family='monospace')
ax.text(98.8, -17.2, 'Satelit: Terra, Aqua, Suomi NPP, NOAA-20', family='monospace')

try:
    logo = mpimg.imread("logo_bmkg.png")
    imagebox = OffsetImage(logo, zoom=0.15)
    ab = AnnotationBbox(imagebox, (97.3, -16.0), frameon=False, zorder=10)
    ax.add_artist(ab)
except FileNotFoundError:
    print("WARNING: BMKG logo not found (logo_bmkg.png). Skipping.")

plt.tight_layout()
plt.savefig("update_hotspot.png", dpi=150)

print("\nWork has been completed. Map 'update_hotspot.png' has been generated.")
