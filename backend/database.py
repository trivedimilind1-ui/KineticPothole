"""
KineticPothole - SQLite Database & Hazard Clustering Engine

Handles persistent storage of raw events, geographic clustering into
suspected road hazards, confidence scoring, and multi-trip/multi-device tracking.
"""

import sqlite3
import math
import os
import time
from typing import List, Dict, Any, Optional, Tuple


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points
    on the earth in meters using the Haversine formula.
    """
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


class Database:
    """SQLite Database manager with automated hazard clustering."""

    SEVERITY_WEIGHTS = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    SEVERITY_LEVELS = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}

    def __init__(self, db_path: str = "kinetic_pothole.db", cluster_radius_meters: float = 20.0):
        self.db_path = db_path
        self.cluster_radius_meters = cluster_radius_meters
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize database schema with required tables and indices."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Hazards table (geographic clusters)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hazards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                radius_meters REAL DEFAULT 20.0,
                severity TEXT NOT NULL,
                hazard_type TEXT NOT NULL,
                report_count INTEGER DEFAULT 1,
                unique_devices_count INTEGER DEFAULT 1,
                avg_peak_accel REAL NOT NULL,
                max_peak_accel REAL NOT NULL,
                first_reported REAL NOT NULL,
                last_reported REAL NOT NULL,
                confidence_score REAL NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Events table (individual road impact triggers)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                latitude REAL,
                longitude REAL,
                gps_accuracy REAL,
                severity TEXT NOT NULL,
                hazard_type TEXT NOT NULL,
                peak_dynamic_accel REAL NOT NULL,
                peak_raw_magnitude REAL,
                rms REAL,
                std_dev REAL,
                confidence REAL,
                device_id TEXT DEFAULT 'phone-default',
                trip_id TEXT DEFAULT 'trip-default',
                is_synthetic INTEGER DEFAULT 0,
                hazard_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (hazard_id) REFERENCES hazards(id) ON DELETE SET NULL
            );
            """)

            # Calibrations table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS calibrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                baseline_mean REAL NOT NULL,
                baseline_std REAL NOT NULL,
                threshold_low REAL NOT NULL,
                threshold_med REAL NOT NULL,
                threshold_high REAL NOT NULL,
                sample_count INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # CCTV Cameras table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cctv_cameras (
                camera_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                road_segment TEXT,
                status TEXT DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # CCTV Detections table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cctv_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                frame_index INTEGER,
                image_file TEXT,
                confidence REAL NOT NULL,
                box_json TEXT,
                defect_type TEXT DEFAULT 'suspected visual road defect',
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                hazard_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (hazard_id) REFERENCES hazards(id) ON DELETE SET NULL,
                FOREIGN KEY (camera_id) REFERENCES cctv_cameras(camera_id)
            );
            """)

            # Ensure fusion columns exist on hazards
            cursor.execute("PRAGMA table_info(hazards)")
            hazard_columns = [col[1] for col in cursor.fetchall()]

            fusion_cols = [
                ("visual_evidence_score", "REAL DEFAULT 0.0"),
                ("smartphone_evidence_score", "REAL DEFAULT 0.0"),
                ("fusion_status", "TEXT DEFAULT 'IMPACT_ONLY'"),
                ("cctv_detections_count", "INTEGER DEFAULT 0"),
                ("last_cctv_image", "TEXT")
            ]
            for col_name, col_type in fusion_cols:
                if col_name not in hazard_columns:
                    cursor.execute(f"ALTER TABLE hazards ADD COLUMN {col_name} {col_type};")

            # Pre-seed default cameras if empty
            cursor.execute("SELECT COUNT(*) FROM cctv_cameras")
            if cursor.fetchone()[0] == 0:
                default_cams = [
                    ("CAM-SRM-MAIN", "SRMIST Main Gate Corridor", 12.823050, 80.044200, "SRM Main Avenue"),
                    ("CAM-POTHERI-STN", "Potheri Station Crossing", 12.825200, 80.046800, "Station Road"),
                    ("CAM-GST-SERVICE", "GST Road Service Lane Cam 1", 12.821500, 80.041800, "NH45 Service Lane")
                ]
                cursor.executemany("""
                    INSERT INTO cctv_cameras (camera_id, name, latitude, longitude, road_segment)
                    VALUES (?, ?, ?, ?, ?)
                """, default_cams)

            # Helpful indices for spatial and temporal queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_hazard ON events(hazard_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hazards_loc ON hazards(latitude, longitude);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cctv_cam ON cctv_detections(camera_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cctv_loc ON cctv_detections(latitude, longitude);")

            conn.commit()

    def reset_all(self):
        """Clear all events, hazards, calibrations, and CCTV detections."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events;")
            cursor.execute("DELETE FROM hazards;")
            cursor.execute("DELETE FROM calibrations;")
            cursor.execute("DELETE FROM cctv_detections;")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('events', 'hazards', 'calibrations', 'cctv_detections');")
            conn.commit()

    def record_calibration(self, device_id: str, baseline_mean: float, baseline_std: float,
                           threshold_low: float, threshold_med: float, threshold_high: float,
                           sample_count: int) -> int:
        """Save a calibration record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO calibrations (device_id, baseline_mean, baseline_std,
                                         threshold_low, threshold_med, threshold_high, sample_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (device_id, baseline_mean, baseline_std, threshold_low, threshold_med, threshold_high, sample_count))
            conn.commit()
            return cursor.lastrowid

    def get_latest_calibration(self, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent calibration settings."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if device_id:
                cursor.execute("""
                    SELECT * FROM calibrations WHERE device_id = ? ORDER BY id DESC LIMIT 1
                """, (device_id,))
            else:
                cursor.execute("SELECT * FROM calibrations ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_nearest_hazard(self, lat: float, lon: float) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Find any existing hazard within cluster_radius_meters of (lat, lon).
        Returns (hazard_dict, distance_meters) or None.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Bounding box filter first for efficiency
            # 1 deg lat is ~111km, 20m is ~0.00018 deg
            lat_delta = self.cluster_radius_meters / 111000.0 * 2.0
            lon_delta = lat_delta / max(0.1, math.cos(math.radians(lat)))

            cursor.execute("""
                SELECT * FROM hazards
                WHERE latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
            """, (lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta))

            rows = cursor.fetchall()
            nearest = None
            min_dist = float("inf")

            for r in rows:
                dist = haversine_distance(lat, lon, r["latitude"], r["longitude"])
                if dist <= self.cluster_radius_meters and dist < min_dist:
                    min_dist = dist
                    nearest = (dict(r), dist)

            return nearest

    def calculate_cluster_confidence(self, report_count: int, unique_devices: int,
                                     avg_gps_accuracy: Optional[float], base_confidence: float) -> float:
        """
        Calculates hazard confidence.
        Note: Multi-device confirmation yields genuine community confidence.
        Repeated passes from a single device add modest confidence.
        Poor GPS accuracy degrades confidence.
        """
        score = base_confidence

        # GPS accuracy effect
        if avg_gps_accuracy is not None:
            if avg_gps_accuracy <= 10.0:
                score += 0.10
            elif avg_gps_accuracy <= 25.0:
                score += 0.04
            elif avg_gps_accuracy > 50.0:
                score -= 0.20

        # Repeated passes from the same trip/device
        repeat_passes = max(0, report_count - unique_devices)
        score += min(0.12, repeat_passes * 0.04)

        # Multi-device independent confirmation bonus
        if unique_devices > 1:
            score += min(0.25, (unique_devices - 1) * 0.12)

        return round(max(0.15, min(0.98, score)), 2)

    def record_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save an event to SQLite and cluster it into a road hazard if GPS coordinates exist.
        """
        timestamp = float(event_data.get("timestamp", time.time()))
        lat = event_data.get("lat")
        lon = event_data.get("lon")
        gps_accuracy = event_data.get("accuracy")
        severity = event_data.get("severity", "LOW")
        hazard_type = event_data.get("hazard_type", "suspected road hazard")
        peak_dyn = float(event_data.get("peak_dynamic_accel", 0.0))
        peak_raw = float(event_data.get("peak_raw_magnitude", 0.0))
        rms = float(event_data.get("rms", 0.0))
        std_dev = float(event_data.get("std_dev", 0.0))
        confidence = float(event_data.get("confidence", 0.60))
        device_id = str(event_data.get("device_id", "phone-default"))
        trip_id = str(event_data.get("trip_id", "trip-default"))
        is_synthetic = 1 if event_data.get("is_synthetic", False) else 0

        # Flag poor GPS accuracy
        is_valid_gps = (lat is not None and lon is not None and
                        -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180)

        hazard_id = None

        with self.get_connection() as conn:
            cursor = conn.cursor()

            if is_valid_gps:
                lat = float(lat)
                lon = float(lon)
                gps_accuracy = float(gps_accuracy) if gps_accuracy is not None else None

                # Check if this event falls into an existing hazard cluster
                match = self.find_nearest_hazard(lat, lon)
                if match:
                    existing_hazard, _ = match
                    hazard_id = existing_hazard["id"]

                    # Gather all events belonging to this hazard to recompute metrics
                    cursor.execute("""
                        SELECT peak_dynamic_accel, severity, device_id, gps_accuracy
                        FROM events WHERE hazard_id = ?
                    """, (hazard_id,))
                    existing_events = cursor.fetchall()

                    all_peaks = [e["peak_dynamic_accel"] for e in existing_events] + [peak_dyn]
                    all_devices = {e["device_id"] for e in existing_events} | {device_id}
                    all_accuracies = [e["gps_accuracy"] for e in existing_events if e["gps_accuracy"] is not None]
                    if gps_accuracy is not None:
                        all_accuracies.append(gps_accuracy)

                    new_count = len(existing_events) + 1
                    new_devices_count = len(all_devices)
                    new_avg_peak = round(sum(all_peaks) / len(all_peaks), 2)
                    new_max_peak = round(max(all_peaks), 2)

                    # Update severity to max
                    existing_weight = self.SEVERITY_WEIGHTS.get(existing_hazard["severity"], 1)
                    incoming_weight = self.SEVERITY_WEIGHTS.get(severity, 1)
                    max_weight = max(existing_weight, incoming_weight)
                    new_severity = self.SEVERITY_LEVELS.get(max_weight, "LOW")

                    avg_acc = (sum(all_accuracies) / len(all_accuracies)) if all_accuracies else None
                    new_confidence = self.calculate_cluster_confidence(
                        report_count=new_count,
                        unique_devices=new_devices_count,
                        avg_gps_accuracy=avg_acc,
                        base_confidence=confidence
                    )

                    # Update centroid (simple weighted or moving average)
                    new_lat = round((existing_hazard["latitude"] * existing_hazard["report_count"] + lat) / new_count, 6)
                    new_lon = round((existing_hazard["longitude"] * existing_hazard["report_count"] + lon) / new_count, 6)

                    cursor.execute("""
                        UPDATE hazards SET
                            latitude = ?,
                            longitude = ?,
                            severity = ?,
                            hazard_type = ?,
                            report_count = ?,
                            unique_devices_count = ?,
                            avg_peak_accel = ?,
                            max_peak_accel = ?,
                            last_reported = ?,
                            confidence_score = ?
                        WHERE id = ?
                    """, (new_lat, new_lon, new_severity, hazard_type, new_count, new_devices_count,
                          new_avg_peak, new_max_peak, timestamp, new_confidence, hazard_id))

                else:
                    # Create new hazard cluster
                    initial_confidence = self.calculate_cluster_confidence(
                        report_count=1,
                        unique_devices=1,
                        avg_gps_accuracy=gps_accuracy,
                        base_confidence=confidence
                    )
                    cursor.execute("""
                        INSERT INTO hazards (
                            latitude, longitude, radius_meters, severity, hazard_type,
                            report_count, unique_devices_count, avg_peak_accel, max_peak_accel,
                            first_reported, last_reported, confidence_score
                        ) VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?)
                    """, (lat, lon, self.cluster_radius_meters, severity, hazard_type,
                          peak_dyn, peak_dyn, timestamp, timestamp, initial_confidence))
                    hazard_id = cursor.lastrowid

            # Insert the event record
            cursor.execute("""
                INSERT INTO events (
                    timestamp, latitude, longitude, gps_accuracy, severity, hazard_type,
                    peak_dynamic_accel, peak_raw_magnitude, rms, std_dev, confidence,
                    device_id, trip_id, is_synthetic, hazard_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, lat, lon, gps_accuracy, severity, hazard_type,
                  peak_dyn, peak_raw, rms, std_dev, confidence,
                  device_id, trip_id, is_synthetic, hazard_id))
            event_id = cursor.lastrowid
            conn.commit()

            return {
                "id": event_id,
                "hazard_id": hazard_id,
                "timestamp": timestamp,
                "severity": severity,
                "hazard_type": hazard_type,
                "peak_dynamic_accel": peak_dyn,
                "lat": lat,
                "lon": lon,
                "gps_accuracy": gps_accuracy,
                "confidence": confidence,
                "device_id": device_id,
                "is_synthetic": bool(is_synthetic)
            }

    def get_events(self, limit: int = 100, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent events."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if severity:
                cursor.execute("""
                    SELECT * FROM events WHERE severity = ? ORDER BY id DESC LIMIT ?
                """, (severity.upper(), limit))
            else:
                cursor.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_hazards(self) -> List[Dict[str, Any]]:
        """Retrieve all active hazard clusters for mapping, including synthetic source flag."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT h.*,
                    COALESCE((SELECT MAX(e.is_synthetic) FROM events e WHERE e.hazard_id = h.id), 0) AS is_synthetic
                FROM hazards h
                ORDER BY h.last_reported DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """Aggregate summary statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM events")
            total_events = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM events WHERE severity = 'HIGH'")
            high_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM events WHERE severity = 'MEDIUM'")
            med_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM events WHERE severity = 'LOW'")
            low_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM hazards")
            total_hazards = cursor.fetchone()[0]

            cursor.execute("SELECT AVG(peak_dynamic_accel) FROM events")
            avg_accel = cursor.fetchone()[0]
            avg_accel = round(avg_accel, 2) if avg_accel is not None else 0.0

            cursor.execute("SELECT COUNT(DISTINCT device_id) FROM events")
            total_devices = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT trip_id) FROM events")
            total_trips = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM cctv_detections")
            total_cctv = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM hazards WHERE fusion_status = 'DUAL_CONFIRMED'")
            dual_confirmed = cursor.fetchone()[0]

            return {
                "total_events": total_events,
                "high_severity_events": high_count,
                "medium_severity_events": med_count,
                "low_severity_events": low_count,
                "total_hazards": total_hazards,
                "avg_dynamic_acceleration": avg_accel,
                "unique_devices": total_devices,
                "unique_trips": total_trips,
                "total_cctv_detections": total_cctv,
                "dual_confirmed_hazards": dual_confirmed
            }

    def get_cameras(self) -> List[Dict[str, Any]]:
        """Retrieve list of configured CCTV cameras with their GPS locations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cctv_cameras ORDER BY camera_id")
            return [dict(row) for row in cursor.fetchall()]

    def add_camera(self, camera_id: str, name: str, latitude: float, longitude: float, road_segment: str = "") -> Dict[str, Any]:
        """Configure or register a CCTV camera with its associated GPS coordinates."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cctv_cameras (camera_id, name, latitude, longitude, road_segment)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(camera_id) DO UPDATE SET
                    name = excluded.name,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    road_segment = excluded.road_segment
            """, (camera_id, name, latitude, longitude, road_segment))
            conn.commit()
            return {
                "camera_id": camera_id,
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "road_segment": road_segment
            }

    def record_cctv_detection(self, data: Dict[str, Any]) -> int:
        """Store a CCTV visual detection record in database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cctv_detections (
                    camera_id, timestamp, frame_index, image_file,
                    confidence, box_json, defect_type, latitude, longitude, hazard_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["camera_id"],
                float(data["timestamp"]),
                int(data.get("frame_index", 0)),
                data.get("image_file", ""),
                float(data["confidence"]),
                str(data.get("box", [])),
                data.get("defect_type", "suspected visual road defect"),
                float(data["latitude"]),
                float(data["longitude"]),
                data.get("hazard_id")
            ))
            conn.commit()
            return cursor.lastrowid

    def get_cctv_detections(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent CCTV visual detection events."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM cctv_detections ORDER BY id DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_hazard_fusion(
        self,
        hazard_id: int,
        visual_score: float,
        phone_score: float,
        combined_conf: float,
        fusion_status: str,
        last_image: Optional[str] = None,
        cctv_count: int = 0
    ):
        """Update multi-modal fusion scores on a road hazard cluster."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE hazards SET
                    visual_evidence_score = ?,
                    smartphone_evidence_score = ?,
                    confidence_score = ?,
                    fusion_status = ?,
                    last_cctv_image = COALESCE(?, last_cctv_image),
                    cctv_detections_count = ?
                WHERE id = ?
            """, (visual_score, phone_score, combined_conf, fusion_status, last_image, cctv_count, hazard_id))
            conn.commit()
