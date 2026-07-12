const defaultApiHost = typeof window !== "undefined" && window.location.hostname === "localhost" ? "localhost" : "127.0.0.1";
export const API_BASE_URL = (typeof process !== "undefined" && process.env?.VITE_API_BASE_URL) || (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) || `http://${defaultApiHost}:8000/api/v1`;
export const SOCKET_TIMEOUT_MS = (typeof import.meta !== "undefined" && import.meta.env?.VITE_SOCKET_TIMEOUT_MS) ? parseInt(import.meta.env.VITE_SOCKET_TIMEOUT_MS) : 15000;

