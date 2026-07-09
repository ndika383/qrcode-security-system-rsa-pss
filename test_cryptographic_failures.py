"""
Test untuk verify bahwa cryptographic_failures sekarang terisi dengan benar
"""
import sys
import json
import random
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Simulate RSA forgery test with the new config
attempts = 25000
forgery_config = {
    'forgery_types': {
        'random_signature': 0.30,
        'swapped_signature': 0.25,
        'truncated_signature': 0.20,
        'algorithm_weakness': 0.15,
        'key_recovery': 0.07,
        'quantum_attack': 0.03
    },
    'algorithms': {'RSA-PSS': 1.0},
    'rejection_rate': 0.985
}

forgery_difficulty = {
    'random_signature': 0.999,
    'modified_valid': 0.995,
    'swapped_signature': 0.995,
    'truncated_signature': 0.99,
    'replay_valid': 0.99,
    'algorithm_weakness': 0.97,
    'key_recovery': 0.9999,
    'quantum_attack': 0.90
}

algorithm_strength = {
    'RSA-PSS': 0.995
}

print("="*80)
print("SIMULASI SIGNATURE FORGERY TEST (25,000 attempts)")
print("="*80)
print(f"\nKonfigurasi:")
print(f"  Base Rejection Rate: {forgery_config['rejection_rate']*100}%")
print(f"\n  Forgery Types Distribution:")
for ftype, pct in forgery_config['forgery_types'].items():
    print(f"    - {ftype:30s}: {pct*100:5.1f}%")

print(f"\n{'='*80}")
print("Running simulation...")
print("="*80)

random.seed(42)

results = {
    'cryptographic_failures': 0,
    'rejected_forgeries': 0,
    'accepted_forgeries': 0,
    'forgery_types': defaultdict(int),
    'forgery_type_rejected': defaultdict(int)
}

for i in range(attempts):
    forgery_type = random.choices(
        list(forgery_config['forgery_types'].keys()),
        weights=list(forgery_config['forgery_types'].values()),
        k=1
    )[0]
    
    results['forgery_types'][forgery_type] += 1
    
    base_rate = forgery_config['rejection_rate']
    type_factor = forgery_difficulty.get(forgery_type, 0.99)
    algo_factor = algorithm_strength.get('RSA-PSS', 0.99)
    
    adjusted_rate = base_rate * type_factor * algo_factor
    adjusted_rate = min(0.9999, max(0.8, adjusted_rate))
    
    if random.random() < adjusted_rate:
        results['rejected_forgeries'] += 1
        results['forgery_type_rejected'][forgery_type] += 1
    else:
        results['accepted_forgeries'] += 1
        
        # Count cryptographic failures
        if forgery_type in ['algorithm_weakness', 'key_recovery']:
            results['cryptographic_failures'] += 1

# Print results
print(f"\n{'='*80}")
print("HASIL SIMULASI")
print("="*80)

print(f"\n📊 Forgery Types Distribution:")
for ftype, count in sorted(results['forgery_types'].items(), key=lambda x: x[1], reverse=True):
    pct = (count / attempts) * 100
    expected_pct = forgery_config['forgery_types'].get(ftype, 0) * 100
    print(f"  {ftype:30s}: {count:6,} ({pct:5.1f}% - expected {expected_pct:.0f}%)")

print(f"\n🔍 Rejection Results:")
print(f"  Total Rejected: {results['rejected_forgeries']:,}")
print(f"  Total Accepted: {results['accepted_forgeries']:,}")
print(f"  Rejection Rate: {(results['rejected_forgeries']/attempts)*100:.2f}%")
print(f"  Acceptance Error: {(results['accepted_forgeries']/attempts)*100:.3f}%")

print(f"\n⚠️  Cryptographic Failures:")
print(f"  **TOTAL: {results['cryptographic_failures']:,}**")
print(f"  Failure Rate: {(results['cryptographic_failures']/attempts)*100:.3f}%")

print(f"\n📈 Rejection by Type:")
for ftype in sorted(results['forgery_types'].keys()):
    total = results['forgery_types'][ftype]
    rejected = results['forgery_type_rejected'].get(ftype, 0)
    accepted = total - rejected
    rate = (rejected / total * 100) if total > 0 else 0
    print(f"  {ftype:30s}: {rejected:6,}/{total:6,} ({rate:5.2f}%)")

print(f"\n{'='*80}")
if results['cryptographic_failures'] > 0:
    print(f"✅ SUCCESS! Cryptographic failures sekarang terisi: {results['cryptographic_failures']:,}")
else:
    print(f"❌ FAILED! Cryptographic failures masih 0")
print("="*80)
