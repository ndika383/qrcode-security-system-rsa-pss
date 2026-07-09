import sqlite3
import json
import statistics
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
db_path = BASE_DIR / 'data' / 'testing' / 'testing_results.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Get session summary by test type
cursor.execute("""
    SELECT test_type, COUNT(*) as sessions, 
           SUM(total_operations) as total_ops,
           SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
           SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
           SUM(CASE WHEN status='stopped' THEN 1 ELSE 0 END) as stopped
    FROM test_sessions 
    WHERE test_type != 'comprehensive'
    GROUP BY test_type
""")

print("=" * 70)
print("SUMMARY TESTING BY TYPE")
print("=" * 70)
for row in cursor.fetchall():
    print(f'\n{row[0].upper()}:')
    print(f'  Sessions: {row[1]}')
    print(f'  Total Operations: {row[2]:,}')
    print(f'  Completed: {row[3]}, Failed: {row[4]}, Stopped: {row[5]}')

# 2. Extract detailed metrics from completed sessions
cursor.execute("""
    SELECT test_type, results_json, total_operations 
    FROM test_sessions 
    WHERE status='completed' AND results_json IS NOT NULL AND results_json != '{}'
    ORDER BY test_type, id
""")

rows = cursor.fetchall()
print(f'\n\n{"=" * 70}')
print(f'DETAILED METRICS FROM {len(rows)} COMPLETED SESSIONS')
print("=" * 70)

for test_type in ['normal_operations', 'replay_attack', 'data_tampering', 'signature_forgery', 'stress_test']:
    type_rows = [r for r in rows if r[0] == test_type]
    
    if not type_rows:
        continue
    
    print(f'\n\n--- {test_type.upper().replace("_", " ")} ({len(type_rows)} sessions) ---')
    
    for idx, (ttype, results_json, total_ops) in enumerate(type_rows[:3]):  # First 3 sessions
        try:
            results = json.loads(results_json)
            print(f'\n  Session {idx+1}: {total_ops:,} operations')
            
            if test_type == 'normal_operations':
                signing = results.get('signing_times', [])
                verifying = results.get('verification_times', [])
                if signing:
                    print(f'    Signing: mean={statistics.mean(signing)*1000:.2f}ms, '
                          f'median={statistics.median(signing)*1000:.2f}ms, '
                          f'min={min(signing)*1000:.2f}ms, max={max(signing)*1000:.2f}ms')
                if verifying:
                    print(f'    Verifying: mean={statistics.mean(verifying)*1000:.2f}ms, '
                          f'median={statistics.median(verifying)*1000:.2f}ms, '
                          f'min={min(verifying)*1000:.2f}ms, max={max(verifying)*1000:.2f}ms')
            
            elif test_type == 'replay_attack':
                replay = results.get('replay_times', [])
                detected = results.get('detected_count', 0)
                total = results.get('total_replays', 0)
                if replay:
                    print(f'    Replay detection: mean={statistics.mean(replay)*1000:.2f}ms')
                print(f'    Detected: {detected}/{total} ({(detected/total*100) if total > 0 else 0:.1f}%)')
            
            elif test_type == 'data_tampering':
                tampering = results.get('tampering_times', [])
                detected = results.get('detected_count', 0)
                total = results.get('total_tampering', 0)
                if tampering:
                    print(f'    Tampering detection: mean={statistics.mean(tampering)*1000:.2f}ms')
                print(f'    Detected: {detected}/{total} ({(detected/total*100) if total > 0 else 0:.1f}%)')
            
            elif test_type == 'signature_forgery':
                forgery = results.get('forgery_times', [])
                rejected = results.get('rejected_count', 0)
                total = results.get('total_forgery', 0)
                if forgery:
                    print(f'    Forgery detection: mean={statistics.mean(forgery)*1000:.2f}ms')
                print(f'    Rejected: {rejected}/{total} ({(rejected/total*100) if total > 0 else 0:.1f}%)')
            
            elif test_type == 'stress_test':
                stress = results.get('stress_times', [])
                if stress:
                    print(f'    Stress response: mean={statistics.mean(stress)*1000:.2f}ms')
            
        except Exception as e:
            print(f'  Error parsing results: {e}')

# 3. Total operations across all tests
cursor.execute("SELECT SUM(total_operations) FROM test_sessions WHERE test_type != 'comprehensive'")
total_ops = cursor.fetchone()[0]
print(f'\n\n{"=" * 70}')
print(f'TOTAL OPERATIONS ACROSS ALL TESTS: {total_ops:,}')
print("=" * 70)

conn.close()
