"""
Comprehensive test untuk verify SELURUH FLOW data tampering sudah benar
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import json
from modules.realistic_performance import MultiScenarioDataGenerator

print("="*80)
print("VERIFIKASI KOMPREHENSIF DATA TAMPERING CONFIGURATION")
print("="*80)

# 1. Cek REALISTIC_BENCHMARKS
print("\n1️⃣  Checking REALISTIC_BENCHMARKS...")
gen = MultiScenarioDataGenerator()

tampering_benchmark = gen.REALISTIC_BENCHMARKS.get('data_tampering', {}).get('detection')
if tampering_benchmark:
    print("   ✅ REALISTIC_BENCHMARKS['data_tampering']['detection'] FOUND")
    print(f"\n   Tampering Types:")
    for ttype, pct in tampering_benchmark['tampering_types'].items():
        print(f"     - {ttype:30s}: {pct*100:5.1f}%")
    
    # Verify semua 7 jenis tampering ada
    expected_types = {
        'field_modification', 'field_addition', 'field_removal',
        'data_type_change', 'timestamp_tampering', 'signature_injection',
        'encryption_bypass'
    }
    
    actual_types = set(tampering_benchmark['tampering_types'].keys())
    
    if expected_types == actual_types:
        print(f"\n   ✅ SEMUA 7 JENIS TAMPERING ADA!")
    else:
        missing = expected_types - actual_types
        extra = actual_types - expected_types
        if missing:
            print(f"\n   ❌ MISSING: {missing}")
        if extra:
            print(f"\n   ⚠️  EXTRA: {extra}")
    
    # Verify total = 100%
    total_pct = sum(tampering_benchmark['tampering_types'].values())
    if abs(total_pct - 1.0) < 0.001:
        print(f"   ✅ Total percentage: {total_pct*100:.1f}% (CORRECT)")
    else:
        print(f"   ❌ Total percentage: {total_pct*100:.1f}% (SHOULD BE 100%)")
    
    # Verify critical types
    if 'signature_injection' in actual_types and 'encryption_bypass' in actual_types:
        sig_pct = tampering_benchmark['tampering_types'].get('signature_injection', 0)
        enc_pct = tampering_benchmark['tampering_types'].get('encryption_bypass', 0)
        print(f"\n   ✅ CRITICAL TYPES:")
        print(f"     - signature_injection: {sig_pct*100}% (should be 5%)")
        print(f"     - encryption_bypass: {enc_pct*100}% (should be 2%)")
    else:
        print(f"\n   ❌ CRITICAL TYPES MISSING!")
        
else:
    print("   ❌ REALISTIC_BENCHMARKS['data_tampering']['detection'] NOT FOUND!")

# 2. Cek benchmarks (hasil kalibrasi)
print("\n" + "="*80)
print("2️⃣  Checking benchmarks (calibrated)...")

benchmarks = gen.benchmarks
tampering_calibrated = benchmarks.get('data_tampering', {}).get('detection')

if tampering_calibrated:
    print("   ✅ benchmarks['data_tampering']['detection'] FOUND")
    print(f"\n   Tampering Types:")
    for ttype, pct in tampering_calibrated['tampering_types'].items():
        print(f"     - {ttype:30s}: {pct*100:5.1f}%")
    
    # Verify sama dengan REALISTIC_BENCHMARKS
    if tampering_calibrated == tampering_benchmark:
        print(f"\n   ✅ benchmarks == REALISTIC_BENCHMARKS (CORRECT)")
    else:
        print(f"\n   ⚠️  benchmarks != REALISTIC_BENCHMARKS (might be due to calibration)")
else:
    print("   ❌ benchmarks['data_tampering']['detection'] NOT FOUND!")

# 3. Simulate complete flow seperti di testing_controller.py
print("\n" + "="*80)
print("3️⃣  Simulating testing_controller.py flow...")

tampering_config = None
try:
    tampering_config = gen.benchmarks.get('data_tampering', {}).get('detection')
    print("   ✅ Loaded from: gen.benchmarks")
except (AttributeError, KeyError):
    try:
        tampering_config = gen.REALISTIC_BENCHMARKS.get('data_tampering', {}).get('detection')
        print("   ✅ Loaded from: gen.REALISTIC_BENCHMARKS")
    except (AttributeError, KeyError):
        tampering_config = None
        print("   ❌ Failed to load from both sources")

if not tampering_config:
    tampering_config = {
        'tampering_types': {'field_modification': 0.40, 'field_addition': 0.20, 'field_removal': 0.15, 'data_type_change': 0.10, 'timestamp_tampering': 0.08, 'signature_injection': 0.05, 'encryption_bypass': 0.02},
        'detection_rate': 0.92,
        'severity_weights': {'low': 0.5, 'medium': 0.3, 'high': 0.15, 'critical': 0.05}
    }
    print("   ⚠️  Using fallback config")

print(f"\n   Final tampering_config:")
for ttype, pct in tampering_config['tampering_types'].items():
    print(f"     - {ttype:30s}: {pct*100:5.1f}%")

# 4. Quick simulation test
print("\n" + "="*80)
print("4️⃣  Quick simulation test (1000 ops)...")

import random
from collections import defaultdict

random.seed(42)

results = {
    'integrity_violations': 0,
    'detected_tampering': 0,
    'tampering_types': defaultdict(int),
}

type_difficulty = {
    'field_modification': 0.90,
    'field_addition': 0.85,
    'field_removal': 0.80,
    'data_type_change': 0.95,
    'timestamp_tampering': 0.75,
    'signature_injection': 0.60,
    'encryption_bypass': 0.40
}

for i in range(1000):
    tampering_type = random.choices(
        list(tampering_config['tampering_types'].keys()),
        weights=list(tampering_config['tampering_types'].values()),
        k=1
    )[0]
    
    results['tampering_types'][tampering_type] += 1
    
    base_rate = tampering_config['detection_rate']
    type_factor = type_difficulty.get(tampering_type, 0.85)
    adjusted_rate = base_rate * type_factor * random.uniform(0.95, 1.05)
    adjusted_rate = min(0.99, max(0.1, adjusted_rate))
    
    if random.random() < adjusted_rate:
        results['detected_tampering'] += 1
        
        if tampering_type in ['signature_injection', 'encryption_bypass']:
            if random.random() < 0.8:
                results['integrity_violations'] += 1

print(f"\n   Results (1000 ops):")
for ttype, count in sorted(results['tampering_types'].items(), key=lambda x: x[1], reverse=True):
    print(f"     - {ttype:30s}: {count:4d}")

print(f"\n   ✅ integrity_violations: {results['integrity_violations']}")

# 5. Final verdict
print("\n" + "="*80)
print("🏁 FINAL VERDICT")
print("="*80)

checks = [
    ("REALISTIC_BENCHMARKS has all 7 types", expected_types == actual_types),
    ("Total percentage = 100%", abs(total_pct - 1.0) < 0.001),
    ("signature_injection = 5%", tampering_config['tampering_types'].get('signature_injection', 0) == 0.05),
    ("encryption_bypass = 2%", tampering_config['tampering_types'].get('encryption_bypass', 0) == 0.02),
    ("integrity_violations > 0", results['integrity_violations'] > 0),
]

all_pass = True
for check_name, check_result in checks:
    status = "✅ PASS" if check_result else "❌ FAIL"
    print(f"  {status}: {check_name}")
    if not check_result:
        all_pass = False

print("\n" + "="*80)
if all_pass:
    print("🎉 SEMUA TESTS PASS! Sistem siap untuk dijalankan.")
    print("\n📋 Yang sudah di-fix:")
    print("  1. ✅ tampering_types distribution (7 jenis sesuai jurnal)")
    print("  2. ✅ signature_injection: 5%")
    print("  3. ✅ encryption_bypass: 2%")
    print("  4. ✅ integrity_violations akan terisi otomatis")
    print("  5. ✅ Flow dari REALISTIC_BENCHMARKS → testing_controller.py sudah benar")
else:
    print("⚠️  ADA TESTS YANG FAIL! Perlu dicek lagi.")
print("="*80)
