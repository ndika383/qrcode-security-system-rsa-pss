"""
export_test_data.py - Export semua data pengujian ke CSV dan buat tabel ringkasan
Data mentah dari testing_results.db untuk lampiran paper.

Aturan berkas ini: tidak ada nilai hasil pengujian yang ditulis sebagai
literal. Semua angka dihitung ulang dari testing_results.db (dan berkas
kalibrasi) setiap kali skrip dijalankan, supaya tabel tidak pernah lagi
memuat angka dari basis data yang sudah diganti.
"""

import sqlite3
import json
import csv
import os
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
db_path = BASE_DIR / 'data' / 'testing' / 'testing_results.db'
output_dir = BASE_DIR / 'jurnal'
os.makedirs(output_dir, exist_ok=True)

print("=" * 70)
print("EXPORT DATA PENGUJIAN KE CSV")
print("=" * 70)

# Connect to database
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# ============================================================
# 1. EXPORT SEMUA SESI PENGUJIAN KE CSV
# ============================================================
print("\n[1/6] Exporting test sessions summary...")

cursor.execute("""
    SELECT id, session_id, test_type, test_name, start_time, end_time, 
           status, total_operations, completed_operations, progress, 
           error_message, created_at, timeout_seconds, results_json
    FROM test_sessions 
    WHERE test_type != 'comprehensive'
    ORDER BY test_type, id
""")

sessions = cursor.fetchall()

csv_sessions = os.path.join(output_dir, 'data_sessions_pengujian.csv')
with open(csv_sessions, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'No', 'Session ID', 'Test Type', 'Test Name', 'Start Time', 'End Time',
        'Status', 'Total Operations', 'Completed Operations', 'Progress (%)',
        'Error Message', 'Created At', 'Timeout (seconds)'
    ])
    
    for i, s in enumerate(sessions, 1):
        writer.writerow([
            i, s['session_id'], s['test_type'], s['test_name'],
            s['start_time'], s['end_time'], s['status'],
            s['total_operations'], s['completed_operations'], s['progress'],
            s['error_message'] or '', s['created_at'], s['timeout_seconds']
        ])

print(f"  ✅ Saved: {csv_sessions} ({len(sessions)} sessions)")

# ============================================================
# 2. EXPORT METRIK DETIL PER SESI KE CSV
# ============================================================
print("\n[2/6] Exporting detailed metrics per session...")

csv_metrics = os.path.join(output_dir, 'data_metrik_detil_pengujian.csv')

with open(csv_metrics, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Test Type', 'Session Name', 'Total Operations', 'Status',
        'Avg Time (ms)', 'Median Time (ms)', 'Min Time (ms)', 'Max Time (ms)',
        'P95 Time (ms)', 'Std Dev (ms)', 'Success Count', 'Success Rate (%)',
        'Detection Rate (%)', 'False Positive Rate (%)', 'False Negative Rate (%)'
    ])
    
    for s in sessions:
        if not s['results_json'] or s['results_json'] == '{}':
            continue
        
        results = json.loads(s['results_json'])
        ttype = s['test_type']
        
        row = [
            ttype, s['test_name'], s['total_operations'], s['status'],
            '', '', '', '', '', '', '', '', '', '', ''
        ]
        
        if ttype == 'normal_operations':
            signing = results.get('signing_times', [])
            verify = results.get('verification_times', [])
            
            if signing:
                row[4] = round(statistics.mean(signing) * 1000, 2)
                row[5] = round(statistics.median(signing) * 1000, 2)
                row[6] = round(min(signing) * 1000, 2)
                row[7] = round(max(signing) * 1000, 2)
                row[8] = round(results.get('p95_signing_time', 0) * 1000, 2)
                row[9] = round(statistics.stdev(signing) * 1000, 2) if len(signing) > 1 else 0
                row[10] = results.get('signing_success', 0)
                row[11] = results.get('signing_success_rate', 0)
            writer.writerow(row)
            
            if verify:
                row_copy = row.copy()
                row_copy[4] = round(statistics.mean(verify) * 1000, 2)
                row_copy[5] = round(statistics.median(verify) * 1000, 2)
                row_copy[6] = round(min(verify) * 1000, 2)
                row_copy[7] = round(max(verify) * 1000, 2)
                row_copy[8] = round(results.get('p95_verification_time', 0) * 1000, 2)
                row_copy[9] = round(statistics.stdev(verify) * 1000, 2) if len(verify) > 1 else 0
                row_copy[10] = results.get('verification_success', 0)
                row_copy[11] = results.get('verification_success_rate', 0)
                row_copy[3] = f"{s['status']} (verification)"
                writer.writerow(row_copy)
        
        elif ttype == 'replay_attack':
            det = results.get('detection_times', [])
            if det:
                row[4] = round(statistics.mean(det), 2)
                row[5] = round(statistics.median(det), 2)
                row[6] = round(min(det), 2)
                row[7] = round(max(det), 2)
                row[8] = results.get('p95_detection_latency_ms', 0)
                row[9] = round(statistics.stdev(det), 2) if len(det) > 1 else 0
                
                detected = results.get('detected_replays', 0)
                missed = results.get('missed_replays', 0)
                total = detected + missed
                row[12] = round((detected / total * 100) if total > 0 else 0, 2)
                row[13] = round((results.get('false_positives', 0) / total * 100) if total > 0 else 0, 2)
                row[14] = round((results.get('false_negatives', 0) / total * 100) if total > 0 else 0, 2)
                writer.writerow(row)
        
        elif ttype == 'data_tampering':
            det = results.get('detection_times', [])
            if det:
                row[4] = round(statistics.mean(det), 2)
                row[5] = round(statistics.median(det), 2)
                row[6] = round(min(det), 2)
                row[7] = round(max(det), 2)
                
                detected = results.get('detected_tampering', 0)
                missed = results.get('missed_tampering', 0)
                total = detected + missed
                row[12] = round((detected / total * 100) if total > 0 else 0, 2)
                writer.writerow(row)
        
        elif ttype == 'signature_forgery':
            ver = results.get('verification_times', [])
            if ver:
                row[4] = round(statistics.mean(ver), 2)
                row[5] = round(statistics.median(ver), 2)
                row[6] = round(min(ver), 2)
                row[7] = round(max(ver), 2)
                
                rejected = results.get('rejected_forgeries', 0)
                accepted = results.get('accepted_forgeries', 0)
                total = rejected + accepted
                row[12] = round((rejected / total * 100) if total > 0 else 0, 2)
                writer.writerow(row)
        
        elif ttype == 'stress_test':
            stress = results.get('stress_times', [])
            if stress:
                row[4] = round(statistics.mean(stress) * 1000, 2)
                row[5] = round(statistics.median(stress) * 1000, 2)
                row[6] = round(min(stress) * 1000, 2)
                row[7] = round(max(stress) * 1000, 2)
                row[8] = round(results.get('p95_stress_time', 0) * 1000, 2)
                row[9] = round(statistics.stdev(stress) * 1000, 2) if len(stress) > 1 else 0
                writer.writerow(row)
            
            # Also export response times by user count
            resp_by_users = results.get('response_time_by_user_count', {})
            err_by_users = results.get('error_rate_by_user_count', {})
            succ_by_users = results.get('success_rate_by_user_count', {})
            
            for users in sorted([int(k) for k in resp_by_users.keys()]):
                row_copy = row.copy()
                row_copy[3] = f"{s['status']} ({users} users)"
                row_copy[4] = round(resp_by_users[str(users)] * 1000, 2)
                row_copy[12] = round((100 - err_by_users.get(str(users), 0)), 2)  # detection rate column reused for success rate
                row_copy[13] = round(err_by_users.get(str(users), 0), 2)
                writer.writerow(row_copy)

print(f"  ✅ Saved: {csv_metrics}")

# ============================================================
# 3. EXPORT DETECTION RATES PER JENIS SERANGAN KE CSV
# ============================================================
print("\n[3/6] Exporting detection rates by attack type...")

csv_attacks = os.path.join(output_dir, 'data_deteksi_per_jenis_serangan.csv')

with open(csv_attacks, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Category', 'Attack Type', 'Total Attempts', 'Detected/Rejected', 
        'Missed/Accepted', 'Detection Rate (%)', 'False Positive Rate (%)',
        'False Negative Rate (%)'
    ])
    
    # Replay Attack by pattern
    for s in sessions:
        if s['test_type'] == 'replay_attack' and s['results_json'] and s['results_json'] != '{}':
            results = json.loads(s['results_json'])
            det_by_pattern = results.get('detection_by_pattern', {})
            
            for pattern, data in det_by_pattern.items():
                writer.writerow([
                    'Replay Attack (CAPEC-121)',
                    pattern.replace('_', ' ').title(),
                    data.get('total_operations', 0),
                    data.get('detected', 0),
                    data.get('missed', 0),
                    round(data.get('detection_rate', 0), 2),
                    round(data.get('false_positive_rate', 0) * 100, 2),
                    round(data.get('false_negative_rate', 0) * 100, 2)
                ])
    
    # Data Tampering by type
    for s in sessions:
        if s['test_type'] == 'data_tampering' and s['results_json'] and s['results_json'] != '{}':
            results = json.loads(s['results_json'])
            det_by_type = results.get('detection_by_type', {})
            
            for ttype, data in det_by_type.items():
                writer.writerow([
                    'Data Tampering (CAPEC-440)',
                    ttype.replace('_', ' ').title(),
                    data.get('total', 0),
                    data.get('detected', 0),
                    data.get('missed', 0),
                    round(data.get('detection_rate', 0), 2),
                    '', ''
                ])
    
    # Signature Forgery by type
    for s in sessions:
        if s['test_type'] == 'signature_forgery' and s['results_json'] and s['results_json'] != '{}':
            results = json.loads(s['results_json'])
            alg_perf = results.get('algorithm_performance', {})
            
            for alg, data in alg_perf.items():
                writer.writerow([
                    'Signature Forgery (CAPEC-538)',
                    f"{alg} Forgery",
                    data.get('attempts', 0),
                    data.get('rejected', 0),
                    data.get('accepted', 0),
                    round(data.get('rejection_rate', 0), 2),
                    '', ''
                ])

print(f"  ✅ Saved: {csv_attacks}")

# ============================================================
# 4. EXPORT SKALABILITAS (STRESS TEST) KE CSV
# ============================================================
print("\n[4/6] Exporting scalability data...")

csv_scalability = os.path.join(output_dir, 'data_skalabilitas_stress_test.csv')

with open(csv_scalability, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Concurrent Users', 'Avg Response Time (ms)', 'Error Rate (%)', 
        'Success Rate (%)', 'Throughput (ops/sec)', 'CPU Usage (%)',
        'Memory Usage (MB)'
    ])
    
    for s in sessions:
        if s['test_type'] == 'stress_test' and s['results_json'] and s['results_json'] != '{}':
            results = json.loads(s['results_json'])
            
            resp = results.get('response_time_by_user_count', {})
            err = results.get('error_rate_by_user_count', {})
            succ = results.get('success_rate_by_user_count', {})
            throughput = results.get('throughput_per_user_count', {})
            resource = results.get('resource_utilization', {})
            
            for users in sorted([int(k) for k in resp.keys()]):
                cpu = resource.get('cpu', [])[list(resp.keys()).index(str(users))] if len(resource.get('cpu', [])) > list(resp.keys()).index(str(users)) else ''
                mem = resource.get('memory', [])[list(resp.keys()).index(str(users))] if len(resource.get('memory', [])) > list(resp.keys()).index(str(users)) else ''
                
                writer.writerow([
                    users,
                    round(resp[str(users)] * 1000, 2),
                    round(err.get(str(users), 0), 2),
                    round(succ.get(str(users), 0), 2),
                    round(throughput.get(str(users), 0), 2),
                    round(cpu, 2) if cpu else '',
                    round(mem, 2) if mem else ''
                ])

print(f"  ✅ Saved: {csv_scalability}")

# ============================================================
# 5. AGREGASI METRIK UNTUK TABEL RINGKASAN
# ============================================================
# Semua angka pada tabel ringkasan dihitung ulang dari sumbernya setiap kali
# skrip dijalankan. Jangan menulis nilai hasil pengujian sebagai literal di
# sini: versi lama skrip ini menyalin angka dari basis data yang sudah
# diganti, sehingga tabel melaporkan error rate 0,79% @500 pengguna padahal
# sesi 23 Juli 2026 mencatat 1,78%.
print("\n[5/6] Aggregating metrics...")


def _results(session_row):
    if not session_row['results_json'] or session_row['results_json'] == '{}':
        return None
    return json.loads(session_row['results_json'])


def _pct(part, total):
    return (part / total * 100) if total else None


def _status(value, target, lower_is_better, band=0.10):
    """Verdict terhadap target; 'band' = toleransi relatif untuk 'Mendekati'."""
    if value is None:
        return 'N/A'
    if lower_is_better:
        if value <= target:
            return '✅ Tercapai'
        return '⚠️ Mendekati' if value <= target * (1 + band) else '❌ Perlu Optimasi'
    if value >= target:
        return '✅ Tercapai'
    return '⚠️ Mendekati' if value >= target * (1 - band) else '❌ Perlu Optimasi'


norm_ok = norm_total = 0
replay_detected = replay_total = 0
tamper_detected = tamper_total = 0
forgery_rejected = forgery_total = 0
stress_error_by_users = {}
stress_overall_error = None

for s in sessions:
    r = _results(s)
    if not r:
        continue
    ttype = s['test_type']
    if ttype == 'normal_operations':
        norm_ok += r.get('signing_success', 0) + r.get('verification_success', 0)
        norm_total += len(r.get('signing_times', [])) + len(r.get('verification_times', []))
    elif ttype == 'replay_attack':
        replay_detected += r.get('detected_replays', 0)
        replay_total += r.get('detected_replays', 0) + r.get('missed_replays', 0)
    elif ttype == 'data_tampering':
        tamper_detected += r.get('detected_tampering', 0)
        tamper_total += r.get('detected_tampering', 0) + r.get('missed_tampering', 0)
    elif ttype == 'signature_forgery':
        forgery_rejected += r.get('rejected_forgeries', 0)
        forgery_total += r.get('rejected_forgeries', 0) + r.get('accepted_forgeries', 0)
    elif ttype == 'stress_test':
        for users, err in r.get('error_rate_by_user_count', {}).items():
            stress_error_by_users[int(users)] = err
        stress_overall_error = r.get('overall_error_rate', stress_overall_error)

normal_success_rate = _pct(norm_ok, norm_total)
replay_rate = _pct(replay_detected, replay_total)
tamper_rate = _pct(tamper_detected, tamper_total)
forgery_rate = _pct(forgery_rejected, forgery_total)
total_operations = sum(s['total_operations'] or 0 for s in sessions)
status_counts = Counter(s['status'] for s in sessions)

# Waktu signing/verifikasi diambil dari berkas kalibrasi, BUKAN dari
# testing_results.db: sesi normal_operations di basis data hanya merekam
# micro-sleep pengganti operasi kripto (lihat _run_normal_operations_test
# pada modules/testing_controller.py), jadi durasinya bukan waktu RSA-PSS.
calib_path = BASE_DIR / 'data' / 'calibration' / 'multi_scenario_calibration.json'
crypto = {}
calib_date = ''
if calib_path.exists():
    with open(calib_path, encoding='utf-8') as cf:
        calib = json.load(cf)
    rsa = calib.get('benchmark_results', {}).get('rsa_pss_2048', {})
    for op in ('signing', 'verification'):
        if rsa.get(op):
            crypto[op] = rsa[op]
    calib_date = calib.get('metadata', {}).get('calibration_date', '')
    print(f"  ✅ Kalibrasi RSA-PSS 2048 dimuat ({calib_date or 'tanpa tanggal'})")
else:
    print(f"  ⚠️  Kalibrasi tidak ditemukan: {calib_path}")

# Metrik yang tidak punya sumber terukur di repositori ini. Sengaja tidak
# dicetak sebagai angka supaya tidak lagi beredar sebagai 'hasil pengujian'.
METRIK_TANPA_SUMBER = [
    'Ukuran signature (bit) dan efisiensi terhadap RSA baku',
    'Laju deteksi replay pada data produksi',
    'Pernyataan kepatuhan ISO/IEC 20248:2022',
]


def _hitung_baris(path):
    """Jumlah baris data sebuah CSV (tanpa header), None bila tidak ada."""
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8', errors='replace') as lf:
        return max(0, sum(1 for _ in lf) - 1)


def _hitung_entri_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as jf:
            return len(json.load(jf))
    except (ValueError, TypeError):
        return None


# ============================================================
# 6. BUAT TABEL RINGKASAN (MARKDOWN)
# ============================================================
print("\n[6/6] Creating summary table...")

summary_md = os.path.join(output_dir, 'TABEL_HASIL_PENGUJIAN_LENGKAP.md')

with open(summary_md, 'w', encoding='utf-8') as f:
    f.write("# TABEL HASIL PENGUJIAN LENGKAP\n")
    f.write("# Data Mentah dari testing_results.db\n")
    f.write(f"# Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}\n\n")
    
    f.write("---\n\n")
    f.write("## DAFTAR FILE CSV DATA MENTAH\n\n")
    f.write("| File | Isi | Jumlah Baris |\n")
    f.write("|---|---|---:|\n")
    for nama, isi in [
        ('data_sessions_pengujian.csv', 'Ringkasan sesi pengujian'),
        ('data_metrik_detil_pengujian.csv', 'Metrik detil per sesi (timing, success rate)'),
        ('data_deteksi_per_jenis_serangan.csv', 'Laju deteksi per jenis serangan'),
        ('data_skalabilitas_stress_test.csv', 'Skalabilitas stress test per tingkat beban'),
    ]:
        n = _hitung_baris(os.path.join(output_dir, nama))
        f.write(f"| `{nama}` | {isi} | " + (f"{n:,} |\n" if n is not None else "– |\n"))
    f.write("\n")
    
    f.write("---\n\n")
    f.write("## TABEL 1: RINGKASAN SESI PENGUJIAN\n\n")
    f.write("| No | Test Type | Session Name | Operations | Status |\n")
    f.write("|---|---|---|---:|---|\n")
    for i, s in enumerate(sessions, 1):
        f.write(f"| {i} | {s['test_type']} | {s['test_name']} | {s['total_operations']:,} | {s['status']} |\n")
    
    ringkas_status = ' | '.join(f"**{k.title()}: {v}**" for k, v in sorted(status_counts.items()))
    f.write(f"\n**Total Operasi: {total_operations:,}** | **Sesi: {len(sessions)}** | {ringkas_status}\n\n")
    
    f.write("---\n\n")
    f.write("## TABEL 2: METRIK KINERJA UTAMA\n\n")
    f.write("| Skenario | Metrik | Nilai | Target | Status | Sumber |\n")
    f.write("|---|---|---|---|---|---|\n")
    if crypto.get('signing'):
        c = crypto['signing']
        f.write(f"| RSA-PSS 2048 | Signing Time | {c['mean']:.2f} ± {c['std']:.2f} ms | ≤400 ms | "
                f"{_status(c['mean'], 400, True)} | kalibrasi ({c.get('samples', 0):,} sampel) |\n")
    if crypto.get('verification'):
        c = crypto['verification']
        f.write(f"| RSA-PSS 2048 | Verification Time | {c['mean']:.2f} ± {c['std']:.2f} ms | ≤200 ms | "
                f"{_status(c['mean'], 200, True)} | kalibrasi ({c.get('samples', 0):,} sampel) |\n")
    if normal_success_rate is not None:
        f.write(f"| Normal Operations | Success Rate | {normal_success_rate:.2f}% | ≥99% | "
                f"{_status(normal_success_rate, 99, False)} | testing_results.db |\n")
    if replay_rate is not None:
        f.write(f"| Replay Attack | Detection Rate | {replay_rate:.2f}% | ≥98% | "
                f"{_status(replay_rate, 98, False)} | testing_results.db |\n")
    if tamper_rate is not None:
        f.write(f"| Data Tampering | Detection Accuracy | {tamper_rate:.2f}% | ≥85% | "
                f"{_status(tamper_rate, 85, False)} | testing_results.db |\n")
    if forgery_rate is not None:
        f.write(f"| Signature Forgery | Rejection Rate | {forgery_rate:.2f}% | ≥99.9% | "
                f"{_status(forgery_rate, 99.9, False)} | testing_results.db |\n")
    for users in sorted(stress_error_by_users):
        err = stress_error_by_users[users]
        f.write(f"| Stress Test @{users} users | Error Rate | {err:.2f}% | <2% | "
                f"{_status(err, 2, True)} | testing_results.db |\n")
    if stress_overall_error is not None:
        f.write(f"| Stress Test (agregat) | Error Rate | {stress_overall_error:.2f}% | <2% | "
                f"{_status(stress_overall_error, 2, True)} | testing_results.db |\n")
    f.write("\n")
    f.write("> Baris stress test berasal dari beban simulasi in-process. Baris `@N users` "
            "hanya mencakup tingkat beban tersebut, sedangkan baris agregat mencakup "
            "seluruh tingkat beban sekaligus — dua angka yang berbeda cakupan, bukan "
            "dua angka yang bertentangan.\n\n")
    f.write("> Tidak dicetak di tabel ini karena tidak punya sumber terukur di repositori: "
            + "; ".join(METRIK_TANPA_SUMBER) + ".\n\n")
    
    f.write("---\n\n")
    f.write("## TABEL 3: DETEKSI PER JENIS SERANGAN\n\n")
    
    # Replay by pattern
    f.write("### Replay Attack (CAPEC-121)\n\n")
    f.write("| Pattern | Total | Detected | Missed | Rate (%) |\n")
    f.write("|---|---:|---:|---:|---:|\n")
    for s in sessions:
        if s['test_type'] == 'replay_attack' and s['results_json'] and s['results_json'] != '{}':
            results = json.loads(s['results_json'])
            for pattern, data in results.get('detection_by_pattern', {}).items():
                f.write(f"| {pattern.replace('_', ' ').title()} | {data.get('total_operations', 0):,} | {data.get('detected', 0):,} | {data.get('missed', 0):,} | {data.get('detection_rate', 0):.1f}% |\n")
    
    # Tampering by type
    f.write("\n### Data Tampering (CAPEC-440)\n\n")
    f.write("| Type | Total | Detected | Missed | Rate (%) |\n")
    f.write("|---|---:|---:|---:|---:|\n")
    for s in sessions:
        if s['test_type'] == 'data_tampering' and s['results_json'] and s['results_json'] != '{}':
            results = json.loads(s['results_json'])
            for ttype, data in results.get('detection_by_type', {}).items():
                f.write(f"| {ttype.replace('_', ' ').title()} | {data.get('total', 0):,} | {data.get('detected', 0):,} | {data.get('missed', 0):,} | {data.get('detection_rate', 0):.1f}% |\n")
    
    # Forgery by type
    f.write("\n### Signature Forgery (CAPEC-538)\n\n")
    f.write("| Algorithm | Attempts | Rejected | Accepted | Rate (%) |\n")
    f.write("|---|---:|---:|---:|---:|\n")
    for s in sessions:
        if s['test_type'] == 'signature_forgery' and s['results_json'] and s['results_json'] != '{}':
            results = json.loads(s['results_json'])
            for alg, data in results.get('algorithm_performance', {}).items():
                f.write(f"| {alg} | {data.get('attempts', 0):,} | {data.get('rejected', 0):,} | {data.get('accepted', 0):,} | {data.get('rejection_rate', 0):.2f}% |\n")
    
    f.write("\n---\n\n")
    f.write("## TABEL 4: SKALABILITAS (STRESS TEST)\n\n")
    f.write("| Concurrent Users | Avg Response (ms) | Error Rate (%) | Success Rate (%) |\n")
    f.write("|---:|---:|---:|---:|\n")
    for s in sessions:
        if s['test_type'] == 'stress_test' and s['results_json'] and s['results_json'] != '{}':
            results = json.loads(s['results_json'])
            resp = results.get('response_time_by_user_count', {})
            err = results.get('error_rate_by_user_count', {})
            succ = results.get('success_rate_by_user_count', {})
            for users in sorted([int(k) for k in resp.keys()]):
                f.write(f"| {users} | {resp[str(users)]*1000:.2f} | {err.get(str(users), 0):.2f}% | {succ.get(str(users), 0):.2f}% |\n")
    
    f.write("\n---\n\n")
    f.write("## TABEL 5: PERBANDINGAN DENGAN PENELITIAN TERDAHULU\n\n")
    # Kolom penelitian terdahulu adalah kutipan literatur (tetap literal).
    # Kolom "Penelitian Ini" selalu dihitung dari sumber terukur.
    def _num(nilai, digit=2):
        return f"{nilai:.{digit}f}" if nilai is not None else 'N/A'

    lolos_2persen = [u for u, e in stress_error_by_users.items() if e < 2]
    if lolos_2persen:
        u = max(lolos_2persen)
        skalabilitas = f"{u} (err {stress_error_by_users[u]:.2f}%)"
    else:
        skalabilitas = 'N/A'

    f.write("| Kriteria | **Penelitian Ini** | Lorien & Wellem (2021) | Nuraeni et al. (2024) | Almousa et al. (2024) |\n")
    f.write("|---|---:|---:|---:|---:|\n")
    f.write("| **Metode** | **RSA-PSS + Nonce-TS** | SHA-256 + RSA | RSA + AES-128 | Dual ML |\n")
    f.write(f"| **Signing Time (ms)** | **{_num(crypto.get('signing', {}).get('mean'))}** | ~500 | ~600 | N/A |\n")
    f.write(f"| **Verification Time (ms)** | **{_num(crypto.get('verification', {}).get('mean'))}** | ~250 | ~300 | N/A |\n")
    f.write(f"| **Replay Detection (%)** | **{_num(replay_rate, 1)}** | None | None | None |\n")
    f.write(f"| **Tampering Detection (%)** | **{_num(tamper_rate, 1)}** | 100 | ~95 | 93.50 |\n")
    f.write(f"| **Forgery Rejection (%)** | **{_num(forgery_rate, 1)}** | N/A | N/A | N/A |\n")
    f.write(f"| **Skalabilitas (users)** | **{skalabilitas}** | N/T | N/T | N/T |\n")
    f.write(f"| **Total Operasi Testing** | **{total_operations:,}** | N/R | N/R | N/R |\n")
    f.write("| **Offline Verification** | **Yes** | Yes | Yes | No |\n\n")

    f.write("*Keterangan: N/R = Not Reported; N/T = Not Tested; N/A = Not Applicable*\n\n")
    f.write("*Baris ukuran signature, efisiensi terhadap RSA, dan kepatuhan ISO/IEC 20248:2022 "
            "sengaja tidak dicetak: nilainya tidak dapat dihitung dari sumber mana pun di "
            "repositori ini, jadi harus dilampirkan manual beserta sumbernya.*\n\n")
    
    f.write("---\n\n")
    f.write("## SUMBER DATA\n\n")
    f.write("Semua data di atas diambil langsung dari:\n")
    f.write(f"- `data/testing/testing_results.db` — Basis data pengujian "
            f"({total_operations:,} operasi dalam {len(sessions)} sesi)\n")
    if crypto:
        f.write(f"- `data/calibration/multi_scenario_calibration.json` — Kalibrasi waktu "
                f"RSA-PSS 2048{f' ({calib_date})' if calib_date else ''}\n")
    for label, path in [('Log generate produksi', 'logs/log_generate.csv'),
                        ('Log verifikasi produksi', 'logs/log_verifikasi.csv')]:
        n = _hitung_baris(os.path.join(BASE_DIR, path))
        f.write(f"- `{path}` — {label}" + (f" ({n:,} baris)\n" if n is not None else " (tidak ditemukan)\n"))
    for label, path in [('Log modifikasi', 'logs/modification_logs.json'),
                        ('Log batch modifikasi', 'logs/batch_modification_logs.json')]:
        n = _hitung_entri_json(os.path.join(BASE_DIR, path))
        f.write(f"- `{path}` — {label}" + (f" ({n:,} entri)\n" if n is not None else " (tidak ditemukan)\n"))
    f.write("\n---\n\n")
    f.write(f"*Dibuat: {datetime.now().strftime('%d %B %Y, %H:%M')}*\n")
    f.write("*Seluruh angka dihitung ulang dari sumbernya saat skrip dijalankan.*\n")

print(f"  ✅ Saved: {summary_md}")

conn.close()

print(f"\n{'=' * 70}")
print("SEMUA DATA PENGUJIAN BERHASIL DI-EXPORT!")
print("=" * 70)

# Summary
csv_files = [
    'data_sessions_pengujian.csv',
    'data_metrik_detil_pengujian.csv',
    'data_deteksi_per_jenis_serangan.csv',
    'data_skalabilitas_stress_test.csv'
]

print("\n📊 CSV Files Created:")
for f in csv_files:
    path = os.path.join(output_dir, f)
    if os.path.exists(path):
        size_kb = os.path.getsize(path) / 1024
        with open(path, 'r', encoding='utf-8') as csvf:
            lines = len(csvf.readlines())
        print(f"  ✅ {f}: {size_kb:.1f} KB, {lines} lines")

print(f"\n📄 Summary Table: TABEL_HASIL_PENGUJIAN_LENGKAP.md")
print(f"\n📁 Semua file disimpan di: {output_dir}")
print("\n✅ Ready untuk dilampirkan di paper!")
