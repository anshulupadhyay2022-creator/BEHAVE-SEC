// frontend/js/config.js

/**
 * Global Configuration Settings
 * 
 * If you are running locally on your machine, it uses the local FastAPI server.
 * Otherwise, it defaults to the production Render URL.
 * 
 * NOTE: Before your final deployment, change the URL below to match your actual deployed Render backend URL.
 */

const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

// CHANGE THIS string to your live Render backend URL after deploying it!
const RENDER_BACKEND_URL = 'https://behave-sec.onrender.com';

const API_BASE_URL = isLocalhost ? 'http://localhost:8000' : RENDER_BACKEND_URL;
const WS_BASE_URL = isLocalhost ? 'ws://localhost:8000' : RENDER_BACKEND_URL.replace('http', 'ws');

window.BEHAVE_CONFIG = {
    API_BASE_URL: API_BASE_URL,
    WS_BASE_URL: WS_BASE_URL
};
