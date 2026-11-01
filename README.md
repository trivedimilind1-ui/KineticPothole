# KineticPothole 🚗💥
### Intelligent Road Impact Detection & Geospatial Hazard Mapping System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/backend-Flask%203.x-green.svg)](https://flask.palletsprojects.com/)
[![Leaflet](https://img.shields.io/badge/mapping-Leaflet%201.9-orange.svg)](https://leafletjs.com/)
[![Tests](https://img.shields.io/badge/tests-28%20passing-brightgreen.svg)]()
[![Multi--Modal](https://img.shields.io/badge/fusion-CCTV%20%2B%20Accelerometer-cyan.svg)]()

**KineticPothole** is a hackathon-ready, multi-modal road hazard detection and mapping platform. It combines:
1. **Smartphone Accelerometer & GPS Sensing:** Crowdsourced road impact detection from vehicular motion dynamics.
2. **CCTV AI Road Damage Vision:** Traffic camera video frame extraction and asphalt distress/cavity bounding box detection.
3. **Multi-Modal Sensor Fusion Engine:** Bayesian cross-validation correlating visual damage with physical road impacts.

> [!NOTE]
> **Scientific Integrity & Depth Disclaimer:** Accelerometer data alone cannot calculate the exact physical centimeter depth of a road crater due to vehicle suspension dynamics, tire pressure, and chassis dampening. KineticPothole classifies **impact severity** ($m/s^2$) and registers locations as **suspected road hazards**. CCTV vision analysis confirms surface distress without claiming underground structural depth.

---

## 📹 CCTV AI Road Damage Module & Privacy Shield (`backend/cctv_detector.py`)

1. **Configurable Video Extraction**:
   - Uses OpenCV to sample frames at user-specified intervals (0.5s, 1.0s, or 2.0s).
   - Supports pre-bundled corridor footage (`sample_cctv_pothole.mp4`) and user video uploads (`.mp4`, `.avi`).
2. **Strict Privacy Shield**:
   - In accordance with privacy and surveillance standards, AI analysis is **strictly restricted to the asphalt road surface ROI** (lower 65% of frame).
   - Windshields, oncoming vehicle cabins, pedestrian eye levels, and sky are completely cropped out prior to analysis.
   - Absolutely no facial recognition, vehicle occupant profiling, or license plate harvesting is conducted.
3. **YOLO-Compatible Detection Interface**:
   - Ready to drop in YOLO ONNX model weights into `backend/models/`.
   - Built-in OpenCV adaptive computer-vision asphalt distress and cavity contour analyzer ensures immediate execution without requiring multi-gigabyte external weight downloads.
4. **Visual Bounding Boxes & Confidence**:
   - Detects road pavement cavities, potholes, and surface irregularities.
   - Renders color-coded bounding boxes and confidence badges directly onto extracted frames.
5. **Camera GPS Association**:
   - Pre-seeded with 3 corridor cameras (`CAM-GST-SERVICE`, `CAM-SRM-MAIN`, `CAM-POTHERI-STN`).
   - Interactive configuration modal allows updating camera GPS coordinates, road segments, and camera names.

---

## ⚡ Multi-Modal Sensor Fusion Engine (`backend/sensor_fusion.py`)

KineticPothole solves the false-positive problem of pothole detection (e.g., visual stains vs real craters, or vehicle expansion joints vs road holes) through sensor fusion:

1. **Diminishing Returns on Single-Camera Persistence**:
   - Multiple frames from the *same* camera are not double-counted as independent confirmations:
     $$S_{vis}(k) = S_0 + (S_{max} - S_0) \cdot \left(1 - \frac{1}{1 + 0.35 \cdot (k - 1)}\right)$$
2. **Multi-Camera Confirmation**:
   - When different cameras detect the same road section, visual evidence score increases:
     $$S_{vis, multi} = \min(0.95, S_{vis} + 0.15 \cdot (N_{cams} - 1))$$
3. **Multi-Modal Bayesian Fusion**:
   - Correlates visual detections with physical smartphone impacts within a $35\text{ m}$ spatial radius and $48\text{ h}$ temporal window:
     $$S_{fused} = 1 - (1 - S_{vis}) \cdot (1 - S_{phone})$$
4. **Dual-Confirmation Synergy Boost**:
   - When both visual damage ($S_{vis} \ge 0.5$) and physical impact ($S_{phone} \ge 0.5$) cross-validate the same cluster:
     $$S_{final} = \min(0.99, S_{fused} + 0.15)$$
   - Status transitions to **`DUAL_CONFIRMED`**, marked on the Leaflet map with a glowing cyan/purple star badge ($\bigstar$).

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
│   ├── app.py                 # Flask REST API, CCTV routes & static server
│   ├── detector.py            # Accelerometer signal processing & sliding window
│   ├── cctv_detector.py       # OpenCV video extraction & asphalt distress detector
│   ├── sensor_fusion.py       # Multi-modal Bayesian evidence fusion engine
│   ├── database.py            # SQLite schema, cameras, CCTV detections & clustering
│   ├── requirements.txt       # Dependencies including opencv-python-headless
│   ├── tests/
│   │   ├── test_detector.py   # Signal processing unit tests
│   │   ├── test_database.py   # Spatial clustering & Haversine tests
│   │   ├── test_fusion.py     # Sensor fusion mathematical unit tests
│   │   ├── test_api.py        # Accelerometer API integration tests
│   │   └── test_cctv_api.py   # CCTV & fusion endpoint integration tests
│   ├── cctv_frames/           # Annotated defect frame images
│   └── kinetic_pothole.db     # SQLite database
├── frontend/
│   ├── index.html             # Multi-mode dashboard (Phone, Judge Demo, CCTV)
│   ├── style.css              # Cyberpunk dark theme, CCTV viewer, fusion card
│   ├── app.js                 # Mode switching, demo replay & CCTV AI interactions
│   ├── map.js                 # Leaflet map with Dual-Confirmed stars & CCTV pins
│   └── charts.js              # Real-time Chart.js waveform stream & ripple visualizer
├── data/
│   ├── sample_cctv_pothole.mp4# Prerecorded 10-second road footage with pothole obstacle
│   ├── generate_cctv_video.py # Script generating realistic test road footage
│   ├── sample_normal.csv      # Normal road accelerometer baseline
│   ├── sample_speedbreaker.csv# Speed-breaker biphasic wave
│   └── sample_pothole.csv     # Sharp pothole shock impact
└── README.md                  # Comprehensive manual
```

---

## 🚀 Quickstart Guide

### 1. Installation
```bash
# Clone and enter repo
git clone https://github.com/trivedimilind1-ui/KineticPothole.git
cd KineticPothole

# Install dependencies
pip install -r backend/requirements.txt
```

### 2. Run All Automated Tests
```bash
python -m pytest backend/tests/ -v
```
*(All 28 unit and integration tests should pass.)*

### 3. Start the Server
```bash
python backend/app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

---

## 🎬 3-Mode Demonstration Walkthrough

### Mode A: Smartphone Live Mode 📱
- Reads `DeviceMotionEvent` and HTML5 Geolocation.
- Telemetry meters display live X, Y, Z acceleration and gravity-subtracted magnitude.
- Click **"Phone Sync"** to scan the QR code and connect any iOS or Android phone over Wi-Fi.

### Mode B: Judge Demo Mode 🧪
- Replay 3 pre-bundled benchmark road datasets through the Python detector:
  - **Normal Road (Baseline)**
  - **Speed Breaker (Potheri Stn)**
  - **Pothole Impact (Service Lane)**
- Real-time animated waveform, sound shockwave ripple, and auto-dismissing toast notifications.

### Mode C: CCTV AI Road Damage Monitoring 📹
- Switch to **"CCTV AI Monitoring"** tab.
- Select a traffic camera (`CAM-GST-SERVICE`, `CAM-SRM-MAIN`, `CAM-POTHERI-STN`) or configure custom GPS coordinates.
- Click **"Run AI Detection"**:
  - Video frames are extracted at configured intervals.
  - Asphalt surface ROI is analyzed for distress and cavities.
  - Bounding boxes and confidence ratings are drawn.
  - Defect thumbnails populate the clickable frame carousel.
- Click **"Run Sensor Fusion"**:
  - Cross-validates CCTV visual findings with smartphone impact detections within 35m.
  - Displays combined confidence and evidence metrics.
  - Marks the location as **`DUAL_CONFIRMED`** with a glowing star marker on the map.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health, server timestamp, LAN IP, and database stats |
| `GET` | `/api/events` | List recorded impact events (`?limit=50&severity=HIGH`) |
| `POST` | `/api/events` | Ingest and spatially cluster a detected event |
| `POST` | `/api/feed_sample` | Ingest streaming single sensor sample; executes real-time detector |
| `GET` | `/api/hazards` | Retrieve clustered road hazards with multi-modal fusion scores |
| `GET` | `/api/statistics` | Dashboard statistics (total events, high impacts, dual confirmed) |
| `POST` | `/api/cctv/cameras` | Register or update CCTV camera with GPS coordinates |
| `GET` | `/api/cctv/cameras` | List registered CCTV cameras along the corridor |
| `POST` | `/api/cctv/process_video` | Extract frames and run AI road damage detection |
| `POST` | `/api/cctv/upload_video` | Upload custom CCTV road footage (`.mp4`, `.avi`) |
| `GET` | `/api/cctv/frames/<filename>` | Serve annotated CCTV frame images with bounding boxes |
| `POST` | `/api/fusion/run` | Execute multi-modal Bayesian sensor fusion engine |
| `POST` | `/api/reset` | Clear all events, hazard clusters, and CCTV detections |

---

## 🔬 Scientific Limitations & Future Scope

1. **Vehicle Suspension Decoupling**:
   - Different vehicles (SUV, sedan, auto-rickshaw, 2-wheeler) have vastly different spring-damper curves. The adaptive calibration mode mitigates this, but machine learning models trained on specific vehicle classes would further improve classification.
2. **3D Depth Estimation**:
   - Accelerometers measure force and acceleration response, not physical crater geometry. Future iterations could fuse smartphone camera optical flow (edge vision) with accelerometer timestamps.
3. **Edge Computing / Web Worker**:
   - In production deployments with millions of commuters, sliding-window filtering can be executed entirely client-side inside a JavaScript Web Worker, only sending filtered hazard events to the cloud to minimize bandwidth.
