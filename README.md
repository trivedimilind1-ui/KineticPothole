# KineticPothole 🚗💥
### Intelligent Road Impact Detection & Geospatial Hazard Mapping System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/backend-Flask%203.x-green.svg)](https://flask.palletsprojects.com/)
[![Leaflet](https://img.shields.io/badge/mapping-Leaflet%201.9-orange.svg)](https://leafletjs.com/)
[![Tests](https://img.shields.io/badge/tests-20%20passing-brightgreen.svg)]()

**KineticPothole** is a hackathon-ready, smartphone-based road hazard detection and mapping platform. It transforms standard smartphone accelerometer sensors and GPS telemetry into a crowd-sensed road surface audit tool—**without requiring external IoT hardware, dedicated OBD-II dongles, or vehicle-mounted cameras**.

The system continuously monitors 3-axis motion dynamics, filters baseline gravity and vehicle vibrations, detects abrupt road impact anomalies (such as potholes, speed-breakers, and rough pavement), classifies impact severity, and groups detections into persistent geospatial hazard clusters on an interactive map.

> [!NOTE]
> **Scientific Integrity & Depth Disclaimer:** Accelerometer data alone cannot calculate the exact physical centimeter depth of a road crater due to vehicle suspension dynamics, tire pressure, and chassis dampening. KineticPothole classifies **impact severity** ($m/s^2$) and registers locations as **suspected road hazards**.

---

## 🗺️ Geospatial Focus & Use Case
Configured out-of-the-box for commuter corridors around:
- **SRMIST Kattankulathur Campus** (Main Arch, Potheri Gate, Tech Park)
- **Potheri Railway Station & Crossings**
- **Grand Southern Trunk (GST) Road & Service Lanes (NH 45)**

---

## 🏗️ Architecture & Project Structure

```
KineticPothole/
├── backend/
│   ├── app.py                 # Flask REST API & static frontend server
│   ├── detector.py            # Signal processing, sliding-window & envelope analysis
│   ├── database.py            # SQLite schema, Haversine spatial clustering & confidence engine
│   ├── requirements.txt       # Python backend dependencies
│   ├── tests/
│   │   ├── test_detector.py   # Unit tests for filtering, gravity removal & thresholds
│   │   ├── test_database.py   # Spatial clustering & Haversine distance unit tests
│   │   └── test_api.py        # Integration tests for all REST API endpoints
│   └── kinetic_pothole.db     # Persistent SQLite database (auto-generated)
├── frontend/
│   ├── index.html             # High-tech dark navy dashboard & responsive layout
│   ├── style.css              # Glassmorphic UI, glowing telemetry meters & modal styles
│   ├── app.js                 # HTML5 DeviceMotion & Geolocation APIs, mode controller
│   ├── map.js                 # Leaflet.js map with custom severity markers & 20m cluster rings
│   └── charts.js              # Real-time Chart.js waveform stream & animated shockwave ripple
├── data/
│   ├── generate_samples.py    # Generator script for test scenarios
│   ├── sample_normal.csv      # Smooth asphalt GST Road baseline
│   ├── sample_speedbreaker.csv# Biphasic speed-breaker wave (Potheri Station)
│   └── sample_pothole.csv     # Medium & High pothole shock impacts (Service Lane)
└── README.md                  # Comprehensive setup & demo manual
```

---

## ⚡ Core Signal Processing Engine (`backend/detector.py`)

1. **Vector Magnitude Computation**:
   $$A = \sqrt{x^2 + y^2 + z^2}$$
2. **Dynamic Acceleration (Gravity Baseline Removal)**:
   $$A_{dynamic} = |A_{filtered} - 9.80665\text{ m/s}^2|$$
3. **Low-Pass Exponential Smoothing**:
   $$A_t = \alpha \cdot A_{raw} + (1 - \alpha) \cdot A_{t-1} \quad (\alpha = 0.35)$$
4. **Sliding-Window Statistical Profiling**:
   - Computes **Peak Dynamic Acceleration**, **RMS** ($\sqrt{\frac{1}{N}\sum A_i^2}$), **Standard Deviation** ($\sigma$), and **Crest Factor** ($\frac{A_{peak}}{\mu}$).
5. **Pattern Discrimination**:
   - **Suspected Pothole**: Sharp sudden vertical drop-spike, high crest factor ($>2.2$), steep jerk slope ($>25\text{ m/s}^3$).
   - **Suspected Speed-Breaker**: Biphasic rise-fall sinusoidal wave, longer duration (0.4–0.8s), moderate crest factor ($1.4 - 2.2$).
   - **Rough Road Section**: Sustained elevated variance without an isolated single peak.
6. **Vehicle Suspension Cooldown**:
   - Enforces an event cooldown ($1.2\text{ s}$) following any triggered impact to prevent duplicate reports caused by tire bounce or secondary rear-axle strikes.
7. **Adaptive Baseline Calibration**:
   - Adjusts detection thresholds based on vehicle-specific chassis vibration:
     $$\text{Threshold}_{Low} = \mu_{base} + 3.0\sigma_{base}$$
     $$\text{Threshold}_{Med} = \mu_{base} + 6.5\sigma_{base}$$
     $$\text{Threshold}_{High} = \mu_{base} + 11.5\sigma_{base}$$

---

## 📍 Geospatial Clustering & Hazard Engine (`backend/database.py`)

- **Spatial Radius Grouping**: When an impact is recorded, the backend evaluates existing hazards within a $20\text{ m}$ radius using the Haversine equation.
- **Dynamic Centroid Updates**: Merges repeated reports, updating the cluster centroid coordinate and raising the severity tier if a higher peak is encountered.
- **Multi-Device vs Single-Trip Confidence**:
  - Distinguishes between multiple passes from the *same* device (`device_id`/`trip_id`) versus independent confirmation from *different* devices.
  - Independent multi-device verification boosts confidence to $>90\%$, preventing single-device bias.
  - GPS readings with high error radius ($>50\text{ m}$) receive a confidence penalty.

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12 installed.

### 2. Installation
Open your terminal in the `KineticPothole` directory:

```bash
# Optional: create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 3. Run Automated Tests
Verify detector mathematics, database clustering, and API routes:

```bash
python -m pytest backend/tests/ -v
```
*(All 20 unit and integration tests should pass.)*

### 4. Start the Application Server
Run the Flask server:

```bash
python backend/app.py
```

The server binds to `0.0.0.0:5000` and displays:
```
=========================================================
 KineticPothole Road Impact Detection System Running!
 Local Web Access:    http://127.0.0.1:5000
 Smartphone Access:   http://<YOUR_LAN_IP>:5000
=========================================================
```

Open your browser to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 📱 Connecting a Real Smartphone

1. Ensure your smartphone and laptop are connected to the **same Wi-Fi network**.
2. Click the **"Phone Sync"** button in the dashboard top navigation.
3. Scan the generated QR code or type `http://<YOUR_LAN_IP>:5000` into your mobile browser (Safari on iOS, Chrome on Android).
4. Tap **"Start Detection"**:
   - **iOS (Safari):** A native popup will ask *"Allow this website to use motion sensors?"* Tap **Allow**.
   - **Android (Chrome):** Motion and Geolocation permissions are requested automatically.
5. Place the phone flat or mounted securely in your vehicle. Drive across campus or shake the phone vertically to test real-time shockwave trigger!

---

## 🎬 3-Mode Demonstration Walkthrough

KineticPothole is designed for instant, reliable demonstrations even when not driving:

### Mode A: Live Phone Mode 📱
- Live reads from `DeviceMotionEvent` and HTML5 `Geolocation API`.
- Real-time sampling frequency calculation (Hz).
- Telemetry meters display live X, Y, Z acceleration and dynamic gravity-subtracted magnitude.

### Mode B: Sensor CSV Replay 📂
- Click the **"CSV Replay"** tab in the top navigation.
- Choose from pre-bundled realistic road datasets:
  - `Service Lane — Pothole Impacts (Medium & High)`
  - `Potheri Railway Stn — Speed Breaker`
  - `GST Road — Normal Smooth Asphalt`
- Select playback speed (**1x**, **2x**, or **5x**).
- Click **"Start Replay"** to watch the telemetry stream, waveform chart, animated shockwave ripple, and Leaflet map update in real time!
- You can also upload custom `.csv` files logged from sensor logger apps (columns: `timestamp,x,y,z,lat,lon,accuracy`).

### Mode C: Controlled Test Mode 🧪
- Click the **"Controlled Test"** tab.
- Click any of the one-click synthetic road scenario buttons:
  - **Smooth Road (Baseline)**
  - **Speed Breaker Wave**
  - **Medium Pothole Impact**
  - **Severe High-Impact Pothole**
- Synthetic signals are routed through the exact same signal processing pipeline and clearly tagged with `is_synthetic: true` for scientific honesty.

### Reset Demo
- Click the **"Reset"** button anytime to flush SQLite records, clear the map markers, and reset telemetry counters for a fresh demonstration.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health, server timestamp, LAN IP, and current detector thresholds |
| `GET` | `/api/events` | List recorded impact events (`?limit=50&severity=HIGH`) |
| `POST` | `/api/events` | Ingest and spatially cluster a detected event |
| `POST` | `/api/feed_sample` | Ingest streaming single sensor sample; executes real-time detector |
| `GET` | `/api/hazards` | Retrieve all geographically clustered road hazards with confidence scores |
| `GET` | `/api/statistics` | Aggregated dashboard statistics (totals, breakdown by severity, unique devices) |
| `POST` | `/api/calibrate` | Submit 5-second sample window to adaptively calibrate baseline noise floor |
| `POST` | `/api/process_batch` | Batch process a list of samples (for CSV uploads / trip replays) |
| `POST` | `/api/reset` | Clear all events and hazard clusters |

---

## 🔬 Scientific Limitations & Future Scope

1. **Vehicle Suspension Decoupling**:
   - Different vehicles (SUV, sedan, auto-rickshaw, 2-wheeler) have vastly different spring-damper curves. The adaptive calibration mode mitigates this, but machine learning models trained on specific vehicle classes would further improve classification.
2. **3D Depth Estimation**:
   - Accelerometers measure force and acceleration response, not physical crater geometry. Future iterations could fuse smartphone camera optical flow (edge vision) with accelerometer timestamps.
3. **Edge Computing / Web Worker**:
   - In production deployments with millions of commuters, sliding-window filtering can be executed entirely client-side inside a JavaScript Web Worker, only sending filtered hazard events to the cloud to minimize bandwidth.
