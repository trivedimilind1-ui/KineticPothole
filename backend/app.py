"""
KineticPothole - Flask Backend REST API
Intelligent Road Impact Detection & Hazard Mapping Server
"""

import os
import sys
import socket
import time

# Ensure project root is on sys.path for direct python backend/app.py execution
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from backend.detector import RoadImpactDetector
from backend.database import Database

FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
DB_PATH = os.path.join(BASE_DIR, "kinetic_pothole.db")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# Initialize single detector instance and database
detector = RoadImpactDetector()
db = Database(db_path=DB_PATH)


def get_local_ip() -> str:
    """Detect machine's local LAN IP for easy phone connection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Doesn't need to be reachable, just triggers routing table lookup
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# --- Static frontend routes ---

@app.route("/")
def index():
    """Serve frontend dashboard."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/data/<path:path>")
def sample_data_files(path):
    """Serve sample CSV datasets."""
    data_dir = os.path.join(PROJECT_DIR, "data")
    return send_from_directory(data_dir, path)


@app.route("/<path:path>")
def static_files(path):
    """Serve CSS, JS, and asset files."""
    return send_from_directory(FRONTEND_DIR, path)


# --- REST API Endpoints ---

@app.route("/api/health", methods=["GET"])
def health_check():
    """System status, database health, and connection details."""
    local_ip = get_local_ip()
    db_connected = True
    db_stats = {}
    try:
        db_stats = db.get_statistics()
    except Exception as e:
        db_connected = False
        db_stats = {"error": str(e)}

    return jsonify({
        "status": "healthy",
        "service": "KineticPothole API",
        "version": "1.0.0",
        "server_time": time.time(),
        "local_ip": local_ip,
        "phone_access_url": f"http://{local_ip}:5000",
        "database": {
            "connected": db_connected,
            "engine": "SQLite",
            "total_events": db_stats.get("total_events", 0),
            "total_hazards": db_stats.get("total_hazards", 0)
        },
        "detector_settings": {
            "threshold_low": detector.threshold_low,
            "threshold_med": detector.threshold_med,
            "threshold_high": detector.threshold_high,
            "calibrated": detector.calibrated
        }
    }), 200


@app.route("/api/events", methods=["GET"])
def get_events():
    """
    Retrieve stored road impact events.
    Query parameters:
    - limit: int (default: 50, max: 500)
    - severity: string ('LOW', 'MEDIUM', 'HIGH')
    """
    try:
        limit = min(500, int(request.args.get("limit", 50)))
        severity = request.args.get("severity")
        if severity:
            severity = severity.upper()
            if severity not in ["LOW", "MEDIUM", "HIGH"]:
                return jsonify({"error": "Severity filter must be LOW, MEDIUM, or HIGH"}), 400

        events = db.get_events(limit=limit, severity=severity)
        return jsonify({
            "status": "success",
            "count": len(events),
            "events": events
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/events", methods=["POST"])
def post_event():
    """
    Ingest a detected road-impact event and automatically cluster into hazards.
    Payload:
    {
        "timestamp": float,
        "lat": float,
        "lon": float,
        "accuracy": float,
        "severity": "LOW" | "MEDIUM" | "HIGH",
        "hazard_type": string,
        "peak_dynamic_accel": float,
        "device_id": string (optional),
        "trip_id": string (optional),
        "is_synthetic": bool (optional)
    }
    """
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Invalid or missing JSON payload"}), 400

        # Validate required numerical metrics
        if "peak_dynamic_accel" not in data:
            return jsonify({"error": "peak_dynamic_accel is required"}), 400

        # Severity auto-classification fallback
        peak_dyn = float(data["peak_dynamic_accel"])
        if "severity" not in data:
            data["severity"] = detector.classify_severity(peak_dyn) or "LOW"

        # Record and cluster in database
        saved = db.record_event(data)
        return jsonify({
            "status": "success",
            "event": saved
        }), 201

    except ValueError as ve:
        return jsonify({"error": f"Value error: {str(ve)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/feed_sample", methods=["POST"])
def feed_sample():
    """
    Stream a single live sensor reading from the smartphone.
    Runs the real-time sliding-window detection algorithm.
    If an impact event is triggered, it is automatically persisted to the database.
    Payload:
    {
        "timestamp": float,
        "x": float,
        "y": float,
        "z": float,
        "lat": float (optional),
        "lon": float (optional),
        "accuracy": float (optional),
        "device_id": str (optional),
        "trip_id": str (optional)
    }
    """
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Missing sensor data"}), 400

        metrics, event = detector.process_sample(data)
        saved_event = None

        if event:
            # Attach location and device metadata if provided
            event["lat"] = data.get("lat")
            event["lon"] = data.get("lon")
            event["accuracy"] = data.get("accuracy")
            event["device_id"] = data.get("device_id", "phone-default")
            event["trip_id"] = data.get("trip_id", "trip-default")
            event["is_synthetic"] = data.get("is_synthetic", False)

            saved_event = db.record_event(event)

        return jsonify({
            "status": "success",
            "metrics": {
                "timestamp": metrics["timestamp"],
                "raw_magnitude": round(metrics["raw_magnitude"], 2),
                "dynamic_accel": round(metrics["dynamic_accel"], 2),
                "filtered_magnitude": round(metrics["filtered_magnitude"], 2)
            },
            "event_detected": saved_event is not None,
            "event": saved_event
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/hazards", methods=["GET"])
def get_hazards():
    """Retrieve all clustered road hazards for interactive mapping."""
    try:
        hazards = db.get_hazards()
        return jsonify({
            "status": "success",
            "count": len(hazards),
            "hazards": hazards
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/statistics", methods=["GET"])
def get_statistics():
    """Aggregate statistics for dashboard metrics cards."""
    try:
        stats = db.get_statistics()
        return jsonify({
            "status": "success",
            "statistics": stats
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/calibrate", methods=["POST"])
def calibrate():
    """
    Calibrate accelerometer baseline from stationary or smooth driving sample window.
    Payload:
    {
        "samples": [ {"x": float, "y": float, "z": float, "timestamp": float}, ... ],
        "device_id": str (optional)
    }
    """
    try:
        payload = request.get_json(force=True, silent=True)
        if not payload or "samples" not in payload:
            return jsonify({"error": "Payload must include 'samples' array"}), 400

        samples = payload["samples"]
        device_id = payload.get("device_id", "phone-default")

        cal_result = detector.calibrate_baseline(samples)

        db.record_calibration(
            device_id=device_id,
            baseline_mean=cal_result["baseline_mean"],
            baseline_std=cal_result["baseline_std"],
            threshold_low=cal_result["threshold_low"],
            threshold_med=cal_result["threshold_med"],
            threshold_high=cal_result["threshold_high"],
            sample_count=cal_result["sample_count"]
        )

        return jsonify({
            "status": "success",
            "message": "Baseline calibration complete",
            "calibration": cal_result
        }), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/process_batch", methods=["POST"])
def process_batch():
    """
    Batch processing for uploaded CSV or controlled test signal simulation.
    Payload:
    {
        "samples": [ {"timestamp": float, "x": float, "y": float, "z": float, "lat": float, "lon": float}, ... ],
        "device_id": str,
        "trip_id": str,
        "is_synthetic": bool
    }
    """
    try:
        payload = request.get_json(force=True, silent=True)
        if not payload or "samples" not in payload:
            return jsonify({"error": "Payload must include 'samples' list"}), 400

        samples = payload["samples"]
        device_id = payload.get("device_id", "batch-processor")
        trip_id = payload.get("trip_id", f"trip-{int(time.time())}")
        is_synthetic = bool(payload.get("is_synthetic", False))

        batch_result = detector.process_batch(samples)

        # Store all detected events in database
        saved_events = []
        for evt in batch_result["detected_events"]:
            evt["device_id"] = device_id
            evt["trip_id"] = trip_id
            evt["is_synthetic"] = is_synthetic
            saved = db.record_event(evt)
            saved_events.append(saved)

        return jsonify({
            "status": "success",
            "total_samples": batch_result["total_samples"],
            "event_count": len(saved_events),
            "sampling_rate_hz": batch_result["sampling_rate_hz"],
            "severity_breakdown": batch_result["severity_breakdown"],
            "events": saved_events
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def reset_demo():
    """Reset database and detector states for fresh demonstration."""
    try:
        detector.reset_state()
        db.reset_all()
        return jsonify({
            "status": "success",
            "message": "All hazard and event data has been reset."
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    local_ip = get_local_ip()
    port = int(os.environ.get("PORT", 5000))
    print(f"\n=========================================================")
    print(f" KineticPothole Road Impact Detection System Running!")
    print(f" Local Web Access:    http://127.0.0.1:{port}")
    print(f" Smartphone Access:   http://{local_ip}:{port}")
    print(f"=========================================================\n")
    app.run(host="0.0.0.0", port=port, debug=True)
