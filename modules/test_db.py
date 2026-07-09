import sqlite3
import json
from datetime import datetime
import os

def init_testing_db():
    """Initialize database untuk menyimpan hasil testing"""
    try:
        # Pastikan folder data ada
        os.makedirs('data/testing', exist_ok=True)
        
        db_path = 'data/testing/testing_results.db'
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Tabel untuk session testing
        c.execute('''CREATE TABLE IF NOT EXISTS test_sessions
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     session_id TEXT UNIQUE,
                     test_type TEXT,
                     test_name TEXT,
                     start_time DATETIME,
                     end_time DATETIME,
                     status TEXT,
                     total_operations INTEGER,
                     completed_operations INTEGER,
                     progress REAL DEFAULT 0,
                     results_json TEXT,
                     error_message TEXT,
                     created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        # Tabel untuk metrics detail
        c.execute('''CREATE TABLE IF NOT EXISTS test_metrics
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     session_id TEXT,
                     metric_name TEXT,
                     metric_value REAL,
                     metric_unit TEXT,
                     timestamp DATETIME,
                     FOREIGN KEY (session_id) REFERENCES test_sessions(session_id))''')
        
        # Tabel untuk operation logs
        c.execute('''CREATE TABLE IF NOT EXISTS operation_logs
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     session_id TEXT,
                     operation_type TEXT,
                     operation_id INTEGER,
                     start_time DATETIME,
                     end_time DATETIME,
                     duration REAL,
                     success BOOLEAN,
                     error_message TEXT,
                     details TEXT,
                     FOREIGN KEY (session_id) REFERENCES test_sessions(session_id))''')
        
        # Tabel untuk test scenarios
        c.execute('''CREATE TABLE IF NOT EXISTS test_scenarios
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     scenario_name TEXT UNIQUE,
                     scenario_description TEXT,
                     parameters_json TEXT,
                     created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        # Insert default scenarios jika belum ada
        default_scenarios = [
            ('normal_operations', 'Normal Operations (20.000 operasi)', 
             '{"signing_count": 10000, "verification_count": 10000, "description": "10.000 signing + 10.000 verification"}'),
            
            ('replay_attack', 'Replay Attack Simulation (25.000 attempts)', 
             '{"sample_count": 1500, "repetitions": 20, "description": "1.500 sampel × 15–20 verifikasi berulang"}'),
            
            ('data_tampering', 'Data Tampering Detection (50.000 operasi)', 
             '{"operations": 50000, "description": "Field modification, addition, removal"}'),
            
            ('signature_forgery', 'Signature Forgery Testing (20.000 attempts)', 
             '{"attempts": 20000, "description": "Random, swapped, truncated signatures"}'),
            
            ('stress_test', 'Stress Testing (10.000 operasi)', 
             '{"operations": 10000, "concurrent_users": [100, 500, 1000, 1500], "description": "Simulasi 100–1.500 concurrent users"}')
        ]
        
        for scenario in default_scenarios:
            c.execute('''INSERT OR IGNORE INTO test_scenarios 
                        (scenario_name, scenario_description, parameters_json) 
                        VALUES (?, ?, ?)''', scenario)
        
        # Tabel untuk performance metrics
        c.execute('''CREATE TABLE IF NOT EXISTS performance_metrics
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     session_id TEXT,
                     metric_type TEXT,
                     timestamp DATETIME,
                     value REAL,
                     label TEXT,
                     FOREIGN KEY (session_id) REFERENCES test_sessions(session_id))''')
        
        # Tabel untuk error logs
        c.execute('''CREATE TABLE IF NOT EXISTS error_logs
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     session_id TEXT,
                     error_type TEXT,
                     error_message TEXT,
                     operation_id INTEGER,
                     timestamp DATETIME,
                     stack_trace TEXT,
                     FOREIGN KEY (session_id) REFERENCES test_sessions(session_id))''')
        
        # Buat indexes untuk performa query
        c.execute('CREATE INDEX IF NOT EXISTS idx_sessions_status ON test_sessions(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_sessions_type ON test_sessions(test_type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_sessions_time ON test_sessions(start_time)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_metrics_session ON test_metrics(session_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_logs_session ON operation_logs(session_id)')
        
        conn.commit()
        conn.close()
        
        print(f"✅ Database testing berhasil diinisialisasi di: {db_path}")
        print(f"✅ 5 default test scenarios telah ditambahkan")
        
        # Cek jika berhasil
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM test_scenarios")
        count = c.fetchone()[0]
        conn.close()
        
        print(f"✅ Total {count} test scenarios tersedia")
        
        return True
        
    except Exception as e:
        print(f"❌ Error initializing testing database: {e}")
        return False

def get_db_connection():
    """Mendapatkan koneksi database"""
    db_path = 'data/testing/testing_results.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Mengembalikan hasil sebagai dictionary
    return conn

def create_test_session(session_id, test_type, test_name, total_operations=0):
    """Membuat session testing baru"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''INSERT INTO test_sessions 
                    (session_id, test_type, test_name, start_time, status, total_operations)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (session_id, test_type, test_name, datetime.now(), 'pending', total_operations))
        
        conn.commit()
        session_id = c.lastrowid
        return session_id
    except Exception as e:
        print(f"Error creating test session: {e}")
        return None
    finally:
        conn.close()

def update_test_session(session_id, **kwargs):
    """Update data test session"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        updates = []
        values = []
        
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            values.append(value)
        
        values.append(session_id)
        
        query = f"UPDATE test_sessions SET {', '.join(updates)} WHERE session_id = ?"
        c.execute(query, values)
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating test session: {e}")
        return False
    finally:
        conn.close()

def add_test_metric(session_id, metric_name, metric_value, metric_unit=""):
    """Menambahkan metric ke database"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''INSERT INTO test_metrics 
                    (session_id, metric_name, metric_value, metric_unit, timestamp)
                    VALUES (?, ?, ?, ?, ?)''',
                    (session_id, metric_name, metric_value, metric_unit, datetime.now()))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding test metric: {e}")
        return False
    finally:
        conn.close()

def add_operation_log(session_id, operation_type, operation_id, duration, success=True, error_message=None, details=None):
    """Menambahkan log operasi"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''INSERT INTO operation_logs 
                    (session_id, operation_type, operation_id, start_time, end_time, 
                     duration, success, error_message, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (session_id, operation_type, operation_id, 
                     datetime.fromtimestamp(datetime.now().timestamp() - duration),
                     datetime.now(), duration, success, error_message, 
                     json.dumps(details) if details else None))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding operation log: {e}")
        return False
    finally:
        conn.close()

def get_test_session(session_id):
    """Mendapatkan data test session"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('SELECT * FROM test_sessions WHERE session_id = ?', (session_id,))
        session = c.fetchone()
        
        if session:
            # Konversi ke dictionary
            session_dict = dict(session)
            
            # Parse JSON results jika ada
            if session_dict.get('results_json'):
                try:
                    session_dict['results'] = json.loads(session_dict['results_json'])
                except:
                    session_dict['results'] = {}
            
            return session_dict
        return None
    except Exception as e:
        print(f"Error getting test session: {e}")
        return None
    finally:
        conn.close()

def get_test_metrics(session_id):
    """Mendapatkan semua metrics untuk session tertentu"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('SELECT * FROM test_metrics WHERE session_id = ? ORDER BY timestamp', (session_id,))
        metrics = [dict(row) for row in c.fetchall()]
        return metrics
    except Exception as e:
        print(f"Error getting test metrics: {e}")
        return []
    finally:
        conn.close()

def get_all_test_sessions(limit=50):
    """Mendapatkan semua test sessions"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''SELECT * FROM test_sessions 
                    ORDER BY start_time DESC LIMIT ?''', (limit,))
        sessions = [dict(row) for row in c.fetchall()]
        
        # Parse JSON results
        for session in sessions:
            if session.get('results_json'):
                try:
                    session['results'] = json.loads(session['results_json'])
                except:
                    session['results'] = {}
        
        return sessions
    except Exception as e:
        print(f"Error getting all test sessions: {e}")
        return []
    finally:
        conn.close()

def get_test_scenarios():
    """Mendapatkan semua test scenarios"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('SELECT * FROM test_scenarios ORDER BY scenario_name')
        scenarios = [dict(row) for row in c.fetchall()]
        
        # Parse JSON parameters
        for scenario in scenarios:
            if scenario.get('parameters_json'):
                try:
                    scenario['parameters'] = json.loads(scenario['parameters_json'])
                except:
                    scenario['parameters'] = {}
        
        return scenarios
    except Exception as e:
        print(f"Error getting test scenarios: {e}")
        return []
    finally:
        conn.close()

def delete_all_sessions():
    """Menghapus semua session testing untuk testing ulang dari awal"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Hitung jumlah session yang akan dihapus
        c.execute("SELECT COUNT(*) FROM test_sessions")
        session_count = c.fetchone()[0]

        # Hapus semua data terkait secara berurutan (karena foreign key)
        c.execute("DELETE FROM test_metrics")
        c.execute("DELETE FROM operation_logs")
        c.execute("DELETE FROM performance_metrics")
        c.execute("DELETE FROM error_logs")
        c.execute("DELETE FROM test_sessions")

        conn.commit()
        deleted_count = c.rowcount

        # Vacuum database untuk optimasi dan reclaim space
        c.execute("VACUUM")

        print(f"✅ Deleted all {session_count} test sessions and related data")
        return session_count
    except Exception as e:
        print(f"Error deleting all sessions: {e}")
        return 0
    finally:
        conn.close()

def cleanup_old_sessions(days=30):
    """Membersihkan session yang sudah lama"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        cutoff_date = datetime.now().timestamp() - (days * 24 * 3600)
        cutoff_datetime = datetime.fromtimestamp(cutoff_date)

        # Hapus data terkait
        c.execute("DELETE FROM test_metrics WHERE timestamp < ?", (cutoff_datetime,))
        c.execute("DELETE FROM operation_logs WHERE end_time < ?", (cutoff_datetime,))
        c.execute("DELETE FROM performance_metrics WHERE timestamp < ?", (cutoff_datetime,))
        c.execute("DELETE FROM error_logs WHERE timestamp < ?", (cutoff_datetime,))

        # Hapus sessions
        c.execute("DELETE FROM test_sessions WHERE start_time < ?", (cutoff_datetime,))

        conn.commit()
        deleted_count = c.rowcount
        print(f"✅ Cleaned up {deleted_count} old sessions")

        # Vacuum database untuk optimasi
        c.execute("VACUUM")

        return deleted_count
    except Exception as e:
        print(f"Error cleaning up old sessions: {e}")
        return 0
    finally:
        conn.close()

def export_session_to_csv(session_id, output_path=None):
    """Export session data ke CSV"""
    import csv
    
    session = get_test_session(session_id)
    if not session:
        return False
    
    if not output_path:
        output_path = f"static/testing/exports/session_{session_id}.csv"
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Tulis header session
            writer.writerow(['TEST SESSION REPORT'])
            writer.writerow(['Session ID', session_id])
            writer.writerow(['Test Type', session.get('test_type')])
            writer.writerow(['Test Name', session.get('test_name')])
            writer.writerow(['Start Time', session.get('start_time')])
            writer.writerow(['End Time', session.get('end_time')])
            writer.writerow(['Status', session.get('status')])
            writer.writerow(['Total Operations', session.get('total_operations')])
            writer.writerow(['Completed Operations', session.get('completed_operations')])
            writer.writerow(['Progress', f"{session.get('progress', 0)}%"])
            writer.writerow([])
            
            # Tulis metrics
            metrics = get_test_metrics(session_id)
            if metrics:
                writer.writerow(['METRICS'])
                writer.writerow(['Metric Name', 'Value', 'Unit', 'Timestamp'])
                for metric in metrics:
                    writer.writerow([
                        metric['metric_name'],
                        metric['metric_value'],
                        metric['metric_unit'] or '',
                        metric['timestamp']
                    ])
                writer.writerow([])
        
        print(f"✅ Session exported to CSV: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error exporting session to CSV: {e}")
        return False

# Untuk testing langsung
if __name__ == "__main__":
    print("Initializing testing database...")
    success = init_testing_db()
    if success:
        print("\n✅ Database initialized successfully!")
        
        # Test query
        conn = get_db_connection()
        c = conn.cursor()
        
        # Count tables
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = c.fetchall()
        print(f"\n✅ Tables created: {[table[0] for table in tables]}")
        
        # Show scenarios
        scenarios = get_test_scenarios()
        print(f"\n✅ Test scenarios: {len(scenarios)}")
        for scenario in scenarios:
            print(f"  - {scenario['scenario_name']}: {scenario['scenario_description']}")
        
        conn.close()
    else:
        print("❌ Database initialization failed!") 
