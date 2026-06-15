# src/pipeline/utils/carbon_utils.py

"""
IPCC Tier 1 carbon stock loss calculation functions.
Reference: IPCC 2006 Guidelines for National Greenhouse Gas Inventories, Vol 4, Ch 4.
"""

CARBON_FRACTION = 0.47
CO2E_CONVERSION = 3.6667
Z_90 = 1.645  # 90% confidence interval z-score


def agb_loss(agbd_mean: float, area_ha: float) -> float:
    """Calculate aboveground biomass loss in Mg."""
    return agbd_mean * area_ha


def carbon_loss(agb_loss_mg: float) -> float:
    """Convert AGB loss to carbon mass in Mg C."""
    return agb_loss_mg * CARBON_FRACTION


def co2e(carbon_loss_mg: float) -> float:
    """Convert carbon mass to CO2 equivalent in Mg CO2e."""
    return carbon_loss_mg * CO2E_CONVERSION


def co2e_from_patch(agbd_mean: float, area_ha: float) -> float:
    """Calculate total CO2e loss for a deforested patch."""
    return co2e(carbon_loss(agb_loss(agbd_mean, area_ha)))


def co2e_lower_90(agbd_mean: float, agbd_se: float, area_ha: float) -> float:
    """Lower bound of 90% confidence interval for CO2e loss."""
    agbd_lower = max(0.0, agbd_mean - Z_90 * agbd_se)
    return co2e(carbon_loss(agb_loss(agbd_lower, area_ha)))


def co2e_upper_90(agbd_mean: float, agbd_se: float, area_ha: float) -> float:
    """Upper bound of 90% confidence interval for CO2e loss."""
    agbd_upper = agbd_mean + Z_90 * agbd_se
    return co2e(carbon_loss(agb_loss(agbd_upper, area_ha)))


def summarise_patches(patches: list) -> dict:
    """
    Aggregate per-patch carbon results into a summary dict.
    patches: list of dicts with keys area_ha, agbd_mean, co2e_mg,
             co2e_lower_90, co2e_upper_90.
    """
    if not patches:
        return {}

    total_area = sum(p["area_ha"] for p in patches)
    total_co2e = sum(p["co2e_mg"] for p in patches)
    total_co2e_lower = sum(p["co2e_lower_90"] for p in patches)
    total_co2e_upper = sum(p["co2e_upper_90"] for p in patches)
    mean_agbd = sum(p["agbd_mean"] * p["area_ha"] for p in patches) / total_area

    return {
        "patch_count": len(patches),
        "deforested_area_ha": round(total_area, 2),
        "agbd_mean_mg_ha": round(mean_agbd, 2),
        "total_agb_loss_mg": round(agb_loss(mean_agbd, total_area), 2),
        "total_carbon_loss_mg_c": round(carbon_loss(agb_loss(mean_agbd, total_area)), 2),
        "total_co2e_mg": round(total_co2e, 2),
        "co2e_lower_90_mg": round(total_co2e_lower, 2),
        "co2e_upper_90_mg": round(total_co2e_upper, 2),
        "methodology": "IPCC Tier 1 / VCS-aligned",
        "gedi_product": "L4B_v2.1",
        "agb_only_note": "Belowground, deadwood, litter and soil carbon excluded"
    }