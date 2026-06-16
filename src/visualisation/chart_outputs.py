# src/visualisation/chart_outputs.py

import matplotlib
matplotlib.use("Agg")

import os
import logging
import json
import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd
import rasterio

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

BACKGROUND = "#0a0a0a"
TEXT_COLOR = "#e0e0e0"
GRID_COLOR = "#2a2a2a"
DPI = 300

TRANSITION_COLORS = {
    "2020-2022": "#2196F3",
    "2022-2023": "#FF9800"
}

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
        ax.tick_params(colors=TEXT_COLOR, labelsize=8)
        ax.spines["bottom"].set_color("#444444")
        ax.spines["left"].set_color("#444444")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.title.set_color(TEXT_COLOR)
        ax.xaxis.label.set_color(TEXT_COLOR)
        ax.yaxis.label.set_color(TEXT_COLOR)
        ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--")
        ax.set_axisbelow(True)


def _read_band(path: str, band: int) -> np.ndarray:
    """Read a raster band as float32."""
    with rasterio.open(path) as src:
        return src.read(band).astype(np.float32)


def chart1_summary_statistics(
    run_id: str,
    output_dir: str,
    vectors_local_dir: str,
    reports_local_dir: str
) -> str:
    """
    Chart 1: Summary statistics panel.
    Deforested area, total CO2e with 90% CI, and patch count per transition.
    """
    logger.info("Generating Chart 1: Summary statistics")

    transitions = ["2020-2022", "2022-2023"]
    areas = []
    co2e_totals = []
    co2e_lowers = []
    co2e_uppers = []
    patch_counts = []

    for transition in transitions:
        summary_path = f"{reports_local_dir}/carbon_summary_{transition}.json"
        if os.path.exists(summary_path):
            with open(summary_path) as f:
                summary = json.load(f)
            areas.append(summary.get("deforested_area_ha", 0))
            co2e_totals.append(summary.get("total_co2e_mg", 0) / 1e6)
            co2e_lowers.append(summary.get("co2e_lower_90_mg", 0) / 1e6)
            co2e_uppers.append(summary.get("co2e_upper_90_mg", 0) / 1e6)
            patch_counts.append(summary.get("patch_count", 0))
        else:
            areas.append(0)
            co2e_totals.append(0)
            co2e_lowers.append(0)
            co2e_uppers.append(0)
            patch_counts.append(0)

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    _apply_dark_style(fig, axes)
    fig.suptitle(
        "Pipeline Output Summary | Mato Grosso, Brazil",
        color=TEXT_COLOR, fontsize=13, fontweight="bold"
    )

    colors = [TRANSITION_COLORS[t] for t in transitions]
    x = np.arange(len(transitions))
    bar_w = 0.5

    # deforested area
    axes[0].bar(x, areas, width=bar_w, color=colors, alpha=0.85, edgecolor="#444444")
    axes[0].set_title("Deforested Area", color=TEXT_COLOR, fontsize=10)
    axes[0].set_ylabel("Area (ha)", color=TEXT_COLOR, fontsize=9)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(transitions, color=TEXT_COLOR, fontsize=8)
    for i, v in enumerate(areas):
        axes[0].text(i, v + max(areas) * 0.02, f"{v:,.0f} ha",
                     ha="center", color=TEXT_COLOR, fontsize=8)

    # total CO2e with 90% CI error bars
    yerr_lower = [co2e_totals[i] - co2e_lowers[i] for i in range(len(transitions))]
    yerr_upper = [co2e_uppers[i] - co2e_totals[i] for i in range(len(transitions))]
    axes[1].bar(x, co2e_totals, width=bar_w, color=colors, alpha=0.85,
                edgecolor="#444444",
                yerr=[yerr_lower, yerr_upper],
                error_kw={"ecolor": TEXT_COLOR, "capsize": 5, "linewidth": 1.5})
    axes[1].set_title("Total CO2e Loss", color=TEXT_COLOR, fontsize=10)
    axes[1].set_ylabel("CO2e (Mt)", color=TEXT_COLOR, fontsize=9)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(transitions, color=TEXT_COLOR, fontsize=8)
    for i, v in enumerate(co2e_totals):
        axes[1].text(i, v + max(co2e_totals) * 0.02, f"{v:.2f} Mt",
                     ha="center", color=TEXT_COLOR, fontsize=8)

    # patch count
    axes[2].bar(x, patch_counts, width=bar_w, color=colors, alpha=0.85,
                edgecolor="#444444")
    axes[2].set_title("Deforestation Patch Count", color=TEXT_COLOR, fontsize=10)
    axes[2].set_ylabel("Patches", color=TEXT_COLOR, fontsize=9)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(transitions, color=TEXT_COLOR, fontsize=8)
    for i, v in enumerate(patch_counts):
        axes[2].text(i, v + max(patch_counts) * 0.02, f"{v:,}",
                     ha="center", color=TEXT_COLOR, fontsize=8)

    plt.tight_layout()
    out_path = f"{output_dir}/chart1_summary_statistics.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Chart 1 saved: {out_path}")
    return out_path


def chart2_patch_size_distribution(
    run_id: str,
    output_dir: str,
    vectors_local_dir: str
) -> str:
    """
    Chart 2: Patch size distribution histogram per transition.
    Shows whether deforestation is dominated by large clearings or many small patches.
    """
    logger.info("Generating Chart 2: Patch size distribution")

    transitions = ["2020-2022", "2022-2023"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    _apply_dark_style(fig, axes)
    fig.suptitle(
        "Deforestation Patch Size Distribution | Mato Grosso, Brazil",
        color=TEXT_COLOR, fontsize=13, fontweight="bold"
    )

    for ax, transition in zip(axes, transitions):
        geojson_path = f"{vectors_local_dir}/deforestation_patches_{transition}.geojson"
        if os.path.exists(geojson_path):
            gdf = gpd.read_file(geojson_path)
            areas = gdf["area_ha"].values

            bins = np.logspace(np.log10(max(areas.min(), 0.01)),
                               np.log10(areas.max()), 30)
            ax.hist(areas, bins=bins, color=TRANSITION_COLORS[transition],
                    alpha=0.85, edgecolor="#444444")
            ax.set_xscale("log")

            median_area = np.median(areas)
            ax.axvline(median_area, color="#FF5252", linewidth=1.5, linestyle="--")
            ax.text(median_area * 1.1, ax.get_ylim()[1] * 0.85,
                    f"Median: {median_area:.1f} ha",
                    color="#FF5252", fontsize=8)

            ax.set_title(f"Patch Sizes {transition}",
                         color=TEXT_COLOR, fontsize=10)
            ax.set_xlabel("Patch Area (ha, log scale)", color=TEXT_COLOR, fontsize=9)
            ax.set_ylabel("Number of patches", color=TEXT_COLOR, fontsize=9)

            ax.text(0.97, 0.95,
                    f"n = {len(areas):,}\nMin: {areas.min():.1f} ha\n"
                    f"Max: {areas.max():.0f} ha",
                    transform=ax.transAxes, color=TEXT_COLOR, fontsize=8,
                    ha="right", va="top",
                    bbox=dict(boxstyle="round", facecolor="#1a1a1a", alpha=0.8))

    plt.tight_layout()
    out_path = f"{output_dir}/chart2_patch_size_distribution.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Chart 2 saved: {out_path}")
    return out_path


def chart3_biomass_co2e_scatter(
    run_id: str,
    output_dir: str,
    vectors_local_dir: str
) -> str:
    """
    Chart 3: AGBD vs CO2e scatter plot per patch, coloured by transition.
    Patches with AGBD below 5 Mg/ha excluded (GEDI data gaps between orbital tracks).
    Demonstrates GEDI biomass integration and IPCC Tier 1 calculation chain.
    """
    logger.info("Generating Chart 3: Biomass vs CO2e scatter")

    transitions = ["2020-2022", "2022-2023"]
    min_agbd = 5.0  # exclude patches in GEDI orbital track gaps

    fig, ax = plt.subplots(1, 1, figsize=(10, 7))
    _apply_dark_style(fig, ax)
    fig.suptitle(
        "AGBD vs CO2e Loss per Patch | GEDI L4B + IPCC Tier 1 | Mato Grosso",
        color=TEXT_COLOR, fontsize=12, fontweight="bold"
    )

    for transition in transitions:
        geojson_path = f"{vectors_local_dir}/deforestation_patches_{transition}.geojson"
        if os.path.exists(geojson_path):
            gdf = gpd.read_file(geojson_path)
            if "agbd_mean_mg_ha" in gdf.columns and "co2e_mg" in gdf.columns:
                # filter out patches with near-zero GEDI coverage
                gdf_valid = gdf[gdf["agbd_mean_mg_ha"] >= min_agbd].copy()
                excluded = len(gdf) - len(gdf_valid)

                ax.scatter(
                    gdf_valid["agbd_mean_mg_ha"],
                    gdf_valid["co2e_mg"] / 1000,
                    c=TRANSITION_COLORS[transition],
                    alpha=0.5,
                    s=gdf_valid["area_ha"] * 0.5,
                    label=f"{transition} (n={len(gdf_valid):,}, "
                          f"{excluded} excluded)",
                    edgecolors="none"
                )

    ax.set_xlabel("Mean AGBD (Mg/ha)", color=TEXT_COLOR, fontsize=10)
    ax.set_ylabel("CO2e Loss (thousand Mg)", color=TEXT_COLOR, fontsize=10)
    ax.legend(facecolor="#1a1a1a", labelcolor=TEXT_COLOR, fontsize=9,
              title="Transition", title_fontsize=8)

    ax.text(0.03, 0.95,
            f"Point size proportional to patch area\n"
            f"CO2e = AGBD × area × 0.47 × 3.667 (IPCC Tier 1)\n"
            f"Patches with AGBD < {min_agbd} Mg/ha excluded\n"
            f"(GEDI orbital track gaps)",
            transform=ax.transAxes, color=TEXT_COLOR, fontsize=8,
            va="top",
            bbox=dict(boxstyle="round", facecolor="#1a1a1a", alpha=0.8))

    plt.tight_layout()
    out_path = f"{output_dir}/chart3_biomass_co2e_scatter.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Chart 3 saved: {out_path}")
    return out_path


def chart4_cumulative_co2e(
    run_id: str,
    output_dir: str,
    vectors_local_dir: str
) -> str:
    """
    Chart 4: Cumulative CO2e curve - patches ranked by size.
    Shows what proportion of total emissions come from largest patches.
    """
    logger.info("Generating Chart 4: Cumulative CO2e curve")

    transitions = ["2020-2022", "2022-2023"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    _apply_dark_style(fig, axes)
    fig.suptitle(
        "Cumulative CO2e by Patch Size | Mato Grosso, Brazil",
        color=TEXT_COLOR, fontsize=13, fontweight="bold"
    )

    for ax, transition in zip(axes, transitions):
        geojson_path = f"{vectors_local_dir}/deforestation_patches_{transition}.geojson"
        if os.path.exists(geojson_path):
            gdf = gpd.read_file(geojson_path)
            if "co2e_mg" in gdf.columns:
                gdf_sorted = gdf.sort_values("area_ha", ascending=False).reset_index()
                cumulative_co2e = (gdf_sorted["co2e_mg"].cumsum()
                                   / gdf_sorted["co2e_mg"].sum() * 100)
                patch_pct = (np.arange(1, len(gdf_sorted) + 1)
                             / len(gdf_sorted)) * 100

                ax.plot(patch_pct, cumulative_co2e,
                        color=TRANSITION_COLORS[transition], linewidth=2)
                ax.fill_between(patch_pct, cumulative_co2e,
                                alpha=0.15, color=TRANSITION_COLORS[transition])

                idx_80 = np.searchsorted(cumulative_co2e, 80)
                if idx_80 < len(patch_pct):
                    ax.axhline(80, color="#FF5252", linewidth=1,
                               linestyle="--", alpha=0.7)
                    ax.axvline(patch_pct[idx_80], color="#FF5252",
                               linewidth=1, linestyle="--", alpha=0.7)
                    ax.text(patch_pct[idx_80] + 1, 5,
                            f"{patch_pct[idx_80]:.0f}% of patches\n→ 80% of CO2e",
                            color="#FF5252", fontsize=8)

                ax.set_xlim(0, 100)
                ax.set_ylim(0, 100)
                ax.set_title(f"Cumulative CO2e {transition}",
                             color=TEXT_COLOR, fontsize=10)
                ax.set_xlabel("% of patches (largest first)",
                              color=TEXT_COLOR, fontsize=9)
                ax.set_ylabel("Cumulative % of total CO2e",
                              color=TEXT_COLOR, fontsize=9)

    plt.tight_layout()
    out_path = f"{output_dir}/chart4_cumulative_co2e.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Chart 4 saved: {out_path}")
    return out_path


def chart5_index_time_series(run_id: str, output_dir: str) -> str:
    """
    Chart 5: Mean spectral index values across epochs.
    Labels offset vertically by rank to avoid overlap.
    """
    logger.info("Generating Chart 5: Index time series")

    raster_dir = f"outputs/rasters/{run_id}"
    epochs = ["2020", "2022", "2023"]

    # band indices: NDVI=7, NBR=8, NDMI=9, NDRE=10, EVI=11
    index_bands = {
        "NDVI": 7,
        "NBR": 8,
        "NDMI": 9,
        "NDRE": 10,
        "EVI": 11
    }

    index_colors = {
        "NDVI": "#4CAF50",
        "NBR": "#2196F3",
        "NDMI": "#FF9800",
        "NDRE": "#9C27B0",
        "EVI": "#F44336"
    }

    means = {idx: [] for idx in index_bands}

    for epoch in epochs:
        path = f"{raster_dir}/sentinel2_composite_{epoch}.tif"
        for idx_name, band_num in index_bands.items():
            data = _read_band(path, band_num)
            valid = data[(data > -1) & (data < 1) & ~np.isnan(data)]
            means[idx_name].append(
                float(np.mean(valid)) if len(valid) > 0 else np.nan
            )

    fig, ax = plt.subplots(1, 1, figsize=(10, 7))
    _apply_dark_style(fig, ax)
    fig.suptitle(
        "Mean Spectral Index Values | Mato Grosso, Brazil | 2020-2023",
        color=TEXT_COLOR, fontsize=13, fontweight="bold"
    )

    epoch_nums = [int(e) for e in epochs]

    # plot lines
    for idx_name, values in means.items():
        ax.plot(epoch_nums, values, marker="o", linewidth=2,
                color=index_colors[idx_name], label=idx_name, markersize=8)

    # place labels with vertical offset based on rank at each epoch to avoid overlap
    epoch_values = {e: {} for e in epoch_nums}
    for idx_name, values in means.items():
        for x, y in zip(epoch_nums, values):
            if not np.isnan(y):
                epoch_values[x][idx_name] = y

    for x, idx_vals in epoch_values.items():
        sorted_items = sorted(idx_vals.items(), key=lambda kv: kv[1])
        n = len(sorted_items)
        for rank, (idx_name, y) in enumerate(sorted_items):
            offset = (rank - (n - 1) / 2) * 0.018
            ax.text(x, y + offset, f"{y:.3f}",
                    ha="center", color=index_colors[idx_name],
                    fontsize=7, fontweight="bold")

    ax.set_xlabel("Year", color=TEXT_COLOR, fontsize=10)
    ax.set_ylabel("Mean Index Value", color=TEXT_COLOR, fontsize=10)
    ax.set_xticks(epoch_nums)
    ax.set_xticklabels(epochs, color=TEXT_COLOR)
    ax.legend(facecolor="#1a1a1a", labelcolor=TEXT_COLOR, fontsize=9,
              loc="upper right")

    plt.tight_layout()
    out_path = f"{output_dir}/chart5_index_time_series.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    logger.info(f"Chart 5 saved: {out_path}")
    return out_path


def generate_all_charts(
    run_id: str,
    vectors_local_dir: str,
    reports_local_dir: str
) -> list:
    """Generate all five charts and return list of output paths."""
    output_dir = "outputs/figures"
    os.makedirs(output_dir, exist_ok=True)

    paths = []
    paths.append(chart1_summary_statistics(run_id, output_dir,
                                           vectors_local_dir, reports_local_dir))
    paths.append(chart2_patch_size_distribution(run_id, output_dir,
                                                vectors_local_dir))
    paths.append(chart3_biomass_co2e_scatter(run_id, output_dir, vectors_local_dir))
    paths.append(chart4_cumulative_co2e(run_id, output_dir, vectors_local_dir))
    paths.append(chart5_index_time_series(run_id, output_dir))

    return paths