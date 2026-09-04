// Uji beban jalur verifikasi QR RSA-PSS dari host terpisah.
//
//   k6 run uji_beban.js
//
// Empat tingkat berurutan meniru Tabel VII: 100, 500, 1.000, 1.500 pengguna.
//
// AMBANG PER TINGKAT sengaja dipasang bukan untuk lulus-gagal, melainkan agar
// k6 memecah ringkasannya per tingkat beban. Tanpa ini ringkasan hanya memberi
// satu angka gabungan, padahal yang dibutuhkan justru perbandingan antartingkat.
//
// CATATAN TOKEN. Token sekali pakai: verifikasi kedua atas token yang sama
// ditandai replay dan menempuh cabang kode berbeda. Tiap iterasi mengambil
// token unik berurutan. Penghitung iterasi_jalur_replay melaporkan berapa
// iterasi yang terpaksa memutar ulang indeks setelah token habis.
import http from 'k6/http';
import exec from 'k6/execution';
import { check } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import papaparse from 'https://jslib.k6.io/papaparse/5.1.1/index.js';

const BASE = __ENV.BASE || 'https://staging.rsa-pss.com';
const DUR  = __ENV.DUR  || '60s';

const tokens = new SharedArray('token', function () {
  return papaparse.parse(open('./token_uji.csv'), { header: true })
                  .data.filter(r => r.token).map(r => r.token);
});

export const errorRate  = new Rate('error_rate');
export const tokenHabis = new Counter('iterasi_jalur_replay');

function tahap(vus, startTime) {
  return { executor: 'constant-vus', vus: vus, duration: DUR,
           startTime: startTime, tags: { tingkat: String(vus) } };
}

export const options = {
  discardResponseBodies: true,
  scenarios: {
    beban_100:  tahap(100,  '0s'),
    beban_500:  tahap(500,  '70s'),
    beban_1000: tahap(1000, '140s'),
    beban_1500: tahap(1500, '210s'),
  },
  thresholds: {
    'http_req_duration{tingkat:100}':  ['p(95)<60000'],
    'http_req_duration{tingkat:500}':  ['p(95)<60000'],
    'http_req_duration{tingkat:1000}': ['p(95)<60000'],
    'http_req_duration{tingkat:1500}': ['p(95)<60000'],
    'http_req_failed{tingkat:100}':    ['rate<1'],
    'http_req_failed{tingkat:500}':    ['rate<1'],
    'http_req_failed{tingkat:1000}':   ['rate<1'],
    'http_req_failed{tingkat:1500}':   ['rate<1'],
    'http_reqs{tingkat:100}':          ['count>0'],
    'http_reqs{tingkat:500}':          ['count>0'],
    'http_reqs{tingkat:1000}':         ['count>0'],
    'http_reqs{tingkat:1500}':         ['count>0'],
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  const n = exec.scenario.iterationInTest;
  if (n >= tokens.length) tokenHabis.add(1);
  const token = tokens[n % tokens.length];
  const res = http.get(`${BASE}/v/${token}`, { tags: { name: 'verify' } });
  const ok = check(res, { 'status 200': (r) => r.status === 200 });
  errorRate.add(!ok);
}
