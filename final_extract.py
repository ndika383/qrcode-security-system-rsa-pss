import sqlite3
import json
import statistics
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
db_path = BASE_DIR / 'data' / 'testing' / 'testing_results.db'

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM test_sessions WHERE status='completed' ORDER BY created_at ASC")
rows = cursor.fetchall()

print("CORRECTED DATA FOR JOURNAL UPDATE")
print("="*120)

# TABLE 8: Normal Operations
print("\nTABLE 8: NORMAL OPERATIONS")
print("="*120)

normal_sessions = [dict(r) for r in rows if r['test_type'] == 'normal_operations']
for i, s in enumerate(normal_sessions, 1):
    r = json.loads(s['results_json'])
    # Times are in seconds, convert to ms
    avg_sign_ms = r.get('avg_signing_time', 0) * 1000
    avg_ver_ms = r.get('avg_verification_time', 0) * 1000
    p95_sign_ms = r.get('p95_signing_time', 0) * 1000
    p95_ver_ms = r.get('p95_verification_time', 0) * 1000
    
    print(f"Session {i}: Signing={avg_sign_ms:.2f}ms, Verification={avg_ver_ms:.2f}ms, P95 Sign={p95_sign_ms:.2f}ms, P95 Verify={p95_ver_ms:.2f}ms")

# TABLE 9a: Replay Attack  
print("\n\nTABLE 9a: REPLAY ATTACK DETECTION")
print("="*120)

replay_sessions = [dict(r) for r in rows if r['test_type'] == 'replay_attack']
total_det = sum(r.get('detected_replays', 0) for r in [json.loads(s['results_json']) for s in replay_sessions])
total_att = sum(s['total_operations'] for s in replay_sessions)

for i, s in enumerate(replay_sessions, 1):
    r = json.loads(s['results_json'])
    det = r.get('detected_replays', 0)
    att = s['total_operations']
    fpr = r.get('false_positive_rate', 0) * 100  # Already as decimal
    fnr = r.get('false_negative_rate', 0) * 100
    print(f"Session {i}: {att:,} attempts, Detected={det:,} ({det/att*100:.1f}%), FPR={fpr:.2f}%, FNR={fnr:.2f}%")

print(f"TOTAL: {total_att:,} attempts, Detected={total_det:,} ({total_det/total_att*100:.1f}%)")

# TABLE 9b: Data Tampering
print("\n\nTABLE 9b: DATA TAMPERING DETECTION")
print("="*120)

tamp_s = dict([r for r in rows if r['test_type'] == 'data_tampering'][0])
r_t = json.loads(tamp_s['results_json'])
total_t = r_t.get('total_operations', 50000)
det_t = r_t.get('detected_tampering', 0)
miss_t = r_t.get('missed_tampering', 0)
int_v = r_t.get('integrity_violations', 0)
rate_t = r_t.get('detection_rate', 0)
crit_t = r_t.get('critical_detection_rate', 0)
types_t = r_t.get('tampering_types', {})

print(f"Total: {total_t:,}, Detected: {det_t:,}, Missed: {miss_t:,}")
print(f"Integrity Violations: {int_v}")
print(f"Detection Rate: {rate_t:.1f}%, Critical Detection: {crit_t:.1f}%")
print(f"Types: {json.dumps(types_t, indent=2)}")

# TABLE 9c: Signature Forgery
print("\n\nTABLE 9c: SIGNATURE FORGERY DETECTION")
print("="*120)

forgery_s = [dict(r) for r in rows if r['test_type'] == 'signature_forgery']
total_rej = 0
total_forg_att = 0
total_crypto = 0

for i, s in enumerate(forgery_s, 1):
    r = json.loads(s['results_json'])
    rej = r.get('rejected_forgeries', 0)
    att = s['total_operations']
    crypto = r.get('cryptographic_failures', 0)
    total_rej += rej
    total_forg_att += att
    total_crypto += crypto
    print(f"Session {i}: {att:,} attempts, Rejected={rej:,} ({rej/att*100:.2f}%), Crypto Failures={crypto}")

print(f"TOTAL: {total_forg_att:,} attempts, Rejected={total_rej:,} ({total_rej/total_forg_att*100:.2f}%)")
print(f"Total Cryptographic Failures: {total_crypto}")

# TABLE 10: Stress Testing
print("\n\nTABLE 10: STRESS TESTING")
print("="*120)

stress_s = dict([r for r in rows if r['test_type'] == 'stress_test'][0])
r_st = json.loads(stress_s['results_json'])
resp = r_st.get('response_time_by_user_count', {})
err = r_st.get('error_rate_by_user_count', {})
succ = r_st.get('success_rate_by_user_count', {})
cpu_base = r_st.get('resource_utilization', {}).get('baseline_cpu', 0)
mem_base = r_st.get('resource_utilization', {}).get('baseline_memory_mb', 0)

# Calculate approximate CPU/Memory from lists
cpu_list = r_st.get('resource_utilization', {}).get('cpu', [])
mem_list = r_st.get('resource_utilization', {}).get('memory', [])

print(f"{'Users':>10} {'Response (ms)':>15} {'Error Rate':>12} {'Success Rate':>14}")
print("-"*60)

# Response times in seconds, convert to ms
for users in [100, 500, 1000, 1500]:
    r_ms = resp.get(str(users), 0) * 1000
    e = err.get(str(users), 0)  # Already in percentage
    s = succ.get(str(users), 0)  # Already in percentage
    print(f"{users:>10,} {r_ms:>15.2f} {e:>11.2f}% {s:>13.2f}%")

print(f"\nBaseline CPU: {cpu_base:.1f}%, Baseline Memory: {mem_base:.2f} MB")
print(f"CPU samples range: {min(cpu_list) if cpu_list else 0:.1f}% - {max(cpu_list) if cpu_list else 0:.1f}%")
print(f"Memory samples range: {min(mem_list) if mem_list else 0:.2f} - {max(mem_list) if mem_list else 0:.2f} MB")

print("\n" + "="*120)
print("JOURNAL UPDATE SUMMARY")
print("="*120)

norm_avg_sign = statistics.mean([json.loads(s['results_json']).get('avg_signing_time', 0)*1000 for s in normal_sessions])
norm_avg_ver = statistics.mean([json.loads(s['results_json']).get('avg_verification_time', 0)*1000 for s in normal_sessions])

print(f"\nSigning Time: {norm_avg_sign:.2f} ms")
print(f"Verification Time: {norm_avg_ver:.2f} ms")
print(f"Replay Detection: {total_det/total_att*100:.1f}% ({total_det:,}/{total_att:,})")
print(f"Tampering Detection: {rate_t:.1f}% ({det_t:,}/{total_t:,})")
print(f"Integrity Violations: {int_v}")
print(f"Forgery Rejection: {total_rej/total_forg_att*100:.1f}% ({total_rej:,}/{total_forg_att:,})")
print(f"Cryptographic Failures: {total_crypto}")

# Find max users with <2% error
for users in [100, 500, 1000, 1500]:
    e = err.get(str(users), 0)
    if e < 2:
        print(f"Max users <2% error: {users} (error: {e:.2f}%)")

conn.close()
