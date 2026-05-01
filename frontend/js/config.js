// frontend/js/config.js

/**
 * Global Configuration Settings
 *
 * The FastAPI backend serves both the API and the frontend static files
 * from http://localhost:8000. Update RENDER_BACKEND_URL before deploying.
 */

const isLocalhost = window.location.hostname === 'localhost'
    || window.location.hostname === '127.0.0.1'
    || window.location.hostname === ''
    || window.location.port === '8000';

// CHANGE THIS string to your live Render backend URL after deploying!
const RENDER_BACKEND_URL = 'https://behave-sec.onrender.com';

const API_BASE_URL = isLocalhost ? 'http://localhost:8000' : RENDER_BACKEND_URL;
const WS_BASE_URL  = isLocalhost ? 'http://localhost:8000/ws' : RENDER_BACKEND_URL + '/ws';

// Google OAuth 2.0 Client ID (registered in Google Cloud Console)
const GOOGLE_CLIENT_ID = '712400673827-4d3u6bi41fs47nqs4urjntv6ib3712hu.apps.googleusercontent.com';

window.BEHAVE_CONFIG = {
    API_BASE_URL:     API_BASE_URL,
    WS_BASE_URL:      WS_BASE_URL,
    GOOGLE_CLIENT_ID: GOOGLE_CLIENT_ID,
};

