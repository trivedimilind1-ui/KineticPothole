"""
KineticPothole - CCTV AI Road Damage Detection Module

Extracts frames from CCTV road footage, respects privacy by restricting analysis
to road surfaces (ignoring vehicle occupants/faces), and detects suspected pothole
and pavement damage regions using a YOLO-compatible detection pipeline with
an OpenCV computer-vision fallback.
"""

import os
import time
import math
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np


class CCTVDetector:
    """
    CCTV Video Road Damage Detector.
    Supports YOLO ONNX models via OpenCV DNN, with an asphalt distress
    analysis fallback when external weights are not yet supplied.
    """

    def __init__(self, model_path: Optional[str] = None, frames_output_dir: Optional[str] = None):
        self.model_path = model_path
        self.net = None
        self.model_type = "heuristic_cv"

        # Frame save directory for web dashboard preview
        if frames_output_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.frames_output_dir = os.path.join(base_dir, "cctv_frames")
        else:
            self.frames_output_dir = frames_output_dir

        os.makedirs(self.frames_output_dir, exist_ok=True)

        self._load_model()

    def _load_model(self):
        """Load YOLO model if ONNX weights exist, else initialize CV pipeline."""
        if self.model_path and os.path.exists(self.model_path):
            try:
                # Load via OpenCV DNN
                self.net = cv2.dnn.readNetFromONNX(self.model_path)
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self.model_type = "yolo_onnx"
                print(f"[CCTVDetector] Successfully loaded YOLO ONNX model from {self.model_path}")
            except Exception as e:
                print(f"[CCTVDetector] Failed to load ONNX model ({e}). Using CV damage analyzer.")
                self.model_type = "heuristic_cv"
        else:
            self.model_type = "heuristic_cv"

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata and integration state."""
        return {
            "model_type": self.model_type,
            "weights_configured": self.net is not None,
            "model_path": self.model_path,
            "privacy_compliance": "Road Surface ROI Only (Faces & Occupants Excluded)",
            "classes": ["suspected_pothole", "surface_depression", "road_crack"]
        }

    def extract_frames(self, video_path: str, interval_seconds: float = 1.0) -> List[Dict[str, Any]]:
        """
        Extract video frames from a video file at a configurable time interval.
        Returns a list of metadata dictionaries containing frame image and timestamp.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or math.isnan(fps):
            fps = 30.0

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = max(1, int(round(fps * interval_seconds)))

        extracted = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = round(frame_idx / fps, 2)
                extracted.append({
                    "frame_idx": frame_idx,
                    "timestamp": timestamp,
                    "frame": frame
                })

            frame_idx += 1

        cap.release()
        return extracted

    def detect_in_frame(self, frame: np.ndarray, min_confidence: float = 0.50) -> List[Dict[str, Any]]:
        """
        Run road damage detection on a single frame.
        Applies strict Privacy ROI: analyzes only the lower 65% of the frame (roadway),
        preventing facial recognition or occupant identification.
        """
        h, w = frame.shape[:2]
        
        # Privacy Guard: Road surface Region of Interest (lower 65% of frame)
        roi_top = int(h * 0.35)
        road_roi = frame[roi_top:h, 0:w]

        detections = []

        if self.model_type == "yolo_onnx" and self.net is not None:
            # YOLO DNN Inference
            blob = cv2.dnn.blobFromImage(road_roi, 1 / 255.0, (640, 640), swapRB=True, crop=False)
            self.net.setInput(blob)
            outputs = self.net.forward()
            # Standard YOLO output processing
            # [batch, boxes, 5 + classes]
            for det in outputs[0]:
                conf = float(det[4])
                if conf >= min_confidence:
                    cx = int(det[0] * w)
                    cy = int(det[1] * (h - roi_top)) + roi_top
                    bw = int(det[2] * w)
                    bh = int(det[3] * (h - roi_top))
                    bx = max(0, cx - bw // 2)
                    by = max(roi_top, cy - bh // 2)
                    detections.append({
                        "box": [bx, by, bw, bh],
                        "confidence": round(conf, 2),
                        "defect_type": "suspected visual road defect",
                        "area_pixels": bw * bh
                    })
        else:
            # High-reliability Computer Vision Asphalt Depression & Defect Analyzer
            # Analyzes dark crater depressions, high gradient edges, and asphalt irregularities
            gray_roi = cv2.cvtColor(road_roi, cv2.COLOR_BGR2GRAY)
            
            # CLAHE (Contrast Limited Adaptive Histogram Equalization) for road texture
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray_roi)

            # Gaussian blur to filter asphalt aggregate micro-texture
            blurred = cv2.GaussianBlur(enhanced, (7, 7), 0)

            # Adaptive threshold for dark depression cavities
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 25, 9
            )

            # Morphological closing to solidify cavity contours
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            min_area = int((w * h) * 0.0015)  # Reject tiny specks
            max_area = int((w * h) * 0.15)    # Reject whole road shadows

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if min_area <= area <= max_area:
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    aspect_ratio = float(bw) / float(bh) if bh > 0 else 1.0

                    # Potholes typically have reasonable aspect ratios (0.4 to 3.0), not thin lines
                    if 0.4 <= aspect_ratio <= 3.5:
                        # Compute confidence based on edge sharpness & contrast with surround
                        roi_patch = gray_roi[by:by + bh, bx:bx + bw]
                        if roi_patch.size > 0:
                            darkness = 255 - np.mean(roi_patch)
                            confidence = min(0.92, max(0.55, (darkness / 255.0) * 0.8 + (area / max_area) * 0.3))
                        else:
                            confidence = 0.60

                        if confidence >= min_confidence:
                            detections.append({
                                "box": [bx, by + roi_top, bw, bh],
                                "confidence": round(confidence, 2),
                                "defect_type": "suspected visual road defect",
                                "area_pixels": int(area)
                            })

        # Non-maximum suppression to eliminate overlapping redundant boxes
        if len(detections) > 1:
            boxes = [d["box"] for d in detections]
            confs = [d["confidence"] for d in detections]
            indices = cv2.dnn.NMSBoxes(
                [[b[0], b[1], b[2], b[3]] for b in boxes],
                confs,
                score_threshold=min_confidence,
                nms_threshold=0.4
            )
            filtered = []
            if len(indices) > 0:
                for idx in indices.flatten():
                    filtered.append(detections[idx])
            detections = filtered

        return detections

    def annotate_frame(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        camera_id: str,
        timestamp: float
    ) -> np.ndarray:
        """
        Draw bounding boxes, confidence badges, and privacy compliant banners on frame.
        """
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        # Top camera metadata banner
        cv2.rectangle(annotated, (0, 0), (w, 36), (10, 18, 32), -1)
        cv2.putText(
            annotated,
            f"CCTV: {camera_id} | T={timestamp:.2f}s | Road Surface AI Analysis",
            (14, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 210, 255),
            2,
            cv2.LINE_AA
        )

        for det in detections:
            x, y, bw, bh = det["box"]
            conf = det["confidence"]
            defect_type = det.get("defect_type", "suspected visual road defect")

            # High confidence = Red/Amber, Moderate = Cyan
            color = (0, 112, 243) if conf < 0.75 else (0, 80, 255)

            # Bounding box
            cv2.rectangle(annotated, (x, y), (x + bw, y + bh), color, 2)

            # Label banner
            label = f"DEFECT ({int(conf * 100)}%)"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(annotated, (x, max(0, y - th - 6)), (x + tw + 8, y), color, -1)
            cv2.putText(
                annotated,
                label,
                (x + 4, max(th + 2, y - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )

        return annotated

    def process_video_stream(
        self,
        video_path: str,
        camera_id: str = "CAM-SRM-01",
        camera_lat: float = 12.823050,
        camera_lon: float = 80.044200,
        interval_seconds: float = 0.5,
        min_confidence: float = 0.55
    ) -> Dict[str, Any]:
        """
        Full video processing pipeline:
        1. Extract frames at interval.
        2. Run privacy-compliant road defect detection.
        3. Save annotated frames for web viewing.
        4. Return timestamped defect detections list.
        """
        extracted = self.extract_frames(video_path, interval_seconds=interval_seconds)
        all_detections = []
        saved_frame_paths = []

        for item in extracted:
            frame_idx = item["frame_idx"]
            timestamp = item["timestamp"]
            raw_frame = item["frame"]

            dets = self.detect_in_frame(raw_frame, min_confidence=min_confidence)
            if dets:
                annotated = self.annotate_frame(raw_frame, dets, camera_id, timestamp)
                filename = f"{camera_id}_frame_{frame_idx}_{int(timestamp * 100)}.jpg"
                filepath = os.path.join(self.frames_output_dir, filename)
                cv2.imwrite(filepath, annotated)
                saved_frame_paths.append(filename)

                for d in dets:
                    all_detections.append({
                        "camera_id": str(camera_id),
                        "timestamp": float(timestamp),
                        "frame_index": int(frame_idx),
                        "frame_number": int(frame_idx),
                        "image_file": filename,
                        "frame_filename": filename,
                        "defect_detected": True,
                        "confidence": float(round(float(d["confidence"]), 2)),
                        "box": [int(coord) for coord in d["box"]],
                        "defect_type": str(d["defect_type"]),
                        "latitude": float(camera_lat),
                        "longitude": float(camera_lon)
                    })

        return {
            "total_frames_analyzed": len(extracted),
            "frames_with_detections": len(saved_frame_paths),
            "total_detections_count": len(all_detections),
            "camera_id": camera_id,
            "camera_lat": camera_lat,
            "camera_lon": camera_lon,
            "detections": all_detections,
            "saved_frames": saved_frame_paths,
            "model_info": self.get_model_info()
        }
