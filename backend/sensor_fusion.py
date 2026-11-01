"""
KineticPothole - Multi-Modal Sensor Fusion Engine

Combines visual evidence from CCTV road cameras and physical impact evidence
from smartphone accelerometers using spatial proximity, temporal correlation,
and road-segment topology.

Strictly avoids double-counting multiple video frames from the same camera
as independent source confirmations.
"""

from typing import List, Dict, Any, Optional, Tuple
import math
import time
from backend.database import haversine_distance


class SensorFusionEngine:
    """
    Fuses CCTV visual detections and smartphone impact reports
    into unified, cross-validated road hazards.
    """

    # Maximum matching distance between camera location and smartphone report (meters)
    # 35 meters accounts for camera field-of-view along the road segment
    MATCH_RADIUS_METERS = 35.0

    # Temporal correlation threshold in seconds (optional, e.g. 24 hours for daily aggregation)
    MAX_TIME_DELTA_HOURS = 24.0

    def __init__(self, match_radius_meters: float = 35.0):
        self.match_radius_meters = match_radius_meters

    def calculate_visual_evidence_score(self, detections: List[Dict[str, Any]]) -> Tuple[float, int, List[str]]:
        """
        Compute visual evidence score from CCTV detections.
        Rule: Avoid double-counting multiple frames from the same camera as independent confirmations!
        Multiple frames from the same camera increase persistence bonus (up to +0.15),
        NOT independent source counts.
        """
        if not detections:
            return 0.0, 0, []

        unique_cameras = set()
        max_conf = 0.0
        confs = []

        for d in detections:
            cam_id = d.get("camera_id", "CAM-UNKNOWN")
            unique_cameras.add(cam_id)
            conf = float(d.get("confidence", 0.5))
            confs.append(conf)
            if conf > max_conf:
                max_conf = conf

        # Base score from highest detection confidence
        score = max_conf

        # Persistence bonus: seen across multiple frames from the camera
        frame_count = len(detections)
        if frame_count >= 3:
            score += 0.05
        if frame_count >= 6:
            score += 0.05

        # Independent multi-camera confirmation bonus
        num_cams = len(unique_cameras)
        if num_cams > 1:
            score += min(0.15, (num_cams - 1) * 0.10)

        visual_score = round(min(0.95, max(0.1, score)), 2)
        camera_labels = [f"CCTV: {c}" for c in unique_cameras]

        return visual_score, num_cams, camera_labels

    def calculate_smartphone_evidence_score(self, events: List[Dict[str, Any]]) -> Tuple[float, int, List[str]]:
        """
        Compute physical accelerometer evidence score.
        Differentiates multiple passes from single device vs multiple independent devices.
        """
        if not events:
            return 0.0, 0, []

        unique_devices = set()
        peaks = []
        severities = set()

        for e in events:
            dev_id = e.get("device_id", "phone-default")
            unique_devices.add(dev_id)
            peak = float(e.get("peak_dynamic_accel", 0.0))
            peaks.append(peak)
            severities.add((e.get("severity") or "LOW").upper())

        max_peak = max(peaks) if peaks else 0.0

        # Scale peak dynamic acceleration into evidence score
        # 12+ m/s^2 -> ~0.80 base score; 6-12 m/s^2 -> ~0.65; <6 m/s^2 -> ~0.45
        if max_peak >= 11.5 or "HIGH" in severities:
            base_score = 0.80
        elif max_peak >= 6.5 or "MEDIUM" in severities:
            base_score = 0.65
        else:
            base_score = 0.45

        # Multiple passes bonus
        total_reports = len(events)
        if total_reports >= 2:
            base_score += 0.05

        # Independent distinct device confirmation
        num_devices = len(unique_devices)
        if num_devices > 1:
            base_score += min(0.15, (num_devices - 1) * 0.08)

        phone_score = round(min(0.95, base_score), 2)
        device_labels = [f"Smartphone: {d}" for d in unique_devices]

        return phone_score, num_devices, device_labels

    def fuse_evidence(
        self,
        visual_score: float,
        visual_sources_count: int,
        visual_labels: List[str],
        phone_score: float,
        phone_sources_count: int,
        phone_labels: List[str]
    ) -> Dict[str, Any]:
        """
        Combine visual and physical evidence scores using multi-modal Bayesian fusion.
        Formula: C_fused = 1 - (1 - S_visual) * (1 - S_phone)
        Plus dual-confirmation synergy bonus!
        """
        total_independent_sources = visual_sources_count + phone_sources_count
        all_labels = visual_labels + phone_labels

        if visual_score > 0 and phone_score > 0:
            # Dual confirmation: Both CCTV eye and Vehicle suspension shock match!
            # Synergy bonus reflects independent modality verification
            combined = 1.0 - (1.0 - visual_score) * (1.0 - phone_score)
            combined_confidence = round(min(0.98, combined + 0.06), 2)
            fusion_status = "DUAL_CONFIRMED"
            status_description = "Dual Confirmation: Both CCTV visual defect and vehicle impact confirm hazard."
        elif visual_score > 0:
            combined_confidence = visual_score
            fusion_status = "VISUAL_ONLY"
            status_description = "Visual Evidence Only: CCTV camera detected pavement distress; awaiting vehicle impact confirmation."
        elif phone_score > 0:
            combined_confidence = phone_score
            fusion_status = "IMPACT_ONLY"
            status_description = "Impact Evidence Only: Vehicle suspension shock detected; no CCTV coverage at this coordinate."
        else:
            combined_confidence = 0.0
            fusion_status = "UNVERIFIED"
            status_description = "Insufficient evidence from both modalities."

        return {
            "visual_evidence_score": visual_score,
            "smartphone_evidence_score": phone_score,
            "combined_confidence": combined_confidence,
            "independent_sources_count": total_independent_sources,
            "fusion_status": fusion_status,
            "status_description": status_description,
            "evidence_sources": all_labels
        }

    def correlate_detections_with_hazards(
        self,
        cctv_detections: List[Dict[str, Any]],
        hazards: List[Dict[str, Any]],
        raw_events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Correlate CCTV detections with existing road hazard clusters based on geographic proximity.
        Returns updated hazard list with fusion scores and linked CCTV frame snapshots.
        """
        fused_results = []

        for h in hazards:
            h_lat = float(h["latitude"])
            h_lon = float(h["longitude"])
            hazard_id = h.get("id")

            # Find matching smartphone events for this hazard
            matched_events = [e for e in raw_events if e.get("hazard_id") == hazard_id]
            if not matched_events:
                # Spatial fallback
                matched_events = [
                    e for e in raw_events
                    if e.get("latitude") and e.get("longitude") and
                    haversine_distance(h_lat, h_lon, float(e["latitude"]), float(e["longitude"])) <= self.match_radius_meters
                ]

            # Find matching CCTV detections within match radius
            matched_cctv = []
            for det in cctv_detections:
                c_lat = float(det.get("latitude", 0.0))
                c_lon = float(det.get("longitude", 0.0))
                dist = haversine_distance(h_lat, h_lon, c_lat, c_lon)
                if dist <= self.match_radius_meters:
                    matched_cctv.append(det)

            # Compute evidence scores
            v_score, v_cams, v_labels = self.calculate_visual_evidence_score(matched_cctv)
            p_score, p_devs, p_labels = self.calculate_smartphone_evidence_score(matched_events)

            fusion = self.fuse_evidence(
                visual_score=v_score,
                visual_sources_count=v_cams,
                visual_labels=v_labels,
                phone_score=p_score,
                phone_sources_count=p_devs,
                phone_labels=p_labels
            )

            # Pick latest annotated image
            latest_image = matched_cctv[-1]["image_file"] if matched_cctv else h.get("last_cctv_image")

            fused_hazard = dict(h)
            fused_hazard["visual_evidence_score"] = fusion["visual_evidence_score"]
            fused_hazard["smartphone_evidence_score"] = fusion["smartphone_evidence_score"]
            fused_hazard["combined_confidence"] = fusion["combined_confidence"]
            fused_hazard["confidence_score"] = fusion["combined_confidence"]
            fused_hazard["fusion_status"] = fusion["fusion_status"]
            fused_hazard["status_description"] = fusion["status_description"]
            fused_hazard["independent_sources_count"] = fusion["independent_sources_count"]
            fused_hazard["evidence_sources"] = fusion["evidence_sources"]
            fused_hazard["cctv_detections_count"] = len(matched_cctv)
            fused_hazard["last_cctv_image"] = latest_image

            fused_results.append(fused_hazard)

        return fused_results
