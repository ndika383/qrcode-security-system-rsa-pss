"""
Extract detailed metrics for all sessions with proper field names
"""
import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
db_path = BASE_DIR / 'data' / 'testing' / 'testing_results.db'

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT * FROM test_sessions 
    WHERE status='completed'
    ORDER BY created_at ASC
""")

rows = cursor.fetchall()

for i, row in enumerate(rows, 1):
    session = dict(row)
    print(f"\n{'='*100}")
    print(f"SESSION {i}: {session['session_id']}")
    print(f"{'='*100}")
    print(f"Type: {session['test_type']}")
    print(f"Name: {session['test_name']}")
    print(f"Operations: {session['total_operations']:,}")
    
    if session.get('results_json') and session['results_json'] != '{}':
        try:
            r = json.loads(session['results_json'])
            
            if session['test_type'] == 'normal_operations':
                # Check various possible field names
                print(f"\n  Keys available: {list(r.keys())[:20]}")
                for key in ['avg_signing_time_ms', 'mean_signing_ms', 'signing_time', 'signing_ms', 
                            'avg_signing_ms', 'signing_time_ms']:
                    if key in r:
                        print(f"  Signing Time: {r[key]}")
                for key in ['avg_verification_time_ms', 'mean_verification_ms', 'verification_time', 'verification_ms']:
                    if key in r:
                        print(f"  Verification Time: {r[key]}")
                        
            elif session['test_type'] == 'replay_attack':
                print(f"\n  Detection Rate: {r.get('detection_rate', 'N/A')}%")
                print(f"  Detected: {r.get('detected_replays', 'N/A'):,}")
                print(f"  Missed: {r.get('missed_replays', 'N/A')}")
                print(f"  FPR: {r.get('false_positive_rate', r.get('fpr', 'N/A'))}")
                print(f"  FNR: {r.get('false_negative_rate', r.get('fnr', 'N/A'))}")
                patterns = r.get('detection_by_pattern', r.get('pattern_detection_rates', {}))
                if patterns:
                    print(f"  By Pattern: {json.dumps(patterns, indent=4)[:500]}")
                    
            elif session['test_type'] == 'data_tampering':
                print(f"\n  Detection Rate: {r.get('detection_rate', 'N/A')}%")
                print(f"  Detected: {r.get('detected_tampering', 'N/A'):,}")
                print(f"  Missed: {r.get('missed_tampering', 'N/A'):,}")
                print(f"  Integrity Violations: {r.get('integrity_violations', 'N/A')}")
                print(f"  Critical Detection: {r.get('critical_detection_rate', 'N/A')}%")
                types = r.get('tampering_types', {})
                print(f"  Tampering Types: {json.dumps(types, indent=4)}")
                
            elif session['test_type'] == 'signature_forgery':
                print(f"\n  Rejection Rate: {r.get('rejection_accuracy', 'N/A')}%")
                print(f"  Rejected: {r.get('rejected_forgeries', 'N/A'):,}")
                print(f"  Accepted: {r.get('accepted_forgeries', 'N/A'):,}")
                print(f"  Crypto Failures: {r.get('cryptographic_failures', r.get('critical_failures', 'N/A'))}")
                print(f"  Security Score: {r.get('security_effectiveness', {}).get('overall_score', 'N/A')}")
                
            elif session['test_type'] == 'stress_test':
                print(f"\n  Stress test keys: {list(r.keys())[:20]}")
                
        except Exception as e:
            print(f"  Error: {e}")
            print(f"  First 300 chars: {session['results_json'][:300]}")

conn.close()
