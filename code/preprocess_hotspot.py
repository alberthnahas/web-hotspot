#!/usr/bin/env python3
"""
Assign correct Indonesian province & kabupaten to every hotspot row,
drop any rows outside the official polygons, and write a cleaned TXT.

Usage:
  python preprocess_hotspots.py \
      --input hotspot.txt \
      --prov  indonesia_38prov.geojson \
      --kab   indonesia_kabkota_38prov.geojson \
      --output hotspot.txt
"""
import argparse, sys, pandas as pd, geopandas as gpd
from pathlib import Path
from shapely.geometry import Point

def harmonise_names(gdf, prov_cols, kab_cols):
    """Return two Series: province names, kabupaten names."""
    prov, kab = None, None
    for c in prov_cols:
        if c in gdf.columns:
            prov = gdf[c] if prov is None else prov.fillna(gdf[c])
    for c in kab_cols:
        if c in gdf.columns:
            kab = gdf[c] if kab is None else kab.fillna(gdf[c])
    return prov.str.strip(), (kab.str.strip() if kab is not None else pd.Series([None]*len(gdf)))

def main(a):
    inp, out = Path(a.input), Path(a.output)
    prov_path, kab_path = Path(a.prov), Path(a.kab)

    # 1. Hotspot TXT ➜ GeoDataFrame
    df = pd.read_csv(inp, sep=r'\t+', engine="python")
    gdf_pts = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df['BUJUR'], df['LINTANG']),
        crs="EPSG:4326"
    )

    # 2. Load polygon layers
    prov_gdf = gpd.read_file(prov_path)
    kab_gdf  = gpd.read_file(kab_path)

    # ---- Harmonise name columns ----
    prov_gdf["prov_name"], _ = harmonise_names(
        prov_gdf, ["provinsi", "province", "name"], []
    )
    # ✅ FIX: province first, kabupaten second
    kab_gdf["prov_name"], kab_gdf["kab_name"] = harmonise_names(
        kab_gdf, ["provinsi", "province"], ["kabupaten", "municipality", "name"]
    )

    # 3. Spatial join: point ➜ kabupaten
    gdf_pts = gpd.sjoin(
        gdf_pts,
        kab_gdf[["kab_name", "prov_name", "geometry"]],
        predicate="within",
        how="left"
    )

    # 3b. Fallback: points matched only to province
    missing_kab = gdf_pts["kab_name"].isna()
    if missing_kab.any():
        fallback = gpd.sjoin(
            gdf_pts.loc[missing_kab, ["geometry"]],
            prov_gdf[["prov_name", "geometry"]],
            predicate="within",
            how="left"
        )
        gdf_pts.loc[missing_kab, "prov_name"] = fallback["prov_name"].values

    # 4. Drop rows outside Indonesia (still missing province)
    before, after = len(gdf_pts), gdf_pts["prov_name"].notna().sum()
    gdf_pts = gdf_pts.dropna(subset=["prov_name"]).copy()
    print(f"✔ Matched {after}/{before} rows; removed {before - after} out‑of‑boundary rows.")

    # 5. Write output (preserve original columns)
    export_cols = df.columns.tolist()
    gdf_pts["PROVINSI"]  = gdf_pts["prov_name"]
    gdf_pts["KABUPATEN"] = gdf_pts["kab_name"]
    if "PROVINSI" not in export_cols:
        export_cols.append("PROVINSI")
    if "KABUPATEN" not in export_cols:
        export_cols.append("KABUPATEN")

    gdf_pts[export_cols].to_csv(out, sep="\t", index=False)
    print(f"✔ Saved cleaned file -> {out}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Raw hotspot TXT")
    p.add_argument("--prov",  required=True, help="Province GeoJSON")
    p.add_argument("--kab",   required=True, help="Kabupaten GeoJSON")
    p.add_argument("--output",required=True, help="Destination TXT")
    main(p.parse_args())

