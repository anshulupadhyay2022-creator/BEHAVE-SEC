document.addEventListener('DOMContentLoaded', () => {
    const userId = localStorage.getItem('userId');
    const token = localStorage.getItem('token');
    if (!userId || !token) {
        window.location.href = 'login.html';
        return;
    }

    // 1. Initialize Tracker
    const tracker = new BehaviorTracker({
        userId: userId,
        endpoint: `${window.BEHAVE_CONFIG ? window.BEHAVE_CONFIG.API_BASE_URL : API_BASE_URL}/collect-data`
    });

    // Make tracker available for games
    window.tracker = tracker;

    // Live Graph Logic (Mockup for now, can use Chart.js if imported)
    window.onBehaviorEvent = (data) => {
        updateStats(data);
    };

    // 2. Initialize Games
    initTypingChallenge();
    initReactionGame();
    initQuiz();
    initNotes();
    startSessionTimer();
    initLiveChart();
    initWebSocket(userId, token);
});

function initWebSocket(userId, token) {
    const wsUrl = window.BEHAVE_CONFIG ? window.BEHAVE_CONFIG.WS_BASE_URL : 'ws://localhost:8000';
    const ws = new WebSocket(`${wsUrl}/ws/dashboard?token=${token}`);
    
    ws.onopen = () => {
        console.log("WebSocket connected.");
        ws.send(JSON.stringify({ type: "init", userId: userId }));
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        console.log("WS Data:", msg);

        if (msg.type === "new_session") {
            const riskLabel = document.getElementById("risk-score");
            const anomalyLabel = document.getElementById("anomaly-label");

            if (riskLabel && anomalyLabel) {
                riskLabel.innerText = msg.riskScore + "/100";
                
                if (msg.anomalyLabel === "anomaly") {
                    anomalyLabel.innerText = "DETECTED";
                    anomalyLabel.style.color = "var(--error)";
                    riskLabel.style.color = "var(--error)";
                } else {
                    anomalyLabel.innerText = "Normal";
                    anomalyLabel.style.color = "var(--success)";
                    riskLabel.style.color = "var(--success)";
                }
            }
        } else if (msg.type === "force_logout") {
            alert("SECURITY ALERT: " + msg.reason);
            localStorage.removeItem("token"); // Invalidates current token
            localStorage.setItem("mfaEmail", localStorage.getItem("userEmail"));
            window.location.href = "mfa.html";
        }
    };

    ws.onerror = (error) => console.error("WebSocket Error:", error);
    ws.onclose = () => console.log("WebSocket disconnected.");
}

// --- LIVE CHART LOGIC ---
// Helper to get CSS variable value
function getThemeColor(varName) {
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
}

function initLiveChart() {
    const ctx = document.getElementById('behaviorChart').getContext('2d');

    // Initial colors
    const gridColor = getThemeColor('--chart-grid');
    const axisColor = getThemeColor('--chart-axis');

    const behaviorChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Events per Second',
                data: [],
                borderColor: '#f43334', // Redlight Red
                backgroundColor: 'rgba(244, 51, 52, 0.1)',
                tension: 0.4,
                borderWidth: 2,
                pointBackgroundColor: '#f43334',
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: gridColor },
                    ticks: { color: axisColor }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: axisColor }
                }
            },
            plugins: { legend: { display: false } },
            animation: false // Performance optimization
        }
    });

    // Listen for theme changes
    window.addEventListener('themeChanged', () => {
        const newGrid = getThemeColor('--chart-grid');
        const newAxis = getThemeColor('--chart-axis');

        behaviorChart.options.scales.y.grid.color = newGrid;
        behaviorChart.options.scales.y.ticks.color = newAxis;
        behaviorChart.options.scales.x.ticks.color = newAxis;
        behaviorChart.update();
    });

    // Update Chart every second
    let eventCounter = 0;

    // Hook into the Stats update to count events
    const originalUpdateStats = updateStats;
    updateStats = function (data) {
        originalUpdateStats(data);
        eventCounter++;
    }

    setInterval(() => {
        const now = new Date();
        const timeLabel = now.getHours() + ':' + now.getMinutes() + ':' + now.getSeconds();

        behaviorChart.data.labels.push(timeLabel);
        behaviorChart.data.datasets[0].data.push(eventCounter);

        if (behaviorChart.data.labels.length > 20) {
            behaviorChart.data.labels.shift();
            behaviorChart.data.datasets[0].data.shift();
        }
        behaviorChart.update();
        eventCounter = 0; // Reset for next second
    }, 1000);
}

// --- STATS LOGIC ---
let keyPressCount = 0;
let mouseMoveCount = 0;
let clickCount = 0;

function updateStats(data) {
    if (data.eventType === 'keydown') keyPressCount++;
    if (data.eventType === 'mousemove') mouseMoveCount++;
    if (data.eventType === 'click') clickCount++;

    // Update UI if elements exist
    document.getElementById('kp-stat').innerText = keyPressCount;
    document.getElementById('mm-stat').innerText = mouseMoveCount;
    document.getElementById('cl-stat').innerText = clickCount;
}

function startSessionTimer() {
    let seconds = 0;
    setInterval(() => {
        seconds++;
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        document.getElementById('session-timer').innerText =
            `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }, 1000);
}


// --- TYPING CHALLENGE ---
const paragraphs = [
    "Security is not a product, but a process. It requires continuous monitoring and adaptation.",
    "The only truly secure system is one that is powered off, cast in a block of concrete and sealed in a lead-lined room.",
    "Data privacy is a fundamental human right in the digital age. We must protect it at all costs."
];

function initTypingChallenge() {
    const textDisplay = document.getElementById('typing-text');
    const inputArea = document.getElementById('typing-input');
    const resultDisplay = document.getElementById('typing-result');

    // Select random text
    const targetText = paragraphs[Math.floor(Math.random() * paragraphs.length)];
    textDisplay.innerText = targetText;

    let startTime = null;

    inputArea.addEventListener('focus', () => {
        if (!startTime) startTime = Date.now();
        window.tracker.logGameEvent('start', 'typingChallenge', { text: targetText });
    });

    inputArea.addEventListener('input', () => {
        const typed = inputArea.value;
        if (typed === targetText) {
            const endTime = Date.now();
            const timeTaken = (endTime - startTime) / 1000; // seconds
            const wpm = Math.round((targetText.split(' ').length / timeTaken) * 60);

            resultDisplay.innerText = `Complete! WPM: ${wpm}, Time: ${timeTaken.toFixed(1)}s`;
            resultDisplay.classList.add('success');

            window.tracker.logGameEvent('complete', 'typingChallenge', {
                wpm: wpm,
                time: timeTaken,
                accuracy: 100 // Simplified
            });
            inputArea.disabled = true;
        }
    });
}


// --- REACTION GAME ---
function initReactionGame() {
    const gameArea = document.getElementById('reaction-area');
    const statusText = document.getElementById('reaction-status');
    let gameState = 'waiting'; // waiting, ready, finished
    let showTime = 0;

    gameArea.addEventListener('click', () => {
        if (gameState === 'waiting') {
            statusText.innerText = "Wait for green...";
            gameArea.style.backgroundColor = '#ff6b35'; // Waiting color
            gameState = 'ready';

            const delay = 2000 + Math.random() * 3000; // 2-5 sec
            setTimeout(() => {
                if (gameState === 'ready') {
                    gameArea.style.backgroundColor = '#00ff88'; // Go color
                    statusText.innerText = "CLICK NOW!";
                    showTime = Date.now();
                    gameState = 'go';
                }
            }, delay);

        } else if (gameState === 'go') {
            const reactionTime = Date.now() - showTime;
            statusText.innerText = `${reactionTime}ms`;
            gameArea.style.backgroundColor = '#0a0e27'; // Reset
            gameState = 'waiting';

            window.tracker.logGameEvent('reaction', 'reactionGame', { reactionTime: reactionTime });

        } else if (gameState === 'ready') {
            statusText.innerText = "Too early! Try again.";
            gameArea.style.backgroundColor = '#0a0e27';
            gameState = 'waiting';
            window.tracker.logGameEvent('fail', 'reactionGame', { reason: 'early_click' });
        }
    });
}

// --- QUIZ MODULE ---
function initQuiz() {
    // Simplified quiz logic
    const options = document.querySelectorAll('.quiz-option');
    options.forEach(opt => {
        opt.addEventListener('click', function () {
            // Visual feedback
            options.forEach(o => o.classList.remove('selected'));
            this.classList.add('selected');

            const answer = this.dataset.value;
            window.tracker.logGameEvent('answer', 'quiz', {
                question: '1', // Hardcoded for demo
                answer: answer
            });
        });
    });
}

// --- SECURE NOTES ---
function initNotes() {
    const notesArea = document.getElementById('secure-notes');
    const saveBtn = document.getElementById('save-notes');

    // Auto-save simulation
    setInterval(() => {
        if (notesArea.value.length > 0) {
            // Don't actually send content for privacy, just metadata
            window.tracker.logGameEvent('autosave', 'notes', { length: notesArea.value.length });
            console.log('Notes autosaved (metadata only)');
        }
    }, 10000);

    saveBtn.addEventListener('click', () => {
        window.tracker.logGameEvent('manual_save', 'notes', { length: notesArea.value.length });
        alert('Notes saved securely!');
    });
}
