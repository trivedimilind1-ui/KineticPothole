/**
 * KineticPothole - Charts and Shockwave Visualization Engine
 */

class ShockwaveVisualizer {
    constructor(canvasId, overlayRingId, peakTextId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.ring = document.getElementById(overlayRingId);
        this.peakText = document.getElementById(peakTextId);
        this.waveformHistory = [];
        this.maxWaveformPoints = 60;
        this.init();
    }

    init() {
        if (!this.canvas || !this.ctx) return;
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.renderIdleGrid();
    }

    resize() {
        if (!this.canvas) return;
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width * (window.devicePixelRatio || 1);
        this.canvas.height = rect.height * (window.devicePixelRatio || 1);
        if (this.ctx) {
            this.ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
        }
        this.drawWaveform();
    }

    renderIdleGrid() {
        if (!this.ctx) return;
        const w = this.canvas.clientWidth;
        const h = this.canvas.clientHeight;

        this.ctx.clearRect(0, 0, w, h);
        
        // Draw grid lines
        this.ctx.strokeStyle = '#142038';
        this.ctx.lineWidth = 1;
        this.ctx.beginPath();
        for (let x = 0; x < w; x += 30) {
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, h);
        }
        for (let y = 0; y < h; y += 25) {
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(w, y);
        }
        this.ctx.stroke();

        // Baseline zero line
        this.ctx.strokeStyle = '#1e335a';
        this.ctx.lineWidth = 1.5;
        this.ctx.beginPath();
        this.ctx.moveTo(0, h / 2);
        this.ctx.lineTo(w, h / 2);
        this.ctx.stroke();
    }

    triggerImpact(eventData) {
        const peak = parseFloat(eventData.peak_dynamic_accel || 0);
        const severity = (eventData.severity || 'LOW').toUpperCase();

        // Trigger ring CSS pulse
        if (this.ring) {
            this.ring.classList.remove('pulse-anim');
            void this.ring.offsetWidth; // Force reflow
            if (severity === 'HIGH') {
                this.ring.style.borderColor = '#ef4444';
            } else if (severity === 'MEDIUM') {
                this.ring.style.borderColor = '#f59e0b';
            } else {
                this.ring.style.borderColor = '#10b981';
            }
            this.ring.classList.add('pulse-anim');
        }

        // Update center peak display
        if (this.peakText) {
            this.peakText.innerText = peak.toFixed(1);
            if (severity === 'HIGH') {
                this.peakText.style.color = '#ef4444';
            } else if (severity === 'MEDIUM') {
                this.peakText.style.color = '#f59e0b';
            } else {
                this.peakText.style.color = '#10b981';
            }
        }

        // Store waveform slice
        if (Array.isArray(eventData.waveform) && eventData.waveform.length > 0) {
            this.waveformHistory = eventData.waveform;
        } else {
            // Generate synthetic waveform preview from peak
            this.waveformHistory = this.generateImpactWaveform(peak);
        }
        this.drawWaveform(severity);
    }

    generateImpactWaveform(peak) {
        const points = [];
        const total = 40;
        for (let i = 0; i < total; i++) {
            const t = (i - 15) / 5;
            const val = peak * Math.exp(-0.5 * t * t) * Math.cos(t * 3);
            points.push(Math.abs(val));
        }
        return points;
    }

    drawWaveform(severity = 'MEDIUM') {
        if (!this.ctx) return;
        const w = this.canvas.clientWidth;
        const h = this.canvas.clientHeight;

        this.renderIdleGrid();

        if (!this.waveformHistory || this.waveformHistory.length === 0) return;

        const maxVal = Math.max(...this.waveformHistory, 12);
        const step = w / (this.waveformHistory.length - 1 || 1);
        const midY = h * 0.85;

        // Waveform path
        this.ctx.beginPath();
        for (let i = 0; i < this.waveformHistory.length; i++) {
            const x = i * step;
            const y = midY - (this.waveformHistory[i] / maxVal) * (h * 0.7);
            if (i === 0) this.ctx.moveTo(x, y);
            else this.ctx.lineTo(x, y);
        }

        // Color based on severity
        let strokeColor = '#00d2ff';
        let fillColor = 'rgba(0, 210, 255, 0.15)';
        if (severity === 'HIGH') {
            strokeColor = '#ef4444';
            fillColor = 'rgba(239, 68, 68, 0.2)';
        } else if (severity === 'MEDIUM') {
            strokeColor = '#f59e0b';
            fillColor = 'rgba(245, 158, 11, 0.2)';
        }

        this.ctx.strokeStyle = strokeColor;
        this.ctx.lineWidth = 2.5;
        this.ctx.shadowColor = strokeColor;
        this.ctx.shadowBlur = 8;
        this.ctx.stroke();

        // Area fill under wave
        this.ctx.lineTo(w, midY);
        this.ctx.lineTo(0, midY);
        this.ctx.closePath();
        this.ctx.fillStyle = fillColor;
        this.ctx.fill();

        this.ctx.shadowBlur = 0;
    }
}


class LiveTelemetryChart {
    constructor(canvasId) {
        this.canvasId = canvasId;
        this.chart = null;
        this.maxDataPoints = 120; // ~30-40 seconds of rolling stream
        this.init();
    }

    init() {
        const ctx = document.getElementById(this.canvasId);
        if (!ctx) return;

        const labels = Array.from({ length: this.maxDataPoints }, () => '');

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Dynamic Accel (m/s²)',
                        data: Array(this.maxDataPoints).fill(0),
                        borderColor: '#00d2ff',
                        backgroundColor: 'rgba(0, 210, 255, 0.12)',
                        borderWidth: 2,
                        tension: 0.25,
                        fill: true,
                        pointRadius: 0
                    },
                    {
                        label: 'Z-Axis (m/s²)',
                        data: Array(this.maxDataPoints).fill(9.81),
                        borderColor: '#94a3b8',
                        borderWidth: 1,
                        borderDash: [3, 3],
                        pointRadius: 0,
                        fill: false
                    },
                    {
                        label: 'High Thresh (11.5)',
                        data: Array(this.maxDataPoints).fill(11.5),
                        borderColor: 'rgba(239, 68, 68, 0.65)',
                        borderWidth: 1,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                },
                scales: {
                    x: {
                        display: false
                    },
                    y: {
                        min: 0,
                        max: 20,
                        grid: {
                            color: '#162238'
                        },
                        ticks: {
                            color: '#64748b',
                            font: { family: 'JetBrains Mono', size: 10 },
                            stepSize: 5
                        }
                    }
                }
            }
        });
    }

    appendReading(dynamicAccel, zVal) {
        if (!this.chart) return;

        const datasets = this.chart.data.datasets;
        
        // Push new points
        datasets[0].data.push(dynamicAccel);
        datasets[1].data.push(zVal);

        // Shift old points
        if (datasets[0].data.length > this.maxDataPoints) {
            datasets[0].data.shift();
            datasets[1].data.shift();
        }

        this.chart.update('none');
    }

    reset() {
        if (!this.chart) return;
        this.chart.data.datasets[0].data = Array(this.maxDataPoints).fill(0);
        this.chart.data.datasets[1].data = Array(this.maxDataPoints).fill(9.81);
        this.chart.update('none');
    }
}

// Global visualizer instances
window.shockwaveVisualizer = null;
window.liveChart = null;

document.addEventListener('DOMContentLoaded', () => {
    window.shockwaveVisualizer = new ShockwaveVisualizer(
        'shockwaveCanvas',
        'shockwaveRing',
        'impactPeakText'
    );
    window.liveChart = new LiveTelemetryChart('liveChart');
});
