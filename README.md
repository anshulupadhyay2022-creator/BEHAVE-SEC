# BEHAVE-SEC: Behavioral Data Collection System

A next-generation cybersecurity initiative focused on understanding, analyzing, and securing digital behavior.

## 📋 Project Overview

This project implements a behavioral data collection system with:
- **Frontend**: Interactive assessment form that captures user behavior (keystrokes, mouse movements)
- **Backend**: FastAPI server that receives, validates, and stores behavioral data
- **No AI/ML** (at this stage): Focus is on data collection and storage

## 🎯 Features

### Frontend (`assessment-with-tracking.html`)
- ✅ Captures `keydown` events (key pressed, timestamp)
- ✅ Captures `keyup` events (key released, timestamp)
- ✅ Captures `mousemove` events (X/Y position, timestamp)
- ✅ Real-time event counter
- ✅ Export data to CSV
- ✅ Log data to browser console
- ✅ Send data to backend API
- ✅ Beautiful cybersecurity-themed UI

### Backend (`backend_api.py`)
- ✅ FastAPI RESTful API
- ✅ Pydantic data validation
- ✅ POST endpoint `/collect-data` for receiving data
- ✅ GET endpoint `/stats` for viewing statistics
- ✅ Saves data to JSON and CSV files
- ✅ In-memory storage (temporary)
- ✅ CORS enabled for frontend communication

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Step 1: Set Up Backend

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

2. **Start the FastAPI server:**
```bash
python backend_api.py
```

You should see:
```
🚀 Starting BEHAVE-SEC Backend Server
📡 Server: http://localhost:8000
📖 API Docs: http://localhost:8000/docs
📊 Data Storage: ./behavioral_data/
```

3. **Verify server is running:**
- Open browser to: http://localhost:8000
- You should see: `{"message": "BEHAVE-SEC API is running"}`

4. **Explore API documentation:**
- Open: http://localhost:8000/docs
- Interactive Swagger UI for testing endpoints

### Step 2: Use Frontend

1. **Open the assessment page:**
   - Open `assessment-with-tracking.html` in your web browser
   - You can double-click the file or use a local server

2. **Interact with the page:**
   - Type in text fields
   - Move your mouse around
   - Click on radio buttons and checkboxes
   - Watch the event counter increase in real-time

3. **Export/View Data:**
   - **Log to Console**: Click "📊 Log to Console" button, then open DevTools (F12) to view
   - **Export CSV**: Click "📥 Export CSV" to download behavioral data
   - **Send to Backend**: Click "🚀 Send to Backend" to send data to API

## 📊 Data Structure

### Behavioral Event Format
```json
{
  "eventType": "keydown",
  "timestamp": 1707580800000,
  "relativeTime": 5234,
  "key": "a",
  "keyCode": 65,
  "target": "INPUT",
  "targetId": "industry",
  "targetName": "industry"
}
```

### Complete Payload Format
```json
{
  "userId": "user_12345",
  "sessionId": "1707580800000",
  "events": [ /* array of events */ ],
  "metadata": {
    "userAgent": "Mozilla/5.0...",
    "screenWidth": 1920,
    "screenHeight": 1080,
    "sessionDuration": 45000
  }
}
```

## 🔌 API Endpoints

### POST `/collect-data`
Receive behavioral data from frontend

**Request Body:**
```json
{
  "userId": "string",
  "sessionId": "string",
  "events": [/* BehavioralEvent array */],
  "metadata": {/* SessionMetadata */}
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully received and stored 150 events",
  "data": {
    "userId": "user_12345",
    "sessionId": "1707580800000",
    "eventsReceived": 150,
    "eventBreakdown": {
      "keydown": 45,
      "keyup": 45,
      "mousemove": 60
    }
  }
}
```

### GET `/stats`
Get statistics about collected data

**Response:**
```json
{
  "totalSessions": 5,
  "totalEvents": 750,
  "sessions": [/* session summaries */]
}
```

## 📁 File Structure

```
behave-sec/
├── assessment-with-tracking.html   # Frontend with behavioral tracking
├── backend_api.py                  # FastAPI backend server
├── requirements.txt                # Python dependencies
├── README.md                       # This file
└── behavioral_data/                # Created when backend runs
    ├── session_*.json              # Session data (JSON format)
    └── session_*.csv               # Session data (CSV format)
```

## 🔧 How It Works

### Frontend Data Capture

1. **Event Listeners**: JavaScript adds listeners for `keydown`, `keyup`, `mousemove`
2. **Data Collection**: Each event is captured with timestamp and relevant details
3. **Storage**: Events stored in JavaScript array `behavioralData[]`
4. **Throttling**: Mouse movements throttled to 100ms to avoid excessive data

### Backend Processing

1. **Validation**: Pydantic models validate incoming JSON data
2. **Storage**: Data saved to both JSON and CSV files
3. **In-Memory**: Data also stored in memory for quick statistics
4. **Logging**: Server logs all received data to console

## 🎨 Frontend Features

### Interactive Elements Tracked:
- Text inputs (industry, incidents, concerns, goals)
- Radio buttons (company size, budget)
- Checkboxes (security measures)
- Range slider (security rating)
- Mouse movements across entire page

### Visual Indicators:
- 🟢 Green blinking indicator shows tracking is active
- Real-time event counter
- Progress bar for form completion
- Cybersecurity-themed dark UI with glowing effects

## 🔒 Security Considerations

**Current Implementation (Development):**
- CORS enabled for all origins (`*`)
- No authentication required
- Data stored in local files

**Production Recommendations:**
- Add user authentication (JWT tokens)
- Restrict CORS to specific frontend URL
- Use database instead of file storage
- Implement rate limiting
- Add data encryption
- Add privacy notices and consent

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check if port 8000 is already in use
# On Linux/Mac:
lsof -i :8000

# On Windows:
netstat -ano | findstr :8000

# Kill the process or use a different port
```

### Frontend can't connect to backend
1. Verify backend is running on `http://localhost:8000`
2. Check browser console for CORS errors
3. Ensure you're not using HTTPS for frontend (use HTTP)

### No events being captured
1. Open browser DevTools (F12) and check Console tab
2. Look for "🎯 Behavioral tracking initialized!" message
3. Verify no JavaScript errors

### CSV export not working
1. Check browser console for errors
2. Ensure pop-up blocker isn't blocking downloads
3. Try "Log to Console" first to verify data exists

## 📈 Next Steps (Future Enhancements)

- [ ] Add database support (PostgreSQL/MongoDB)
- [ ] Implement user authentication
- [ ] Add ML/AI analysis for anomaly detection
- [ ] Create analytics dashboard
- [ ] Add session replay functionality
- [ ] Implement real-time data streaming
- [ ] Add data visualization (heatmaps, keystroke patterns)
- [ ] Privacy-preserving data anonymization

## 🤝 Testing the System

### Test Scenario 1: Basic Data Collection
1. Open frontend
2. Type in some text fields
3. Move mouse around
4. Click "Log to Console"
5. Verify events in console

### Test Scenario 2: CSV Export
1. Interact with page for 30 seconds
2. Click "Export CSV"
3. Open downloaded CSV in Excel/Sheets
4. Verify data structure

### Test Scenario 3: Backend Integration
1. Start backend server
2. Open frontend
3. Fill out some form fields
4. Click "Send to Backend"
5. Check backend console for logs
6. Check `behavioral_data/` folder for files

## 📝 Code Comments

Both files are heavily commented for beginners:
- **Frontend**: Detailed JSDoc-style comments explaining each function
- **Backend**: Python docstrings for all classes and functions

## 💡 Tips for Beginners

1. **Start with frontend only**: Test data collection without backend first
2. **Use browser DevTools**: Essential for debugging JavaScript
3. **Read API docs**: Visit `/docs` endpoint for interactive API testing
4. **Check file outputs**: Look at generated JSON/CSV files to understand data structure
5. **Experiment**: Try adding new event types (clicks, scrolls, etc.)

## 📞 Support

For issues or questions:
1. Check browser console for errors
2. Check backend server logs
3. Review this README
4. Check API documentation at `/docs`

---

**Built with ❤️ for BEHAVE-SEC**
