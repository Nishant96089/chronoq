import axios from "axios";

// Base URL comes from env (set in .env as VITE_API_BASE_URL).
// Falls back to localhost for safety.
const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const client = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

// Attach the auth token (if present) to every request.
// We store it in localStorage after login.
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("chronoq_token");
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

// On 401 (unauthorized), clear the stale token and bounce to login.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem("chronoq_token");
      // Avoid redirect loop if we're already on the login page.
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export default client;
