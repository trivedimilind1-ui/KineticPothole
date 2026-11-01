"""
Unit tests for the SQLite Database module and spatial clustering.
"""

import os
import pytest
from backend.database import Database, haversine_distance


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_potholes.db"
    db = Database(db_path=str(db_file), cluster_radius_meters=20.0)
    return db


def test_haversine_distance():
    # Distance between two known points in Kattankulathur, SRM campus
    # Point A: Main Arch (12.8231, 80.0444)
    # Point B: ~50 meters away (12.8235, 80.0444)
    d = haversine_distance(12.8231, 80.0444, 12.8235, 80.0444)
    assert 40.0 < d < 50.0

    # Distance to identical point is 0
    assert haversine_distance(12.8231, 80.0444, 12.8231, 80.0444) == 0.0


def test_record_single_event_creates_hazard(temp_db):
    event_data = {
        "timestamp": 1700000000.0,
        "lat": 12.823050,
        "lon": 80.044200,
        "accuracy": 8.0,
        "severity": "HIGH",
        "hazard_type": "suspected pothole",
        "peak_dynamic_accel": 12.4,
        "device_id": "phone-A",
        "trip_id": "trip-1"
    }

    result = temp_db.record_event(event_data)
    assert result["id"] is not None
    assert result["hazard_id"] is not None

    hazards = temp_db.get_hazards()
    assert len(hazards) == 1
    assert hazards[0]["severity"] == "HIGH"
    assert hazards[0]["report_count"] == 1
    assert hazards[0]["unique_devices_count"] == 1


def test_hazard_clustering_within_radius(temp_db):
    # Event 1 at location
    temp_db.record_event({
        "timestamp": 1700000000.0,
        "lat": 12.823000,
        "lon": 80.044200,
        "accuracy": 5.0,
        "severity": "MEDIUM",
        "hazard_type": "suspected pothole",
        "peak_dynamic_accel": 7.5,
        "device_id": "phone-A",
        "trip_id": "trip-1"
    })

    # Event 2 just 8 meters away (should be clustered into same hazard!)
    temp_db.record_event({
        "timestamp": 1700000050.0,
        "lat": 12.823050,
        "lon": 80.044200,
        "accuracy": 5.0,
        "severity": "HIGH",
        "hazard_type": "suspected pothole",
        "peak_dynamic_accel": 13.0,
        "device_id": "phone-B",
        "trip_id": "trip-2"
    })

    hazards = temp_db.get_hazards()
    assert len(hazards) == 1  # Grouped together!
    h = hazards[0]
    assert h["report_count"] == 2
    assert h["unique_devices_count"] == 2
    assert h["severity"] == "HIGH"  # Upgraded to HIGH
    assert h["max_peak_accel"] == 13.0
    assert h["avg_peak_accel"] == pytest.approx(10.25, 0.05)


def test_event_without_gps(temp_db):
    result = temp_db.record_event({
        "timestamp": 1700000100.0,
        "lat": None,
        "lon": None,
        "severity": "LOW",
        "peak_dynamic_accel": 3.8
    })
    assert result["id"] is not None
    assert result["hazard_id"] is None

    stats = temp_db.get_statistics()
    assert stats["total_events"] == 1
    assert stats["total_hazards"] == 0


def test_calibration_storage(temp_db):
    cal_id = temp_db.record_calibration(
        device_id="device-test",
        baseline_mean=0.22,
        baseline_std=0.08,
        threshold_low=3.0,
        threshold_med=6.5,
        threshold_high=11.5,
        sample_count=100
    )
    assert cal_id > 0
    latest = temp_db.get_latest_calibration("device-test")
    assert latest is not None
    assert latest["baseline_mean"] == 0.22
