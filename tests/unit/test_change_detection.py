# tests/unit/test_change_detection.py

import numpy as np
import pytest
from src.pipeline.tasks.change_detection import (
    calculate_dnbr,
    apply_threshold,
    apply_forest_mask,
    apply_mapbiomas_filter,
    calibrate_threshold
)


def test_calculate_dnbr():
    nbr_t1 = np.array([[0.5, 0.6], [0.4, 0.7]])
    nbr_t2 = np.array([[0.3, 0.5], [0.4, 0.4]])
    result = calculate_dnbr(nbr_t1, nbr_t2)
    expected = np.array([[0.2, 0.1], [0.0, 0.3]])
    np.testing.assert_array_almost_equal(result, expected)


def test_apply_threshold():
    dnbr = np.array([[0.05, 0.15], [0.25, 0.08]])
    result = apply_threshold(dnbr, threshold=0.10)
    expected = np.array([[0, 1], [1, 0]], dtype=np.uint8)
    np.testing.assert_array_equal(result, expected)


def test_apply_forest_mask():
    deforestation = np.array([[1, 1], [1, 0]], dtype=np.uint8)
    forest_t1 = np.array([[1, 0], [1, 1]], dtype=np.uint8)
    result = apply_forest_mask(deforestation, forest_t1)
    expected = np.array([[1, 0], [1, 0]], dtype=np.uint8)
    np.testing.assert_array_equal(result, expected)


def test_apply_mapbiomas_filter():
    deforestation = np.array([[1, 1], [1, 1]], dtype=np.uint8)
    forest_t1 = np.array([[1, 1], [0, 1]], dtype=np.uint8)
    forest_t2 = np.array([[0, 1], [0, 0]], dtype=np.uint8)
    result = apply_mapbiomas_filter(deforestation, forest_t1, forest_t2)
    # only pixels that were forest at t1 AND non-forest at t2
    expected = np.array([[1, 0], [0, 1]], dtype=np.uint8)
    np.testing.assert_array_equal(result, expected)


def test_calibrate_threshold_finds_optimum():
    # create synthetic dnbr and prodes mask with known signal
    dnbr = np.zeros((100, 100))
    dnbr[10:30, 10:30] = 0.20  # deforested area
    prodes = np.zeros((100, 100), dtype=np.uint8)
    prodes[10:30, 10:30] = 1
    forest_t1 = np.ones((100, 100), dtype=np.uint8)

    threshold, f1 = calibrate_threshold(dnbr, prodes, forest_t1)
    assert f1 > 0.8
    assert threshold < 0.0  # threshold should be negative (loss signal)


def test_calibrate_threshold_no_signal():
    dnbr = np.zeros((50, 50))
    prodes = np.zeros((50, 50), dtype=np.uint8)
    forest_t1 = np.ones((50, 50), dtype=np.uint8)
    threshold, f1 = calibrate_threshold(dnbr, prodes, forest_t1)
    assert f1 == 0.0