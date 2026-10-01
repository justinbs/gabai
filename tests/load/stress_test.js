// Stepped stress test for the deployed site, run with k6 (https://k6.io).
//
//   k6 run -e BASE=https://gabai.help -e STAFF_EMAIL=... -e STAFF_PASSWORD=... tests/load/stress_test.js
//
// Read-only. Staff sessions on one test account step up from 20 to 40 to 60 at
// once, one minute each. The run stops early if more than 5% of requests fail.
// Run it outside office hours.

import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "https://gabai.help";

export const options = {
  noCookiesReset: true,
  stages: [
    { duration: "20s", target: 20 },
    { duration: "1m", target: 20 },
    { duration: "20s", target: 40 },
    { duration: "1m", target: 40 },
    { duration: "20s", target: 60 },
    { duration: "1m", target: 60 },
    { duration: "15s", target: 0 },
  ],
  thresholds: {
    http_req_failed: [{ threshold: "rate<0.05", abortOnFail: true, delayAbortEval: "30s" }],
    http_req_duration: ["p(95)<2000"],
  },
};

export default function () {
  if (__ITER === 0) {
    const res = http.post(`${BASE}/api/auth/login`, { username: __ENV.STAFF_EMAIL, password: __ENV.STAFF_PASSWORD });
    check(res, { "signed in": (r) => r.status === 204 });
  }
  check(http.get(`${BASE}/`), { "home page": (r) => r.status === 200 });
  check(http.get(`${BASE}/api/site`), { "site details": (r) => r.status === 200 });
  check(http.get(`${BASE}/api/requests?status=routed&status=in_progress&status=classified`), { "queue": (r) => r.status === 200 });
  check(http.get(`${BASE}/api/notifications?limit=20`), { "notifications": (r) => r.status === 200 });
  sleep(1 + Math.random() * 2);
}
