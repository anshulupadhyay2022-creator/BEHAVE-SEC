// ========================================
// BEHAVIORAL DATA TRACKING SYSTEM
// ========================================

/**
 * Array to store all captured behavioral events
 * Each event contains: type, timestamp, and event-specific data
 */
let behavioralData = [];

/**
 * Session start timestamp for calculating relative timing
 */
const sessionStartTime = Date.now();

/**
 * Event listener for keyboard keydown events
 * Captures: key pressed and timestamp
 */
document.addEventListener('keydown', function (event) {
    const eventData = {
        eventType: 'keydown',
        timestamp: Date.now(),
        relativeTime: Date.now() - sessionStartTime, // Time since session start
        key: event.key,
        keyCode: event.keyCode,
        target: event.target.tagName,
        targetId: event.target.id || null,
        targetName: event.target.name || null
    };

    behavioralData.push(eventData);
    updateEventCount();
});

/**
 * Event listener for keyboard keyup events
 * Captures: key released and timestamp
 */
document.addEventListener('keyup', function (event) {
    const eventData = {
        eventType: 'keyup',
        timestamp: Date.now(),
        relativeTime: Date.now() - sessionStartTime,
        key: event.key,
        keyCode: event.keyCode,
        target: event.target.tagName,
        targetId: event.target.id || null,
        targetName: event.target.name || null
    };

    behavioralData.push(eventData);
    updateEventCount();
});

/**
 * Event listener for mouse movement
 * Captures: mouse position (x, y) and timestamp
 * Throttled to avoid excessive data collection
 */
let lastMouseMoveTime = 0;
const MOUSE_MOVE_THROTTLE = 100; // Capture mouse position every 100ms

document.addEventListener('mousemove', function (event) {
    const now = Date.now();

    // Throttle mouse move events to reduce data volume
    if (now - lastMouseMoveTime < MOUSE_MOVE_THROTTLE) {
        return;
    }

    lastMouseMoveTime = now;

    const eventData = {
        eventType: 'mousemove',
        timestamp: now,
        relativeTime: now - sessionStartTime,
        clientX: event.clientX,
        clientY: event.clientY,
        pageX: event.pageX,
        pageY: event.pageY,
        target: event.target.tagName,
        targetId: event.target.id || null
    };

    behavioralData.push(eventData);
    updateEventCount();
});

/**
 * Update the event counter display
 */
function updateEventCount() {
    document.getElementById('eventCount').textContent = `Events captured: ${behavioralData.length}`;
}

/**
 * Log all behavioral data to browser console
 * Useful for debugging and verification
 */
function logToConsole() {
    console.log('=== BEHAVIORAL DATA LOG ===');
    console.log(`Total Events Captured: ${behavioralData.length}`);
    console.log(`Session Duration: ${Math.round((Date.now() - sessionStartTime) / 1000)} seconds`);
    console.log('');
    console.log('Event Breakdown:');

    // Count events by type
    const eventCounts = behavioralData.reduce((acc, event) => {
        acc[event.eventType] = (acc[event.eventType] || 0) + 1;
        return acc;
    }, {});

    console.table(eventCounts);
    console.log('');
    console.log('Full Event Data:');
    console.table(behavioralData);

    alert(`✅ Logged ${behavioralData.length} events to console. Open DevTools to view.`);
}

/**
 * Export behavioral data to CSV file
 * Converts JSON data to CSV format and triggers download
 */
function exportToCSV() {
    if (behavioralData.length === 0) {
        alert('⚠️ No behavioral data to export yet. Interact with the page first!');
        return;
    }

    // CSV Headers
    let csvContent = 'Event Type,Timestamp,Relative Time (ms),';

    // Add headers based on event type
    csvContent += 'Key,Key Code,Client X,Client Y,Page X,Page Y,Target Element,Target ID,Target Name\n';

    // Add data rows
    behavioralData.forEach(event => {
        const row = [
            event.eventType,
            new Date(event.timestamp).toISOString(),
            event.relativeTime,
            event.key || '',
            event.keyCode || '',
            event.clientX || '',
            event.clientY || '',
            event.pageX || '',
            event.pageY || '',
            event.target || '',
            event.targetId || '',
            event.targetName || ''
        ];

        csvContent += row.map(field => `"${field}"`).join(',') + '\n';
    });

    // Create blob and download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', `behavioral-data-${Date.now()}.csv`);
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    alert(`✅ Exported ${behavioralData.length} events to CSV file!`);
}

/**
 * Send behavioral data to FastAPI backend
 * Makes POST request to /collect-data endpoint
 */
async function sendToBackend() {
    if (behavioralData.length === 0) {
        alert('⚠️ No behavioral data to send yet. Interact with the page first!');
        return;
    }

    try {
        // Prepare payload
        const payload = {
            userId: 'user_12345', // In production, use actual user ID
            sessionId: sessionStartTime.toString(),
            events: behavioralData,
            metadata: {
                userAgent: navigator.userAgent,
                screenWidth: window.screen.width,
                screenHeight: window.screen.height,
                sessionDuration: Date.now() - sessionStartTime
            }
        };

        // Send to backend
        const response = await fetch('http://localhost:8000/collect-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const result = await response.json();
            alert(`✅ Successfully sent ${behavioralData.length} events to backend!\n\nResponse: ${result.message}`);
            console.log('Backend response:', result);
        } else {
            const error = await response.json();
            alert(`❌ Error sending data: ${error.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error sending data to backend:', error);
        alert(`❌ Failed to connect to backend. Make sure FastAPI server is running on http://localhost:8000\n\nError: ${error.message}`);
    }
}

// ========================================
// FORM HANDLING FUNCTIONS
// ========================================

/**
 * Update range slider value display
 */
function updateRangeValue(value) {
    document.getElementById('securityRating').textContent = value;
    updateProgress();
}

/**
 * Calculate and update form progress
 */
function updateProgress() {
    const form = document.getElementById('assessmentForm');
    const inputs = form.querySelectorAll('input[required], textarea[required]');
    let filled = 0;

    inputs.forEach(input => {
        if (input.type === 'radio') {
            const radioGroup = form.querySelectorAll(`input[name="${input.name}"]`);
            const isChecked = Array.from(radioGroup).some(radio => radio.checked);
            if (isChecked && !input.dataset.counted) {
                radioGroup.forEach(radio => radio.dataset.counted = 'true');
                filled++;
            }
        } else if (input.value.trim() !== '') {
            filled++;
        }
    });

    const percentage = Math.round((filled / inputs.length) * 100);
    document.getElementById('progressFill').style.width = percentage + '%';
    document.getElementById('progressPercentage').textContent = percentage + '%';
}

/**
 * Initialize event listeners on page load
 */
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('assessmentForm');
    const inputs = form.querySelectorAll('input, textarea');

    inputs.forEach(input => {
        input.addEventListener('input', updateProgress);
        input.addEventListener('change', updateProgress);
    });

    // Initial progress calculation
    updateProgress();

    console.log('🎯 Behavioral tracking initialized!');
    console.log('📊 Events being captured: keydown, keyup, mousemove');
});

/**
 * Handle form submission
 */
document.getElementById('assessmentForm').addEventListener('submit', function (e) {
    e.preventDefault();

    // Collect form data
    const formData = new FormData(this);
    const data = {};

    for (let [key, value] of formData.entries()) {
        if (data[key]) {
            if (Array.isArray(data[key])) {
                data[key].push(value);
            } else {
                data[key] = [data[key], value];
            }
        } else {
            data[key] = value;
        }
    }

    console.log('Assessment Data:', data);
    console.log(`Behavioral Events Captured: ${behavioralData.length}`);

    // Hide form and show success message
    this.style.display = 'none';
    document.querySelector('.assessment-intro').style.display = 'none';
    document.querySelector('.progress-container').style.display = 'none';
    document.querySelector('.tracking-status').style.display = 'none';
    document.querySelector('.data-export').style.display = 'none';
    document.getElementById('successMessage').classList.add('active');

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

/**
 * Save form draft to localStorage
 */
function saveDraft() {
    const form = document.getElementById('assessmentForm');
    const formData = new FormData(form);
    const data = {};

    for (let [key, value] of formData.entries()) {
        data[key] = value;
    }

    localStorage.setItem('assessmentDraft', JSON.stringify(data));
    alert('✅ Draft saved successfully! You can continue later.');
    console.log('Draft saved:', data);
}

/**
 * Logout function
 */
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = 'introduction.html';
    }
}

/**
 * Load draft from localStorage on page load
 */
window.addEventListener('load', function () {
    const draft = localStorage.getItem('assessmentDraft');
    if (draft) {
        const shouldLoad = confirm('You have a saved draft. Would you like to continue from where you left off?');
        if (shouldLoad) {
            const data = JSON.parse(draft);
            for (let [key, value] of Object.entries(data)) {
                const input = document.querySelector(`[name="${key}"]`);
                if (input) {
                    if (input.type === 'radio') {
                        const radio = document.querySelector(`[name="${key}"][value="${value}"]`);
                        if (radio) radio.checked = true;
                    } else {
                        input.value = value;
                    }
                }
            }
            updateProgress();
        }
    }
});
