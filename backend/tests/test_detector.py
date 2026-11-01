"""
Unit tests for the RoadImpactDetector signal processing engine.
"""

import pytest
import math
import numpy as np
from backend.detector import RoadImpactDetector


def test_detector_initialization():
    detector = RoadImpactDetector(threshold_low=3.0, threshold_med=6.0, threshold_high=10.0)
    assert detector.threshold_low == 3.0
    assert detector.threshold_med == 6.0
    assert detector.threshold_high == 10.0
    assert detector.calibrated is False


def test_threshold_validation():
    detector = RoadImpactDetector()
    with pytest.raises(ValueError):
        detector.set_thresholds(5.0, 3.0, 10.0)  # low > med is invalid
    with pytest.raises(ValueError):
        detector.set_thresholds(3.0, 8.0, 5.0)  # med > high is invalid


def test_normal_gravity_subtraction():
    detector = RoadImpactDetector()
    # Pure 1G stationary reading
    sample = {"timestamp": 1000.0, "x": 0.0, "y": 0.0, "z": 9.80665}
    metrics = detector.compute_sample_metrics(sample)
    
    assert pytest.approx(metrics["raw_magnitude"], 0.01) == 9.80665
    assert pytest.approx(metrics["dynamic_accel"], 0.01) == 0.0


def test_severity_classification():
    detector = RoadImpactDetector(threshold_low=3.0, threshold_med=6.0, threshold_high=11.0)
    assert detector.classify_severity(1.5) is None
    assert detector.classify_severity(3.5) == "LOW"
    assert detector.classify_severity(7.2) == "MEDIUM"
    assert detector.classify_severity(13.5) == "HIGH"


def test_cooldown_prevents_duplicate_events():
    detector = RoadImpactDetector(
        threshold_low=3.0,
        threshold_med=6.0,
        threshold_high=10.0,
        window_size=5,
        cooldown_seconds=1.0
    )

    events = []
    # Feed 20 samples with high impact every 100ms
    # Even though multiple samples cross threshold, cooldown should limit triggers
    t = 1000.0
    for i in range(20):
        # Spikes at t=1000, 1100, 1200, 1300...
        sample = {
            "timestamp": t + (i * 0.1),
            "x": 2.0,
            "y": 2.0,
            "z": 9.8 + 12.0  # Dynamic > 12
        }
        _, evt = detector.process_sample(sample)
        if evt:
            events.append(evt)

    # In 2.0 seconds with 1.0 second cooldown, should have at most 2 events, not 15
    assert 1 <= len(events) <= 2


def test_calibration_baseline():
    detector = RoadImpactDetector()
    # Generate smooth road samples with small noise around 0.2 m/s^2
    smooth_samples = []
    for i in range(50):
        noise = float(np.random.normal(0, 0.15))
        smooth_samples.append({
            "timestamp": 1000.0 + i * 0.02,
            "x": 0.1 + noise,
            "y": 0.1,
            "z": 9.80665 + noise
        })

    result = detector.calibrate_baseline(smooth_samples)
    assert detector.calibrated is True
    assert "baseline_mean" in result
    assert "baseline_std" in result
    assert detector.threshold_low > detector.baseline_mean
    assert detector.threshold_med > detector.threshold_low
    assert detector.threshold_high > detector.threshold_med


def test_batch_processing():
    detector = RoadImpactDetector(window_size=5, cooldown_seconds=0.5)
    
    samples = []
    # 2 seconds of smooth road (100 samples at 50Hz)
    for i in range(100):
        samples.append({
            "timestamp": 1000.0 + i * 0.02,
            "x": 0.0,
            "y": 0.0,
            "z": 9.80665
        })

    # One sudden sharp pothole impact at t=1002.0
    for i in range(5):
        samples.append({
            "timestamp": 1002.0 + i * 0.02,
            "x": 4.0,
            "y": 3.0,
            "z": 9.80665 + 14.0  # high dynamic impact
        })

    # Another 2 seconds smooth
    for i in range(100):
        samples.append({
            "timestamp": 1002.1 + i * 0.02,
            "x": 0.0,
            "y": 0.0,
            "z": 9.80665
        })

    res = detector.process_batch(samples)
    assert res["total_samples"] == 205
    assert res["event_count"] >= 1
    assert res["severity_breakdown"]["HIGH"] >= 1
