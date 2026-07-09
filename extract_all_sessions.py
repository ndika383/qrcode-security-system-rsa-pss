"""
Extract all 8 test sessions data from database and prepare for journal update
"""
import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
db_path = BASE_DIR / 'data' / 'testing' / 'testing_results.db'

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all completed sessions
cursor.execute("""
    SELECT * FROM test_sessions 
    WHERE status='completed'
    ORDER BY created_at ASC
""")

rows = cursor.fetchall()

print(f"Total completed sessions: {len(rows)}\n")
print("="*100)

# Session overview
for i, row in enumerate(rows, 1):
    session_data = dict(row)
    print(f"\n📊 Session {i}: {session_data['session_id']}")
    print(f"   Test Type: {session_data['test_type']}")
    print(f"   Test Name: {session_data['test_name']}")
    print(f"   Total Operations: {session_data['total_operations']:,}")
    print(f"   Status: {session_data['status']}")
    print(f"   Created: {session_data['created_at']}")
    
    # Parse results_json if available
    if session_data.get('results_json') and session_data['results_json'] != '{}':
        try:
            results = json.loads(session_data['results_json'])
            
            if session_data['test_type'] == 'normal_operations':
                # Get signing/verification stats
                print(f"   Signing Time: {results.get('avg_signing_time_ms', 'N/A')} ms")
                print(f"   Verification Time: {results.get('avg_verification_time_ms', 'N/A')} ms")
                print(f"   Throughput: {results.get('throughput', 'N/A')} ops/sec")
                
            elif session_data['test_type'] == 'replay_attack':
                print(f"   Detection Rate: {results.get('detection_rate', 'N/A')}%")
                print(f"   Detected: {results.get('detected_replays', 'N/A'):,}")
                print(f"   Total Attempts: {results.get('total_attempts', results.get('total_operations', 'N/A')):,}")
                
            elif session_data['test_type'] == 'data_tampering':
                print(f"   Detection Rate: {results.get('detection_rate', 'N/A')}%")
                print(f"   Detected: {results.get('detected_tampering', 'N/A'):,}")
                print(f"   Integrity Violations: {results.get('integrity_violations', 'N/A')}")
                print(f"   Tampering Types: {dict(results.get('tampering_types', {}))}")
                
            elif session_data['test_type'] == 'signature_forgery':
                print(f"   Rejection Rate: {results.get('rejection_accuracy', 'N/A')}%")
                print(f"   Rejected: {results.get('rejected_forgeries', 'N/A'):,}")
                print(f"   Cryptographic Failures: {results.get('cryptographic_failures', results.get('critical_failures', 'N/A'))}")
                
            elif session_data['test_type'] == 'stress_test':
                print(f"   Max Concurrent Users: {results.get('max_concurrent_users', 'N/A')}")
                print(f"   Error Rates: {results.get('error_rates', 'N/A')}")
                
        except Exception as e:
            print(f"   ⚠️  Error parsing results: {e}")
    
    print("="*100)

# Summary statistics
print("\n\n📈 SUMMARY STATISTICS")
print("="*100)

test_types = {}
for row in rows:
    ttype = row['test_type']
    if ttype not in test_types:
        test_types[ttype] = []
    test_types[ttype].append(dict(row))

for ttype, sessions in test_types.items():
    total_ops = sum(s['total_operations'] for s in sessions)
    print(f"\n{ttype.upper()}:")
    print(f"  Sessions: {len(sessions)}")
    print(f"  Total Operations: {total_ops:,}")
    print(f"  Avg per Session: {total_ops // len(sessions):,}")

conn.close()
