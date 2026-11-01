"""
Test CCTV AI Road Damage and Sensor Fusion API endpoints.
"""
import os
import pytest
from backend.app import app
from backend.database import Database

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_cctv_cameras_endpoints(client):
    # 1. GET cameras
    res = client.get("/api/cctv/cameras")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["count"] >= 3
    cam_ids = [c["camera_id"] for c in data["cameras"]]
    assert "CAM-GST-SERVICE" in cam_ids

    # 2. POST update/add camera
    res_post = client.post("/api/cctv/cameras", json={
        "camera_id": "CAM-TEST-CORRIDOR",
        "name": "Test Corridor Camera",
        "latitude": 12.824000,
        "longitude": 80.045000,
        "road_segment": "SRM Service Road"
    })
    assert res_post.status_code in [200, 201]
    post_data = res_post.get_json()
    assert post_data["camera"]["camera_id"] == "CAM-TEST-CORRIDOR"


def test_cctv_process_video_and_serve_frames(client):
    # Process sample video
    res = client.post("/api/cctv/process_video", json={
        "video_filename": "sample_cctv_pothole.mp4",
        "camera_id": "CAM-GST-SERVICE",
        "interval_seconds": 2.0
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["total_frames_analyzed"] > 0
    assert len(data["detections"]) > 0

    first_det = data["detections"][0]
    assert "frame_filename" in first_det
    assert "confidence" in first_det
    assert "defect_detected" in first_det

    # Verify frame serving route
    frame_fn = first_det["frame_filename"]
    res_img = client.get(f"/api/cctv/frames/{frame_fn}")
    assert res_img.status_code == 200
    assert res_img.mimetype.startswith("image/")


def test_fusion_run_endpoint(client):
    # Post a smartphone impact event near CAM-GST-SERVICE (12.821500, 80.041800)
    client.post("/api/events", json={
        "timestamp": 1700000020.0,
        "lat": 12.821510,
        "lon": 80.041810,
        "severity": "HIGH",
        "peak_dynamic_accel": 14.5,
        "hazard_type": "Pothole-like Impact",
        "device_id": "phone-eval-1",
        "is_synthetic": True
    })

    # Run fusion
    res_fusion = client.post("/api/fusion/run", json={
        "max_spatial_distance_meters": 35.0,
        "max_time_window_hours": 48.0
    })
    assert res_fusion.status_code == 200
    fdata = res_fusion.get_json()
    assert fdata["status"] == "success"
    assert "hazards" in fdata
