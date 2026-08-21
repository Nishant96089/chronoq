import http from "k6/http";
import { check } from "k6";

const API_BASE = __ENV.API_BASE || "http://django:8000";

export const options = {
  vus: 1,
  iterations: 1,
};

export default function () {
  const res = http.post(`${API_BASE}/api/auth/token/`, {
    username: "admin",
    password: "chronoq123",
  });

  // Debug: show exactly what came back.
  console.log(`status: ${res.status}`);
  console.log(`body (first 300 chars): ${res.body.substring(0, 300)}`);

  check(res, {
    "status is 200": (r) => r.status === 200,
  });
}