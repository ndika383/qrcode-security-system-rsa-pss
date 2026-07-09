import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
db_path = BASE_DIR / 'data' / 'testing' / 'testing_results.db'

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check normal operations
cursor.execute("SELECT results_json FROM test_sessions WHERE test_type='normal_operations' LIMIT 1")
row = cursor.fetchone()
r = json.loads(row['results_json'])
print("NORMAL OPERATIONS KEYS:")
for k, v in r.items():
    if not isinstance(v, list):
        print(f"  {k}: {v}")

# Check stress test
cursor.execute("SELECT results_json FROM test_sessions WHERE test_type='stress_test' LIMIT 1")
row = cursor.fetchone()
r = json.loads(row['results_json'])
print("\n\nSTRESS TEST KEYS:")
for k, v in r.items():
    if not isinstance(v, list):
        print(f"  {k}: {v}")
    else:
        print(f"  {k}: [list with {len(v)} items]")

# Check replay
cursor.execute("SELECT results_json FROM test_sessions WHERE test_type='replay_attack' LIMIT 1")
row = cursor.fetchone()
r = json.loads(row['results_json'])
print("\n\nREPLAY ATTACK - FPR/FNR keys:")
for k in ['false_positive_rate', 'fpr', 'false_negative_rate', 'fnr', 'fpr_percent', 'fnr_percent']:
    if k in r:
        print(f"  {k}: {r[k]}")

conn.close()
