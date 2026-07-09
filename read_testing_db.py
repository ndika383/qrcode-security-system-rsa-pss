import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
db_path = BASE_DIR / 'data' / 'testing' / 'testing_results.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f'Tables found: {len(tables)}')
    for t in tables:
        print(f'  - {t[0]}')
    
    # Try to read from first table
    if tables:
        table_name = tables[0][0]
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'\n{table_name}: {count} rows')
        
        # Get columns
        cursor.execute(f'PRAGMA table_info({table_name})')
        columns = cursor.fetchall()
        print(f'Columns: {[c[1] for c in columns]}')
        
        # Sample 5 rows
        cursor.execute(f'SELECT * FROM {table_name} LIMIT 5')
        rows = cursor.fetchall()
        for i, row in enumerate(rows):
            print(f'\nRow {i+1}:')
            for col, val in zip([c[1] for c in columns], row):
                print(f'  {col}: {str(val)[:100]}')
    
    conn.close()
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
