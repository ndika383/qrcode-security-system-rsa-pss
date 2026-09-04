// Kalibrasi pendahuluan: memastikan LAPTOP sanggup membangkitkan beban.
//
// Bila laptop yang jenuh lebih dulu, yang terukur adalah laptop, bukan server.
// Jalankan ini sebelum uji_beban.js dan periksa dua hal pada ringkasannya:
//   1. iteration_rate mendekati target (VU / waktu respons rata-rata)
//   2. dropped_iterations bernilai nol
//
//   k6 run uji_kalibrasi.js
import http from 'k6/http';
import { check } from 'k6';
import { SharedArray } from 'k6/data';
import papaparse from 'https://jslib.k6.io/papaparse/5.1.1/index.js';

const BASE = __ENV.BASE || 'https://staging.rsa-pss.com';
const tokens = new SharedArray('token', function () {
  return papaparse.parse(open('./token_uji.csv'), { header: true })
                  .data.filter(r => r.token).map(r => r.token);
});

export const options = {
  discardResponseBodies: true,
  scenarios: { kalibrasi: { executor: 'constant-vus', vus: 50, duration: '30s' } },
  thresholds: { http_req_failed: ['rate<0.01'] },
  summaryTrendStats: ['avg', 'med', 'p(95)', 'max'],
};

export default function () {
  const token = tokens[Math.floor(Math.random() * tokens.length)];
  const res = http.get(`${BASE}/v/${token}`);
  check(res, { 'status 200': (r) => r.status === 200 });
}
