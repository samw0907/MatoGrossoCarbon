# scripts/generate_poster.py

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
import numpy as np
import os

BACKGROUND = "#0a0a0a"
TEXT_COLOR = "#e0e0e0"
ACCENT = "#4a9eff"
HEADING_COLOR = "#ffffff"
DPI = 150

FIGURES = {
    "forest_loss":    "figures/figure3_forest_cover.png",
    "carbon_loss":    "figures/figure4_carbon_loss.png",
    "dnbr":           "figures/figure2_change_detection.png",
    "cumulative_co2e": "figures/chart4_cumulative_co2e.png",
    "index_series":   "figures/chart5_index_time_series.png",
}


def load_img(path):
    """Load image as numpy array."""
    return np.array(Image.open(path))


def add_section_heading(ax, text):
    """Add a small section heading label."""
    ax.text(0, 1.02, text, transform=ax.transAxes,
            color=ACCENT, fontsize=7, fontweight="bold",
            fontfamily="monospace", va="bottom")


def main():
    os.makedirs("outputs/figures", exist_ok=True)

    fig = plt.figure(figsize=(24, 16), facecolor=BACKGROUND)

    # header strip
    header_ax = fig.add_axes([0.0, 0.93, 1.0, 0.07], facecolor=BACKGROUND)
    header_ax.axis("off")
    header_ax.text(0.02, 0.7,
                   "Deforestation & Carbon Stock Monitoring  |  Mato Grosso, Brazil  |  2020-2023",
                   color=HEADING_COLOR, fontsize=18, fontweight="bold",
                   transform=header_ax.transAxes, va="top")
    header_ax.text(0.02, 0.2,
                   "IPCC Tier 1 / VCS-aligned methodology  |  Sentinel-2 · GEDI L4B · MapBiomas · PRODES",
                   color=TEXT_COLOR, fontsize=10,
                   transform=header_ax.transAxes, va="top")
    header_ax.axhline(0.05, color=ACCENT, linewidth=1)

    # main grid: [left | centre | right]
    # left: 0.01-0.38, centre: 0.40-0.62, right: 0.64-0.99
    # rows: top 0.52-0.92, bottom 0.02-0.50

    pad = 0.01

    # LEFT TOP: forest cover loss panel
    ax_forest = fig.add_axes([0.01, 0.48, 0.37, 0.43], facecolor=BACKGROUND)
    ax_forest.imshow(load_img(FIGURES["forest_loss"]))
    ax_forest.axis("off")
    add_section_heading(ax_forest, "FOREST COVER & 2020-2023 LOSS  |  MapBiomas Collection 10")

    # LEFT BOTTOM: carbon loss map
    ax_carbon = fig.add_axes([0.01, 0.02, 0.37, 0.44], facecolor=BACKGROUND)
    ax_carbon.imshow(load_img(FIGURES["carbon_loss"]))
    ax_carbon.axis("off")
    add_section_heading(ax_carbon, "CO2e LOSS PER PATCH  |  IPCC Tier 1")

    # CENTRE: text column
    ax_text = fig.add_axes([0.39, 0.02, 0.22, 0.89], facecolor=BACKGROUND)
    ax_text.axis("off")

    text_content = [
        ("STUDY AREA", ACCENT, 9, "bold", 0.97),
        ("Mato Grosso, Brazilian Amazon\n~500,000 ha | Alta Floresta region\nArc of Deforestation",
         TEXT_COLOR, 7.5, "normal", 0.93),

        ("METHODOLOGY", ACCENT, 9, "bold", 0.83),
        ("Sentinel-2 L2A dry season composites\n(June-August) via Google Earth Engine.\nSCL cloud masking, median compositing.",
         TEXT_COLOR, 7.5, "normal", 0.79),
        ("Dual-filter deforestation detection:\n(1) dNBR threshold calibrated against\nPRODES by F1 score optimisation\n(2) MapBiomas forest transition\nconfirmation",
         TEXT_COLOR, 7.5, "normal", 0.70),
        ("Carbon stock loss per patch via\nNASA GEDI L4B aboveground biomass\n(1km v2.1), IPCC Tier 1 formula:\nCO2e = AGBD x area x 0.47 x 3.667\n90% CI from GEDI uncertainty.",
         TEXT_COLOR, 7.5, "normal", 0.59),

        ("KEY FINDINGS", ACCENT, 9, "bold", 0.47),
        ("Forest loss 2020-2023\n~124,000 ha  (~4.5% of baseline)",
         HEADING_COLOR, 8, "bold", 0.43),
        ("                  2020-2022    2022-2023",
         TEXT_COLOR, 7, "normal", 0.38),
        ("Deforested       39,910 ha    16,336 ha",
         TEXT_COLOR, 7, "normal", 0.35),
        ("Total CO2e          3.94 Mt      1.93 Mt",
         TEXT_COLOR, 7, "normal", 0.32),
        ("Patches               1,628          831",
         TEXT_COLOR, 7, "normal", 0.29),
        ("F1 vs PRODES         0.392        0.418",
         TEXT_COLOR, 7, "normal", 0.26),
        ("5-6% of patches account for\n80% of total CO2e loss",
         HEADING_COLOR, 7.5, "bold", 0.20),
        ("Declining rate consistent with\nnational PRODES trend post-2022",
         TEXT_COLOR, 7.5, "normal", 0.15),

        ("PIPELINE", ACCENT, 9, "bold", 0.08),
        ("Python · Prefect · GEE · AWS S3\nGitHub Actions CI/CD · Docker",
         TEXT_COLOR, 7.5, "normal", 0.04),
    ]

    for text, color, size, weight, y in text_content:
        ax_text.text(0.05, y, text,
                     transform=ax_text.transAxes,
                     color=color, fontsize=size, fontweight=weight,
                     fontfamily="monospace" if weight == "normal" else "sans-serif",
                     va="top", linespacing=1.4)

    # RIGHT TOP: dNBR change detection
    ax_dnbr = fig.add_axes([0.63, 0.62, 0.36, 0.29], facecolor=BACKGROUND)
    ax_dnbr.imshow(load_img(FIGURES["dnbr"]))
    ax_dnbr.axis("off")
    add_section_heading(ax_dnbr, "dNBR CHANGE DETECTION  |  2020-2022 & 2022-2023")

    # RIGHT MIDDLE: cumulative CO2e
    ax_cumco2e = fig.add_axes([0.63, 0.33, 0.36, 0.27], facecolor=BACKGROUND)
    ax_cumco2e.imshow(load_img(FIGURES["cumulative_co2e"]))
    ax_cumco2e.axis("off")
    add_section_heading(ax_cumco2e, "CUMULATIVE CO2e BY PATCH SIZE")

    # RIGHT BOTTOM: index time series
    ax_idx = fig.add_axes([0.63, 0.02, 0.36, 0.29], facecolor=BACKGROUND)
    ax_idx.imshow(load_img(FIGURES["index_series"]))
    ax_idx.axis("off")
    add_section_heading(ax_idx, "MEAN SPECTRAL INDEX VALUES  |  2020-2023")

    # footer
    footer_ax = fig.add_axes([0.0, 0.0, 1.0, 0.02], facecolor=BACKGROUND)
    footer_ax.axis("off")
    footer_ax.axhline(0.9, color=ACCENT, linewidth=0.5)
    footer_ax.text(0.01, 0.4,
                   "github.com/samw0907/MatoGrossoCarbon  |  "
                   "Sentinel-2: Copernicus/ESA  |  GEDI L4B: NASA ORNL DAAC  |  "
                   "MapBiomas Collection 10  |  PRODES: INPE/TerraBrasilis",
                   color=TEXT_COLOR, fontsize=6.5,
                   transform=footer_ax.transAxes, va="center")

    out_path = "outputs/figures/poster_mato_grosso.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor=BACKGROUND, edgecolor="none")
    plt.close(fig)
    print(f"Poster saved: {out_path}")


if __name__ == "__main__":
    main()