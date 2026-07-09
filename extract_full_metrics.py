import sqlite3
import json
import statistics
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
db_path = BASE_DIR / 'data' / 'testing' / 'testing_results.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get ALL completed sessions with full results
cursor.execute("""
    SELECT test_type, results_json, total_operations, test_name
    FROM test_sessions 
    WHERE status='completed' AND results_json IS NOT NULL AND results_json != '{}'
    ORDER BY test_type, id
""")

rows = cursor.fetchall()
print(f"Total completed sessions with data: {len(rows)}\n")

for ttype in ['normal_operations', 'replay_attack', 'data_tampering', 'signature_forgery', 'stress_test']:
    type_rows = [(r[1], r[2], r[3]) for r in rows if r[0] == ttype]
    
    if not type_rows:
        continue
    
    print(f"\n{'='*70}")
    print(f"{ttype.upper().replace('_', ' ')}: {len(type_rows)} sessions")
    print(f"{'='*70}")
    
    for idx, (results_json, total_ops, test_name) in enumerate(type_rows):
        try:
            results = json.loads(results_json)
            print(f"\n  Session: {test_name}")
            print(f"  Operations: {total_ops:,}")
            
            # Print ALL keys in results
            print(f"  Keys: {list(results.keys())}")
            
            # Print sample values for each key
            for key in results:
                val = results[key]
                if isinstance(val, list):
                    if len(val) > 0:
                        print(f"    {key}: list[{len(val)}], mean={statistics.mean(val)*1000:.2f}ms, "
                              f"median={statistics.median(val)*1000:.2f}ms, "
                              f"min={min(val)*1000:.2f}ms, max={max(val)*1000:.2f}ms")
                    else:
                        print(f"    {key}: empty list")
                elif isinstance(val, dict):
                    print(f"    {key}: {json.dumps(val, indent=6)[:200]}")
                else:
                    print(f"    {key}: {val}")
            
        except Exception as e:
            print(f"  Error: {e}")

conn.close()
