import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# Load hotspot data
hotspot_df = pd.read_csv("archived_hotspot_idn.csv")

# Construct datetime column from year, month, day
hotspot_df['acq_date'] = pd.to_datetime(hotspot_df[['year', 'month', 'day']])

# Convert to GeoDataFrame
hotspot_gdf = gpd.GeoDataFrame(
    hotspot_df,
    geometry=gpd.points_from_xy(hotspot_df.lon, hotspot_df.lat),
    crs="EPSG:4326"
)

# Extract year-month
hotspot_gdf['year_month'] = hotspot_gdf['acq_date'].dt.to_period('M')

# Load province and municipality GeoJSONs
gdf_province = gpd.read_file("indonesia_38prov.geojson")
gdf_kabkota = gpd.read_file("indonesia_kabkota_38prov.geojson")

# Spatial join for provinces
joined_prov = gpd.sjoin(hotspot_gdf, gdf_province, how="inner", predicate='intersects')
prov_grouped = joined_prov.groupby(['year_month', gdf_province.columns[0]]).size().reset_index(name='hotspot_count')
prov_grouped['date'] = prov_grouped['year_month'].astype(str)
prov_grouped = prov_grouped.rename(columns={gdf_province.columns[0]: 'province'})
prov_grouped[['date', 'province', 'hotspot_count']].to_csv("hotspot_by_province.csv", index=False)

# Spatial join for kabupaten/kota
joined_kab = gpd.sjoin(hotspot_gdf, gdf_kabkota, how="inner", predicate='intersects')
kab_grouped = joined_kab.groupby(['year_month', gdf_kabkota.columns[0], gdf_kabkota.columns[1]]).size().reset_index(name='hotspot_count')
kab_grouped['date'] = kab_grouped['year_month'].astype(str)
kab_grouped = kab_grouped.rename(columns={
    gdf_kabkota.columns[1]: 'province',
    gdf_kabkota.columns[0]: 'kabupaten'
})
kab_grouped[['date', 'province', 'kabupaten', 'hotspot_count']].to_csv("hotspot_by_municipality.csv", index=False)

