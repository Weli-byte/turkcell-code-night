const API_BASE = "/api";

const Auth = {
  getToken:    ()  => localStorage.getItem("dge_token"),
  getUsername: ()  => localStorage.getItem("dge_username"),
  getUserId:   ()  => localStorage.getItem("dge_user_id"),
  getRole:     ()  => localStorage.getItem("dge_role"),
  save: (token, username, userId, role) => {
    localStorage.setItem("dge_token",    token);
    localStorage.setItem("dge_username", username);
    localStorage.setItem("dge_user_id",  userId);
    localStorage.setItem("dge_role",     role);
  },
  clear: () => {
    ["dge_token","dge_username","dge_user_id","dge_role"]
      .forEach(k => localStorage.removeItem(k));
  },
  isLoggedIn: () => !!localStorage.getItem("dge_token"),
  requireAuth: () => {
    if (!localStorage.getItem("dge_token")) {
      window.location.href = "/index.html";
    }
  },
  requireAdmin: () => {
    if (localStorage.getItem("dge_role") !== "admin") {
      window.location.href = "/catalog.html";
    }
  },
};

async function tryRefresh() {
  try {
    const token = Auth.getToken();
    if (!token) return false;
    const res = await fetch(API_BASE + "/auth/refresh", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
      },
    });
    if (!res.ok) return false;
    const data = await res.json();
    Auth.save(
      data.token,
      Auth.getUsername(),
      Auth.getUserId(),
      Auth.getRole()
    );
    return true;
  } catch(e) {
    return false;
  }
}

async function apiFetch(endpoint, options = {}, _retry = false) {
  const token = Auth.getToken();
  const res = await fetch(API_BASE + endpoint, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "Authorization": "Bearer " + token } : {}),
      ...(options.headers || {}),
    },
  });

  if (res.status === 401 && !_retry) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return apiFetch(endpoint, options, true);
    } else {
      Auth.clear();
      window.location.href = "/index.html";
      return;
    }
  }

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "API hatasi");
  return data;
}

const API = {
  login:              (u, p) => apiFetch("/auth/login",
    { method:"POST", body: JSON.stringify({username:u, password:p}) }),
  register:           (u, p) => apiFetch("/auth/register",
    { method:"POST", body: JSON.stringify({username:u, password:p}) }),
  getMe:              ()     => apiFetch("/users/me"),
  getHistory:         ()     => apiFetch("/users/me/points-history"),
  getMyStats:         ()     => apiFetch("/users/me/stats"),
  getMyWeekly:        ()     => apiFetch("/users/me/weekly"),
  getMyProfile:       ()     => apiFetch("/users/me/profile"),
  changePassword:     (old_password, new_password) =>
    apiFetch("/users/me/password", { method:"PUT", body: JSON.stringify({old_password, new_password}) }),
  getPublicProfile:   (username) => apiFetch(`/users/public/${encodeURIComponent(username)}`),
  getCatalog:         (q)    => apiFetch("/content/catalog" + (q||"")),
  getContent:         (id)   => apiFetch("/content/" + id),
  startSession:       (cid)  => apiFetch("/watch/session/start",
    { method:"POST", body: JSON.stringify({content_id:cid}) }),
  endSession:         (sid)  => apiFetch("/watch/session/end",
    { method:"POST", body: JSON.stringify({session_id:sid}) }),
  heartbeat:          (sid)  => apiFetch("/watch/session/heartbeat",
    { method:"POST", body: JSON.stringify({session_id:sid}) }),
  getChallenges:      ()     => apiFetch("/challenges/active"),
  getLeaderboard:       (q)   => apiFetch("/leaderboard" + (q ? `?q=${encodeURIComponent(q)}` : "")),
  getWeeklyLeaderboard: ()   => apiFetch("/leaderboard/weekly"),
  getStreakLeaderboard: ()   => apiFetch("/leaderboard/streaks"),
  getMyRankHistory:     ()   => apiFetch("/leaderboard/my-history"),
  getMyBadges:        ()     => apiFetch("/badges/mine"),
  getBadgeProgress:   ()     => apiFetch("/badges/progress"),
  askAI:              (q)    => apiFetch("/ai/explain",
    { method:"POST", body: JSON.stringify({question:q}) }),
  getAIRecommendations: ()  => apiFetch("/ai/recommendations"),
  getAIChallengeTips:   ()  => apiFetch("/ai/challenge-tips"),
  getAIDigest:          ()  => apiFetch("/ai/digest", { method:"POST" }),
  getAIStatus:          ()  => apiFetch("/ai/status"),
  runPipeline:          ()       => apiFetch("/pipeline/run", { method:"POST" }),
  getPipelineRuns:      ()       => apiFetch("/pipeline/runs"),
  getAdminMetrics:      ()       => apiFetch("/pipeline/metrics"),
  getAllChallenges:      ()       => apiFetch("/challenges/all"),
  getChallengeFields:   ()       => apiFetch("/challenges/fields"),
  createChallenge:      (body)   => apiFetch("/challenges/", { method:"POST", body: JSON.stringify(body) }),
  updateChallenge:      (id, b)  => apiFetch(`/challenges/${id}`, { method:"PUT",    body: JSON.stringify(b) }),
  toggleChallenge:      (id)     => apiFetch(`/challenges/${id}/toggle`, { method:"POST" }),
  deleteChallenge:      (id)     => apiFetch(`/challenges/${id}`, { method:"DELETE" }),
};
