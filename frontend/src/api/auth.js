import client from "./client";

// POST username+password, get back a token, store it.
export async function login(username, password) {
  // Token endpoint is at /api/auth/token/ — note it's NOT behind auth,
  // so we can call it with the shared client (no token yet is fine).
  const { data } = await client.post("/auth/token/", { username, password });
  localStorage.setItem("chronoq_token", data.token);
  return data.token;
}

export function logout() {
  localStorage.removeItem("chronoq_token");
}

export function isAuthenticated() {
  return Boolean(localStorage.getItem("chronoq_token"));
}

// POST new-account details, get back a token, store it (same as login()).
export async function register(username, password, email) {
  const { data } = await client.post("/auth/register/", {
    username,
    password,
    email,
  });
  localStorage.setItem("chronoq_token", data.token);
  return data.token;
}

// Public: whether self-service registration is enabled on the backend.
export async function fetchRegistrationEnabled() {
  try {
    const { data } = await client.get("/auth/config/");
    return Boolean(data.registration_enabled);
  } catch {
    return false;
  }
}
