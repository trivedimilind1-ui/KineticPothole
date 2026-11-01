/**
 * KineticPothole — Core Application Controller
 * Connects Smartphone Sensors, Signal Processing, API, Map, and Demo Modes
 */

(function () {
    'use strict';

    // Application State
    const state = {
        mode: 'live', // 'live' | 'csv' | 'synthetic'
        isDetecting: false,
        deviceMotionListener: null,
        geolocationWatchId: null,
        
        // Latest GPS telemetry
        currentGps: {
            lat: 12.823050,
            lon: 80.044200,
            accuracy: 5.0,
            timestamp: Date.now()
        },
        hasRealGps: false,

        // Sampling rate measurement
        lastSampleTimestamp: null,
        sampleIntervals: [],
        currentFrequencyHz: 0.0,

        // In-memory ring buffer of recent sensor samples
        sampleBuffer: [],
        maxBufferSize: 300,

        // Device identification
        deviceId: 'device-' + (localStorage.getItem('kp_device_id') || Math.random().toString(36).substring(2, 9)),
        tripId: 'trip-' + Date.now(),

        // CSV Replay State
        csvData: [],
        csvReplayIndex: 0,
        csvReplayTimer: null,
        csvReplaySpeed: 2,
        isCsvReplaying: false,

        // Calibration State
        isCalibrating: false,
        calibrationBuffer: [],
        calibrationTimer: null
    };

    localStorage.setItem('kp_device_id', state.deviceId);

    // DOM Elements
    const elements = {
        // Nav & Status
        systemStatusDot: document.getElementById('systemStatusDot'),
        systemStatusText: document.getElementById('systemStatusText'),
        startDetectionBtn: document.getElementById('startDetectionBtn'),
        stopDetectionBtn: document.getElementById('stopDetectionBtn'),
        calibrateBtn: document.getElementById('calibrateBtn'),
        qrModalBtn: document.getElementById('qrModalBtn'),
        resetDemoBtn: document.getElementById('resetDemoBtn'),
        noticeBanner: document.getElementById('noticeBanner'),
        noticeText: document.getElementById('noticeText'),
        noticeIcon: document.getElementById('noticeIcon'),
        closeNoticeBtn: document.getElementById('closeNoticeBtn'),

        // Mode Switchers & Control Strips
        modeLiveBtn: document.getElementById('modeLiveBtn'),
        modeCsvBtn: document.getElementById('modeCsvBtn'),
        modeSyntheticBtn: document.getElementById('modeSyntheticBtn'),
        csvControlStrip: document.getElementById('csvControlStrip'),
        syntheticControlStrip: document.getElementById('syntheticControlStrip'),

        // Statistics
        statTotalEvents: document.getElementById('statTotalEvents'),
        statHighEvents: document.getElementById('statHighEvents'),
        statMedEvents: document.getElementById('statMedEvents'),
        statTotalHazards: document.getElementById('statTotalHazards'),

        // Telemetry Readouts
        samplingRateBadge: document.getElementById('samplingRateBadge'),
        accelX: document.getElementById('accelX'),
        accelY: document.getElementById('accelY'),
        accelZ: document.getElementById('accelZ'),
        meterX: document.getElementById('meterX'),
        meterY: document.getElementById('meterY'),
        meterZ: document.getElementById('meterZ'),
        rawMagVal: document.getElementById('rawMagVal'),
        dynAccelVal: document.getElementById('dynAccelVal'),
        gpsCoords: document.getElementById('gpsCoords'),
        gpsAccuracyBadge: document.getElementById('gpsAccuracyBadge'),

        // Shockwave Details
        lastEventSeverityBadge: document.getElementById('lastEventSeverityBadge'),
        impactHazardType: document.getElementById('impactHazardType'),
        impactJerk: document.getElementById('impactJerk'),
        impactConfidence: document.getElementById('impactConfidence'),
        impactLocation: document.getElementById('impactLocation'),
        impactTime: document.getElementById('impactTime'),

        // History Table
        eventTableBody: document.getElementById('eventTableBody'),
        historyCountBadge: document.getElementById('historyCountBadge'),

        // CSV Replay
        csvDatasetSelect: document.getElementById('csvDatasetSelect'),
        loadPresetCsvBtn: document.getElementById('loadPresetCsvBtn'),
        customCsvInput: document.getElementById('customCsvInput'),
        customFileName: document.getElementById('customFileName'),
        csvReplayToggleBtn: document.getElementById('csvReplayToggleBtn'),
        csvProgressBar: document.getElementById('csvProgressBar'),
        csvProgressText: document.getElementById('csvProgressText'),
        speedButtons: document.querySelectorAll('.speed-btn'),

        // Synthetic Buttons
        simSmoothBtn: document.getElementById('simSmoothBtn'),
        simSpeedBreakerBtn: document.getElementById('simSpeedBreakerBtn'),
        simMedPotholeBtn: document.getElementById('simMedPotholeBtn'),
        simHighPotholeBtn: document.getElementById('simHighPotholeBtn'),

        // Calibration Modal
        calibrationModal: document.getElementById('calibrationModal'),
        closeCalibrateModalBtn: document.getElementById('closeCalibrateModalBtn'),
        startCalibBtn: document.getElementById('startCalibBtn'),
        doneCalibBtn: document.getElementById('doneCalibBtn'),
        calibProgressBar: document.getElementById('calibProgressBar'),
        calibStatusText: document.getElementById('calibStatusText'),
        calibStatsPreview: document.getElementById('calibStatsPreview'),
        calibMean: document.getElementById('calibMean'),
        calibStd: document.getElementById('calibStd'),
        calibThreshLow: document.getElementById('calibThreshLow'),
        calibThreshMed: document.getElementById('calibThreshMed'),
        calibThreshHigh: document.getElementById('calibThreshHigh'),

        // QR Modal
        qrModal: document.getElementById('qrModal'),
        closeQrModalBtn: document.getElementById('closeQrModalBtn'),
        qrCodeImage: document.getElementById('qrCodeImage'),
        phoneAccessUrl: document.getElementById('phoneAccessUrl'),
        copyPhoneUrlBtn: document.getElementById('copyPhoneUrlBtn'),

        // Map buttons
        mapCenterCampusBtn: document.getElementById('mapCenterCampusBtn'),
        mapCenterUserBtn: document.getElementById('mapCenterUserBtn'),
        refreshMapBtn: document.getElementById('refreshMapBtn')
    };

    // ==========================================
    // NOTIFICATION & STATUS HELPERS
    // ==========================================

    function showNotice(message, icon = 'ℹ️', durationMs = 5000) {
        if (!elements.noticeBanner) return;
        elements.noticeText.innerText = message;
        elements.noticeIcon.innerText = icon;
        elements.noticeBanner.classList.remove('hidden');
        if (durationMs > 0) {
            setTimeout(() => {
                elements.noticeBanner.classList.add('hidden');
            }, durationMs);
        }
    }

    function setSystemStatus(text, statusClass) {
        if (elements.systemStatusText) elements.systemStatusText.innerText = text;
        if (elements.systemStatusDot) {
            elements.systemStatusDot.className = 'status-dot ' + statusClass;
        }
    }

    // ==========================================
    // SMARTPHONE SENSOR INTEGRATION (MODE A)
    // ==========================================

    async function requestMotionPermission() {
        // iOS 13+ requires explicit user gesture permission
        if (typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function') {
            try {
                const response = await DeviceMotionEvent.requestPermission();
                if (response !== 'granted') {
                    showNotice('Motion sensor permission denied on iOS.', '⚠️');
                    return false;
                }
                return true;
            } catch (err) {
                console.error('Motion permission error:', err);
                showNotice('Could not request motion permission: ' + err.message, '⚠️');
                return false;
            }
        }
        return true; // Non-iOS or older browsers
    }

    function startGeolocation() {
        if (!navigator.geolocation) {
            console.warn('Geolocation not supported on this browser');
            return;
        }

        state.geolocationWatchId = navigator.geolocation.watchPosition(
            position => {
                state.currentGps = {
                    lat: position.coords.latitude,
                    lon: position.coords.longitude,
                    accuracy: position.coords.accuracy || 10.0,
                    timestamp: position.timestamp || Date.now()
                };
                state.hasRealGps = true;

                // Update UI coords
                if (elements.gpsCoords) {
                    elements.gpsCoords.innerText = `${state.currentGps.lat.toFixed(6)}, ${state.currentGps.lon.toFixed(6)}`;
                }

                if (elements.gpsAccuracyBadge) {
                    const acc = state.currentGps.accuracy;
                    elements.gpsAccuracyBadge.innerText = `Acc: ± ${acc.toFixed(1)}m`;
                    if (acc <= 15) {
                        elements.gpsAccuracyBadge.className = 'gps-acc-badge badge-good';
                    } else {
                        elements.gpsAccuracyBadge.className = 'gps-acc-badge badge-poor';
                    }
                }

                // Update user marker on Leaflet map
                if (window.hazardMap) {
                    window.hazardMap.updateUserPosition(state.currentGps.lat, state.currentGps.lon, state.currentGps.accuracy);
                }
            },
            err => {
                console.warn('Geolocation watch error:', err.message);
                if (elements.gpsAccuracyBadge) {
                    elements.gpsAccuracyBadge.innerText = 'GPS: Default SRM';
                }
            },
            {
                enableHighAccuracy: true,
                maximumAge: 2000,
                timeout: 10000
            }
        );
    }

    function stopGeolocation() {
        if (state.geolocationWatchId !== null) {
            navigator.geolocation.clearWatch(state.geolocationWatchId);
            state.geolocationWatchId = null;
        }
    }

    function handleDeviceMotion(event) {
        const now = performance.now();

        // 1. Calculate actual sampling frequency (Hz)
        if (state.lastSampleTimestamp !== null) {
            const dt = now - state.lastSampleTimestamp;
            if (dt > 0) {
                state.sampleIntervals.push(dt);
                if (state.sampleIntervals.length > 30) state.sampleIntervals.shift();
                const avgInterval = state.sampleIntervals.reduce((a, b) => a + b, 0) / state.sampleIntervals.length;
                state.currentFrequencyHz = Math.round((1000 / avgInterval) * 10) / 10;
                if (elements.samplingRateBadge) {
                    elements.samplingRateBadge.innerText = `${state.currentFrequencyHz.toFixed(1)} Hz`;
                }
            }
        }
        state.lastSampleTimestamp = now;

        // 2. Read accelerometer values
        // Some devices provide accelerationIncludingGravity, some provide acceleration
        const acc = event.accelerationIncludingGravity || event.acceleration;
        if (!acc || (acc.x === null && acc.y === null && acc.z === null)) {
            return;
        }

        const x = acc.x || 0.0;
        const y = acc.y || 0.0;
        const z = acc.z || 0.0;

        // 3. Process reading through common pipeline
        const timestamp = Date.now() / 1000.0;
        const sample = {
            timestamp: timestamp,
            x: x,
            y: y,
            z: z,
            lat: state.currentGps.lat,
            lon: state.currentGps.lon,
            accuracy: state.currentGps.accuracy,
            device_id: state.deviceId,
            trip_id: state.tripId,
            is_synthetic: false
        };

        processSensorSample(sample);
    }

    // Common sample processing engine
    async function processSensorSample(sample) {
        // Calculate magnitude: A = sqrt(x² + y² + z²)
        const rawMagnitude = Math.sqrt(sample.x * sample.x + sample.y * sample.y + sample.z * sample.z);
        // Dynamic acceleration: |A - 9.81|
        const dynamicAccel = Math.abs(rawMagnitude - 9.80665);

        // Update telemetry gauges in UI
        if (elements.accelX) elements.accelX.innerText = sample.x.toFixed(2);
        if (elements.accelY) elements.accelY.innerText = sample.y.toFixed(2);
        if (elements.accelZ) elements.accelZ.innerText = sample.z.toFixed(2);
        if (elements.rawMagVal) elements.rawMagVal.innerText = `${rawMagnitude.toFixed(2)} m/s²`;
        if (elements.dynAccelVal) elements.dynAccelVal.innerText = `${dynamicAccel.toFixed(2)} m/s²`;

        // Update mini progress bars
        if (elements.meterX) elements.meterX.style.width = `${Math.min(100, Math.abs(sample.x) * 5)}%`;
        if (elements.meterY) elements.meterY.style.width = `${Math.min(100, Math.abs(sample.y) * 5)}%`;
        if (elements.meterZ) elements.meterZ.style.width = `${Math.min(100, (Math.abs(sample.z) / 20) * 100)}%`;

        // Append to rolling chart
        if (window.liveChart) {
            window.liveChart.appendReading(dynamicAccel, sample.z);
        }

        // Calibration collection mode
        if (state.isCalibrating) {
            state.calibrationBuffer.push(sample);
            return;
        }

        // Buffer in memory
        state.sampleBuffer.push(sample);
        if (state.sampleBuffer.length > state.maxBufferSize) {
            state.sampleBuffer.shift();
        }

        // Stream sample to backend detector
        try {
            const res = await fetch('/api/feed_sample', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(sample)
            });

            if (res.ok) {
                const data = await res.json();
                if (data.event_detected && data.event) {
                    onRoadImpactDetected(data.event);
                }
            }
        } catch (err) {
            // Backend offline or local network drop; silently handle
        }
    }

    function onRoadImpactDetected(event) {
        // Trigger shockwave visualizer
        if (window.shockwaveVisualizer) {
            window.shockwaveVisualizer.triggerImpact(event);
        }

        // Update shockwave details card
        const severity = (event.severity || 'LOW').toUpperCase();
        if (elements.lastEventSeverityBadge) {
            elements.lastEventSeverityBadge.innerText = severity + ' IMPACT';
            elements.lastEventSeverityBadge.className = `severity-pill badge-${severity.toLowerCase()}`;
        }
        if (elements.impactHazardType) {
            elements.impactHazardType.innerText = event.hazard_type ? event.hazard_type.toUpperCase() : 'ROAD IMPACT';
        }
        if (elements.impactJerk) {
            elements.impactJerk.innerText = `RMS: ${(event.rms || 0).toFixed(1)} | Std: ${(event.std_dev || 0).toFixed(1)}`;
        }
        if (elements.impactConfidence) {
            elements.impactConfidence.innerText = `${Math.round((event.confidence || 0.6) * 100)}% Confidence`;
        }
        if (elements.impactLocation) {
            elements.impactLocation.innerText = event.lat && event.lon ?
                `${event.lat.toFixed(5)}, ${event.lon.toFixed(5)}` : 'Unlocalized';
        }
        if (elements.impactTime) {
            const d = new Date(event.timestamp > 10000000000 ? event.timestamp : event.timestamp * 1000);
            elements.impactTime.innerText = d.toLocaleTimeString();
        }

        // Refresh hazards on Leaflet map
        if (window.hazardMap) {
            window.hazardMap.fetchAndRenderHazards();
        }

        // Update statistics cards and event audit table
        refreshDashboardData();
    }

    async function startLiveDetection() {
        const hasPermission = await requestMotionPermission();
        if (!hasPermission) return;

        state.isDetecting = true;
        setSystemStatus('Sensors Active', 'active');
        elements.startDetectionBtn.disabled = true;
        elements.stopDetectionBtn.disabled = false;

        // Check if devicemotion fires on this device
        let motionDetected = false;
        const testHandler = (e) => {
            if (e.accelerationIncludingGravity && e.accelerationIncludingGravity.z !== null) {
                motionDetected = true;
            }
            window.removeEventListener('devicemotion', testHandler);
        };
        window.addEventListener('devicemotion', testHandler);

        setTimeout(() => {
            if (!motionDetected && state.mode === 'live') {
                showNotice('No active accelerometer detected on this desktop browser. Switch to CSV Replay or Controlled Test mode, or open this page on your phone via "Phone Sync"!', 'ℹ️', 8000);
            }
        }, 1500);

        // Attach real-time motion listener
        state.deviceMotionListener = handleDeviceMotion;
        window.addEventListener('devicemotion', state.deviceMotionListener);

        // Start GPS tracking
        startGeolocation();

        showNotice('Live smartphone detection activated. Collecting 3-axis motion & GPS.', '✅', 4000);
    }

    function stopLiveDetection() {
        state.isDetecting = false;
        setSystemStatus('Standby', 'standby');
        elements.startDetectionBtn.disabled = false;
        elements.stopDetectionBtn.disabled = true;

        if (state.deviceMotionListener) {
            window.removeEventListener('devicemotion', state.deviceMotionListener);
            state.deviceMotionListener = null;
        }

        stopGeolocation();
        if (elements.samplingRateBadge) elements.samplingRateBadge.innerText = '0.0 Hz';
    }

    // ==========================================
    // CSV SENSOR REPLAY (MODE B)
    // ==========================================

    function parseCsvText(csvText) {
        const lines = csvText.trim().split('\n');
        if (lines.length < 2) return [];

        const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
        const samples = [];

        for (let i = 1; i < lines.length; i++) {
            const parts = lines[i].split(',').map(p => p.trim());
            if (parts.length < headers.length) continue;

            const row = {};
            headers.forEach((h, idx) => {
                row[h] = parseFloat(parts[idx]);
            });

            if (!isNaN(row.x) && !isNaN(row.y) && !isNaN(row.z)) {
                samples.push({
                    timestamp: row.timestamp || (Date.now() / 1000 + i * 0.02),
                    x: row.x,
                    y: row.y,
                    z: row.z,
                    lat: row.lat || 12.823050,
                    lon: row.lon || 80.044200,
                    accuracy: row.accuracy || 5.0,
                    device_id: 'csv-replayer',
                    trip_id: 'csv-trip',
                    is_synthetic: false
                });
            }
        }
        return samples;
    }

    async function loadPresetCsv(path) {
        try {
            const res = await fetch(path);
            if (!res.ok) throw new Error(`Could not load ${path}`);
            const text = await res.text();
            state.csvData = parseCsvText(text);
            state.csvReplayIndex = 0;
            updateCsvProgress();
            showNotice(`Loaded ${state.csvData.length} samples from ${path.split('/').pop()}`, '📂', 3000);
        } catch (err) {
            showNotice('Failed to load preset CSV: ' + err.message, '⚠️');
        }
    }

    function updateCsvProgress() {
        const total = state.csvData.length;
        const current = state.csvReplayIndex;
        const pct = total > 0 ? (current / total) * 100 : 0;
        if (elements.csvProgressBar) elements.csvProgressBar.style.width = `${pct}%`;
        if (elements.csvProgressText) elements.csvProgressText.innerText = `${current} / ${total}`;
    }

    function startCsvReplay() {
        if (!state.csvData || state.csvData.length === 0) {
            showNotice('Please select or upload a CSV dataset first.', '⚠️');
            return;
        }

        state.isCsvReplaying = true;
        setSystemStatus('Replaying CSV', 'active');
        elements.csvReplayToggleBtn.innerText = 'Pause Replay';
        elements.csvReplayToggleBtn.className = 'btn btn-sm btn-danger';

        // Replay tick interval (50Hz = 20ms base divided by speed)
        const intervalMs = Math.max(4, Math.floor(20 / state.csvReplaySpeed));

        state.csvReplayTimer = setInterval(() => {
            if (state.csvReplayIndex >= state.csvData.length) {
                stopCsvReplay();
                showNotice('CSV replay completed!', '✅', 4000);
                return;
            }

            const sample = state.csvData[state.csvReplayIndex];
            state.csvReplayIndex++;
            updateCsvProgress();

            // Calculate simulated frequency
            if (elements.samplingRateBadge) {
                elements.samplingRateBadge.innerText = `${(50.0 * state.csvReplaySpeed).toFixed(1)} Hz`;
            }

            // Route through standard detection pipeline
            processSensorSample(sample);
        }, intervalMs);
    }

    function stopCsvReplay() {
        state.isCsvReplaying = false;
        setSystemStatus('Standby', 'standby');
        if (elements.csvReplayToggleBtn) {
            elements.csvReplayToggleBtn.innerText = 'Start Replay';
            elements.csvReplayToggleBtn.className = 'btn btn-sm btn-primary';
        }
        if (state.csvReplayTimer) {
            clearInterval(state.csvReplayTimer);
            state.csvReplayTimer = null;
        }
    }

    // ==========================================
    // CONTROLLED TEST MODE (MODE C)
    // ==========================================

    async function injectSyntheticSignal(type) {
        showNotice(`Injecting synthetic ${type} signal...`, '🧪', 2000);

        const baseLat = 12.823050;
        const baseLon = 80.044200;
        const samples = [];
        const startTs = Date.now() / 1000.0;
        const dt = 0.02; // 50 Hz

        let durationSec = 1.0;
        if (type === 'smooth') durationSec = 2.0;
        else if (type === 'speedbreaker') durationSec = 1.5;
        else if (type === 'pothole_med') durationSec = 1.0;
        else if (type === 'pothole_high') durationSec = 1.0;

        const count = Math.floor(durationSec / dt);

        for (let i = 0; i < count; i++) {
            const t = startTs + i * dt;
            let zVal = 9.80665;
            let xVal = 0.1;
            let yVal = 0.1;

            if (type === 'smooth') {
                zVal += (Math.random() - 0.5) * 0.3;
            } else if (type === 'speedbreaker') {
                // Biphasic wave between 0.3s and 1.1s
                const relT = (i * dt) - 0.7;
                if (Math.abs(relT) < 0.4) {
                    zVal += 7.0 * Math.sin((relT / 0.4) * Math.PI * 2);
                    xVal += 1.5 * Math.cos(relT * 5);
                }
            } else if (type === 'pothole_med') {
                // Sharp jolt at 0.4s
                const relT = (i * dt) - 0.4;
                if (relT >= 0 && relT <= 0.2) {
                    zVal += 8.0 * Math.exp(-relT * 15) * Math.cos(relT * 35);
                }
            } else if (type === 'pothole_high') {
                // Severe impact at 0.3s
                const relT = (i * dt) - 0.3;
                if (relT >= 0 && relT <= 0.3) {
                    zVal += 14.5 * Math.exp(-relT * 12) * Math.cos(relT * 40);
                    xVal += 4.0 * Math.exp(-relT * 10);
                }
            }

            samples.push({
                timestamp: t,
                x: xVal,
                y: yVal,
                z: zVal,
                lat: baseLat + (Math.random() - 0.5) * 0.0008,
                lon: baseLon + (Math.random() - 0.5) * 0.0008,
                accuracy: 4.0,
                device_id: 'synthetic-generator',
                trip_id: 'test-trip-sim',
                is_synthetic: true
            });
        }

        // Stream synthetic samples sequentially to visually display on live chart and meters
        let idx = 0;
        const interval = setInterval(() => {
            if (idx >= samples.length) {
                clearInterval(interval);
                return;
            }
            processSensorSample(samples[idx]);
            idx++;
        }, 15);
    }

    // ==========================================
    // VEHICLE BASELINE CALIBRATION
    // ==========================================

    function openCalibrationModal() {
        elements.calibrationModal.classList.remove('hidden');
        elements.calibProgressBar.style.width = '0%';
        elements.calibStatusText.innerText = 'Click "Start 5s Baseline" and keep vehicle steady or cruising smoothly.';
        elements.startCalibBtn.disabled = false;
        elements.doneCalibBtn.disabled = true;
        elements.calibStatsPreview.classList.add('hidden');
    }

    function closeCalibrationModal() {
        elements.calibrationModal.classList.add('hidden');
        if (state.calibrationTimer) {
            clearInterval(state.calibrationTimer);
            state.calibrationTimer = null;
        }
        state.isCalibrating = false;
    }

    function startCalibrationRun() {
        state.isCalibrating = true;
        state.calibrationBuffer = [];
        elements.startCalibBtn.disabled = true;
        setSystemStatus('Calibrating...', 'calibrating');

        // Ensure motion listener is active during calibration
        if (!state.deviceMotionListener) {
            state.deviceMotionListener = handleDeviceMotion;
            window.addEventListener('devicemotion', state.deviceMotionListener);
        }

        let elapsedSeconds = 0;
        const totalSeconds = 5;

        state.calibrationTimer = setInterval(async () => {
            elapsedSeconds += 0.2;
            const pct = Math.min(100, (elapsedSeconds / totalSeconds) * 100);
            elements.calibProgressBar.style.width = `${pct}%`;
            elements.calibStatusText.innerText = `Recording baseline... ${elapsedSeconds.toFixed(1)}s / ${totalSeconds}s (${state.calibrationBuffer.length} samples)`;

            if (elapsedSeconds >= totalSeconds) {
                clearInterval(state.calibrationTimer);
                state.calibrationTimer = null;
                state.isCalibrating = false;

                // Send to backend calibration API
                await submitCalibrationData();
            }
        }, 200);
    }

    async function submitCalibrationData() {
        elements.calibStatusText.innerText = 'Analyzing baseline and calculating adaptive thresholds...';

        // Fallback: if browser has no motion sensors, generate synthetic calibration samples
        if (state.calibrationBuffer.length < 10) {
            for (let i = 0; i < 50; i++) {
                state.calibrationBuffer.push({
                    timestamp: Date.now() / 1000 + i * 0.02,
                    x: (Math.random() - 0.5) * 0.2,
                    y: (Math.random() - 0.5) * 0.2,
                    z: 9.80665 + (Math.random() - 0.5) * 0.3
                });
            }
        }

        try {
            const res = await fetch('/api/calibrate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    samples: state.calibrationBuffer,
                    device_id: state.deviceId
                })
            });

            if (res.ok) {
                const data = await res.json();
                const cal = data.calibration;
                elements.calibMean.innerText = `${cal.baseline_mean} m/s²`;
                elements.calibStd.innerText = `±${cal.baseline_std} m/s²`;
                elements.calibThreshLow.innerText = `${cal.threshold_low} m/s²`;
                elements.calibThreshMed.innerText = `${cal.threshold_med} m/s²`;
                elements.calibThreshHigh.innerText = `${cal.threshold_high} m/s²`;

                elements.calibStatsPreview.classList.remove('hidden');
                elements.calibStatusText.innerText = 'Baseline calibrated successfully!';
                elements.doneCalibBtn.disabled = false;
                setSystemStatus('Calibrated', 'standby');
                showNotice('Detector calibrated to vehicle baseline vibration.', '✅', 4000);
            } else {
                elements.calibStatusText.innerText = 'Calibration failed on server.';
            }
        } catch (err) {
            elements.calibStatusText.innerText = 'Network error during calibration.';
        }
    }

    // ==========================================
    // PHONE SYNC / QR MODAL
    // ==========================================

    async function openQrModal() {
        try {
            const res = await fetch('/api/health');
            if (res.ok) {
                const data = await res.json();
                const phoneUrl = data.phone_access_url || window.location.href;
                elements.phoneAccessUrl.innerText = phoneUrl;
                // Generate QR code via free public API
                elements.qrCodeImage.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(phoneUrl)}`;
            }
        } catch (e) {
            elements.phoneAccessUrl.innerText = window.location.href;
            elements.qrCodeImage.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(window.location.href)}`;
        }
        elements.qrModal.classList.remove('hidden');
    }

    function closeQrModal() {
        elements.qrModal.classList.add('hidden');
    }

    // ==========================================
    // DATA REFRESH & DASHBOARD METRICS
    // ==========================================

    async function refreshDashboardData() {
        try {
            // 1. Fetch statistics
            const statsRes = await fetch('/api/statistics');
            if (statsRes.ok) {
                const statsData = await statsRes.json();
                const stats = statsData.statistics;
                if (elements.statTotalEvents) elements.statTotalEvents.innerText = stats.total_events || 0;
                if (elements.statHighEvents) elements.statHighEvents.innerText = stats.high_severity_events || 0;
                if (elements.statMedEvents) elements.statMedEvents.innerText = stats.medium_severity_events || 0;
                if (elements.statTotalHazards) elements.statTotalHazards.innerText = stats.total_hazards || 0;
            }

            // 2. Fetch recent events table
            const eventsRes = await fetch('/api/events?limit=25');
            if (eventsRes.ok) {
                const eventsData = await eventsRes.json();
                renderEventTable(eventsData.events || []);
            }
        } catch (err) {
            console.warn('Dashboard data refresh error:', err);
        }
    }

    function renderEventTable(events) {
        if (!elements.eventTableBody) return;

        if (elements.historyCountBadge) {
            elements.historyCountBadge.innerText = `${events.length} detections`;
        }

        if (events.length === 0) {
            elements.eventTableBody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="7">No road impact events detected yet. Click "Start Detection" or run a demo scenario.</td>
                </tr>
            `;
            return;
        }

        let html = '';
        events.forEach(evt => {
            const d = new Date(evt.timestamp > 10000000000 ? evt.timestamp : evt.timestamp * 1000);
            const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const sev = (evt.severity || 'LOW').toUpperCase();
            const badgeClass = `badge-${sev.toLowerCase()}`;
            const coordsStr = (evt.latitude && evt.longitude) ?
                `${parseFloat(evt.latitude).toFixed(5)}, ${parseFloat(evt.longitude).toFixed(5)}` : 'None';
            const peak = parseFloat(evt.peak_dynamic_accel || 0).toFixed(1);
            const conf = Math.round((parseFloat(evt.confidence) || 0.6) * 100);
            const hazardType = (evt.hazard_type || 'hazard').toUpperCase();
            const isSynth = evt.is_synthetic ? ' 🧪' : '';

            html += `
                <tr>
                    <td>${timeStr}</td>
                    <td><span class="stat-badge ${badgeClass}">${sev}</span></td>
                    <td>${hazardType}${isSynth}</td>
                    <td><strong>${peak}</strong> m/s²</td>
                    <td>${conf}%</td>
                    <td>${coordsStr}</td>
                    <td>
                        ${evt.latitude && evt.longitude ? 
                            `<button class="btn btn-xs btn-outline locate-btn" data-lat="${evt.latitude}" data-lon="${evt.longitude}">Locate</button>` : 
                            `<span class="text-muted">--</span>`}
                    </td>
                </tr>
            `;
        });

        elements.eventTableBody.innerHTML = html;

        // Attach locate button click handlers
        document.querySelectorAll('.locate-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const lat = parseFloat(e.target.getAttribute('data-lat'));
                const lon = parseFloat(e.target.getAttribute('data-lon'));
                if (window.hazardMap && lat && lon) {
                    window.hazardMap.panToCoordinates(lat, lon, 18);
                }
            });
        });
    }

    async function resetAllData() {
        if (!confirm('Reset all road hazard detections, events, and statistics?')) return;

        try {
            const res = await fetch('/api/reset', { method: 'POST' });
            if (res.ok) {
                showNotice('All data has been reset to clean slate.', '🔄', 3000);
                if (window.liveChart) window.liveChart.reset();
                if (window.shockwaveVisualizer) window.shockwaveVisualizer.renderIdleGrid();
                if (window.hazardMap) window.hazardMap.fetchAndRenderHazards();
                refreshDashboardData();
            }
        } catch (err) {
            showNotice('Failed to reset data: ' + err.message, '⚠️');
        }
    }

    // ==========================================
    // MODE SWITCHING LOGIC
    // ==========================================

    function setMode(mode) {
        state.mode = mode;

        // Update button active states
        elements.modeLiveBtn.classList.toggle('active', mode === 'live');
        elements.modeCsvBtn.classList.toggle('active', mode === 'csv');
        elements.modeSyntheticBtn.classList.toggle('active', mode === 'synthetic');

        // Toggle control strips
        elements.csvControlStrip.classList.toggle('hidden', mode !== 'csv');
        elements.syntheticControlStrip.classList.toggle('hidden', mode !== 'synthetic');

        if (mode === 'csv') {
            stopLiveDetection();
            // Automatically preload the service lane pothole CSV if not already loaded
            if (state.csvData.length === 0) {
                loadPresetCsv('data/sample_pothole.csv');
            }
        } else if (mode === 'synthetic') {
            stopLiveDetection();
            stopCsvReplay();
        } else if (mode === 'live') {
            stopCsvReplay();
        }
    }

    // ==========================================
    // INITIALIZATION & EVENT LISTENERS
    // ==========================================

    function initEventListeners() {
        // Mode switchers
        elements.modeLiveBtn.addEventListener('click', () => setMode('live'));
        elements.modeCsvBtn.addEventListener('click', () => setMode('csv'));
        elements.modeSyntheticBtn.addEventListener('click', () => setMode('synthetic'));

        // Top Action buttons
        elements.startDetectionBtn.addEventListener('click', startLiveDetection);
        elements.stopDetectionBtn.addEventListener('click', stopLiveDetection);
        elements.calibrateBtn.addEventListener('click', openCalibrationModal);
        elements.qrModalBtn.addEventListener('click', openQrModal);
        elements.resetDemoBtn.addEventListener('click', resetAllData);
        elements.closeNoticeBtn.addEventListener('click', () => elements.noticeBanner.classList.add('hidden'));

        // CSV Replay controls
        elements.loadPresetCsvBtn.addEventListener('click', () => {
            const selected = elements.csvDatasetSelect.value;
            loadPresetCsv(selected);
        });

        elements.customCsvInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            elements.customFileName.innerText = file.name;
            const reader = new FileReader();
            reader.onload = (evt) => {
                state.csvData = parseCsvText(evt.target.result);
                state.csvReplayIndex = 0;
                updateCsvProgress();
                showNotice(`Loaded ${state.csvData.length} samples from ${file.name}`, '📂', 3000);
            };
            reader.readAsText(file);
        });

        elements.csvReplayToggleBtn.addEventListener('click', () => {
            if (state.isCsvReplaying) stopCsvReplay();
            else startCsvReplay();
        });

        elements.speedButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                elements.speedButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.csvReplaySpeed = parseFloat(btn.getAttribute('data-speed'));
                if (state.isCsvReplaying) {
                    stopCsvReplay();
                    startCsvReplay();
                }
            });
        });

        // Synthetic inject buttons
        elements.simSmoothBtn.addEventListener('click', () => injectSyntheticSignal('smooth'));
        elements.simSpeedBreakerBtn.addEventListener('click', () => injectSyntheticSignal('speedbreaker'));
        elements.simMedPotholeBtn.addEventListener('click', () => injectSyntheticSignal('pothole_med'));
        elements.simHighPotholeBtn.addEventListener('click', () => injectSyntheticSignal('pothole_high'));

        // Calibration Modal
        elements.closeCalibrateModalBtn.addEventListener('click', closeCalibrationModal);
        elements.startCalibBtn.addEventListener('click', startCalibrationRun);
        elements.doneCalibBtn.addEventListener('click', closeCalibrationModal);

        // QR Modal
        elements.closeQrModalBtn.addEventListener('click', closeQrModal);
        elements.copyPhoneUrlBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(elements.phoneAccessUrl.innerText).then(() => {
                elements.copyPhoneUrlBtn.innerText = 'Copied!';
                setTimeout(() => { elements.copyPhoneUrlBtn.innerText = 'Copy'; }, 2000);
            });
        });

        // Map buttons
        if (elements.mapCenterCampusBtn) {
            elements.mapCenterCampusBtn.addEventListener('click', () => {
                if (window.hazardMap) window.hazardMap.centerOnCampus();
            });
        }
        if (elements.mapCenterUserBtn) {
            elements.mapCenterUserBtn.addEventListener('click', () => {
                if (window.hazardMap) window.hazardMap.centerOnUser();
            });
        }
        if (elements.refreshMapBtn) {
            elements.refreshMapBtn.addEventListener('click', () => {
                if (window.hazardMap) window.hazardMap.fetchAndRenderHazards();
                refreshDashboardData();
            });
        }

        // Periodic background poll for data updates (every 5 seconds)
        setInterval(refreshDashboardData, 5000);
    }

    document.addEventListener('DOMContentLoaded', () => {
        initEventListeners();
        refreshDashboardData();
    });

})();
