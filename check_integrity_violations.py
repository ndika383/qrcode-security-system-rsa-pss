import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
db_path = BASE_DIR / 'data' / 'testing' / 'testing_results.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get data_tampering sessions
cursor.execute("""
    SELECT session_id, test_name, status, total_operations, results_json 
    FROM test_sessions 
    WHERE test_type='data_tampering' AND status='completed' 
    ORDER BY created_at DESC 
    LIMIT 5
""")

rows = cursor.fetchall()

print(f"Found {len(rows)} data_tampering sessions\n")
print("="*80)

for i, (session_id, test_name, status, total_ops, results_json) in enumerate(rows, 1):
    print(f"\nSession {i}: {session_id}")
    print(f"Test Name: {test_name}")
    print(f"Total Operations: {total_ops:,}")
    
    if results_json and results_json != '{}':
        try:
            results = json.loads(results_json)
            print(f"  integrity_violations: {results.get('integrity_violations', 'NOT FOUND')}")
            print(f"  detected_tampering: {results.get('detected_tampering', 'N/A')}")
            print(f"  missed_tampering: {results.get('missed_tampering', 'N/A')}")
            print(f"  detection_rate: {results.get('detection_rate', 'N/A')}")
            print(f"  critical_detection_rate: {results.get('critical_detection_rate', 'N/A')}")
            
            tampering_types = results.get('tampering_types', {})
            if tampering_types:
                print(f"\n  Tampering Types Distribution:")
                for ttype, count in tampering_types.items():
                    print(f"    - {ttype}: {count:,}")
        except Exception as e:
            print(f"  Error parsing results_json: {e}")
            print(f"  First 200 chars: {results_json[:200]}")
    else:
        print("  No results_json data")
    
    print("="*80)

conn.close()
