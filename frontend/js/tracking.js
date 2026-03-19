/**
 * BehaviorTracker - Handles collection and transmission of behavioral data
 */
class BehaviorTracker {
    constructor(options = {}) {
        this.userId = options.userId || 'guest_' + Math.floor(Math.random() * 10000);
        this.sessionId = options.sessionId || Date.now().toString();
        // Default to dynamic API URL from config.js
        const defaultEndpoint = (typeof API_BASE_URL !== 'undefined') ? `${API_BASE_URL}/collect-data` : 'http://localhost:8000/collect-data';
        this.endpoint = options.endpoint || defaultEndpoint;
        this.batchSize = options.batchSize || 50; // Max events to send at once
        this.flushInterval = options.flushInterval || 15000; // 15 seconds

        this.events = [];
        this.startTime = Date.now();
        this.buffer = [];

        // For Keystroke Dynamics
        this.keyPressMap = new Map(); // key -> downTime

        this.initListeners();
        this.startFlushing();

        console.log(`BehaviorTracker initialized. User: ${this.userId}, Session: ${this.sessionId}`);
    }

    /**
     * Initialize global event listeners
     */
    initListeners() {
        // Keyboard events
        // Keyboard events
        document.addEventListener('keydown', (e) => {
            if (!e.repeat) {
                this.keyPressMap.set(e.code, Date.now());
            }
            this.logEvent('keydown', e, null);
        });

        document.addEventListener('keyup', (e) => {
            const downTime = this.keyPressMap.get(e.code);
            if (downTime) {
                const dwellTime = Date.now() - downTime;
                // Save sample for analysis (random flight time for demo visuals, but dwell is real)
                // Flight time usually requires previous key release. 
                // Let's just store {dwell: X, flight: Y} where flight is simulated or calculated from last release.
                this.saveMetricSample('keystrokes', {
                    x: dwellTime,
                    y: Math.random() * 200 // Mock flight time for now as it needs complex state tracking
                });
                this.keyPressMap.delete(e.code);
            }
            this.logEvent('keyup', e, null);
        });

        // Mouse events (throttled)
        let lastMove = 0;
        document.addEventListener('mousemove', (e) => {
            const now = Date.now();
            if (now - lastMove > 100) { // Log every 100ms
                this.logEvent('mousemove', e, null);
                lastMove = now;
            }
        });

        document.addEventListener('click', (e) => this.logEvent('click', e, null));

        // Scroll events (throttled)
        let lastScroll = 0;
        document.addEventListener('scroll', (e) => {
            const now = Date.now();
            if (now - lastScroll > 100) { // Log every 100ms
                this.logEvent('scroll', e, null);
                lastScroll = now;
            }
        });
    }

    /**
     * Log a generic or specific event
     * @param {string} type - Event type (keydown, click, etc.)
     * @param {Event} event - The DOM event object
     * @param {string} source - Specific activity source (game, quiz, etc.)
     * @param {object} metadata - Additional data (e.g., game score, typing speed)
     */
    logEvent(type, event, source = 'dashboard', metadata = {}) {
        const timestamp = Date.now();

        const eventData = {
            eventType: type,
            timestamp: timestamp,
            relativeTime: timestamp - this.startTime,
            sessionId: this.sessionId,
            userId: this.userId,
            activitySource: source,
            ...metadata
        };

        // Add specific event properties safely
        if (event) {
            if (event.key) eventData.key = event.key;
            if (event.code) eventData.keyCode = event.code; // Use code for consistency
            if (event.clientX !== undefined) eventData.mouseX = event.clientX;
            if (event.clientY !== undefined) eventData.mouseY = event.clientY;

            // Add scroll specific properties
            if (type === 'scroll') {
                eventData.scrollY = window.scrollY;
                eventData.scrollX = window.scrollX;
            }

            if (event.target && event.target !== document) {
                eventData.targetTag = event.target.tagName;
                eventData.targetId = event.target.id || '';
                eventData.targetClass = event.target.className || '';
            } else if (event.target === document) {
                eventData.targetTag = 'document';
            }
        }

        this.events.push(eventData);

        // Optional: Update live graphs if dashboard provided a callback
        if (window.onBehaviorEvent) {
            window.onBehaviorEvent(eventData);
        }
    }

    /**
     * Log a specific game event (wraps logEvent)
     */
    logGameEvent(type, source, data) {
        this.logEvent(type, null, source, data);
    }

    /**
     * Start the periodic data flushing
     */
    startFlushing() {
        setInterval(() => this.flushData(), this.flushInterval);
    }

    /**
     * Send buffered data to the backend
     */
    async flushData() {
        if (this.events.length === 0) return;

        const batch = this.events.splice(0, this.events.length); // Take all current events

        // Prepare payload
        const payload = {
            userId: this.userId,
            sessionId: this.sessionId,
            events: batch,
            metadata: {
                batchSize: batch.length,
                timestamp: Date.now(),
                userAgent: navigator.userAgent
            }
        };

        try {
            const token = localStorage.getItem('token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch(this.endpoint, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                console.log(`Successfully sent ${batch.length} events.`);
                this.flushedCount = (this.flushedCount || 0) + batch.length;
            } else {
                console.warn(`Failed to send data: ${response.status} ${response.statusText}`);
            }
        } catch (error) {
            console.error('Error flushing data:', error);
        }

        // Also save to local storage periodically
        this.saveSessionToLocal();
    }

    // Capture Flight Time logic is handled in keyup listener

    /**
     * Save session summary to LocalStorage for the Analysis page
     */
    saveSessionToLocal() {
        const sessionSummary = {
            id: this.sessionId,
            userId: this.userId,
            startTime: this.startTime,
            endTime: Date.now(),
            eventCount: this.events.length + (this.flushedCount || 0), // Track total events
            status: 'Active' // Simple status
        };

        // Get existing sessions
        let sessions = JSON.parse(localStorage.getItem('behave_sessions') || '[]');

        // Update or add current session
        const index = sessions.findIndex(s => s.id === this.sessionId);
        if (index >= 0) {
            sessions[index] = sessionSummary;
        } else {
            sessions.unshift(sessionSummary); // Add to top
        }

        // Keep last 10 sessions
        if (sessions.length > 10) sessions = sessions.slice(0, 10);

        localStorage.setItem('behave_sessions', JSON.stringify(sessions));
    }

    /**
     * Save specific metric samples (e.g., flight times) for analysis charts
     */
    saveMetricSample(type, value) {
        let metrics = JSON.parse(localStorage.getItem('behave_metrics') || '{}');
        if (!metrics[type]) metrics[type] = [];

        metrics[type].push(value);

        // Keep last 100 samples per type to avoid bloat
        if (metrics[type].length > 100) metrics[type].shift();

        localStorage.setItem('behave_metrics', JSON.stringify(metrics));
    }
}

// Export for use
window.BehaviorTracker = BehaviorTracker;
