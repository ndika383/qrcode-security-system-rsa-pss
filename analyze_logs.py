import csv
import json
import os
import statistics
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

print("=" * 60)
print("ANALISIS DATA RIIL DARI LOG SISTEM")
print("=" * 60)

# 1. Generate Log Analysis
gen_log = BASE_DIR / 'logs' / 'log_generate.csv'
if os.path.exists(gen_log):
    with open(gen_log, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f'\n--- LOG GENERATE ({len(rows)} entries) ---')
    if rows:
        total_times = [float(r['Total Waktu (detik)']) for r in rows]
        sign_times = [float(r['Waktu Sign (detik)']) for r in rows]
        qr_times = [float(r['Waktu QR (detik)']) for r in rows]
        file_sizes = [float(r['Ukuran File (KB)']) for r in rows]
        sig_lengths = [int(r['Panjang Signature']) for r in rows]
        
        print(f'Total Waktu: mean={statistics.mean(total_times):.4f}s, median={statistics.median(total_times):.4f}s')
        if len(total_times) > 1:
            print(f'  std={statistics.stdev(total_times):.4f}s, min={min(total_times):.4f}s, max={max(total_times):.4f}s')
        
        print(f'Sign Waktu: mean={statistics.mean(sign_times):.4f}s, median={statistics.median(sign_times):.4f}s')
        print(f'QR Waktu: mean={statistics.mean(qr_times):.4f}s, median={statistics.median(qr_times):.4f}s')
        print(f'Ukuran File: mean={statistics.mean(file_sizes):.2f} KB')
        print(f'Panjang Signature: mean={statistics.mean(sig_lengths):.1f} chars')
        
        # QR versions
        versions = [int(r['Versi QR']) for r in rows]
        modules = [int(r['Modul']) for r in rows]
        print(f'QR Version: {versions}')
        print(f'QR Modules: {modules}')

# 2. Verification Log Analysis
ver_log = BASE_DIR / 'logs' / 'log_verifikasi.csv'
if os.path.exists(ver_log):
    with open(ver_log, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        ver_rows = list(reader)
    
    print(f'\n--- LOG VERIFIKASI ({len(ver_rows)} entries) ---')
    if ver_rows:
        statuses = {}
        for r in ver_rows:
            status = r['Status']
            statuses[status] = statuses.get(status, 0) + 1
        
        for status, count in statuses.items():
            print(f'  {status}: {count}')
        
        total_times = [float(r['Total Waktu (detik)']) for r in ver_rows]
        print(f'Total Waktu: mean={statistics.mean(total_times):.4f}s')

# 3. Batch Modification Logs
batch_log = BASE_DIR / 'logs' / 'batch_modification_logs.json'
if os.path.exists(batch_log):
    with open(batch_log, 'r', encoding='utf-8') as f:
        batch_data = json.load(f)
    
    print(f'\n--- BATCH MODIFICATION ({len(batch_data)} batches) ---')
    total_fake = sum(entry.get('total_fake_qr', 0) for entry in batch_data)
    print(f'Total fake QR: {total_fake}')

# 4. Modification Logs
mod_log = BASE_DIR / 'logs' / 'modification_logs.json'
if os.path.exists(mod_log):
    with open(mod_log, 'r', encoding='utf-8') as f:
        mod_data = json.load(f)
    
    print(f'\n--- MODIFICATION LOGS ({len(mod_data)} entries) ---')
    
    # Count modification types
    mod_types = {'nama_changed': 0, 'id_changed': 0, 'nonce_changed': 0, 'timestamp_changed': 0, 'signature_modified': 0}
    for entry in mod_data:
        mods = entry.get('modifications', {})
        for key in mod_types:
            if mods.get(key, False):
                mod_types[key] += 1
    
    for mod_type, count in mod_types.items():
        print(f'  {mod_type}: {count}')

# 5. QR Stats
stats_file = BASE_DIR / 'logs' / 'qr_stats.json'
if os.path.exists(stats_file):
    with open(stats_file, 'r', encoding='utf-8') as f:
        stats = json.load(f)
    
    print(f'\n--- QR STATS ---')
    print(f'QR Count: {stats["qr_count"]}')
    print(f'Verify Count: {stats["verify_count"]}')
    print(f'Total Generate Time: {stats["total_generate_time"]:.4f}s')
    print(f'Total Verify Time: {stats["total_verify_time"]:.4f}s')
    if stats['file_sizes']:
        print(f'File Sizes: {stats["file_sizes"]}')
    if stats['dimensions']:
        print(f'Dimensions: {stats["dimensions"]}')

print('\n' + '=' * 60)
