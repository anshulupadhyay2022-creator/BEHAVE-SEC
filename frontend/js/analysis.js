document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch(`${window.BEHAVE_CONFIG ? window.BEHAVE_CONFIG.API_BASE_URL : API_BASE_URL}/stats`);
        const data = await response.json();
        
        // Update summary cards
        document.getElementById('stat-sessions').innerText = data.totalSessions || 0;
        document.getElementById('stat-events').innerText = data.totalEvents || 0;
        
        const sessions = data.sessions || [];
        const anomalyCount = sessions.filter(s => s.anomaly && s.anomaly.label === 'anomaly').length;
        document.getElementById('stat-anomalies').innerText = anomalyCount;
        
        const statusEl = document.getElementById('stat-status');
        if (anomalyCount > 0) {
            statusEl.innerText = "Risk Detected";
            statusEl.style.color = "var(--danger)";
        } else {
            statusEl.innerText = "Normal";
            statusEl.style.color = "var(--success)";
        }
        
        initRealCharts(sessions);
        populateRealTable(sessions);
        initExportConfig(data);
    } catch (e) {
        console.error("Failed to fetch stats from backend:", e);
        document.getElementById('stat-status').innerText = "Offline";
        document.getElementById('stat-status').style.color = "var(--text-secondary)";
        
        // Fallback to empty state
        initRealCharts([]);
        populateRealTable([]);
    }
});

// Helper to get CSS variable value
function getThemeColor(varName) {
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
}

function initRealCharts(sessions) {
    // Initial colors
    const gridColor = getThemeColor('--chart-grid');
    const axisColor = getThemeColor('--chart-axis');
    const textColor = getThemeColor('--chart-text');
    const primaryColor = getThemeColor('--chart-primary');
    const primaryBg = getThemeColor('--chart-primary-bg');

    // 1. Keystroke Dynamics (Scatter Plot) - Visual Mockup
    // (We don't send thousands of keystroke floats over /stats for performance)
    const ctxKey = document.getElementById('keystrokeChart').getContext('2d');
    const keyData = generateMockKeystrokeData();

    const keystrokeChart = new Chart(ctxKey, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Flight Time vs Dwell Time (ms)',
                data: keyData,
                backgroundColor: '#f43334', // Redlight Red
                borderColor: '#f43334',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: { display: true, text: 'Dwell Time (ms)', color: axisColor },
                    grid: { color: gridColor },
                    ticks: { color: axisColor }
                },
                y: {
                    title: { display: true, text: 'Flight Time (ms)', color: axisColor },
                    grid: { color: gridColor },
                    ticks: { color: axisColor }
                }
            },
            plugins: {
                legend: { labels: { color: textColor } }
            }
        }
    });

    // 2. Mouse Movement - Visual Mockup
    const ctxMouse = document.getElementById('mouseRadarChart').getContext('2d');
    const mouseRadarChart = new Chart(ctxMouse, {
        type: 'radar',
        data: {
            labels: ['Velocity', 'Acceleration', 'Clicks', 'Curvature', 'Pauses'],
            datasets: [{
                label: 'Current Session',
                data: [85, 70, 60, 40, 90],
                backgroundColor: primaryBg,
                borderColor: primaryColor,
                borderWidth: 2
            }, {
                label: 'Average Profile',
                data: [60, 60, 50, 50, 60],
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                borderColor: axisColor,
                borderWidth: 1,
                borderDash: [5, 5]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: { color: gridColor },
                    grid: { color: gridColor },
                    pointLabels: { color: textColor },
                    ticks: { backdropColor: 'transparent', color: axisColor }
                }
            },
            plugins: {
                legend: { labels: { color: textColor } }
            }
        }
    });

    // 3. User Risk Trend (Line) - Real Backend Data
    // We plot the Anomaly Score for the last 15 sessions
    const ctxRisk = document.getElementById('riskTrendChart').getContext('2d');
    const recentSessions = sessions.slice().reverse().slice(0, 15).reverse();
    
    let labels = recentSessions.map(s => {
        if (!s.timestamp) return "Unknown";
        return new Date(s.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    
    // Anomaly score (0.0 to 1.0)
    let dataPoints = recentSessions.map(s => s.anomaly && s.anomaly.score != null ? s.anomaly.score : 0);

    if (labels.length === 0) {
        labels = ['-'];
        dataPoints = [0];
    }

    const riskTrendChart = new Chart(ctxRisk, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Anomaly Score (0.0 - 1.0)',
                data: dataPoints,
                borderColor: '#f43334',
                backgroundColor: 'rgba(244, 51, 52, 0.2)',
                pointBackgroundColor: '#f43334',
                fill: true,
                tension: 0.2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1.0,
                    grid: { color: gridColor },
                    ticks: { color: axisColor }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: axisColor }
                }
            },
            plugins: {
                legend: { display: true, labels: { color: textColor } }
            }
        }
    });

    // Listen for theme changes
    window.addEventListener('themeChanged', () => {
        const newGrid = getThemeColor('--chart-grid');
        const newAxis = getThemeColor('--chart-axis');
        const newText = getThemeColor('--chart-text');
        const newPrimary = getThemeColor('--chart-primary');
        const newPrimaryBg = getThemeColor('--chart-primary-bg');

        // Update Keystroke Chart
        keystrokeChart.options.scales.x.grid.color = newGrid;
        keystrokeChart.options.scales.x.ticks.color = newAxis;
        keystrokeChart.options.scales.x.title.color = newAxis;
        keystrokeChart.options.scales.y.grid.color = newGrid;
        keystrokeChart.options.scales.y.ticks.color = newAxis;
        keystrokeChart.options.scales.y.title.color = newAxis;
        keystrokeChart.options.plugins.legend.labels.color = newText;
        keystrokeChart.update();

        // Update Mouse Radar Chart
        mouseRadarChart.options.scales.r.angleLines.color = newGrid;
        mouseRadarChart.options.scales.r.grid.color = newGrid;
        mouseRadarChart.options.scales.r.pointLabels.color = newText;
        mouseRadarChart.options.scales.r.ticks.color = newAxis;
        mouseRadarChart.data.datasets[0].borderColor = newPrimary;
        mouseRadarChart.data.datasets[0].backgroundColor = newPrimaryBg;
        mouseRadarChart.data.datasets[1].borderColor = newAxis;
        mouseRadarChart.options.plugins.legend.labels.color = newText;
        mouseRadarChart.update();

        // Update Risk Trend Chart
        riskTrendChart.options.scales.y.grid.color = newGrid;
        riskTrendChart.options.scales.y.ticks.color = newAxis;
        riskTrendChart.options.scales.x.ticks.color = newAxis;
        riskTrendChart.options.plugins.legend.labels.color = newText;
        riskTrendChart.update();
    });
}

function generateMockKeystrokeData() {
    const data = [];
    for (let i = 0; i < 50; i++) {
        data.push({
            x: 50 + Math.random() * 100,
            y: 20 + Math.random() * 200
        });
    }
    return data;
}

function populateRealTable(sessions) {
    const tableBody = document.getElementById('session-table-body');
    tableBody.innerHTML = ''; // Clear existing

    if (!sessions || sessions.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center">No session data found in backend yet.</td></tr>';
        return;
    }

    // Show newest first
    const sortedSessions = sessions.slice().reverse();

    sortedSessions.forEach(session => {
        const row = document.createElement('tr');
        
        const isAnomaly = session.anomaly && session.anomaly.label === 'anomaly';
        const isPending = session.anomaly && session.anomaly.label === 'pending';
        
        let badgeClass = 'status-safe';
        let statusText = 'Normal';
        
        if (isAnomaly) {
            badgeClass = 'status-risk';
            statusText = 'Anomaly';
        } else if (isPending) {
            badgeClass = '';
            statusText = 'Training...';
        }

        const startTime = session.timestamp ? new Date(session.timestamp).toLocaleString() : 'N/A';
        const duration = 'N/A'; // Backend /stats doesn't serve duration right now

        const scoreText = session.anomaly && session.anomaly.score != null ? session.anomaly.score.toFixed(3) : 'N/A';
        const alertMsg = `Details:\\nUser ID: ${session.userId}\\nScore: ${scoreText}\\nLabel: ${session.anomaly ? session.anomaly.label : 'N/A'}`;

        row.innerHTML = `
            <td>${session.sessionId ? session.sessionId.substring(0, 8) : 'Unknown'}...</td>
            <td>${startTime}</td>
            <td>${duration}</td>
            <td>${session.eventCount || 0}</td>
            <td><span class="status-badge ${badgeClass}">${statusText}</span></td>
            <td><button class="logout-btn" style="padding:0.2rem 0.5rem; font-size:0.8rem" onclick="alert('${alertMsg}')">Details</button></td>
        `;
        tableBody.appendChild(row);
    });
}

function initExportConfig(backendData) {
    const exportBtn = document.querySelector('.logout-btn[style*="border-color"]'); // The export reported button
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(backendData, null, 2));
            const downloadAnchorNode = document.createElement('a');
            downloadAnchorNode.setAttribute("href", dataStr);
            downloadAnchorNode.setAttribute("download", "behave_sec_backend_report.json");
            document.body.appendChild(downloadAnchorNode); // required for firefox
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
        });
    }
}
