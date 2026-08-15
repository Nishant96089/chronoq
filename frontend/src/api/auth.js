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
