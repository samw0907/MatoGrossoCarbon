# tests/unit/test_carbon_utils.py

import pytest
from src.pipeline.utils.carbon_utils import (
    agb_loss,
    carbon_loss,
    co2e,
    co2e_from_patch,
    co2e_lower_90,
    co2e_upper_90,
    summarise_patches
)


def test_agb_loss():
    assert agb_loss(200.0, 10.0) == 2000.0
    assert agb_loss(0.0, 10.0) == 0.0


def test_carbon_loss():
    assert carbon_loss(2000.0) == pytest.approx(940.0, rel=1e-3)


def test_co2e():
    assert co2e(940.0) == pytest.approx(3444.698, rel=1e-3)


def test_co2e_from_patch():
    result = co2e_from_patch(agbd_mean=200.0, area_ha=10.0)
    assert result == pytest.approx(3444.698, rel=1e-3)


def test_co2e_lower_90_less_than_mean():
    lower = co2e_lower_90(agbd_mean=200.0, agbd_se=20.0, area_ha=10.0)
    mean = co2e_from_patch(agbd_mean=200.0, area_ha=10.0)
    assert lower < mean


def test_co2e_upper_90_greater_than_mean():
    upper = co2e_upper_90(agbd_mean=200.0, agbd_se=20.0, area_ha=10.0)
    mean = co2e_from_patch(agbd_mean=200.0, area_ha=10.0)
    assert upper > mean


def test_co2e_lower_90_zero_se():
    lower = co2e_lower_90(agbd_mean=200.0, agbd_se=0.0, area_ha=10.0)
    mean = co2e_from_patch(agbd_mean=200.0, area_ha=10.0)
    assert lower == pytest.approx(mean, rel=1e-3)


def test_co2e_lower_clamps_at_zero():
    # very high SE should not produce negative biomass
    lower = co2e_lower_90(agbd_mean=10.0, agbd_se=100.0, area_ha=5.0)
    assert lower >= 0.0


def test_summarise_patches():
    patches = [
        {"area_ha": 5.0, "agbd_mean": 150.0, "co2e_mg": 1300.0,
         "co2e_lower_90": 1100.0, "co2e_upper_90": 1500.0},
        {"area_ha": 10.0, "agbd_mean": 200.0, "co2e_mg": 2600.0,
         "co2e_lower_90": 2200.0, "co2e_upper_90": 3000.0},
    ]
    summary = summarise_patches(patches)
    assert summary["patch_count"] == 2
    assert summary["deforested_area_ha"] == 15.0
    assert summary["total_co2e_mg"] == pytest.approx(3900.0, rel=1e-3)


def test_summarise_patches_empty():
    assert summarise_patches([]) == {}