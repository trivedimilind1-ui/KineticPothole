"""
Unit tests for the Multi-Modal Sensor Fusion Engine.
"""

import pytest
from backend.sensor_fusion import SensorFusionEngine


def test_visual_evidence_single_camera_persistence():
    engine = SensorFusionEngine()
    # 10 detections from the SAME camera (should not count as 10 independent sources!)
    detections = [
        {"camera_id": "CAM-SRM-01", "confidence": 0.72, "latitude": 12.823, "longitude": 80.044}
        for _ in range(10)
    ]
    score, sources_count, labels = engine.calculate_visual_evidence_score(detections)
    
    assert sources_count == 1  # Strictly 1 independent source!
    assert len(labels) == 1
    assert "CAM-SRM-01" in labels[0]
    # Score should include base confidence + persistence bonus
    assert 0.75 <= score <= 0.85


def test_visual_evidence_multi_camera_confirmation():
    engine = SensorFusionEngine()
    # Detections from TWO different cameras observing the same intersection
    detections = [
        {"camera_id": "CAM-SRM-NORTH", "confidence": 0.70},
        {"camera_id": "CAM-SRM-SOUTH", "confidence": 0.75}
    ]
    score, sources_count, labels = engine.calculate_visual_evidence_score(detections)

    assert sources_count == 2
    assert len(labels) == 2
    assert score > 0.75  # Multi-camera bonus applied


def test_smartphone_evidence_score():
    engine = SensorFusionEngine()
    events = [
        {"device_id": "phone-A", "peak_dynamic_accel": 13.5, "severity": "HIGH"},
        {"device_id": "phone-B", "peak_dynamic_accel": 12.8, "severity": "HIGH"}
    ]
    score, sources_count, labels = engine.calculate_smartphone_evidence_score(events)

    assert sources_count == 2
    assert len(labels) == 2
    assert score >= 0.85  # Multi-device high impact


def test_dual_confirmation_synergy_boost():
    engine = SensorFusionEngine()
    # Visual evidence: 0.75, Smartphone evidence: 0.80
    fusion = engine.fuse_evidence(
        visual_score=0.75,
        visual_sources_count=1,
        visual_labels=["CCTV: CAM-01"],
        phone_score=0.80,
        phone_sources_count=1,
        phone_labels=["Smartphone: phone-1"]
    )

    assert fusion["fusion_status"] == "DUAL_CONFIRMED"
    assert fusion["independent_sources_count"] == 2
    # Combined confidence should exceed both individual scores
    assert fusion["combined_confidence"] >= 0.90
    assert len(fusion["evidence_sources"]) == 2


def test_single_modality_status():
    engine = SensorFusionEngine()

    # Visual only
    vis_only = engine.fuse_evidence(
        visual_score=0.70,
        visual_sources_count=1,
        visual_labels=["CCTV: CAM-01"],
        phone_score=0.0,
        phone_sources_count=0,
        phone_labels=[]
    )
    assert vis_only["fusion_status"] == "VISUAL_ONLY"
    assert vis_only["combined_confidence"] == 0.70

    # Impact only
    imp_only = engine.fuse_evidence(
        visual_score=0.0,
        visual_sources_count=0,
        visual_labels=[],
        phone_score=0.65,
        phone_sources_count=1,
        phone_labels=["Smartphone: phone-1"]
    )
    assert imp_only["fusion_status"] == "IMPACT_ONLY"
    assert imp_only["combined_confidence"] == 0.65
