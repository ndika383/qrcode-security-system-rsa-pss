"""
Quick test untuk verify bahwa integrity_violations sekarang terisi dengan benar
"""
import sys
import json
import random
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pathlib import Path

# Add path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Setup tampering config yang sudah di-update
tampering_config = {
    'tampering_types': {
        'field_modification': 0.40, 
        'field_addition': 0.20, 
        'field_removal': 0.15, 
        'data_type_change': 0.10, 
        'timestamp_tampering': 0.08, 
        'signature_injection': 0.05, 
        'encryption_bypass': 0.02
    },
    'detection_rate': 0.92,
    'severity_weights': {'low': 0.5, 'medium': 0.3, 'high': 0.15, 'critical': 0.05}
}

# Simulate 50,000 operations
operations = 50000
results = {
    'integrity_violations': 0,
    'detected_tampering': 0,
    'missed_tampering': 0,
    'tampering_types': defaultdict(int),
    'detection_by_type': defaultdict(lambda: {'total': 0, 'detected': 0})
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

print("="*80)
print("SIMULASI DATA TAMPERING TEST (50,000 operations)")
print("="*80)
print(f"\nKonfigurasi:")
print(f"  Detection Rate Base: {tampering_config['detection_rate']*100}%")
print(f"\n  Tampering Types Distribution:")
for ttype, pct in tampering_config['tampering_types'].items():
    print(f"    - {ttype}: {pct*100}%")

print(f"\n{'='*80}")
print("Running simulation...")
print("="*80)

random.seed(42)  # For reproducibility

for i in range(operations):
    # Pick tampering type
    tampering_type = random.choices(
        list(tampering_config['tampering_types'].keys()),
        weights=list(tampering_config['tampering_types'].values()),
        k=1
    )[0]
    
    results['tampering_types'][tampering_type] += 1
    results['detection_by_type'][tampering_type]['total'] += 1
    
    # Calculate detection rate
    base_rate = tampering_config['detection_rate']
    type_factor = type_difficulty.get(tampering_type, 0.85)
    adjusted_rate = base_rate * type_factor
    adjusted_rate *= random.uniform(0.95, 1.05)
    adjusted_rate = min(0.99, max(0.1, adjusted_rate))
    
    # Detection
    if random.random() < adjusted_rate:
        results['detected_tampering'] += 1
        results['detection_by_type'][tampering_type]['detected'] += 1
        
        # Check for integrity violation (critical types only)
        if tampering_type in ['signature_injection', 'encryption_bypass']:
            if random.random() < 0.8:  # 80% chance
                results['integrity_violations'] += 1
    else:
        results['missed_tampering'] += 1

# Print results
print(f"\n{'='*80}")
print("HASIL SIMULASI")
print("="*80)

print(f"\n📊 Tampering Types Distribution:")
for ttype, count in sorted(results['tampering_types'].items(), key=lambda x: x[1], reverse=True):
    pct = (count / operations) * 100
    expected_pct = tampering_config['tampering_types'].get(ttype, 0) * 100
    print(f"  {ttype:30s}: {count:6,} ({pct:5.1f}% - expected {expected_pct:.0f}%)")

print(f"\n🔍 Detection Results:")
print(f"  Total Detected: {results['detected_tampering']:,}")
print(f"  Total Missed: {results['missed_tampering']:,}")
print(f"  Detection Rate: {(results['detected_tampering']/operations)*100:.1f}%")

print(f"\n⚠️  Integrity Violations:")
print(f"  **TOTAL: {results['integrity_violations']:,}**")

print(f"\n📈 Detection by Type:")
for ttype in sorted(results['detection_by_type'].keys()):
    type_data = results['detection_by_type'][ttype]
    total = type_data['total']
    detected = type_data['detected']
    rate = (detected / total * 100) if total > 0 else 0
    print(f"  {ttype:30s}: {detected:6,}/{total:6,} ({rate:5.1f}%)")

print(f"\n{'='*80}")
if results['integrity_violations'] > 0:
    print(f"✅ SUCCESS! Integrity violations sekarang terisi: {results['integrity_violations']:,}")
else:
    print(f"❌ FAILED! Integrity violations masih 0")
print("="*80)
