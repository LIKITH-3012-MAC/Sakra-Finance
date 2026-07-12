import { API_BASE_URL } from "./config.js";
import { getAccessToken, setAccessToken, removeAccessToken, getRefreshToken, setRefreshToken } from "./storage.js";

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

async function customFetch(url, options = {}) {
  const absoluteUrl = url.startsWith("http") ? url : `${API_BASE_URL}${url}`;
  
  // Setup headers
  options.headers = options.headers || {};
  const token = getAccessToken();
  if (token) {
    options.headers["Authorization"] = `Bearer ${token}`;
  }
  
  // Crucial: ensure credentials are sent for HttpOnly cookie (refresh token)
  options.credentials = "include";

  try {
    const response = await fetch(absoluteUrl, options);
    
    // Auto-parse JSON response if success
    if (response.ok) {
      const payload = await response.json();
      return payload; // Returns the parsed APIResponse directly (equivalent to response.data in axios)
    }

    // Handle 401 Token Expiration Rotation
    if (response.status === 401) {
      console.warn(`[AUTH] 401 Unauthorized received for request: ${url}`);
      const isRefreshRequest = url.includes("/auth/refresh") || url.includes("/auth/login");
      if (isRefreshRequest) {
        console.error(`[AUTH] Refresh request failed with 401. Logging out user.`);
        removeAccessToken();
        const errPayload = await response.json().catch(() => ({}));
        throw errPayload;
      }

      if (isRefreshing) {
        console.log(`[AUTH] Silent token refresh already in progress. Queueing request: ${url}`);
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((newToken) => {
            options.headers["Authorization"] = `Bearer ${newToken}`;
            return customFetch(url, options);
          })
          .catch((err) => Promise.reject(err));
      }

      isRefreshing = true;
      console.log(`[AUTH] Access token expired. Attempting silent token rotation...`);

      try {
        const rToken = getRefreshToken();
        // Attempt token rotation via fetch
        const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ refresh_token: rToken }),
          credentials: "include"
        });

        if (!refreshResponse.ok) {
          throw new Error(`Refresh request failed with status: ${refreshResponse.status}`);
        }

        const refreshPayload = await refreshResponse.json();
        const newAccessToken = refreshPayload.data.access_token;
        const newRefreshToken = refreshPayload.data.refresh_token;
        console.log(`[AUTH] Silent token rotation succeeded. Updating token in storage.`);
        setAccessToken(newAccessToken);
        if (newRefreshToken) {
          setRefreshToken(newRefreshToken);
        }

        processQueue(null, newAccessToken);
        isRefreshing = false;

        // Retry original request
        options.headers["Authorization"] = `Bearer ${newAccessToken}`;
        return await customFetch(url, options);

      } catch (refreshErr) {
        console.error(`[AUTH] Silent token rotation failed: ${refreshErr.message}. Clearing session and triggering logout.`);
        processQueue(refreshErr, null);
        isRefreshing = false;
        removeAccessToken();
        window.dispatchEvent(new Event("auth-expired"));
        throw refreshErr;
      }
    }

    // For other error statuses, read and throw the body details
    const errorPayload = await response.json().catch(() => ({}));
    throw errorPayload;

  } catch (error) {
    // Return standard error payload matching Axios response interceptor format
    throw error;
  }
}

const api = {
  get: (url, params = null, options = {}) => {
    let finalUrl = url;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null) {
          searchParams.append(key, val);
        }
      });
      const separator = url.includes("?") ? "&" : "?";
      finalUrl = `${url}${separator}${searchParams.toString()}`;
    }
    return customFetch(finalUrl, { ...options, method: "GET" });
  },
  post: (url, data = {}, options = {}) => {
    return customFetch(url, {
      ...options,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      },
      body: JSON.stringify(data)
    });
  },
  put: (url, data = {}, options = {}) => {
    return customFetch(url, {
      ...options,
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      },
      body: JSON.stringify(data)
    });
  },
  patch: (url, data = {}, options = {}) => {
    return customFetch(url, {
      ...options,
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      },
      body: JSON.stringify(data)
    });
  },
  delete: (url, options = {}) => {
    return customFetch(url, { ...options, method: "DELETE" });
  }
};

export default api;
export { customFetch };
