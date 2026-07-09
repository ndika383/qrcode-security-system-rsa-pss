"""
Script untuk memperbaiki end_time pada session yang sudah ada di database.
Ini akan mengestimasi end_time berdasarkan start_time dan typical test duration.
"""

import sqlite3
from datetime import datetime, timedelta
import json
import os

def fix_end_time_for_completed_sessions():
    """Update end_time untuk completed sessions yang belum memilikinya"""
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'testing', 'testing_results.db')
    
    if not os.path.exists(db_path):
        print(f"Database tidak ditemukan di: {db_path}")
        return
    
    print(f"Menggunakan database: {db_path}")
    print("=" * 80)
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    
    # Cari completed sessions tanpa end_time
    c.execute("""
        SELECT session_id, test_type, start_time, status, end_time, 
               total_operations, completed_operations
        FROM test_sessions 
        WHERE status = 'completed' 
        AND (end_time IS NULL OR end_time = '')
    """)
    
    sessions_to_fix = c.fetchall()
    
    if not sessions_to_fix:
        print("✅ Semua completed sessions sudah memiliki end_time yang valid.")
        conn.close()
        return
    
    print(f"Ditemukan {len(sessions_to_fix)} session yang perlu diperbaiki:\n")
    
    # Estimasi durasi berdasarkan jenis test dan jumlah operasi
    # Berdasarkan data testing aktual: 20,000 ops signature_forgery = 14 detik → 0.7ms/op
    
    estimated_duration_ms = {
        'normal_operations': 0.8,    # 0.8ms per operation
        'replay_attack': 0.7,        # 0.7ms per operation
        'data_tampering': 0.7,       # 0.7ms per operation
        'signature_forgery': 0.7,    # 0.7ms per operation (14s untuk 20K ops)
        'stress_test': 0.8           # 0.8ms per operation
    }
    
    updated_count = 0
    for session_id, test_type, start_time, status, end_time, total_ops, completed_ops in sessions_to_fix:
        try:
            # Parse start_time
            start_str = start_time
            if 'Z' in start_str:
                start_str = start_str.replace('Z', '+00:00')
            start_dt = datetime.fromisoformat(start_str)
            
            # Get operations count
            ops = completed_ops if completed_ops else total_ops
            
            # Calculate estimated duration
            duration_per_op = estimated_duration_ms.get(test_type, 0.020)  # Default 20ms
            estimated_duration_seconds = ops * duration_per_op / 1000  # Convert ms to seconds
            
            # Ensure minimum 5 seconds and maximum 2 hours
            estimated_duration_seconds = max(5, min(7200, estimated_duration_seconds))
            
            # Calculate end_time
            end_dt = start_dt + timedelta(seconds=estimated_duration_seconds)
            
            # Update database
            c.execute("""
                UPDATE test_sessions 
                SET end_time = ? 
                WHERE session_id = ?
            """, (end_dt.isoformat(), session_id))
            
            print(f"✓ Session: {session_id[:40]}...")
            print(f"  Test Type: {test_type}")
            print(f"  Start: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Operations: {ops}")
            print(f"  Estimated Duration: {estimated_duration_seconds:.1f}s")
            print(f"  End Time (baru): {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            updated_count += 1
            
        except Exception as e:
            print(f"✗ Error processing session {session_id[:40]}: {e}\n")
    
    conn.commit()
    conn.close()
    
    print("=" * 80)
    print(f"✅ Berhasil memperbaiki {updated_count} dari {len(sessions_to_fix)} session.")
    print("Catatan: End time adalah estimasi berdasarkan jumlah operasi dan jenis test.")

if __name__ == '__main__':
    fix_end_time_for_completed_sessions()
