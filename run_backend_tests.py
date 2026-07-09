import os
import sys
import time
import subprocess
import sqlite3
import pandas as pd

def run_backend_tests():
    print("=" * 60)
    print("🚀 AUTOMATED TESTING SYSTEM - BACKEND EXECUTION")
    print("=" * 60)
    
    # 1. Jalankan Kalibrasi Mode Quick Check
    print("\n[1/3] Menjalankan Kalibrasi Performa (Quick Check)...")
    try:
        subprocess.run([sys.executable, "calibrate_performance.py", "--tier", "quick_check"], check=True)
        print("✅ Kalibrasi berhasil diselesaikan.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Gagal melakukan kalibrasi: {e}")
        print("Pastikan file 'calibrate_performance.py' ada di direktori root.")
        return
    except FileNotFoundError:
        print("❌ File 'calibrate_performance.py' tidak ditemukan.")
        return

    # 2. Definisikan Skenario Pengujian (Sesuai Permintaan)
    test_sessions = [
        {"type": "normal_operations", "name": "Normal Operations - Session 1", "ops": 50000, "filename": "normal-operations-1.csv"},
        {"type": "normal_operations", "name": "Normal Operations - Session 2", "ops": 50000, "filename": "normal-operations-2.csv"},
        {"type": "replay_attack", "name": "Replay Attack Simulation - Session 1", "ops": 55000, "filename": "replay-attack-1.csv"},
        {"type": "replay_attack", "name": "Replay Attack Simulation - Session 2", "ops": 55000, "filename": "replay-attack-2.csv"},
        {"type": "data_tampering", "name": "Data Tampering Detection - Session 1", "ops": 50000, "filename": "data-tampering-1.csv"},
        {"type": "signature_forgery", "name": "Signature Forgery Testing - Session 1", "ops": 25000, "filename": "signature-forgery-1.csv"},
        {"type": "signature_forgery", "name": "Signature Forgery Testing - Session 2", "ops": 25000, "filename": "signature-forgery-2.csv"},
        {"type": "stress_test", "name": "Stress Testing - Session 1", "ops": 40000, "filename": "stress-test-1.csv"}
    ]

    print("\n[2/3] Memulai Eksekusi Pengujian (Backend Mode)...")
    
    try:
        # CATATAN: Import aplikasi Flask Anda untuk mendapatkan app_context
        from app import app
        import inspect
        
        # 1. Deteksi otomatis nama Class di dalam modules.testing_controller
        import modules.testing_controller as tc
        
        runner_class = None
        for name, obj in inspect.getmembers(tc, inspect.isclass):
            if 'Test' in name or 'Controller' in name or 'Runner' in name or 'System' in name:
                runner_class = obj
                break
                
        if not runner_class:
            print("\n❌ Gagal menemukan class pengujian di dalam modules.testing_controller!")
            print("Isi module yang tersedia:")
            for name in dir(tc):
                if not name.startswith('_'):
                    print(f"  - {name}")
            return
            
        print(f"✅ Ditemukan class pengujian otomatis: {runner_class.__name__}")
        
        with app.app_context():
            tester = runner_class()
            
            # 2. Deteksi otomatis nama method eksekusi test
            method_name = None
            for m in ['start_test_session', 'run_test', 'execute_test', 'run_session', 'run_testing_session', 'start_test', 'run_automated_test']:
                if hasattr(tester, m):
                    method_name = m
                    break
                    
            if not method_name:
                print(f"\n❌ Gagal menemukan method eksekusi di dalam {runner_class.__name__}!")
                print("Method yang tersedia:", [m for m in dir(tester) if not m.startswith('_') and callable(getattr(tester, m))])
                return
                
            print(f"✅ Ditemukan method pengujian otomatis: {method_name}")
            
            for i, session in enumerate(test_sessions, 1):
                print(f"\n  ▶ Menjalankan ({i}/{len(test_sessions)}): {session['name']} [{session['ops']:,} operasi]")
                start_time = time.time()
                
                # 3. Deteksi otomatis parameter yang dibutuhkan method
                method = getattr(tester, method_name)
                sig = inspect.signature(method)
                kwargs = {}
                
                # Cek apakah method membutuhkan parameter dictionary bernama 'params'
                if 'params' in sig.parameters:
                    kwargs['params'] = {
                        'test_type': session['type'],
                        'test_name': session['name'],
                        'total_operations': session['ops']
                    }
                
                if 'test_type' in sig.parameters: kwargs['test_type'] = session['type']
                elif 'type' in sig.parameters: kwargs['type'] = session['type']
                
                if 'session_name' in sig.parameters: kwargs['session_name'] = session['name']
                elif 'test_name' in sig.parameters: kwargs['test_name'] = session['name']
                
                if 'operations' in sig.parameters: kwargs['operations'] = session['ops']
                elif 'total_operations' in sig.parameters: kwargs['total_operations'] = session['ops']
                elif 'ops' in sig.parameters: kwargs['ops'] = session['ops']
                
                # Eksekusi
                test_result = method(**kwargs)
                
                # Jika eksekusi bersifat asynchronous (background thread), tunggu hingga selesai
                session_id = None
                if isinstance(test_result, dict) and 'session_id' in test_result:
                    session_id = test_result['session_id']
                elif isinstance(test_result, str) and test_result.startswith('test_'):
                    session_id = test_result
                    
                if session_id and hasattr(tester, 'get_test_session'):
                    while True:
                        info = tester.get_test_session(session_id)
                        if not info:
                            break
                        status = info.get('status', 'unknown')
                        progress = info.get('progress', 0)
                        sys.stdout.write(f"\r  ⏳ Progress: {progress:.1f}% | Status: {status}    ")
                        sys.stdout.flush()
                        if status in ['completed', 'failed', 'stopped']:
                            print() # Pindah baris
                            break
                        time.sleep(2.0)
                
                duration = time.time() - start_time
                print(f"  ✅ Selesai dalam {duration:.2f} detik.")
                
    except ImportError as e:
        print(f"\n⚠️ PERHATIAN: Gagal mengimpor modul ({e}).")
        return
    except Exception as e:
        print(f"\n❌ Terjadi kesalahan saat menjalankan pengujian: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Ekspor Data ke CSV
    print("\n[3/3] Menyimpan Hasil Pengujian ke CSV...")
    
    db_path = 'data/testing/testing_results.db'
    export_base_dir = 'data/export_csv/quick_check'
    os.makedirs(export_base_dir, exist_ok=True)
    
    try:
        conn = sqlite3.connect(db_path)
        master_dfs = []
        for session in test_sessions:
            # Buat folder khusus berdasarkan tipe tes
            session_dir = os.path.join(export_base_dir, session['type'])
            os.makedirs(session_dir, exist_ok=True)
            
            filename = session['filename']
            session_name = session['name']
            filepath = os.path.join(session_dir, filename)
            
            # Ambil data dari tabel test_sessions berdasarkan test_name
            query = f"SELECT * FROM test_sessions WHERE test_name = '{session_name}' ORDER BY id DESC LIMIT 1"
            df = pd.read_sql(query, conn)
            
            if not df.empty:
                df.to_csv(filepath, index=False)
                print(f"  📁 Tersimpan: {filepath} ({len(df)} baris)")
                
                # Siapkan data untuk master CSV
                df_master = df.copy()
                df_master['calibration_mode'] = 'quick_check'
                master_dfs.append(df_master)
            else:
                print(f"  ⚠️ Data tidak ditemukan untuk sesi: {session_name}")
                
        # Simpan/Append ke Master CSV
        if master_dfs:
            master_df = pd.concat(master_dfs, ignore_index=True)
            master_filepath = 'data/export_csv/master_all_tests.csv'
            header = not os.path.exists(master_filepath)
            master_df.to_csv(master_filepath, mode='a', header=header, index=False)
            print(f"\n  📊 MASTER CSV Diperbarui: {master_filepath} (+{len(master_df)} baris)")
            
        conn.close()
        print("\n🎉 SEMUA PENGUJIAN DAN EKSPOR DATA SELESAI!")
        
    except sqlite3.OperationalError as e:
         print(f"\n❌ Gagal mengakses database: {e}")
         print("Pastikan database ada di 'data/testing/testing_results.db' dan tabel bernama 'test_results'.")

if __name__ == "__main__":
    run_backend_tests()