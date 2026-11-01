"""
Comprehensive verification test for all 3 hackathon demonstration scenarios.
"""
import requests
import csv
import sys

BASE_URL = "http://127.0.0.1:5000"


def replay_file(filename):
    with open(filename) as f:
        reader = csv.DictReader(f)
        samples = list(reader)

    events = []
    for s in samples:
        payload = {
            "timestamp": float(s["timestamp"]),
            "x": float(s["x"]),
            "y": float(s["y"]),
            "z": float(s["z"]),
            "lat": float(s["lat"]),
            "lon": float(s["lon"]),
            "accuracy": float(s["accuracy"]),
            "device_id": "judge-demo-device",
            "trip_id": f"trip-{filename}",
            "is_synthetic": True
        }
        r = requests.post(f"{BASE_URL}/api/feed_sample", json=payload)
        assert r.status_code == 200
        data = r.json()
        if data.get("event_detected") and data.get("event"):
            events.append(data["event"])
    return events


def test_all_scenarios():
    print("--- 1. Testing Normal Road (Baseline) ---")
    requests.post(f"{BASE_URL}/api/reset")
    normal_events = replay_file("data/sample_normal.csv")
    print(f"Normal Road Events: {len(normal_events)} (Should be 0 false positives)")
    assert len(normal_events) == 0, "Normal road should not trigger false positives"

    print("--- 2. Testing Speed Breaker Scenario ---")
    requests.post(f"{BASE_URL}/api/reset")
    sb_events = replay_file("data/sample_speedbreaker.csv")
    print(f"Speed Breaker Events: {len(sb_events)}")
    assert len(sb_events) >= 1, "Expected speed breaker event"
    for e in sb_events:
        print(f"  Detected: {e['severity']} ({e['hazard_type']}) - Peak: {e['peak_dynamic_accel']} m/s²")

    print("--- 3. Testing Pothole-like Impact Scenario ---")
    requests.post(f"{BASE_URL}/api/reset")
    pothole_events = replay_file("data/sample_pothole.csv")
    print(f"Pothole Events: {len(pothole_events)}")
    assert len(pothole_events) >= 1, "Expected pothole event"
    for e in pothole_events:
        print(f"  Detected: {e['severity']} ({e['hazard_type']}) - Peak: {e['peak_dynamic_accel']} m/s² at {e['lat']}, {e['lon']}")

    print("--- 4. Checking Clustered Hazards & Statistics ---")
    h_res = requests.get(f"{BASE_URL}/api/hazards").json()
    s_res = requests.get(f"{BASE_URL}/api/statistics").json()
    print(f"Total hazards mapped: {len(h_res['hazards'])}")
    print(f"Statistics: {s_res['statistics']}")

    print("--- 5. Resetting Database to Clean State for Judges ---")
    requests.post(f"{BASE_URL}/api/reset")
    clean_stats = requests.get(f"{BASE_URL}/api/statistics").json()["statistics"]
    assert clean_stats["total_events"] == 0
    assert clean_stats["total_hazards"] == 0
    print("ALL 3 DEMO SCENARIOS VERIFIED SUCCESSFULLY!")


if __name__ == "__main__":
    test_all_scenarios()
