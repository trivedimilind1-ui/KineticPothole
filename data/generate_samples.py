"""
Generate realistic sample datasets for KineticPothole demonstration.
Coordinates centered around SRM Kattankulathur, Potheri Railway Station, and GST Road.
"""

import csv
import math
import numpy as np

# Coordinates around SRMIST Kattankulathur & GST Road
# Start near SRM Main Gate: 12.823050, 80.044200
# Potheri Station: 12.825800, 80.047500
# GST Road flyover / service lane: 12.821000, 80.041000

BASE_LAT = 12.823050
BASE_LON = 80.044200
GRAVITY = 9.80665
SAMPLE_RATE_HZ = 50
DT = 1.0 / SAMPLE_RATE_HZ


def generate_normal_csv(filename="data/sample_normal.csv", duration_sec=15.0):
    """Normal smooth asphalt driving with typical engine vibration and minor asphalt texture."""
    num_samples = int(duration_sec * SAMPLE_RATE_HZ)
    start_time = 1700000000.0

    rows = []
    for i in range(num_samples):
        t = start_time + i * DT
        # Moving along GST Road northwards
        progress = i / num_samples
        lat = round(BASE_LAT + progress * 0.0018, 6)
        lon = round(BASE_LON + progress * 0.0012, 6)

        # Baseline engine / vehicle vibration (0.1 - 0.3 m/s^2)
        vibe_x = float(np.random.normal(0, 0.12))
        vibe_y = float(np.random.normal(0, 0.15))
        vibe_z = float(np.random.normal(0, 0.20))

        rows.append({
            "timestamp": round(t, 3),
            "x": round(0.1 + vibe_x, 3),
            "y": round(0.2 + vibe_y, 3),
            "z": round(GRAVITY + vibe_z, 3),
            "lat": lat,
            "lon": lon,
            "accuracy": 4.5
        })

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "x", "y", "z", "lat", "lon", "accuracy"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {filename} ({len(rows)} samples)")


def generate_speedbreaker_csv(filename="data/sample_speedbreaker.csv", duration_sec=18.0):
    """Vehicle approaching and crossing a road speed-breaker near Potheri railway station."""
    num_samples = int(duration_sec * SAMPLE_RATE_HZ)
    start_time = 1700000000.0
    sb_center_time = start_time + 8.0  # Speed breaker hits at 8 seconds

    rows = []
    for i in range(num_samples):
        t = start_time + i * DT
        progress = i / num_samples
        lat = round(12.825200 + progress * 0.0015, 6)
        lon = round(80.046800 + progress * 0.0010, 6)

        vibe_x = float(np.random.normal(0, 0.15))
        vibe_y = float(np.random.normal(0, 0.18))
        vibe_z = float(np.random.normal(0, 0.22))

        # Speed breaker profile: biphasic sinusoidal hump lasting ~0.8s (t in sb_center_time ± 0.4s)
        time_to_sb = t - sb_center_time
        if -0.45 <= time_to_sb <= 0.45:
            # Rise-fall wave
            wave = math.sin((time_to_sb / 0.45) * math.pi * 2)
            z_impact = 7.2 * wave
            x_impact = 1.8 * abs(wave)
        else:
            z_impact = 0.0
            x_impact = 0.0

        rows.append({
            "timestamp": round(t, 3),
            "x": round(0.15 + vibe_x + x_impact, 3),
            "y": round(0.18 + vibe_y, 3),
            "z": round(GRAVITY + vibe_z + z_impact, 3),
            "lat": lat,
            "lon": lon,
            "accuracy": 5.0
        })

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "x", "y", "z", "lat", "lon", "accuracy"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {filename} ({len(rows)} samples)")


def generate_pothole_csv(filename="data/sample_pothole.csv", duration_sec=20.0):
    """Vehicle encountering a medium pothole and a severe road impact on the service lane."""
    num_samples = int(duration_sec * SAMPLE_RATE_HZ)
    start_time = 1700000000.0
    pothole1_time = start_time + 5.5  # Medium impact pothole at 5.5s
    pothole2_time = start_time + 12.0 # High impact pothole at 12.0s

    rows = []
    for i in range(num_samples):
        t = start_time + i * DT
        progress = i / num_samples
        lat = round(12.821500 + progress * 0.0020, 6)
        lon = round(80.041800 + progress * 0.0016, 6)

        vibe_x = float(np.random.normal(0, 0.15))
        vibe_y = float(np.random.normal(0, 0.15))
        vibe_z = float(np.random.normal(0, 0.20))

        z_extra = 0.0
        x_extra = 0.0

        # Pothole 1: Medium sharp drop and jolt (peak dynamic ~8.0 m/s^2)
        dt1 = t - pothole1_time
        if 0.0 <= dt1 <= 0.35:
            decay = math.exp(-dt1 * 8.0)
            z_extra = 8.2 * math.cos(dt1 * 25.0) * decay
            x_extra = 2.0 * decay

        # Pothole 2: Severe High impact (peak dynamic ~14.5 m/s^2)
        dt2 = t - pothole2_time
        if 0.0 <= dt2 <= 0.40:
            decay = math.exp(-dt2 * 7.0)
            z_extra = 15.2 * math.cos(dt2 * 25.0) * decay
            x_extra = 4.2 * decay

        rows.append({
            "timestamp": round(t, 3),
            "x": round(0.1 + vibe_x + x_extra, 3),
            "y": round(0.12 + vibe_y, 3),
            "z": round(GRAVITY + vibe_z + z_extra, 3),
            "lat": lat,
            "lon": lon,
            "accuracy": 4.0
        })

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "x", "y", "z", "lat", "lon", "accuracy"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {filename} ({len(rows)} samples)")


if __name__ == "__main__":
    generate_normal_csv()
    generate_speedbreaker_csv()
    generate_pothole_csv()
