/**
 * api.js — DGE API istemcisi + Auth katmani.
 * Tum sayfa verileri bu katman uzerinden BACKEND'den gelir.
 * Frontend'de is mantigi yok: puan/rozet/sira hesabi sunucuda.
 */

const API_BASE = '';

// ── AUTH (localStorage) ───────────────────
const Auth = {
  setSession(data) {
    localStorage.setItem('dge_token',    data.token);
    localStorage.setItem('dge_user_id',  data.user_id);
    localStorage.setItem('dge_username', data.username);
    localStorage.setItem('dge_role',     data.role);
  },
  getToken:    () => localStorage.getItem('dge_token'),
  getUserId:   () => localStorage.getItem('dge_user_id'),
  getUsername: () => localStorage.getItem('dge_username'),
  getRole:     () => localStorage.getItem('dge_role'),
  isLoggedIn:  () => !!localStorage.getItem('dge_token'),
  setToken(token) {
    localStorage.setItem('dge_token', token);
  },
  clear() {
    localStorage.removeItem('dge_token');
    localStorage.removeItem('dge_user_id');
    localStorage.removeItem('dge_username');
    localStorage.removeItem('dge_role');
  },
};

// ── ORTAK FETCH ───────────────────────────
async function apiFetch(endpoint, options = {}) {
  const headers = Object.assign(
    { 'Content-Type': 'application/json' },
    options.headers || {}
  );
  const token = Auth.getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(API_BASE + endpoint, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    Auth.clear();
    window.location.href = '/index.html';
    throw new Error('Oturum suresi doldu');
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail || detail;
    } catch (e) { /* govde json degil */ }
    throw new Error(detail);
  }

  return res.json();
}

// ── API METOTLARI ─────────────────────────
const API = {
  // Genel yardimcilar
  get:  (endpoint)       => apiFetch(endpoint),
  post: (endpoint, body) => apiFetch(endpoint, {
    method: 'POST',
    body: JSON.stringify(body || {}),
  }),

  // Auth
  register: (username, password) =>
    API.post('/api/auth/register', { username, password }),
  login: (username, password) =>
    API.post('/api/auth/login', { username, password }),
  refresh: () => API.post('/api/auth/refresh'),

  // Kullanici
  getMe:            () => API.get('/api/users/me'),
  getHistory: (limit = 100) =>
    API.get(`/api/users/me/points-history?limit=${limit}`),
  getPointsHistory: (limit = 100) =>
    API.get(`/api/users/me/points-history?limit=${limit}`),
  getStats:         () => API.get('/api/users/me/stats'),

  // Icerik
  getCatalog: () => API.get('/api/content/catalog'),
  getContent: (id) => API.get(`/api/content/${encodeURIComponent(id)}`),

  // Izleme
  startSession: (contentId) =>
    API.post('/api/watch/session/start', { content_id: contentId }),
  endSession: (sessionId) =>
    API.post('/api/watch/session/end', { session_id: sessionId }),
  heartbeat: (sessionId) =>
    API.post('/api/watch/session/heartbeat', { session_id: sessionId }),

  // Challenge / Leaderboard / Rozet
  getChallenges:  () => API.get('/api/challenges/active'),
  getLeaderboard: (limit = 50) =>
    API.get(`/api/leaderboard?limit=${limit}`),
  getWeeklyLeaderboard: () => API.get('/api/leaderboard/weekly'),
  getMyRankHistory: () => API.get('/api/leaderboard/my-history'),
  getMyBadges:     () => API.get('/api/badges/mine'),
  getBadgeProgress: () => API.get('/api/badges/progress'),

  // AI
  askAI: (question) => API.post('/api/ai/explain', { question }),
  askAgent: (question) => API.post('/api/ai/agent', { question }),
  getAIStatus: () => API.get('/api/ai/status'),
  generateChallenges: () => API.post('/api/ai/challenge/generate'),
  getAILeaderboard: (category) =>
    API.get(`/api/ai/leaderboard/${encodeURIComponent(category)}`),
  getRecommendations: () => API.get('/api/ai/recommendations'),

  // Admin
  runPipeline: () => API.post('/api/pipeline/run'),
};

// Global'e ac
window.Auth = Auth;
window.API  = API;
window.apiFetch = apiFetch;
