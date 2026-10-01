// Load test for the deployed site, run with k6 (https://k6.io).
//
//   k6 run -e BASE=https://gabai.help -e STAFF_EMAIL=... -e STAFF_PASSWORD=... \
//          -e RESIDENT_EMAIL=... -e RESIDENT_PASSWORD=... tests/load/load_test.js
//
// Use a staff account and an approved resident account made for testing, both
// already past the terms screen. The "browse" scenario only reads. The "submit"
// scenario creates 10 requests marked LOAD TEST; staff close them afterwards.

import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";

const BASE = __ENV.BASE || "https://gabai.help";
const classification = new Trend("classification_seconds");

export const options = {
  noCookiesReset: true,
  scenarios: {
    browse: {
      executor: "ramping-vus",
      exec: "browse",
      stages: [
        { duration: "30s", target: 20 },
        { duration: "1m", target: 20 },
        { duration: "15s", target: 0 },
      ],
    },
    submit: {
      executor: "per-vu-iterations",
      exec: "submit",
      vus: 1,
      iterations: 10,
      startTime: "40s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    checks: ["rate>0.99"],
    "http_req_duration{scenario:browse}": ["p(95)<2000"],
  },
};

function signIn(email, password) {
  const res = http.post(`${BASE}/api/auth/login`, { username: email, password: password });
  check(res, { "signed in": (r) => r.status === 204 });
}

// Staff sessions on one test account opening the site, the queue and notifications.
export function browse() {
  if (__ITER === 0) signIn(__ENV.STAFF_EMAIL, __ENV.STAFF_PASSWORD);
  check(http.get(`${BASE}/`), { "home page": (r) => r.status === 200 });
  check(http.get(`${BASE}/api/site`), { "site details": (r) => r.status === 200 });
  check(http.get(`${BASE}/api/requests?status=routed&status=in_progress&status=classified`), { "queue": (r) => r.status === 200 });
  check(http.get(`${BASE}/api/notifications?limit=20`), { "notifications": (r) => r.status === 200 });
  sleep(1 + Math.random() * 2);
}

// A resident submitting a request, timed until the system has sorted it.
export function submit() {
  if (__ITER === 0) signIn(__ENV.RESIDENT_EMAIL, __ENV.RESIDENT_PASSWORD);
  const body = JSON.stringify({
    description: `LOAD TEST ${__ITER + 1}: May malaking butas sa kalsada sa harap ng barangay hall, delikado na sa gabi.`,
  });
  const res = http.post(`${BASE}/api/requests`, body, { headers: { "Content-Type": "application/json" } });
  if (!check(res, { "request accepted": (r) => r.status === 201 })) return;
  const id = res.json("id");
  const started = Date.now();
  for (let i = 0; i < 30; i++) {
    sleep(0.5);
    const r = http.get(`${BASE}/api/requests/${id}`, { tags: { name: "request detail" } });
    const status = r.status === 200 ? r.json("status") : null;
    if (status && status !== "submitted") {
      classification.add((Date.now() - started) / 1000);
      return;
    }
  }
  check(null, { "sorted within 15 s": () => false });
}
