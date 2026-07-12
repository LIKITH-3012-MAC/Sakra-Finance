import api from "./api.js";
import { 
  getAccessToken, 
  setAccessToken, 
  removeAccessToken,
  getRefreshToken,
  setRefreshToken,
  removeRefreshToken
} from "./storage.js";

export function getCachedUser() {
  const cached = localStorage.getItem("user");
  if (cached) {
    try {
      return JSON.parse(cached);
    } catch {
      return null;
    }
  }
  return null;
}

export function setCachedUser(user) {
  if (user) {
    localStorage.setItem("user", JSON.stringify(user));
  } else {
    localStorage.removeItem("user");
  }
}

export async function checkSession() {
  const token = getAccessToken();
  if (!token) {
    setCachedUser(null);
    return null;
  }
  
  try {
    const response = await api.get("/auth/me");
    const user = response.data || response;
    setCachedUser(user);
    return user;
  } catch (err) {
    removeAccessToken();
    removeRefreshToken();
    setCachedUser(null);
    return null;
  }
}

export async function login(username, password) {
  try {
    const response = await api.post("/auth/login", { username, password });
    const payload = response.data || response;
    const accessToken = payload.token.access_token;
    const refreshToken = payload.token.refresh_token;
    const userData = payload.user;
    
    setAccessToken(accessToken);
    if (refreshToken) {
      setRefreshToken(refreshToken);
    }
    setCachedUser(userData);
    return userData;
  } catch (err) {
    removeAccessToken();
    removeRefreshToken();
    setCachedUser(null);
    throw err;
  }
}

export async function logout() {
  try {
    await api.post("/auth/logout");
  } catch (err) {
    console.warn("Logout endpoint error:", err);
  } finally {
    removeAccessToken();
    removeRefreshToken();
    setCachedUser(null);
    window.location.href = "/login.html";
  }
}
