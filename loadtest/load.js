import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const API_BASE = __ENV.API_BASE || "http://django:8000";

// Custom metrics so we can see per-endpoint behavior, not just aggregate.
const errorRate = new Rate("errors");
const listTrend = new Trend("list_jobs_duration", true);
const createTrend = new Trend("create_job_duration", true);

// Load profile: ramp up in stages so we can watch WHERE it starts to break.
export const options = {
  stages: [
    { duration: "20s", target: 10 },  // warm up to 10 VUs
    { duration: "30s", target: 50 },  // ramp to 50
    { duration: "30s", target: 100 }, // ramp to 100 — likely stress point
    { duration: "20s", target: 0 },   // ramp down
  ],
  thresholds: {
    // These define "acceptable". If violated, k6 marks the test failed —
    // which is exactly what we want to SEE happen under load.
    http_req_duration: ["p(95)<1000"], // 95% of requests under 1s
    errors: ["rate<0.05"],             // under 5% errors
  },
};

// setup() runs ONCE before the test. We get a token here and share it.
export function setup() {
  const res = http.post(`${API_BASE}/api/auth/token/`, {
    username: "admin",
    password: "chronoq123",
  });
  const token = JSON.parse(res.body).token;
  return { token };
}

export default function (data) {
  const headers = {
    Authorization: `Token ${data.token}`,
    "Content-Type": "application/json",
  };

  // --- Read: list jobs (the most common operation) ---
  const listRes = http.get(`${API_BASE}/api/jobs/`, { headers });
  listTrend.add(listRes.timings.duration);
  const listOk = check(listRes, {
    "list status 200": (r) => r.status === 200,
  });
  errorRate.add(!listOk);

  // --- Write: create a job (heavier — involves cron computation + insert) ---
  const payload = JSON.stringify({
    name: `loadtest-${__VU}-${__ITER}`,
    target_url: "https://example.com/hook",
    http_method: "POST",
    schedule_cron: "*/5 * * * *",
    is_active: false, // inactive so we don't actually schedule/fire these
  });
  const createRes = http.post(`${API_BASE}/api/jobs/`, payload, { headers });
  createTrend.add(createRes.timings.duration);
  const createOk = check(createRes, {
    "create status 201": (r) => r.status === 201,
  });
  errorRate.add(!createOk);

  // Small pause so each VU isn't an infinite tight loop.
  sleep(0.5);
}