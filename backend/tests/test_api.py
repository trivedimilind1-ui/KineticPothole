"""
Integration tests for KineticPothole Flask REST API.
"""

import pytest
import json
from backend.app import app, db, detector


@pytest.fixture
def client():
    app.config["TESTING"] = True
    # Reset state
    detector.reset_state()
    db.reset_all()
    with app.test_client() as client:
        yield client
    # Clean up after
    db.reset_all()


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert "local_ip" in data
    assert "phone_access_url" in data


def test_post_event_and_get_events(client):
    payload = {
        "timestamp": 1700000000.0,
        "lat": 12.8232,
        "lon": 80.0441,
        "accuracy": 4.5,
        "severity": "HIGH",
        "hazard_type": "suspected pothole",
        "peak_dynamic_accel": 12.8,
        "device_id": "test-phone-1",
        "trip_id": "trip-alpha"
    }

    res_post = client.post("/api/events", json=payload)
    assert res_post.status_code == 201
    post_data = res_post.get_json()
    assert post_data["status"] == "success"
    assert post_data["event"]["id"] is not None

    res_get = client.get("/api/events")
    assert res_get.status_code == 200
    get_data = res_get.get_json()
    assert get_data["count"] == 1
    assert get_data["events"][0]["severity"] == "HIGH"


def test_feed_sample_stream(client):
    # Send a smooth sample
    sample = {
        "timestamp": 1700000000.0,
        "x": 0.0,
        "y": 0.0,
        "z": 9.80665,
        "lat": 12.8230,
        "lon": 80.0440
    }
    res = client.post("/api/feed_sample", json=sample)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "metrics" in data
    assert data["event_detected"] is False


def test_hazards_and_statistics(client):
    # Post two events near SRM Kattankulathur
    client.post("/api/events", json={
        "timestamp": 1700000010.0,
        "lat": 12.82310,
        "lon": 80.04420,
        "accuracy": 5.0,
        "severity": "MEDIUM",
        "peak_dynamic_accel": 7.2
    })
    client.post("/api/events", json={
        "timestamp": 1700000020.0,
        "lat": 12.82312,
        "lon": 80.04422,
        "accuracy": 6.0,
        "severity": "HIGH",
        "peak_dynamic_accel": 13.5
    })

    res_hazards = client.get("/api/hazards")
    assert res_hazards.status_code == 200
    hazards_data = res_hazards.get_json()
    # Clustered into 1 hazard because points are ~3m apart
    assert hazards_data["count"] == 1
    assert hazards_data["hazards"][0]["report_count"] == 2
    assert hazards_data["hazards"][0]["severity"] == "HIGH"

    res_stats = client.get("/api/statistics")
    assert res_stats.status_code == 200
    stats = res_stats.get_json()["statistics"]
    assert stats["total_events"] == 2
    assert stats["total_hazards"] == 1
    assert stats["high_severity_events"] == 1
    assert stats["medium_severity_events"] == 1


def test_calibrate_endpoint(client):
    samples = [
        {"timestamp": 1700000000.0 + i * 0.02, "x": 0.05, "y": 0.05, "z": 9.80665}
        for i in range(25)
    ]
    res = client.post("/api/calibrate", json={"samples": samples, "device_id": "phone-calib"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "calibration" in data


def test_batch_process_endpoint(client):
    samples = []
    # 50 normal samples
    for i in range(50):
        samples.append({
            "timestamp": 1000.0 + i * 0.02,
            "x": 0.0,
            "y": 0.0,
            "z": 9.80665,
            "lat": 12.8234,
            "lon": 80.0445
        })
    # Spike (pothole impact)
    for i in range(5):
        samples.append({
            "timestamp": 1001.0 + i * 0.02,
            "x": 3.0,
            "y": 4.0,
            "z": 9.80665 + 13.0,
            "lat": 12.8235,
            "lon": 80.0446
        })
    for i in range(50):
        samples.append({
            "timestamp": 1001.1 + i * 0.02,
            "x": 0.0,
            "y": 0.0,
            "z": 9.80665,
            "lat": 12.8236,
            "lon": 80.0447
        })

    res = client.post("/api/process_batch", json={
        "samples": samples,
        "device_id": "test-batch-runner",
        "trip_id": "test-trip",
        "is_synthetic": True
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["total_samples"] == 105
    assert data["event_count"] >= 1
    assert data["events"][0]["is_synthetic"] is True


def test_reset_endpoint(client):
    client.post("/api/events", json={
        "timestamp": 1700000010.0,
        "lat": 12.823,
        "lon": 80.044,
        "severity": "LOW",
        "peak_dynamic_accel": 4.0
    })
    res_reset = client.post("/api/reset")
    assert res_reset.status_code == 200
    
    res_stats = client.get("/api/statistics")
    stats = res_stats.get_json()["statistics"]
    assert stats["total_events"] == 0
    assert stats["total_hazards"] == 0


def test_static_and_data_routes(client):
    # Test index route
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert b"KineticPothole" in res_index.data

    # Test static assets
    res_css = client.get("/style.css")
    assert res_css.status_code == 200

    res_js = client.get("/app.js")
    assert res_js.status_code == 200

    # Test sample data route
    res_csv = client.get("/data/sample_pothole.csv")
    assert res_csv.status_code == 200
    assert b"timestamp,x,y,z" in res_csv.data
