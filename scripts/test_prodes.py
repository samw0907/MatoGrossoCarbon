# scripts/test_prodes.py

from src.pipeline.tasks.prodes import load_prodes_polygons

gdf = load_prodes_polygons(
    bbox=(-56.0, -13.0, -54.0, -11.0),
    state_filter="MT",
    year_start=2020,
    year_end=2023
)

print(f"Features in AOI: {len(gdf)}")
print(f"Years present: {sorted(gdf['year'].unique())}")
print(gdf[["state", "year", "area_km"]].head(5))