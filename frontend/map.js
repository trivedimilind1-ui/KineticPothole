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

    createCustomMarkerIcon(severity, reportCount) {
        let colorClass = 'marker-green';
        let badgeColor = '#10b981';

        if (severity === 'HIGH') {
            colorClass = 'marker-red';
            badgeColor = '#ef4444';
        } else if (severity === 'MEDIUM') {
            colorClass = 'marker-amber';
            badgeColor = '#f59e0b';
        }

        const countBadge = reportCount > 1 ? `<span class="marker-count">${reportCount}</span>` : '';

        const html = `
            <div class="custom-pothole-marker ${colorClass}">
                <div class="marker-pin" style="background: ${badgeColor};">
                    <span class="marker-icon-symbol">⚠️</span>
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

    renderHazards(hazards) {
        if (!this.map) return;
        this.hazardsCache = hazards || [];

        this.markersLayer.clearLayers();
        this.radiusLayer.clearLayers();

        hazards.forEach(hazard => {
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

            // 1. Draw 20-meter grouping cluster radius
            let radiusColor = '#10b981';
            if (severity === 'HIGH') radiusColor = '#ef4444';
            else if (severity === 'MEDIUM') radiusColor = '#f59e0b';

            const circle = L.circle([lat, lon], {
                radius: hazard.radius_meters || 20,
                color: radiusColor,
                weight: 1.5,
                fillColor: radiusColor,
                fillOpacity: 0.12,
                dashArray: '3, 4'
            });
            this.radiusLayer.addLayer(circle);

            // 2. Marker Pin
            const icon = this.createCustomMarkerIcon(severity, reportCount);
            const marker = L.marker([lat, lon], { icon: icon });

            // Popup content
            const popupHtml = `
                <div class="map-popup-card">
                    <div class="popup-header">
                        <span class="popup-title">${hazardType.toUpperCase()}</span>
                        <span class="popup-severity badge-${severity.toLowerCase()}">${severity}</span>
                    </div>
                    <div class="popup-body">
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
