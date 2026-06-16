# src/visualisation/map_outputs.py

import os
import logging
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, Normalize
import matplotlib.cm as cm
import rasterio
import geopandas as gpd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

BACKGROUND = "#0a0a0a"
TEXT_COLOR = "#e0e0e0"
DPI = 300

EPOCH_COLORS = {
    "2020": "#2196F3",
    "2022": "#FF9800",
    "2023": "#4CAF50"
}


def _apply_dark_style(fig, axes):
    """Apply consistent dark background style."""
    fig.patch.set_facecolor(BACKGROUND)
    for ax in (axes.flat if hasattr(axes, "flat") else
               axes if hasattr(axes, "__iter__") else [axes]):
        ax.set_facecolor(BACKGROUND)
        ax.tick_params(colors=TEXT_COLOR, labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333333")
        ax.title.set_color(TEXT_COLOR)
        ax.xaxis.label.set_color(TEXT_COLOR)
        ax.yaxis.label.set_color(TEXT_COLOR)


def _read_band(path: str, band: int) -> np.ndarray:
    """Read a raster band as float32."""
    with rasterio.open(path) as src:
        data = src.read(band).astype(np.float32)
        nodata = src.nodata
    if nodata is not None:
        data[data == nodata] = np.nan
    return data


def _get_extent(path: str) -> list:
    """Get [left, right, bottom, top] extent from raster."""
    with rasterio.open(path) as src:
        b = src.bounds
    return [b.left, b.right, b.bottom, b.top]


def _normalise(arr: np.ndarray, p_low: float = 2, p_high: float = 98) -> np.ndarray:
    """Percentile stretch normalisation."""
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return arr
    lo, hi = np.percentile(valid, [p_low, p_high])
    if hi == lo:
        return np.zeros_like(arr)
    return np.clip((arr - lo) / (hi - lo), 0, 1)


def _make_rgb(path: str) -> np.ndarray:
    """
    True colour RGB from Sentinel-2 composite.
    Band order: B2(1), B4(2), B5(3), B8(4), B11(5), B12(6),
    NDVI(7), NBR(8), NDMI(9), NDRE(10), EVI(11).
    R=B4(2), G=B5(3), B=B2(1).
    """
    r = _normalise(_read_band(path, 2))
    g = _normalise(_read_band(path, 3))
    b = _normalise(_read_band(path, 1))
    return np.dstack([r, g, b])


def figure1_composites(run_id: str, output_dir: str) -> str:
    """Figure 1: Sentinel-2 RGB true colour composites, three epochs."""
    logger.info("Generating Figure 1: RGB composites")
    raster_dir = f"outputs/rasters/{run_id}"
    epochs = ["2020", "2022", "2023"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 7))
    _apply_dark_style(fig, axes)
    fig.suptitle(
        "Sentinel-2 RGB Composites | Mato Grosso, Brazil | June-August",
        color=TEXT_COLOR, fontsize=13, fontweight="bold", y=1.01
    )

    for ax, epoch in zip(axes, epochs):
        rgb = _make_rgb(f"{raster_dir}/sentinel2_composite_{epoch}.tif")
        ax.imshow(rgb, interpolation="bilinear")
        ax.set_title(epoch, color=EPOCH_COLORS[epoch], fontsize=11, fontweight="bold")
        ax.set_xticks([])
        ax.set_yticks([])

    plt.tight_layout()
    out_path = f"{output_dir}/figure1_composites.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Figure 1 saved: {out_path}")
    return out_path


def figure2_change_detection(run_id: str, output_dir: str) -> str:
    """Figure 2: dNBR change detection maps for both transitions."""
    logger.info("Generating Figure 2: dNBR change detection")
    raster_dir = f"outputs/rasters/{run_id}"
    transitions = [("2020", "2022"), ("2022", "2023")]
    labels = ["2020-2022", "2022-2023"]

    dnbr_cmap = LinearSegmentedColormap.from_list(
        "dnbr", ["#1565C0", "#42A5F5", "#FFFFFF", "#EF9A9A", "#B71C1C"]
    )

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    _apply_dark_style(fig, axes)
    fig.suptitle(
        "dNBR Change Detection | Mato Grosso, Brazil",
        color=TEXT_COLOR, fontsize=13, fontweight="bold", y=1.01
    )

    for ax, (t1, t2), label in zip(axes, transitions, labels):
        nbr_t1 = _read_band(f"{raster_dir}/sentinel2_composite_{t1}.tif", 8)
        nbr_t2 = _read_band(f"{raster_dir}/sentinel2_composite_{t2}.tif", 8)
        dnbr = nbr_t1 - nbr_t2
        extent = _get_extent(f"{raster_dir}/sentinel2_composite_{t1}.tif")

        vmax = np.nanpercentile(np.abs(dnbr), 98)
        im = ax.imshow(dnbr, cmap=dnbr_cmap, vmin=-vmax, vmax=vmax,
                       extent=extent, aspect="auto")
        ax.set_title(f"dNBR {label}", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        ax.set_xlabel("Longitude", color=TEXT_COLOR, fontsize=8)
        ax.set_ylabel("Latitude", color=TEXT_COLOR, fontsize=8)

        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("dNBR", color=TEXT_COLOR, fontsize=8)
        cbar.ax.yaxis.set_tick_params(color=TEXT_COLOR)
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color=TEXT_COLOR)

    plt.tight_layout()
    out_path = f"{output_dir}/figure2_change_detection.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Figure 2 saved: {out_path}")
    return out_path


def figure3_forest_cover(run_id: str, output_dir: str) -> str:
    """
    Figure 3: MapBiomas forest cover per epoch - binary forest/non-forest.
    Industry standard opening figure for REDD+ monitoring reports.
    """
    logger.info("Generating Figure 3: Forest cover maps")
    raster_dir = f"outputs/rasters/{run_id}"
    epochs = ["2020", "2022", "2023"]

    forest_cmap = LinearSegmentedColormap.from_list(
        "forest", ["#d4c49a", "#1b5e20"]
    )

    fig, axes = plt.subplots(1, 3, figsize=(18, 7))
    _apply_dark_style(fig, axes)
    fig.suptitle(
        "Forest Cover | MapBiomas Collection 10 | Mato Grosso, Brazil",
        color=TEXT_COLOR, fontsize=13, fontweight="bold", y=1.01
    )

    for ax, epoch in zip(axes, epochs):
        forest = _read_band(f"{raster_dir}/mapbiomas_forest_{epoch}.tif", 1)
        extent = _get_extent(f"{raster_dir}/mapbiomas_forest_{epoch}.tif")
        ax.imshow(forest, cmap=forest_cmap, vmin=0, vmax=1,
                  extent=extent, aspect="auto", interpolation="none")
        ax.set_title(epoch, color=EPOCH_COLORS[epoch], fontsize=11, fontweight="bold")
        ax.set_xlabel("Longitude", color=TEXT_COLOR, fontsize=8)
        ax.set_ylabel("Latitude", color=TEXT_COLOR, fontsize=8)

    legend_elements = [
        mpatches.Patch(facecolor="#1b5e20", label="Forest"),
        mpatches.Patch(facecolor="#d4c49a", label="Non-forest"),
    ]
    axes[-1].legend(handles=legend_elements, loc="lower right",
                    facecolor="#1a1a1a", labelcolor=TEXT_COLOR, fontsize=8)

    plt.tight_layout()
    out_path = f"{output_dir}/figure3_forest_cover.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Figure 3 saved: {out_path}")
    return out_path


def figure4_carbon_loss(run_id: str, output_dir: str, vectors_local_dir: str) -> str:
    """
    Figure 4: Carbon loss map.
    Deforestation patches coloured by CO2e loss on forest/non-forest background.
    Standard presentation in VCS project documents.
    """
    logger.info("Generating Figure 4: Carbon loss map")
    raster_dir = f"outputs/rasters/{run_id}"
    transitions = ["2020-2022", "2022-2023"]

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    _apply_dark_style(fig, axes)
    fig.suptitle(
        "Carbon Loss from Deforestation | Mato Grosso, Brazil | IPCC Tier 1",
        color=TEXT_COLOR, fontsize=13, fontweight="bold", y=1.01
    )

    for ax, transition in zip(axes, transitions):
        t1 = transition.split("-")[0]

        # forest/non-forest binary background
        forest = _read_band(f"{raster_dir}/mapbiomas_forest_{t1}.tif", 1)
        extent = _get_extent(f"{raster_dir}/mapbiomas_forest_{t1}.tif")
        forest_cmap = LinearSegmentedColormap.from_list(
            "forest_bg", ["#2d2d1a", "#1b5e20"]
        )
        ax.imshow(forest, cmap=forest_cmap, vmin=0, vmax=1,
                  extent=extent, aspect="auto", interpolation="none")

        # deforestation patches coloured by CO2e
        geojson_path = f"{vectors_local_dir}/deforestation_patches_{transition}.geojson"
        if os.path.exists(geojson_path):
            patches_gdf = gpd.read_file(geojson_path)
            if len(patches_gdf) > 0 and "co2e_mg" in patches_gdf.columns:
                patches_gdf.plot(
                    column="co2e_mg",
                    cmap="YlOrRd",
                    ax=ax,
                    legend=True,
                    legend_kwds={
                        "label": "CO2e loss (Mg)",
                        "orientation": "vertical",
                        "shrink": 0.7,
                        "pad": 0.02
                    },
                    alpha=0.9,
                    linewidth=0
                )

        ax.set_title(
            f"CO2e Loss {transition}",
            color=TEXT_COLOR, fontsize=11, fontweight="bold"
        )
        ax.set_xlabel("Longitude", color=TEXT_COLOR, fontsize=8)
        ax.set_ylabel("Latitude", color=TEXT_COLOR, fontsize=8)

    plt.tight_layout()
    out_path = f"{output_dir}/figure4_carbon_loss.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Figure 4 saved: {out_path}")
    return out_path


def figure5_gedi_biomass(run_id: str, output_dir: str) -> str:
    """
    Figure 5: GEDI L4B aboveground biomass density.
    Standalone biomass reference surface figure - standard in REDD+ methodology docs.
    """
    logger.info("Generating Figure 5: GEDI AGBD biomass density")
    raster_dir = f"outputs/rasters/{run_id}"

    agbd = _read_band(f"{raster_dir}/gedi_l4b_agbd.tif", 1)
    extent = _get_extent(f"{raster_dir}/gedi_l4b_agbd.tif")

    # mask zeros and very low values (no data / water)
    agbd[agbd <= 0] = np.nan

    fig, ax = plt.subplots(1, 1, figsize=(10, 9))
    _apply_dark_style(fig, ax)
    fig.suptitle(
        "Aboveground Biomass Density | GEDI L4B v2.1 | Mato Grosso, Brazil",
        color=TEXT_COLOR, fontsize=13, fontweight="bold"
    )

    im = ax.imshow(agbd, cmap="YlGn", extent=extent, aspect="auto",
                   vmin=np.nanpercentile(agbd, 5),
                   vmax=np.nanpercentile(agbd, 95))
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("AGBD (Mg/ha)", color=TEXT_COLOR, fontsize=9)
    cbar.ax.yaxis.set_tick_params(color=TEXT_COLOR)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=TEXT_COLOR)

    ax.set_xlabel("Longitude", color=TEXT_COLOR, fontsize=9)
    ax.set_ylabel("Latitude", color=TEXT_COLOR, fontsize=9)

    ax.text(
        0.02, 0.02,
        "Source: NASA GEDI L4B v2.1\nResolution: 1 km | Carbon fraction: 0.47",
        transform=ax.transAxes, color=TEXT_COLOR, fontsize=7,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round", facecolor="#1a1a1a", alpha=0.8)
    )

    plt.tight_layout()
    out_path = f"{output_dir}/figure5_gedi_biomass.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Figure 5 saved: {out_path}")
    return out_path


def figure6_validation(run_id: str, output_dir: str) -> str:
    """
    Figure 6: Validation panel - detected deforestation vs PRODES.
    TP/FP/FN spatial comparison with RGB background.
    Standard accuracy assessment figure in Sentinel-2 + PRODES literature.
    """
    logger.info("Generating Figure 6: Validation panel")
    raster_dir = f"outputs/rasters/{run_id}"
    transitions = ["2020-2022", "2022-2023"]

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    _apply_dark_style(fig, axes)
    fig.suptitle(
        "Deforestation Detection vs PRODES Validation | Mato Grosso, Brazil",
        color=TEXT_COLOR, fontsize=13, fontweight="bold", y=1.01
    )

    for ax, transition in zip(axes, transitions):
        t1, t2 = transition.split("-")[0], transition.split("-")[1]
        prodes_year = int(t2)

        # RGB background (faint)
        rgb = _make_rgb(f"{raster_dir}/sentinel2_composite_{t2}.tif")
        ax.imshow(rgb * 0.35, interpolation="bilinear")

        # load masks
        prodes = _read_band(f"{raster_dir}/prodes_{prodes_year}.tif", 1)
        forest_t1 = _read_band(f"{raster_dir}/mapbiomas_forest_{t1}.tif", 1)
        forest_t2 = _read_band(f"{raster_dir}/mapbiomas_forest_{t2}.tif", 1)
        detected = ((forest_t1 == 1) & (forest_t2 == 0)).astype(np.float32)

        # build RGBA overlay
        h, w = prodes.shape
        overlay = np.zeros((h, w, 4), dtype=np.float32)

        tp = (detected == 1) & (prodes == 1)
        fp = (detected == 1) & (prodes == 0)
        fn = (detected == 0) & (prodes == 1)

        overlay[tp] = [0.2, 0.9, 0.2, 0.85]   # green: true positive
        overlay[fp] = [0.9, 0.2, 0.2, 0.75]   # red: false positive
        overlay[fn] = [1.0, 0.6, 0.0, 0.75]   # orange: false negative

        ax.imshow(overlay, interpolation="none")

        # metrics
        tp_n = int(np.sum(tp))
        fp_n = int(np.sum(fp))
        fn_n = int(np.sum(fn))
        precision = tp_n / (tp_n + fp_n) if (tp_n + fp_n) > 0 else 0.0
        recall = tp_n / (tp_n + fn_n) if (tp_n + fn_n) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0.0)

        ax.text(
            0.02, 0.02,
            f"Precision: {precision:.3f}\nRecall:    {recall:.3f}\nF1:        {f1:.3f}",
            transform=ax.transAxes, color=TEXT_COLOR, fontsize=8,
            verticalalignment="bottom", fontfamily="monospace",
            bbox=dict(boxstyle="round", facecolor="#1a1a1a", alpha=0.85)
        )

        legend_elements = [
            mpatches.Patch(facecolor="#33CC33", label="True Positive"),
            mpatches.Patch(facecolor="#CC3333", label="False Positive"),
            mpatches.Patch(facecolor="#FF9900", label="False Negative"),
        ]
        ax.legend(handles=legend_elements, loc="upper right",
                  facecolor="#1a1a1a", labelcolor=TEXT_COLOR, fontsize=7)

        ax.set_title(f"Validation {transition}", color=TEXT_COLOR,
                     fontsize=11, fontweight="bold")
        ax.set_xticks([])
        ax.set_yticks([])

    plt.tight_layout()
    out_path = f"{output_dir}/figure6_validation.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Figure 6 saved: {out_path}")
    return out_path


def generate_all_figures(run_id: str, vectors_local_dir: str) -> list:
    """Generate all six figures and return list of output paths."""
    output_dir = "outputs/figures"
    os.makedirs(output_dir, exist_ok=True)

    paths = []
    paths.append(figure1_composites(run_id, output_dir))
    paths.append(figure2_change_detection(run_id, output_dir))
    paths.append(figure3_forest_cover(run_id, output_dir))
    paths.append(figure4_carbon_loss(run_id, output_dir, vectors_local_dir))
    paths.append(figure5_gedi_biomass(run_id, output_dir))
    paths.append(figure6_validation(run_id, output_dir))

    return paths