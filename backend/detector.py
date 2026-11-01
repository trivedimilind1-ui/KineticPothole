"""
KineticPothole - Signal Processing & Road Hazard Detection Engine

Analyzes smartphone accelerometer time-series data to detect, filter, and classify
sudden road-impact events (e.g. suspected potholes, speed breakers, rough surfaces)
without claiming exact physical depth estimation.
"""

from typing import List, Dict, Any, Optional, Tuple
import math
import numpy as np


class RoadImpactDetector:
    """
    Detector for road anomalies based on sliding-window statistical analysis
    of 3-axis accelerometer readings.
    """

    # Default baseline gravity
    STANDARD_GRAVITY = 9.80665

    # Default acceleration thresholds (dynamic acceleration in m/s^2)
    DEFAULT_THRESHOLDS = {
        "LOW": 3.2,       # Minor road vibration
        "MEDIUM": 6.5,    # Moderate road impact
        "HIGH": 11.5      # Strong road impact
    }

    def __init__(
        self,
        threshold_low: float = 3.2,
        threshold_med: float = 6.5,
        threshold_high: float = 11.5,
        window_size: int = 15,          # Window size in samples (~0.3s at 50Hz)
        cooldown_seconds: float = 1.2,   # Enforce cooldown to prevent rebound duplicates
        filter_alpha: float = 0.75      # Exponential smoothing factor (0 to 1)
    ):
        self.threshold_low = threshold_low
        self.threshold_med = threshold_med
        self.threshold_high = threshold_high
        self.window_size = window_size
        self.cooldown_seconds = cooldown_seconds
        self.filter_alpha = filter_alpha

        # Internal state for streaming detection
        self.buffer: List[Dict[str, Any]] = []
        self.last_event_time: Optional[float] = None
        self.last_filtered_magnitude: Optional[float] = None
        
        # Impact candidate state
        self.active_candidate: Optional[Dict[str, Any]] = None
        self.sub_threshold_count = 0

        # Calibration state
        self.calibrated = False
        self.baseline_mean = 0.0
        self.baseline_std = 0.0

    def reset_state(self):
        """Reset internal streaming buffer and event history."""
        self.buffer.clear()
        self.last_event_time = None
        self.last_filtered_magnitude = None
        self.active_candidate = None
        self.sub_threshold_count = 0

    def set_thresholds(self, low: float, med: float, high: float):
        """Update detection thresholds."""
        if low <= 0 or med <= low or high <= med:
            raise ValueError("Thresholds must satisfy 0 < low < med < high")
        self.threshold_low = float(low)
        self.threshold_med = float(med)
        self.threshold_high = float(high)

    def calibrate_baseline(self, samples: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calibrate baseline from smooth driving or stationary data.
        Adjusts thresholds relative to vehicle/device mounting baseline noise floor.
        """
        if not samples or len(samples) < 10:
            raise ValueError("Need at least 10 samples to calibrate baseline")

        dyn_accels = []
        for s in samples:
            x = float(s.get("x", 0.0))
            y = float(s.get("y", 0.0))
            z = float(s.get("z", 0.0))
            mag = math.sqrt(x * x + y * y + z * z)
            dyn = abs(mag - self.STANDARD_GRAVITY)
            dyn_accels.append(dyn)

        arr = np.array(dyn_accels)
        self.baseline_mean = float(np.mean(arr))
        self.baseline_std = float(np.std(arr))
        self.calibrated = True

        # Adaptive thresholding based on noise floor
        self.threshold_low = max(2.5, self.baseline_mean + 3.0 * max(0.4, self.baseline_std))
        self.threshold_med = max(5.5, self.baseline_mean + 6.5 * max(0.4, self.baseline_std))
        self.threshold_high = max(10.0, self.baseline_mean + 11.5 * max(0.4, self.baseline_std))

        return {
            "baseline_mean": round(self.baseline_mean, 3),
            "baseline_std": round(self.baseline_std, 3),
            "threshold_low": round(self.threshold_low, 3),
            "threshold_med": round(self.threshold_med, 3),
            "threshold_high": round(self.threshold_high, 3),
            "sample_count": len(samples)
        }

    def compute_sample_metrics(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract magnitude and dynamic acceleration from a single reading.
        Applies low-pass smoothing to remove sensor white noise.
        """
        x = float(sample.get("x", 0.0))
        y = float(sample.get("y", 0.0))
        z = float(sample.get("z", 0.0))
        timestamp = float(sample.get("timestamp", 0.0))

        raw_magnitude = math.sqrt(x * x + y * y + z * z)

        # Exponential moving average filter
        if self.last_filtered_magnitude is None:
            filtered_magnitude = raw_magnitude
        else:
            filtered_magnitude = (
                self.filter_alpha * raw_magnitude +
                (1.0 - self.filter_alpha) * self.last_filtered_magnitude
            )
        self.last_filtered_magnitude = filtered_magnitude

        # Dynamic acceleration removing gravity baseline
        dynamic_accel = abs(filtered_magnitude - self.STANDARD_GRAVITY)

        return {
            "timestamp": timestamp,
            "x": x,
            "y": y,
            "z": z,
            "raw_magnitude": raw_magnitude,
            "filtered_magnitude": filtered_magnitude,
            "dynamic_accel": dynamic_accel,
            "lat": sample.get("lat"),
            "lon": sample.get("lon"),
            "accuracy": sample.get("accuracy")
        }

    def classify_severity(self, peak_dyn: float) -> Optional[str]:
        """Classify dynamic acceleration impact into severity categories."""
        if peak_dyn >= self.threshold_high:
            return "HIGH"
        elif peak_dyn >= self.threshold_med:
            return "MEDIUM"
        elif peak_dyn >= self.threshold_low:
            return "LOW"
        return None

    def analyze_window_pattern(self, window: List[Dict[str, Any]]) -> Tuple[str, float]:
        """
        Pattern discrimination heuristic:
        - Suspected Pothole: Sharp sudden vertical drop-spike, very high jerk, quick onset.
        - Suspected Speed Breaker: Biphasic rise-fall or fall-rise wave, longer duration, moderate jerk.
        - Rough Surface: Sustained elevated variance without a solitary peak.
        - Suspected Road Hazard: Default prudent label without claiming 3D physical depth.
        """
        if len(window) < 3:
            return "suspected road hazard", 0.50

        dyns = np.array([w["dynamic_accel"] for w in window])
        times = np.array([w["timestamp"] for w in window])
        
        peak_idx = int(np.argmax(dyns))
        peak_val = dyns[peak_idx]
        mean_val = np.mean(dyns)
        std_val = np.std(dyns)

        # Calculate jerk (rate of change of acceleration)
        time_diffs = np.diff(times)
        valid_td = time_diffs > 0
        if np.any(valid_td):
            jerks = np.abs(np.diff(dyns)[valid_td] / time_diffs[valid_td])
            max_jerk = float(np.max(jerks)) if len(jerks) > 0 else 0.0
        else:
            max_jerk = 0.0

        # Peak to average ratio (crest factor)
        crest_factor = peak_val / (mean_val + 1e-5)

        if crest_factor > 2.2 and (max_jerk > 25.0 or len(window) <= 10):
            hazard_type = "suspected pothole"
            confidence = min(0.92, 0.55 + (crest_factor / 10.0))
        elif 1.4 <= crest_factor <= 2.2 and std_val > 1.0:
            hazard_type = "suspected speed breaker"
            confidence = min(0.85, 0.50 + (std_val / 6.0))
        elif std_val > 1.8 and crest_factor < 1.8:
            hazard_type = "rough road section"
            confidence = min(0.80, 0.45 + (std_val / 5.0))
        else:
            hazard_type = "suspected road hazard"
            confidence = 0.60

        return hazard_type, round(confidence, 2)

    def _finalize_candidate(self) -> Optional[Dict[str, Any]]:
        """Finalize the active impact candidate and return the event."""
        if not self.active_candidate:
            return None

        cand = self.active_candidate
        self.active_candidate = None
        self.sub_threshold_count = 0

        peak_dyn = cand["peak_dyn"]
        severity = self.classify_severity(peak_dyn)
        if severity is None:
            return None

        window = cand["window"]
        hazard_type, confidence = self.analyze_window_pattern(window)

        dyns = np.array([w["dynamic_accel"] for w in window])
        rms = float(np.sqrt(np.mean(dyns ** 2)))
        std = float(np.std(dyns))

        peak_sample = cand["peak_sample"]
        self.last_event_time = peak_sample["timestamp"]

        return {
            "timestamp": peak_sample["timestamp"],
            "severity": severity,
            "hazard_type": hazard_type,
            "peak_dynamic_accel": round(peak_dyn, 2),
            "peak_raw_magnitude": round(peak_sample["raw_magnitude"], 2),
            "rms": round(rms, 2),
            "std_dev": round(std, 2),
            "confidence": confidence,
            "x": round(peak_sample["x"], 2),
            "y": round(peak_sample["y"], 2),
            "z": round(peak_sample["z"], 2),
            "lat": peak_sample.get("lat"),
            "lon": peak_sample.get("lon"),
            "accuracy": peak_sample.get("accuracy"),
            "window_size": len(window),
            "waveform": [round(w["dynamic_accel"], 2) for w in window]
        }

    def process_sample(self, sample: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Stream processing for a single sensor sample.
        Returns (enriched_sample_metrics, detected_event_or_None).
        """
        metrics = self.compute_sample_metrics(sample)
        self.buffer.append(metrics)

        if len(self.buffer) > self.window_size * 2:
            self.buffer.pop(0)

        current_time = metrics["timestamp"]
        dyn_accel = metrics["dynamic_accel"]

        # Check cooldown
        in_cooldown = False
        if self.last_event_time is not None:
            dt = current_time - self.last_event_time
            dt_sec = dt / 1000.0 if dt > 10000 else dt
            if dt_sec < self.cooldown_seconds:
                in_cooldown = True

        detected_event = None

        if in_cooldown:
            # Inside cooldown, ignore new triggers
            return metrics, None

        # Check if sample crosses trigger threshold
        if dyn_accel >= self.threshold_low:
            self.sub_threshold_count = 0
            if self.active_candidate is None:
                # Start tracking new impact pulse
                self.active_candidate = {
                    "start_time": current_time,
                    "peak_dyn": dyn_accel,
                    "peak_sample": metrics,
                    "window": list(self.buffer[-max(3, len(self.buffer)):])
                }
            else:
                # Update existing candidate
                self.active_candidate["window"].append(metrics)
                if dyn_accel > self.active_candidate["peak_dyn"]:
                    self.active_candidate["peak_dyn"] = dyn_accel
                    self.active_candidate["peak_sample"] = metrics

                # If impact lasts longer than 0.4s, finalize it to avoid lingering
                dur = current_time - self.active_candidate["start_time"]
                dur_sec = dur / 1000.0 if dur > 10000 else dur
                if dur_sec >= 0.4:
                    detected_event = self._finalize_candidate()
        else:
            if self.active_candidate is not None:
                self.active_candidate["window"].append(metrics)
                self.sub_threshold_count += 1
                # If sub-threshold for 2 consecutive samples, impact pulse is complete
                if self.sub_threshold_count >= 2:
                    detected_event = self._finalize_candidate()

        return metrics, detected_event

    def process_batch(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process an entire recorded trip or uploaded CSV batch.
        Returns detected events list and summary statistics.
        """
        self.reset_state()
        events = []
        metrics_stream = []

        for s in samples:
            metric, evt = self.process_sample(s)
            metrics_stream.append(metric)
            if evt:
                events.append(evt)

        # Finalize any lingering candidate at end of stream
        if self.active_candidate is not None:
            final_evt = self._finalize_candidate()
            if final_evt:
                events.append(final_evt)

        # Calculate sampling frequency estimate
        if len(samples) >= 2:
            t0 = float(samples[0].get("timestamp", 0))
            t1 = float(samples[-1].get("timestamp", 0))
            total_duration = t1 - t0
            duration_sec = total_duration / 1000.0 if total_duration > 10000 else total_duration
            sampling_rate_hz = round(len(samples) / duration_sec, 1) if duration_sec > 0 else 0.0
        else:
            sampling_rate_hz = 0.0

        return {
            "total_samples": len(samples),
            "detected_events": events,
            "event_count": len(events),
            "sampling_rate_hz": sampling_rate_hz,
            "severity_breakdown": {
                "HIGH": sum(1 for e in events if e["severity"] == "HIGH"),
                "MEDIUM": sum(1 for e in events if e["severity"] == "MEDIUM"),
                "LOW": sum(1 for e in events if e["severity"] == "LOW"),
            }
        }
