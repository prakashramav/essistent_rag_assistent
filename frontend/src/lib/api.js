const getApiBase = () => {
  let base = process.env.NEXT_PUBLIC_API_BASE_URL || "https://essistent-rag-assistent.onrender.com/api/v1";
  if (!base.startsWith("http://") && !base.startsWith("https://")) {
    base = `https://${base}`;
  }
  if (!base.endsWith("/api/v1")) {
    base = base.replace(/\/+$/, "") + "/api/v1";
  }
  return base;
};

const API_BASE = getApiBase();

const STORAGE_KEYS = {
  ACCESS_TOKEN: "rag_access_token",
  REFRESH_TOKEN: "rag_refresh_token",
  ACTIVE_ORG_ID: "rag_active_org_id",
};

export const getAccessToken = () => {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
};

export const getRefreshToken = () => {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
};

export const getActiveOrgId = () => {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEYS.ACTIVE_ORG_ID);
};

export const setTokens = (accessToken, refreshToken) => {
  if (typeof window === "undefined") return;
  if (accessToken) localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, accessToken);
  if (refreshToken) localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refreshToken);
};

export const setActiveOrgId = (orgId) => {
  if (typeof window === "undefined") return;
  if (orgId) {
    localStorage.setItem(STORAGE_KEYS.ACTIVE_ORG_ID, orgId);
  } else {
    localStorage.removeItem(STORAGE_KEYS.ACTIVE_ORG_ID);
  }
};

export const clearAuthStorage = () => {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
  localStorage.removeItem(STORAGE_KEYS.ACTIVE_ORG_ID);
};

export async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const headers = { ...options.headers };

  // Only set application/json if body is not FormData
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const token = getAccessToken();
  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const activeOrgId = getActiveOrgId();
  if (activeOrgId && !headers["X-Organization-Id"]) {
    headers["X-Organization-Id"] = activeOrgId;
  }

  let response = await fetch(url, {
    ...options,
    headers,
  });

  // Attempt refresh token flow if 401 Unauthorized
  if (
    response.status === 401 &&
    !endpoint.includes("/auth/login") &&
    !endpoint.includes("/auth/signup") &&
    !endpoint.includes("/auth/refresh")
  ) {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        const refreshResponse = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (refreshResponse.ok) {
          const tokenData = await refreshResponse.json();
          setTokens(tokenData.access_token, tokenData.refresh_token);
          headers["Authorization"] = `Bearer ${tokenData.access_token}`;
          // Retry original request
          response = await fetch(url, {
            ...options,
            headers,
          });
        } else {
          clearAuthStorage();
          if (typeof window !== "undefined" && window.location.pathname !== "/login") {
            window.location.href = "/login";
          }
        }
      } catch (err) {
        clearAuthStorage();
      }
    }
  }

  let data = null;
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const errorMessage = (data && data.detail) || response.statusText || "Request failed";
    const error = new Error(typeof errorMessage === "string" ? errorMessage : JSON.stringify(errorMessage));
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

export const api = {
  health: () => request("/health"),
  auth: {
    signup: (payload) => request("/auth/signup", { method: "POST", body: JSON.stringify(payload) }),
    login: (payload) => request("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
    refresh: (payload) => request("/auth/refresh", { method: "POST", body: JSON.stringify(payload) }),
    me: () => request("/auth/me"),
  },
  organizations: {
    list: () => request("/organizations"),
    create: (payload) => request("/organizations", { method: "POST", body: JSON.stringify(payload) }),
    getMembers: (orgId) => request(`/organizations/${orgId}/members`),
    addMember: (orgId, payload) => request(`/organizations/${orgId}/members`, { method: "POST", body: JSON.stringify(payload) }),
    updateMemberRole: (orgId, userId, payload) => request(`/organizations/${orgId}/members/${userId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    removeMember: (orgId, userId) => request(`/organizations/${orgId}/members/${userId}`, { method: "DELETE" }),
  },
  documents: {
    upload: (formData) => request("/documents/upload", { method: "POST", body: formData }),
    ingestUrl: (payload) => request("/documents/url", { method: "POST", body: JSON.stringify(payload) }),
    list: (params = {}) => {
      const query = new URLSearchParams();
      if (params.status) query.append("status", params.status);
      if (params.fileType) query.append("file_type", params.fileType);
      const qs = query.toString();
      return request(`/documents${qs ? `?${qs}` : ""}`);
    },
    get: (id) => request(`/documents/${id}`),
    getStatus: (id) => request(`/documents/${id}/status`),
    getChunks: (id) => request(`/documents/${id}/chunks`),
    reindex: (id) => request(`/documents/${id}/reindex`, { method: "POST" }),
    delete: (id) => request(`/documents/${id}`, { method: "DELETE" }),
  },
  retrieval: {
    search: (payload) => request("/retrieval/search", { method: "POST", body: JSON.stringify(payload) }),
  },
  chat: {
    listConversations: (page = 1, pageSize = 20) => request(`/chat/conversations?page=${page}&page_size=${pageSize}`),
    createConversation: (payload = {}) => request("/chat/conversations", { method: "POST", body: JSON.stringify(payload) }),
    getConversation: (id) => request(`/chat/conversations/${id}`),
    updateConversation: (id, payload) => request(`/chat/conversations/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    deleteConversation: (id) => request(`/chat/conversations/${id}`, { method: "DELETE" }),
    sendMessage: (id, payload) => request(`/chat/conversations/${id}/messages`, { method: "POST", body: JSON.stringify(payload) }),
    streamMessage: async (id, payload, { onStatus, onSources, onDelta, onDone, onError } = {}) => {
      const url = `${API_BASE}/chat/conversations/${id}/messages/stream`;
      const token = getAccessToken();
      const activeOrgId = getActiveOrgId();

      const headers = {
        "Content-Type": "application/json",
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (activeOrgId) headers["X-Organization-Id"] = activeOrgId;

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || `Stream failed with status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            try {
              const event = JSON.parse(trimmed.slice(6));
              if (event.type === "retrieval_status" && onStatus) onStatus(event.data);
              else if (event.type === "sources" && onSources) onSources(event.data);
              else if (event.type === "delta" && onDelta) onDelta(event.data);
              else if (event.type === "done" && onDone) onDone(event.data);
              else if (event.type === "error" && onError) onError(event.data);
            } catch (err) {
              console.error("Error parsing SSE line:", err, trimmed);
            }
          }
        }
      }
    },
  },
  evaluation: {
    single: (payload) => request("/evaluation/single", { method: "POST", body: JSON.stringify(payload) }),
    runBenchmark: (payload = {}) => request("/evaluation/run", { method: "POST", body: JSON.stringify(payload) }),
    listRuns: () => request("/evaluation/runs"),
    getRun: (id) => request(`/evaluation/runs/${id}`),
  },
  observability: {
    getDiagnostics: () => request("/health/diagnostics"),
    getMetrics: async () => {
      const token = getAccessToken();
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE}/metrics`, { headers });
      if (!res.ok) throw new Error("Failed to fetch metrics");
      return await res.text();
    },
  },
};
