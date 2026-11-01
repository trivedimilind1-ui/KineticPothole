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
from backend.cctv_detector import CCTVDetector
from backend.sensor_fusion import SensorFusionEngine

FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
if is_serverless:
    DB_PATH = "/tmp/kinetic_pothole.db"
    CCTV_FRAMES_DIR = "/tmp/cctv_frames"
else:
    DB_PATH = os.path.join(BASE_DIR, "kinetic_pothole.db")
    CCTV_FRAMES_DIR = os.path.join(BASE_DIR, "cctv_frames")
os.makedirs(CCTV_FRAMES_DIR, exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# Initialize single detector, database, cctv detector, and fusion engine
detector = RoadImpactDetector()
db = Database(db_path=DB_PATH)
cctv_detector = CCTVDetector(frames_output_dir=CCTV_FRAMES_DIR)
fusion_engine = SensorFusionEngine(match_radius_meters=35.0)


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
def reset_database():
    """Clear all recorded events, clustered hazards, calibrations, and CCTV detections."""
    try:
        db.reset_all()
        detector.reset_state()
        return jsonify({
            "status": "success",
            "message": "All database records and detector state reset successfully"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cctv/frames/<path:filename>")
def get_cctv_frame(filename):
    """Serve annotated CCTV frame images."""
    return send_from_directory(CCTV_FRAMES_DIR, filename)


@app.route("/api/cctv/cameras", methods=["GET"])
def get_cctv_cameras():
    """List registered CCTV cameras with manually configured GPS coordinates."""
    try:
        cameras = db.get_cameras()
        return jsonify({
            "status": "success",
            "count": len(cameras),
            "cameras": cameras
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cctv/cameras", methods=["POST"])
def configure_cctv_camera():
    """Register or update a CCTV camera with its associated GPS coordinates."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        cam_id = data.get("camera_id")
        if not cam_id:
            return jsonify({"error": "camera_id is required"}), 400

        name = data.get("name", cam_id)
        lat = float(data.get("latitude", 12.823050))
        lon = float(data.get("longitude", 80.044200))
        road_segment = data.get("road_segment", "")

        saved = db.add_camera(cam_id, name, lat, lon, road_segment)
        return jsonify({
            "status": "success",
            "camera": saved
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cctv/detections", methods=["GET"])
def get_cctv_detections():
    """Retrieve visual detection records."""
    try:
        limit = min(200, int(request.args.get("limit", 50)))
        dets = db.get_cctv_detections(limit=limit)
        return jsonify({
            "status": "success",
            "count": len(dets),
            "detections": dets
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cctv/process_video", methods=["POST"])
def process_cctv_video():
    """
    Process prerecorded or uploaded CCTV video:
    1. Extract frames at interval.
    2. Run road damage model / CV analyzer on road ROI.
    3. Save annotated frames with bounding boxes.
    4. Store detections in SQLite.
    5. Trigger sensor fusion with smartphone hazard clusters.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        video_filename = data.get("video_file") or data.get("video_filename") or "sample_cctv_pothole.mp4"
        camera_id = data.get("camera_id", "CAM-SRM-MAIN")
        interval_sec = float(data.get("interval_seconds", 0.5))
        min_conf = float(data.get("min_confidence", 0.55))

        # Lookup camera coordinates
        cameras = {c["camera_id"]: c for c in db.get_cameras()}
        cam_info = cameras.get(camera_id, {
            "latitude": 12.821500,
            "longitude": 80.041800,
            "road_segment": "Service Lane"
        })

        # Locate video file
        video_path = os.path.join(PROJECT_DIR, "data", video_filename)
        if not os.path.exists(video_path):
            video_path = os.path.join(PROJECT_DIR, "data", "uploads", video_filename)
        if not os.path.exists(video_path):
            video_path = os.path.join("/tmp", "uploads", video_filename)

        if not os.path.exists(video_path):
            return jsonify({"error": f"Video file not found: {video_filename}"}), 404

        # Run CCTV detector
        result = cctv_detector.process_video_stream(
            video_path=video_path,
            camera_id=camera_id,
            camera_lat=float(cam_info["latitude"]),
            camera_lon=float(cam_info["longitude"]),
            interval_seconds=interval_sec,
            min_confidence=min_conf
        )

        # Record each detection into database
        for d in result["detections"]:
            db.record_cctv_detection(d)

        # Run Sensor Fusion across all hazards
        all_hazards = db.get_hazards()
        all_events = db.get_events(limit=500)
        all_cctv = db.get_cctv_detections(limit=500)

        fused_hazards = fusion_engine.correlate_detections_with_hazards(
            cctv_detections=all_cctv,
            hazards=all_hazards,
            raw_events=all_events
        )

        # Update hazards in SQLite
        for fh in fused_hazards:
            db.update_hazard_fusion(
                hazard_id=fh["id"],
                visual_score=fh["visual_evidence_score"],
                phone_score=fh["smartphone_evidence_score"],
                combined_conf=fh["combined_confidence"],
                fusion_status=fh["fusion_status"],
                last_image=fh.get("last_cctv_image"),
                cctv_count=fh.get("cctv_detections_count", 0)
            )

        return jsonify({
            "status": "success",
            "camera_id": camera_id,
            "video_file": video_filename,
            "total_frames_analyzed": result["total_frames_analyzed"],
            "total_detections_count": result["total_detections_count"],
            "saved_frames": result["saved_frames"],
            "detections": result["detections"][:30],  # preview slice
            "fused_hazards_count": len(fused_hazards),
            "model_info": result["model_info"]
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cctv/upload_video", methods=["POST"])
def upload_cctv_video():
    """Upload custom road video file."""
    try:
        if "video" not in request.files:
            return jsonify({"error": "No video file attached"}), 400

        file = request.files["video"]
        if file.filename == "":
            return jsonify({"error": "Empty filename"}), 400

        if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            upload_dir = "/tmp/uploads"
        else:
            upload_dir = os.path.join(PROJECT_DIR, "data", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"upload_{int(time.time())}_{file.filename}"
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        return jsonify({
            "status": "success",
            "message": "Video uploaded successfully",
            "video_file": filename,
            "path": filepath
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/fusion/run", methods=["POST"])
def run_sensor_fusion():
    """Run sensor fusion across all hazards, events, and CCTV detections."""
    try:
        all_hazards = db.get_hazards()
        all_events = db.get_events(limit=500)
        all_cctv = db.get_cctv_detections(limit=500)

        fused = fusion_engine.correlate_detections_with_hazards(
            cctv_detections=all_cctv,
            hazards=all_hazards,
            raw_events=all_events
        )

        for fh in fused:
            db.update_hazard_fusion(
                hazard_id=fh["id"],
                visual_score=fh["visual_evidence_score"],
                phone_score=fh["smartphone_evidence_score"],
                combined_conf=fh["combined_confidence"],
                fusion_status=fh["fusion_status"],
                last_image=fh.get("last_cctv_image"),
                cctv_count=fh.get("cctv_detections_count", 0)
            )

        return jsonify({
            "status": "success",
            "fused_hazards_count": len(fused),
            "hazards": fused
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
