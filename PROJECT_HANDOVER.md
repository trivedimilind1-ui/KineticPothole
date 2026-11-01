# 🚗💥 KineticPothole — Project Handover Document
**Intelligent Road Impact Detection, CCTV AI Vision & Geospatial Hazard Mapping System**

---

## 📌 1. Project Overview & Pitch

**KineticPothole** is an end-to-end, multi-modal road surface monitoring and hazard mapping platform. It solves the critical infrastructure problem of undetected potholes and dangerous road irregularities by combining:

1. **Crowdsourced Smartphone Sensing:** Converts standard smartphone motion sensors (`DeviceMotionEvent`) and GPS into a vehicular shockwave and road impact logger—**without requiring external IoT hardware, OBD-II dongles, or vehicle-mounted cameras**.
2. **CCTV AI Video Analysis:** Ingests traffic camera footage along urban corridors, isolates the road pavement with a strict **Privacy Shield** (excluding vehicle occupants and pedestrians), and detects asphalt cavities/damage using computer vision.
3. **Multi-Modal Bayesian Sensor Fusion:** Cross-validates physical accelerometer shocks with CCTV visual distress detections within a 35m spatial radius, elevating verified hazards to **`DUAL_CONFIRMED`** status.

> [!NOTE]
> **Scientific Integrity & Depth Disclaimer:** Accelerometer data alone cannot calculate the exact physical centimeter depth of a crater due to vehicle suspension damping and tire pressure. KineticPothole classifies **dynamic impact severity** ($m/s^2$) and maps locations as **suspected road hazards**. CCTV vision analysis verifies surface distress without claiming subterranean structural depth.

---

## 🌐 2. Live Links & Repository

| Resource | Link |
|---|---|
| **Live Production Website** | [https://kinetic-pothole.vercel.app](https://kinetic-pothole.vercel.app) |
| **GitHub Repository** | [https://github.com/trivedimilind1-ui/KineticPothole](https://github.com/trivedimilind1-ui/KineticPothole) |
| **Vercel Project Dashboard** | [https://vercel.com/trivedimilind1-ui/kinetic-pothole](https://vercel.com/trivedimilind1-ui/kinetic-pothole) |

*Deployment is configured with automated continuous delivery: every commit pushed to `main` automatically builds and deploys to Vercel.*

---

## 🏗️ 3. Architecture & Tech Stack

### Frontend:
- **Stack:** Pure Vanilla HTML5, CSS3, Modern ES6+ JavaScript (zero heavy framework overhead, blazing fast load times).
- **Theme:** Glassmorphic Cyberpunk Dark Navy UI (`#090e17`), electric cyan (`#00d2ff`) & purple (`#8b5cf6`) accents.
- **Mapping:** **Leaflet.js 1.9** with free CartoDB Voyager / OpenStreetMap tiles (**No Google Maps API keys or billing required**).
- **Data Visualizations:** **Chart.js 4.4** (sliding-window real-time telemetry stream) and HTML5 `<canvas>` (shockwave ripple visualizer).
- **Sensors:** HTML5 `DeviceMotionEvent` (accelerometer) and `Geolocation API` (GPS coordinates & accuracy).

### Backend:
- **Framework:** **Flask 3.x** REST API with `Flask-CORS`.
- **Database:** **SQLite 3** (`kinetic_pothole.db`) with automatic 20-meter Haversine spatial clustering, multi-device tracking, and serverless `/tmp` fallback for Vercel.
- **Signal Processing:** **NumPy** for exponential smoothing, sliding-window RMS, gravity baseline subtraction ($|A - 9.81\text{ m/s}^2|$), jerk analysis, and crest factor evaluation.
- **Computer Vision:** **OpenCV** (`opencv-python-headless`) for video frame extraction at configurable intervals (0.5s–2.0s), asphalt surface ROI isolation, contour-based road defect detection, and bounding box drawing.
- **Sensor Fusion:** Custom Bayesian probabilistic cross-validation engine.

---

## 📁 4. Project Directory Structure

```
KineticPothole/
├── api/
│   └── index.py               # Vercel serverless WSGI entrypoint
├── backend/
│   ├── app.py                 # Core Flask REST API & static file server
│   ├── detector.py            # Accelerometer signal processing & sliding-window detector
│   ├── database.py            # SQLite schema, Haversine clustering & confidence engine
│   ├── cctv_detector.py       # OpenCV video extractor, privacy shield & bounding box engine
│   ├── sensor_fusion.py       # Multi-modal Bayesian evidence fusion engine
│   ├── requirements.txt       # Python backend dependencies
│   ├── cctv_frames/           # Output directory for annotated AI defect images
│   └── tests/
│       ├── test_detector.py   # Signal processing unit tests (gravity, thresholds, cooldown)
│       ├── test_database.py   # Spatial clustering & multi-device tests
│       ├── test_api.py        # Accelerometer API integration tests
│       ├── test_fusion.py     # Sensor fusion mathematical tests
│       └── test_cctv_api.py   # CCTV & fusion endpoint integration tests
├── frontend/
│   ├── index.html             # Main dashboard (Phone, Judge Demo, CCTV modes, modals)
│   ├── style.css              # Glassmorphic responsive styling & presentation mode
│   ├── app.js                 # Core application controller & event wiring
│   ├── map.js                 # Leaflet map manager, dual-confirmed star pins, source filters
│   └── charts.js              # Real-time Chart.js stream & shockwave visualizer
├── data/
│   ├── sample_cctv_pothole.mp4# Prerecorded 10s traffic camera road video
│   ├── generate_cctv_video.py # Synthetic video generator script
│   ├── sample_normal.csv      # Normal road accelerometer baseline (GST Road)
│   ├── sample_speedbreaker.csv# Biphasic speed-breaker wave (Potheri Stn)
│   └── sample_pothole.csv     # Severe pothole shock impacts (Service Lane)
├── vercel.json                # Vercel serverless runtime and rewrite rules
├── requirements.txt           # Root requirements for Vercel build
└── README.md                  # Comprehensive documentation and quickstart
```

---

## ⚙️ 5. Key Algorithms & Mathematical Formulations

### A. Dynamic Acceleration (Gravity Removal):
$$A = \sqrt{x^2 + y^2 + z^2}$$
$$A_{dynamic} = |A_{filtered} - 9.80665\text{ m/s}^2|$$

### B. Suspension Bounce Cooldown:
Enforces a $1.2\text{ s}$ event cooldown after an impact is registered to prevent tire rebound and rear-axle strikes from double-counting.

### C. Adaptive Noise Floor Calibration:
$$\text{Threshold}_{Low} = \mu_{base} + 3.0\sigma_{base}$$
$$\text{Threshold}_{Med} = \mu_{base} + 6.5\sigma_{base}$$
$$\text{Threshold}_{High} = \mu_{base} + 11.5\sigma_{base}$$

### D. Multi-Modal Bayesian Sensor Fusion:
$$S_{fused} = 1 - (1 - S_{vis}) \cdot (1 - S_{phone})$$
When both visual damage ($S_{vis} \ge 0.5$) and physical accelerometer shocks ($S_{phone} \ge 0.5$) cross-validate within a $35\text{ m}$ spatial radius:
$$S_{final} = \min(0.99, S_{fused} + 0.15)$$
Status transitions to **`DUAL_CONFIRMED`** with a glowing cyan/purple star marker ($\bigstar$) on the map.

---

## 💻 6. How to Run Locally

### Prerequisites:
- Python 3.10, 3.11, or 3.12
- Node.js (optional, only if using Vercel CLI)

### 1. Clone & Install:
```bash
git clone https://github.com/trivedimilind1-ui/KineticPothole.git
cd KineticPothole

# Install dependencies
pip install -r requirements.txt
```

### 2. Run All Automated Tests:
```bash
python -m pytest backend/tests/ -v
```
*(All 28 tests will execute and pass in < 1 second.)*

### 3. Start Local Server:
```bash
python backend/app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

---

## 🎬 7. Demonstration Guide (For Presentation & Judging)

### Mode 1: 📱 Smartphone Live Mode
- Open on mobile or click **"Phone Sync"** to scan the QR code.
- Tap **"Start Live Phone"**.
- Shake or drive with the phone: real-time telemetry meters, dynamic gravity removal, and the live sliding-window chart stream active readings.

### Mode 2: 🧪 Judge Demo Mode
- Click **"Judge Demo Mode"** in the top navigation.
- Select from 3 pre-bundled benchmark corridor datasets:
  1. `Normal Road (GST Road Smooth Baseline)`
  2. `Speed Breaker (Potheri Stn Biphasic Wave)`
  3. `Pothole Impact (Service Lane Severe Jolts)`
- Hit **"Play Dataset"** (choose 1x, 2x, or 5x speed) to watch the telemetry meters, animated ripple canvas, and map cluster pins update in real time.

### Mode 3: 📹 CCTV AI Road Damage Monitoring
- Click **"CCTV AI Monitoring"** in the top navigation.
- Choose traffic camera `CAM-GST-SERVICE` (or click **"Configure GPS"** to set custom coordinates).
- Click **"▶ Run AI Detection"**: OpenCV extracts frames at the selected interval, isolates the road ROI, computes damage contours, draws color-coded bounding boxes, and populates the clickable thumbnail carousel.
- Click **"⚡ Run Sensor Fusion"**: Correlates CCTV defect frames with smartphone impact clusters. The status pill lights up as **`⚡ DUAL-CONFIRMED MULTI-MODAL`** and the map marks the spot with a glowing star marker ($\bigstar$).

### Big-Screen Mode:
- Click **"📽️ Presentation Mode"** (or press the `P` key) to toggle a high-contrast, magnified view optimized for projectors and stage presentations.

---

## 📡 8. REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check, server time, detector thresholds, and DB stats |
| `GET` | `/api/events` | List recorded impact events (`?limit=50&severity=HIGH`) |
| `POST` | `/api/events` | Ingest and spatially cluster a detected event |
| `POST` | `/api/feed_sample` | Stream a single real-time sensor sample through detector |
| `GET` | `/api/hazards` | Retrieve clustered hazards with multi-modal fusion scores |
| `GET` | `/api/statistics` | Dashboard metrics (total events, high impacts, dual confirmed) |
| `POST` | `/api/calibrate` | Submit 5-second sample window to adaptively calibrate baseline |
| `POST` | `/api/process_batch` | Batch process samples for CSV replays |
| `GET` | `/api/cctv/cameras` | List corridor CCTV cameras with GPS coordinates |
| `POST` | `/api/cctv/cameras` | Register or update CCTV camera location |
| `POST` | `/api/cctv/process_video` | Extract frames and run AI road damage detection |
| `POST` | `/api/cctv/upload_video` | Upload custom CCTV road footage (`.mp4`, `.avi`) |
| `GET` | `/api/cctv/frames/<filename>` | Serve annotated CCTV frame images with bounding boxes |
| `POST` | `/api/fusion/run` | Execute multi-modal Bayesian sensor fusion engine |
| `POST` | `/api/reset` | Clear all events, hazard clusters, and CCTV detections |

---

## 🚀 9. Future Roadmap & Hackathon Extensions

1. **Edge YOLOv8 Deployment:** Export fine-tuned YOLOv8 weights trained on RDD2022 (Road Damage Dataset) into ONNX format and place in `backend/models/`.
2. **Municipal Work-Order Integration:** Add 1-click export to PWD/NHAI municipal road maintenance systems (GeoJSON / CSV exports).
3. **OBD-II CAN-Bus Bridge:** Pair accelerometer readings with vehicle speed and suspension wheel speed sensors for even tighter vehicle dynamics filtering.
