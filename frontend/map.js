/**
 * KineticPothole - Leaflet Geospatial Road Hazard Map Engine
 * Centered on SRM Kattankulathur, Potheri Railway Station, and GST Road
 */

class HazardMapManager {
    constructor(mapContainerId) {
        this.containerId = mapContainerId;
        this.map = null;
        this.markersLayer = null;
        this.radiusLayer = null;
        this.userMarker = null;
        this.userAccuracyCircle = null;

        // Default: SRM Kattankulathur Campus & GST Road
        this.DEFAULT_CENTER = [12.823050, 80.044200];
        this.DEFAULT_ZOOM = 15;

        this.hazardsCache = [];
        this.currentSourceFilter = 'ALL';
        this.initMap();
    }

    initMap() {
        const container = document.getElementById(this.containerId);
        if (!container) return;

        // Create Leaflet map instance
        this.map = L.map(this.containerId, {
            center: this.DEFAULT_CENTER,
            zoom: this.DEFAULT_ZOOM,
            zoomControl: true,
            attributionControl: true
        });

        // Add Dark Matter / High-Contrast OpenStreetMap Carto Tiles
        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }).addTo(this.map);

        // Feature layer groups
        this.radiusLayer = L.layerGroup().addTo(this.map);
        this.markersLayer = L.layerGroup().addTo(this.map);

        // Initial fetch
        this.fetchAndRenderHazards();
    }

    createCustomMarkerIcon(severity, reportCount, fusionStatus = 'IMPACT_ONLY') {
        let colorClass = 'marker-green';
        let badgeColor = '#10b981';
        let symbol = '⚠️';

        if (fusionStatus === 'DUAL_CONFIRMED') {
            colorClass = 'marker-dual-confirmed';
            badgeColor = '#00d2ff';
            symbol = '★';
        } else if (fusionStatus === 'VISUAL_ONLY') {
            colorClass = 'marker-cctv-visual';
            badgeColor = '#3b82f6';
            symbol = '📹';
        } else {
            if (severity === 'HIGH') {
                colorClass = 'marker-red';
                badgeColor = '#ef4444';
            } else if (severity === 'MEDIUM') {
                colorClass = 'marker-amber';
                badgeColor = '#f59e0b';
            }
        }

        const countBadge = reportCount > 1 ? `<span class="marker-count">${reportCount}</span>` : '';

        const html = `
            <div class="custom-pothole-marker ${colorClass}">
                <div class="marker-pin" style="background: ${badgeColor};">
                    <span class="marker-icon-symbol">${symbol}</span>
                    ${countBadge}
                </div>
                <div class="marker-shadow"></div>
            </div>
        `;

        return L.divIcon({
            className: 'custom-leaflet-div-icon',
            html: html,
            iconSize: [32, 42],
            iconAnchor: [16, 42],
            popupAnchor: [0, -40]
        });
    }

    formatTimestamp(ts) {
        if (!ts) return '--';
        const d = new Date(ts > 10000000000 ? ts : ts * 1000);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    setSourceFilter(sourceType) {
        this.currentSourceFilter = sourceType || 'ALL';
        this.renderHazards(this.hazardsCache);
    }

    renderHazards(hazards) {
        if (!this.map) return;
        this.hazardsCache = hazards || [];

        this.markersLayer.clearLayers();
        this.radiusLayer.clearLayers();

        // Apply source filtering
        let displayList = this.hazardsCache;
        if (this.currentSourceFilter === 'DUAL_CONFIRMED') {
            displayList = displayList.filter(h => h.fusion_status === 'DUAL_CONFIRMED');
        } else if (this.currentSourceFilter === 'IMPACT_ONLY') {
            displayList = displayList.filter(h => h.fusion_status === 'IMPACT_ONLY' || (!h.fusion_status && (h.cctv_detections_count || 0) === 0));
        } else if (this.currentSourceFilter === 'VISUAL_ONLY') {
            displayList = displayList.filter(h => h.fusion_status === 'VISUAL_ONLY' || ((h.cctv_detections_count || 0) > 0 && (!h.report_count || h.report_count === 0)));
        }

        displayList.forEach(hazard => {
            const lat = parseFloat(hazard.latitude);
            const lon = parseFloat(hazard.longitude);
            if (isNaN(lat) || isNaN(lon)) return;

            const severity = (hazard.severity || 'LOW').toUpperCase();
            const reportCount = parseInt(hazard.report_count || 1);
            const uniqueDevices = parseInt(hazard.unique_devices_count || 1);
            const maxPeak = parseFloat(hazard.max_peak_accel || 0).toFixed(1);
            const avgPeak = parseFloat(hazard.avg_peak_accel || 0).toFixed(1);
            const confidencePct = Math.round((parseFloat(hazard.confidence_score) || 0.6) * 100);
            const lastReportedStr = this.formatTimestamp(hazard.last_reported);
            const hazardType = hazard.hazard_type || 'Suspected Road Hazard';
            const fusionStatus = hazard.fusion_status || (hazard.cctv_detections_count > 0 && hazard.report_count > 0 ? 'DUAL_CONFIRMED' : 'IMPACT_ONLY');

            // 1. Draw 20-meter grouping cluster radius
            let radiusColor = '#10b981';
            if (fusionStatus === 'DUAL_CONFIRMED') radiusColor = '#00d2ff';
            else if (fusionStatus === 'VISUAL_ONLY') radiusColor = '#3b82f6';
            else if (severity === 'HIGH') radiusColor = '#ef4444';
            else if (severity === 'MEDIUM') radiusColor = '#f59e0b';

            const circle = L.circle([lat, lon], {
                radius: hazard.radius_meters || 20,
                color: radiusColor,
                weight: fusionStatus === 'DUAL_CONFIRMED' ? 2.5 : 1.5,
                fillColor: radiusColor,
                fillOpacity: fusionStatus === 'DUAL_CONFIRMED' ? 0.22 : 0.12,
                dashArray: fusionStatus === 'DUAL_CONFIRMED' ? '4, 4' : '3, 4'
            });
            this.radiusLayer.addLayer(circle);

            // 2. Marker Pin
            const icon = this.createCustomMarkerIcon(severity, reportCount, fusionStatus);
            const marker = L.marker([lat, lon], { icon: icon });

            // CCTV Image Thumbnail in Popup
            const cctvThumbHtml = hazard.last_cctv_image ? `
                <div class="p-row">
                    <span>CCTV Defect Snapshot:</span>
                </div>
                <img src="/api/cctv/frames/${hazard.last_cctv_image}" class="popup-cctv-thumb" alt="CCTV Defect Snapshot">
            ` : '';

            // Fusion Details in Popup
            const fusionBadgeHtml = fusionStatus === 'DUAL_CONFIRMED' ? `
                <div class="p-row" style="background: rgba(0,210,255,0.12); padding: 4px 6px; border-radius: 4px; margin-bottom: 6px;">
                    <span style="color:#00d2ff; font-weight:800;">⚡ MULTI-MODAL FUSION:</span>
                    <strong style="color:#00d2ff;">DUAL CONFIRMED</strong>
                </div>
                <div class="p-row">
                    <span>Visual Evidence (CCTV):</span>
                    <span>${Math.round((hazard.visual_evidence_score || 0.8) * 100)}%</span>
                </div>
                <div class="p-row">
                    <span>Physical Impact (Phone):</span>
                    <span>${Math.round((hazard.smartphone_evidence_score || 0.75) * 100)}%</span>
                </div>
            ` : '';

            // Popup content
            const popupHtml = `
                <div class="map-popup-card">
                    <div class="popup-header">
                        <span class="popup-title">${hazardType.toUpperCase()}</span>
                        <span class="popup-severity badge-${severity.toLowerCase()}">${severity}</span>
                    </div>
                    <div class="popup-body">
                        ${fusionBadgeHtml}
                        ${cctvThumbHtml}
                        <div class="p-row">
                            <span>Max Dynamic Impact:</span>
                            <strong>${maxPeak} m/s²</strong>
                        </div>
                        <div class="p-row">
                            <span>Avg Dynamic Impact:</span>
                            <span>${avgPeak} m/s²</span>
                        </div>
                        <div class="p-row">
                            <span>Total Reports:</span>
                            <strong>${reportCount} pass${reportCount > 1 ? 'es' : ''}</strong>
                        </div>
                        <div class="p-row">
                            <span>Unique Devices:</span>
                            <span>${uniqueDevices} ${uniqueDevices > 1 ? '(Multi-device verified)' : '(Single device)'}</span>
                        </div>
                        <div class="p-row">
                            <span>Confidence:</span>
                            <div class="conf-bar-wrap">
                                <div class="conf-bar-fill" style="width: ${confidencePct}%;"></div>
                                <span class="conf-text">${confidencePct}%</span>
                            </div>
                        </div>
                        <div class="p-row">
                            <span>Last Recorded:</span>
                            <span>${lastReportedStr}</span>
                        </div>
                        <div class="popup-source-tag ${hazard.is_synthetic ? 'badge-simulated' : 'badge-live'}">
                            ${hazard.is_synthetic ? '🧪 Source: Simulated Demo Replay (Test GPS)' : '📱 Source: Live Smartphone Sensor'}
                        </div>
                        <div class="p-coords">
                            ${lat.toFixed(6)}, ${lon.toFixed(6)}
                        </div>
                    </div>
                </div>
            `;

            marker.bindPopup(popupHtml);
            this.markersLayer.addLayer(marker);
        });
    }

    async fetchAndRenderHazards() {
        try {
            const res = await fetch('/api/hazards');
            if (!res.ok) return;
            const data = await res.json();
            if (data && data.hazards) {
                this.renderHazards(data.hazards);
            }
        } catch (e) {
            console.warn('Could not fetch hazard data from backend:', e);
        }
    }

    updateUserPosition(lat, lon, accuracy = 5) {
        if (!this.map) return;

        const coords = [lat, lon];

        if (!this.userMarker) {
            // Create user pulsing marker
            const userIcon = L.divIcon({
                className: 'user-location-marker',
                html: `<div class="user-pulse-beacon"></div>`,
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });

            this.userMarker = L.marker(coords, { icon: userIcon, zIndexOffset: 1000 }).addTo(this.map);
            this.userAccuracyCircle = L.circle(coords, {
                radius: accuracy,
                color: '#00d2ff',
                weight: 1,
                fillColor: '#00d2ff',
                fillOpacity: 0.12
            }).addTo(this.map);
        } else {
            this.userMarker.setLatLng(coords);
            this.userAccuracyCircle.setLatLng(coords);
            this.userAccuracyCircle.setRadius(accuracy);
        }
    }

    centerOnCampus() {
        if (this.map) {
            this.map.setView(this.DEFAULT_CENTER, this.DEFAULT_ZOOM);
        }
    }

    centerOnUser() {
        if (this.map && this.userMarker) {
            this.map.setView(this.userMarker.getLatLng(), 17);
        } else if (this.map) {
            this.centerOnCampus();
        }
    }

    panToCoordinates(lat, lon, zoom = 17) {
        if (this.map && lat && lon) {
            this.map.setView([lat, lon], zoom, { animate: true });
        }
    }

    invalidateSize() {
        if (this.map) {
            setTimeout(() => {
                this.map.invalidateSize();
            }, 100);
        }
    }
}

// Global instance
window.hazardMap = null;

document.addEventListener('DOMContentLoaded', () => {
    window.hazardMap = new HazardMapManager('hazardMap');
});
