// Load test for the deployed site, run with k6 (https://k6.io).
//
//   k6 run -e BASE=https://gabai.help -e STAFF_EMAIL=... -e STAFF_PASSWORD=... \
//          -e RESIDENT_EMAIL=... -e RESIDENT_PASSWORD=... tests/load/load_test.js
//
// Use a staff account and an approved resident account made for testing, both
// already past the terms screen. The "browse" scenario only reads. The "submit"
// scenario creates 10 requests marked LOAD TEST; staff close them afterwards.
// With -e PHOTO=path/to/photo.jpg each of those requests also uploads that photo
// and downloads it again, so storing and reading an encrypted file is timed.
// Make the photo with tests/load/make_test_photo.py (2 MB, no location data).
// Classification time is only comparable with 4 Oct in the run without PHOTO.

import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";
import crypto from "k6/crypto";

const BASE = __ENV.BASE || "https://gabai.help";
const classification = new Trend("classification_seconds");
const photo = __ENV.PHOTO ? open(__ENV.PHOTO, "b") : null;
const photoHash = photo ? crypto.sha256(photo, "hex") : null;

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
  if (photo) {
    const up = http.post(`${BASE}/api/requests/${id}/attachments`,
      { file: http.file(photo, "photo.jpg", "image/jpeg") }, { tags: { name: "photo upload" } });
    if (check(up, { "photo stored": (r) => r.status === 201 })) {
      const down = http.get(`${BASE}/api/requests/${id}/attachments/${up.json("id")}`, { tags: { name: "photo download" }, responseType: "binary" });
      check(down, { "photo returned unchanged (same SHA-256)": (r) => r.status === 200 && crypto.sha256(r.body, "hex") === photoHash });
    }
  }
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
