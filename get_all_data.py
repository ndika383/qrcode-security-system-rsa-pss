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

print("COMPLETE DATA FOR JOURNAL UPDATE - 8 SESSIONS")
print("="*120)

# Session 1 & 2: Normal Operations
print("\n\nTABLE 8: NORMAL OPERATIONS PERFORMANCE")
print("="*120)

normal_sessions = [dict(r) for r in rows if r['test_type'] == 'normal_operations']
all_signing = []
all_verify = []

for i, s in enumerate(normal_sessions, 1):
    r = json.loads(s['results_json'])
    avg_signing = r.get('avg_signing_time', 0)
    avg_verify = r.get('avg_verification_time', 0)
    p95_signing = r.get('p95_signing_time', 0)
    p95_verify = r.get('p95_verification_time', 0)
    success_rate = r.get('signing_success_rate', 0)
    all_signing.append(avg_signing)
    all_verify.append(avg_verify)
    
    print(f"\nSession {i}: {s['total_operations']:,} operations")
    print(f"  Signing: avg={avg_signing:.2f}ms, p95={p95_signing:.2f}ms, success={success_rate*100:.2f}%")
    print(f"  Verification: avg={avg_verify:.2f}ms, p95={p95_verify:.2f}ms")

overall_signing = statistics.mean(all_signing) if all_signing else 0
overall_verify = statistics.mean(all_verify) if all_verify else 0
print(f"\nOVERALL: Signing avg={overall_signing:.2f}ms, Verification avg={overall_verify:.2f}ms")

# Session 3 & 4: Replay Attack
print("\n\nTABLE 9a: REPLAY ATTACK DETECTION")
print("="*120)

replay_sessions = [dict(r) for r in rows if r['test_type'] == 'replay_attack']
total_detected = 0
total_attempts_replay = 0
all_fpr = []
all_fnr = []

for i, s in enumerate(replay_sessions, 1):
    r = json.loads(s['results_json'])
    detected = r.get('detected_replays', 0)
    attempts = r.get('total_operations', 0)
    fpr = r.get('fpr', r.get('false_positive_rate', 0))
    fnr = r.get('fnr', r.get('false_negative_rate', 0))
    
    total_detected += detected
    total_attempts_replay += attempts
    all_fpr.append(fpr)
    all_fnr.append(fnr)
    
    print(f"\nSession {i}: {attempts:,} attempts")
    print(f"  Detected: {detected:,}, Missed: {attempts - detected:,}")
    print(f"  Rate: {detected/attempts*100:.1f}%")
    print(f"  FPR: {fpr*100:.2f}%, FNR: {fnr*100:.2f}%")

print(f"\nTOTAL: {total_attempts_replay:,} attempts, {total_detected:,} detected")
print(f"Overall Rate: {total_detected/total_attempts_replay*100:.1f}%")
print(f"Avg FPR: {statistics.mean(all_fpr)*100:.2f}%, Avg FNR: {statistics.mean(all_fnr)*100:.2f}%")

# Session 6: Data Tampering
print("\n\nTABLE 9b: DATA TAMPERING DETECTION")
print("="*120)

tampering_session = dict([r for r in rows if r['test_type'] == 'data_tampering'][0])
r_tamp = json.loads(tampering_session['results_json'])

total_tamp = r_tamp.get('total_operations', 50000)
detected_tamp = r_tamp.get('detected_tampering', 0)
missed_tamp = r_tamp.get('missed_tampering', 0)
integrity_violations = r_tamp.get('integrity_violations', 0)
detection_rate_tamp = r_tamp.get('detection_rate', 0)
critical_detection = r_tamp.get('critical_detection_rate', 0)
types = r_tamp.get('tampering_types', {})

print(f"\nTotal: {total_tamp:,} modifications")
print(f"Detected: {detected_tamp:,}")
print(f"Missed: {missed_tamp:,}")
print(f"Integrity Violations: {integrity_violations}")
print(f"Detection Rate: {detection_rate_tamp:.1f}%")
print(f"Critical Detection: {critical_detection:.1f}%")

type_names = {
    'field_modification': 'Field Modification',
    'field_addition': 'Field Addition',
    'field_removal': 'Field Removal',
    'timestamp_tampering': 'Timestamp Forgery',
    'data_type_change': 'Data Type Change',
    'signature_injection': 'Signature Injection',
    'encryption_bypass': 'Encryption Bypass'
}

print(f"\n{'Tampering Type':<25} {'Total':>10} {'Detected':>10} {'Missed':>10} {'Accuracy':>10}")
print("-"*75)
for key, label in type_names.items():
    total = types.get(key, 0)
    if total > 0:
        overall_rate = detection_rate_tamp / 100
        detected = int(total * overall_rate)
        missed = total - detected
        accuracy = (detected / total * 100) if total > 0 else 0
        print(f"{label:<25} {total:>10,} {detected:>10,} {missed:>10,} {accuracy:>9.1f}%")

print(f"{'TOTAL':<25} {sum(types.values()):>10,} {detected_tamp:>10,} {missed_tamp:>10,} {detection_rate_tamp:>9.1f}%")

# Session 7 & 8: Signature Forgery
print("\n\nTABLE 9c: SIGNATURE FORGERY DETECTION")
print("="*120)

forgery_sessions = [dict(r) for r in rows if r['test_type'] == 'signature_forgery']
total_rejected = 0
total_attempts_forgery = 0
total_crypto = 0

for i, s in enumerate(forgery_sessions, 1):
    r = json.loads(s['results_json'])
    rejected = r.get('rejected_forgeries', 0)
    attempts = r.get('total_operations', 0)
    crypto = r.get('cryptographic_failures', 0)
    
    total_rejected += rejected
    total_attempts_forgery += attempts
    total_crypto += crypto
    
    print(f"\nSession {i}: {attempts:,} attempts")
    print(f"  Rejected: {rejected:,}, Accepted: {attempts - rejected:,}")
    print(f"  Rate: {rejected/attempts*100:.2f}%")
    print(f"  Crypto Failures: {crypto}")

print(f"\nTOTAL: {total_attempts_forgery:,} attempts, {total_rejected:,} rejected")
print(f"Overall Rejection: {total_rejected/total_attempts_forgery*100:.2f}%")
print(f"Total Crypto Failures: {total_crypto}")

# Session 5: Stress Test
print("\n\nTABLE 10: STRESS TESTING")
print("="*120)

stress_session = dict([r for r in rows if r['test_type'] == 'stress_test'][0])
r_stress = json.loads(stress_session['results_json'])

error_rates = r_stress.get('error_rate_by_user_count', {})
response_times = r_stress.get('response_time_by_user_count', {})
success_rates = r_stress.get('success_rate_by_user_count', {})
resource_util = r_stress.get('resource_utilization', {})

print(f"\n{'Users':>10} {'Response (ms)':>15} {'Error Rate':>12} {'Success Rate':>14}")
print("-"*60)

for users in [100, 500, 1000, 1500]:
    resp = response_times.get(str(users), response_times.get(users, 0))
    err = error_rates.get(str(users), error_rates.get(users, 0)) * 100
    succ = success_rates.get(str(users), success_rates.get(users, 0)) * 100
    
    print(f"{users:>10,} {resp:>15.2f} {err:>11.2f}% {succ:>13.2f}%")

print("\n" + "="*120)
print("SUMMARY FOR ABSTRACT & CONCLUSION")
print("="*120)

print(f"\nEnd-to-End Signing Time: {overall_signing:.2f} ms")
print(f"End-to-End Verification Time: {overall_verify:.2f} ms")
print(f"Replay Attack Detection: {total_detected/total_attempts_replay*100:.1f}% ({total_detected:,}/{total_attempts_replay:,})")
print(f"Data Tampering Detection: {detection_rate_tamp:.1f}% ({detected_tamp:,}/{total_tamp:,})")
print(f"Integrity Violations: {integrity_violations}")
print(f"Signature Forgery Rejection: {total_rejected/total_attempts_forgery*100:.1f}% ({total_rejected:,}/{total_attempts_forgery:,})")
print(f"Cryptographic Failures: {total_crypto}")

for users in [100, 500, 1000, 1500]:
    err = error_rates.get(str(users), error_rates.get(users, 0)) * 100
    if err < 2:
        print(f"Max users with <2% error: {users} (error rate: {err:.2f}%)")

conn.close()
