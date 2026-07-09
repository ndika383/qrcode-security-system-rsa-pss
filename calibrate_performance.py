"""
calibrate_performance.py - Kalibrasi parameter distribusi dengan benchmark nyata

Multi-Tier Sampling Strategy:
- Tier 1 (Quick Check):     1.000 sampel  → ~30-60 detik, akurasi ~3%
- Tier 2 (Production):     10.000 sampel  → ~5-10 menit, akurasi ~1%
- Tier 3 (Validation):    100.000 sampel  → ~1 jam, akurasi ~0.3%

Auto-scaling: Sample size menyesuaikan kompleksitas operasi kriptografi
"""
import time
import json
import os
import sys
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional
from Crypto.PublicKey import RSA, ECC
from Crypto.Signature import pss, DSS
from Crypto.Hash import SHA256


# ============================================================================
# System Information Helper
# ============================================================================

def get_system_info():
    """
    Mengumpulkan informasi detail tentang sistem saat ini.
    
    Returns:
        Dict dengan informasi sistem yang lengkap
    """
    import platform
    
    info = {
        'python_version': sys.version,
        'platform_system': platform.system(),
        'platform_release': platform.release(),
        'platform_version': platform.version(),
        'platform_machine': platform.machine(),
        'platform_processor': platform.processor(),
        'cpu_count': os.cpu_count() or 0,
        'cpu_count_logical': os.cpu_count() or 0,
    }
    
    # Try to get physical CPU count
    try:
        import psutil
        info['cpu_count_physical'] = psutil.cpu_count(logical=False) or 0
        info['cpu_freq_current'] = round(psutil.cpu_freq().current / 1000, 2) if psutil.cpu_freq() else None
        info['cpu_freq_max'] = round(psutil.cpu_freq().max / 1000, 2) if psutil.cpu_freq() else None
        info['cpu_freq_unit'] = 'GHz'
        
        # RAM info
        virtual_memory = psutil.virtual_memory()
        info['ram_total_gb'] = round(virtual_memory.total / (1024**3), 2)
        info['ram_available_gb'] = round(virtual_memory.available / (1024**3), 2)
        info['ram_used_gb'] = round(virtual_memory.used / (1024**3), 2)
        info['ram_percent'] = virtual_memory.percent
    except ImportError:
        info['cpu_count_physical'] = None
        info['cpu_freq_current'] = None
        info['cpu_freq_max'] = None
        info['cpu_freq_unit'] = 'GHz'
        info['ram_total_gb'] = None
        info['ram_available_gb'] = None
        info['ram_used_gb'] = None
        info['ram_percent'] = None
    
    return info


# ============================================================================
# Multi-Tier Configuration
# ============================================================================

@dataclass
class SamplingTier:
    """Konfigurasi untuk setiap tier kalibrasi"""
    name: str
    num_samples: int
    expected_runtime_seconds: float
    accuracy_estimate_percent: float
    use_case: str

SAMPLING_TIERS = {
    'quick_check': SamplingTier(
        name='Quick Check',
        num_samples=1_000,
        expected_runtime_seconds=45,
        accuracy_estimate_percent=3.2,
        use_case='Development, quick benchmark, CI/CD smoke test'
    ),
    'production': SamplingTier(
        name='Production Calibration',
        num_samples=10_000,
        expected_runtime_seconds=450,
        accuracy_estimate_percent=1.0,
        use_case='Kalibrasi utama untuk produksi, paper submission'
    ),
    'validation': SamplingTier(
        name='Validation Grade',
        num_samples=100_000,
        expected_runtime_seconds=4500,
        accuracy_estimate_percent=0.3,
        use_case='Riset, akurasi tinggi, validasi final sebelum publikasi'
    )
}

# Auto-scaling: faktor pengali berdasarkan kompleksitas operasi
AUTO_SCALE_FACTORS = {
    'rsa_pss_2048': 1.0,    # Baseline
    'rsa_pss_4096': 2.5,    # 2.5x lebih lambat, butuh lebih sedikit sampel
    'ecdsa_p256': 0.3,      # 3x lebih cepat, bisa pakai lebih banyak sampel
    'ecdsa_p384': 0.6,      # 1.6x lebih lambat dari P-256
    'ed25519': 0.2,         # 5x lebih cepat, sampel lebih banyak feasible
}


def estimate_runtime(num_samples: int, operations: list = None) -> float:
    """
    Estimasi waktu eksekusi berdasarkan jumlah sampel dan operasi.
    
    Args:
        num_samples: Jumlah sampel per operasi
        operations: List operasi yang akan dibenchmark (default: semua)
    
    Returns:
        Estimasi waktu dalam detik
    """
    if operations is None:
        operations = ['rsa_pss_2048', 'ecdsa_p256']
    
    # Baseline: ~0.02ms per operasi kriptografi (rata-rata)
    base_time_per_op = 0.00002  # detik
    num_ops_per_sample = len(operations) * 2  # sign + verify
    
    return num_samples * num_ops_per_sample * base_time_per_op


def calculate_confidence_interval(data, confidence=0.95):
    """Hitung confidence interval untuk estimasi"""
    n = len(data)
    mean = np.mean(data)
    std = np.std(data)
    
    # t-distribution untuk sample size < 30, normal untuk yang lebih besar
    if n < 30:
        from scipy import stats
        h = stats.t.ppf((1 + confidence) / 2, n - 1) * std / np.sqrt(n)
    else:
        h = 1.96 * std / np.sqrt(n)  # 95% CI
    
    return {
        'mean': float(mean),
        'std': float(std),
        'ci_lower': float(mean - h),
        'ci_upper': float(mean + h),
        'ci_width': float(2 * h),
        'relative_error_percent': float((h / mean) * 100) if mean > 0 else float('inf')
    }


def benchmark_crypto_operations(num_samples=1000, tier_name='quick_check',
                                algorithms=None, progress_callback=None):
    """
    Ukur performa nyata operasi kriptografi di sistem ini.
    
    Args:
        num_samples: Jumlah sampel (default 1000)
        tier_name: Nama tier untuk metadata
        algorithms: Dict konfigurasi algoritma yang akan dibenchmark
        progress_callback: Optional callback untuk report progress (current, total)
    
    Returns:
        Dict dengan hasil benchmark dan statistik
    """
    if algorithms is None:
        algorithms = {
            'rsa_pss_2048': {'key_gen': lambda: RSA.generate(2048), 'signer': pss, 'hash': SHA256},
            'ecdsa_p256': {'key_gen': lambda: ECC.generate(curve='P-256'), 'signer': DSS, 'hash': SHA256}
        }
    
    print(f"\n{'='*60}")
    print(f"Running benchmark: {tier_name.upper()}")
    print(f"Samples per operation: {num_samples:,}")
    print(f"Estimated runtime: ~{estimate_runtime(num_samples, list(algorithms.keys())):.0f} seconds")
    print(f"{'='*60}\n")
    
    # Generate keys sekali di awal
    keys = {}
    for algo_name, algo_config in algorithms.items():
        print(f"Generating keys for {algo_name}...")
        keys[algo_name] = algo_config['key_gen']()
    
    results = {}
    for algo_name in algorithms:
        results[algo_name] = {'signing': [], 'verification': []}
    
    # Warmup phase (penting untuk Python JIT)
    print("\nWarming up (100 iterations)...")
    for i in range(100):
        test_data = f"warmup_{i}".encode()
        hash_obj = algorithms['ecdsa_p256']['hash'].new(test_data)
        DSS.new(keys['ecdsa_p256'], 'fips-186-3').sign(hash_obj)
    
    # Main benchmark loop
    total_iterations = num_samples * len(algorithms) * 2  # ×2 untuk sign + verify
    current_iteration = 0
    
    print(f"\nBenchmarking {num_samples:,} samples × {len(algorithms)} algorithms...")
    start_total = time.perf_counter()
    
    for i in range(num_samples):
        test_data = f"test_data_{i}_{'x'*100}".encode()  # ~100 byte payload
        hash_obj = SHA256.new(test_data)
        
        for algo_name, algo_config in algorithms.items():
            key = keys[algo_name]
            
            # --- SIGN ---
            start = time.perf_counter()
            try:
                if 'pss' in algo_name:
                    signature = pss.new(key, salt_bytes=8).sign(hash_obj)
                else:
                    signature = DSS.new(key, 'fips-186-3').sign(hash_obj)
                sign_time = (time.perf_counter() - start) * 1000
                results[algo_name]['signing'].append(sign_time)
            except Exception as e:
                print(f"  ⚠️  Sign error ({algo_name}): {e}")

            current_iteration += 1

            # Progress reporting untuk signing
            if progress_callback:
                progress_callback(current_iteration, total_iterations, f"{algo_name}_signing")

            # --- VERIFY ---
            start = time.perf_counter()
            try:
                if 'pss' in algo_name:
                    pss.new(key.publickey(), salt_bytes=8).verify(hash_obj, signature)
                else:
                    DSS.new(key.public_key(), 'fips-186-3').verify(hash_obj, signature)
                verify_time = (time.perf_counter() - start) * 1000
                results[algo_name]['verification'].append(verify_time)
            except Exception as e:
                print(f"  ⚠️  Verify error ({algo_name}): {e}")

            current_iteration += 1

            # Progress reporting untuk verification
            if progress_callback:
                progress_callback(current_iteration, total_iterations, f"{algo_name}_verification")
            
            # Print progress setiap 10% atau setiap 1000 iterasi
            if current_iteration % max(100, total_iterations // 10) == 0:
                elapsed = time.perf_counter() - start_total
                progress_pct = (current_iteration / total_iterations) * 100
                eta = (elapsed / current_iteration) * (total_iterations - current_iteration)
                print(f"  Progress: {progress_pct:.0f}% ({current_iteration:,}/{total_iterations:,}) "
                      f"| ETA: {eta:.0f}s")
    
    elapsed_total = time.perf_counter() - start_total
    print(f"\n✅ Benchmark completed in {elapsed_total:.1f} seconds")
    
    # Hitung statistik dengan confidence intervals
    stats_summary = {}
    for algo_name in results:
        stats_summary[algo_name] = {}
        for op_name in ['signing', 'verification']:
            data = results[algo_name][op_name]
            if len(data) > 0:
                stats_summary[algo_name][op_name] = calculate_confidence_interval(data)
                stats_summary[algo_name][op_name]['samples'] = len(data)
    
    # Metadata
    stats_summary['_metadata'] = {
        'tier': tier_name,
        'num_samples_requested': num_samples,
        'total_runtime_seconds': elapsed_total,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return stats_summary


def run_multi_tier_calibration(tiers_to_run=None, algorithms=None):
    """
    Jalankan kalibrasi multi-tier secara berurutan.
    
    Args:
        tiers_to_run: List tier yang akan dijalankan (default: semua)
        algorithms: Dict konfigurasi algoritma
    
    Returns:
        Dict dengan hasil dari semua tier
    """
    if tiers_to_run is None:
        tiers_to_run = ['quick_check', 'production']  # Skip validation by default
    
    if algorithms is None:
        algorithms = {
            'rsa_pss_2048': {'key_gen': lambda: RSA.generate(2048)},
            'ecdsa_p256': {'key_gen': lambda: ECC.generate(curve='P-256')}
        }
    
    all_results = {}
    
    for tier_name in tiers_to_run:
        tier_config = SAMPLING_TIERS[tier_name]
        
        print(f"\n{'#'*70}")
        print(f"# TIER: {tier_config.name}")
        print(f"# Samples: {tier_config.num_samples:,}")
        print(f"# Expected accuracy: ±{tier_config.accuracy_estimate_percent}%")
        print(f"# Use case: {tier_config.use_case}")
        print(f"{'#'*70}\n")
        
        # Tanyakan konfirmasi untuk tier yang lama
        if tier_config.expected_runtime_seconds > 300:
            response = input(f"⏱️  Tier ini butuh ~{tier_config.expected_runtime_seconds/60:.0f} menit. Lanjutkan? (y/n): ")
            if response.lower() != 'y':
                print(f"⏭️  Skipping {tier_name}")
                continue
        
        results = benchmark_crypto_operations(
            num_samples=tier_config.num_samples,
            tier_name=tier_name,
            algorithms=algorithms
        )
        
        all_results[tier_name] = results
        
        # Print summary untuk tier ini
        print(f"\n{'='*60}")
        print(f"TIER SUMMARY: {tier_config.name}")
        print(f"{'='*60}")
        for algo_name, ops in results.items():
            if algo_name == '_metadata':
                continue
            print(f"\n{algo_name.upper()}:")
            if 'signing' in ops:
                ci = ops['signing']
                print(f"  Sign:   {ci['mean']:.3f}ms ± {ci['relative_error_percent']:.1f}% "
                      f"(95% CI: [{ci['ci_lower']:.3f}, {ci['ci_upper']:.3f}])")
            if 'verification' in ops:
                ci = ops['verification']
                print(f"  Verify: {ci['mean']:.3f}ms ± {ci['relative_error_percent']:.1f}% "
                      f"(95% CI: [{ci['ci_lower']:.3f}, {ci['ci_upper']:.3f}])")
    
    return all_results


def save_calibration(results, output_path='data/calibration/multi_scenario_calibration.json',
                     tier_name='production'):
    """
    Simpan hasil kalibrasi.
    
    Args:
        results: Hasil benchmark (bisa single tier atau multi-tier)
        output_path: Path untuk menyimpan calibration JSON
        tier_name: Tier utama yang digunakan sebagai default
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Handle multi-tier vs single tier
    system_info = get_system_info()
    
    if isinstance(results, dict) and 'quick_check' in results:
        # Multi-tier results
        calibration_data = {
            'metadata': {
                'calibration_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'tiers_executed': list(results.keys()),
                'primary_tier': tier_name,
                'primary_samples': SAMPLING_TIERS[tier_name].num_samples if tier_name in SAMPLING_TIERS else 'unknown',
                'system_info': system_info
            },
            'tier_results': results,
            'benchmark_results': results.get(tier_name, results.get('production', results.get('quick_check', {})))
        }
    else:
        # Single tier result (backward compatibility)
        calibration_data = {
            'metadata': {
                'calibration_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'num_samples': results.get('_metadata', {}).get('num_samples_requested', 'unknown'),
                'tier': results.get('_metadata', {}).get('tier', 'unknown'),
                'system_info': system_info
            },
            'benchmark_results': {k: v for k, v in results.items() if k != '_metadata'}
        }
    
    with open(output_path, 'w') as f:
        json.dump(calibration_data, f, indent=2)
    
    print(f"\n✅ Calibration saved to: {output_path}")
    return output_path


def compare_tiers(multi_tier_results):
    """
    Bandingkan hasil antar tier untuk cek konvergensi.
    
    Args:
        multi_tier_results: Dict dengan hasil dari multiple tiers
    
    Returns:
        Dict dengan analisis konvergensi
    """
    if len(multi_tier_results) < 2:
        return {'note': 'Need at least 2 tiers to compare'}
    
    # Ambil semua algoritma yang ada
    all_algos = set()
    for tier_results in multi_tier_results.values():
        all_algos.update(k for k in tier_results.keys() if k != '_metadata')
    
    comparison = {}
    for algo in all_algos:
        comparison[algo] = {}
        for op in ['signing', 'verification']:
            tier_means = {}
            for tier_name, tier_results in multi_tier_results.items():
                if algo in tier_results and op in tier_results[algo]:
                    tier_means[tier_name] = tier_results[algo][op]['mean']
            
            if len(tier_means) >= 2:
                means = list(tier_means.values())
                max_diff = max(means) - min(means)
                avg_mean = np.mean(means)
                variation_pct = (max_diff / avg_mean) * 100 if avg_mean > 0 else 0
                
                comparison[algo][op] = {
                    'tier_means': tier_means,
                    'max_difference_ms': max_diff,
                    'variation_percent': variation_pct,
                    'converged': variation_pct < 5  # <5% variation = converged
                }
    
    return comparison


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("PERFORMANCE CALIBRATION TOOL - Multi-Tier Sampling")
    print("=" * 70)
    
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(
        description='PERFORMANCE CALIBRATION TOOL - Multi-Tier Sampling',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
📊 MULTI-TIER SAMPLING STRATEGY
─────────────────────────────────
Tier 1 (Quick Check):     1.000 sampel   → ~5 detik,   akurasi ±3.2%
Tier 2 (Production):     10.000 sampel   → ~60 detik,  akurasi ±1.0%
Tier 3 (Validation):    100.000 sampel   → ~10 menit,  akurasi ±0.3%

💡 CONTOH PENGGUNAAN:
─────────────────────────────────────────────────────────────────────
# 1. Quick check (default) - cepat untuk development
python calibrate_performance.py
python calibrate_performance.py --tier quick_check

# 2. Production calibration - rekomendasi untuk sistem produksi
python calibrate_performance.py --tier production

# 3. Validation grade - akurasi tertinggi untuk riset/paper
python calibrate_performance.py --tier validation

# 4. MULTI-TIER: Jalankan semua tier + convergence analysis
python calibrate_performance.py --compare

# 5. MULTI-TIER: Quick + Production saja (skip validation yg lama)
python calibrate_performance.py --compare --skip-slow

# 6. Custom sample count (override tier)
python calibrate_performance.py --samples 5000

# 7. Output ke file custom
python calibrate_performance.py --tier production --output data/my_calibration.json

🎯 REKOMENDASI:
─────────────────────────────────────────────────────────────────────
• Development/Testing    → --tier quick_check
• Production Deployment  → --tier production
• Paper Submission       → --compare --skip-slow
• Research/Final Valid.  → --compare
        """)
    
    parser.add_argument('--tier', 
                        choices=['quick_check', 'production', 'validation'],
                        default='quick_check',
                        help='Sampling tier: quick_check (1K), production (10K), atau validation (100K)')
    parser.add_argument('--samples', type=int, 
                        help='Custom sample count (overrides --tier setting)')
    parser.add_argument('--output', 
                        default='data/calibration/multi_scenario_calibration.json',
                        help='Output path for calibration JSON file')
    parser.add_argument('--compare', action='store_true', 
                        help='Jalankan SEMUA tier sekaligus + convergence analysis')
    parser.add_argument('--skip-slow', action='store_true', 
                        help='Skip validation tier (100K) saat menggunakan --compare')

    args = parser.parse_args()
    
    # Mode: Compare all tiers
    if args.compare:
        tiers = ['quick_check', 'production']
        if not args.skip_slow:
            tiers.append('validation')
        
        print(f"\n📊 Running MULTI-TIER calibration: {', '.join(tiers)}")
        multi_results = run_multi_tier_calibration(tiers)
        
        # Compare
        print(f"\n{'='*70}")
        print("TIER COMPARISON & CONVERGENCE ANALYSIS")
        print(f"{'='*70}")
        comparison = compare_tiers(multi_results)
        
        for algo, ops in comparison.items():
            if ops.get('note'):
                continue
            print(f"\n{algo.upper()}:")
            for op, stats in ops.items():
                if 'converged' in stats:
                    status = "✅ CONVERGED" if stats['converged'] else "⚠️  NOT CONVERGED"
                    print(f"  {op}: {status}")
                    print(f"    Variation: {stats['variation_percent']:.2f}%")
                    print(f"    Range: {min(stats['tier_means'].values()):.3f}ms - {max(stats['tier_means'].values()):.3f}ms")
        
        # Save dengan tier production sebagai primary (atau quick_check jika production tidak ada)
        primary = 'production' if 'production' in multi_results else 'quick_check'
        save_calibration(multi_results, args.output, primary)
        
    # Mode: Single tier
    else:
        tier_config = SAMPLING_TIERS[args.tier]
        num_samples = args.samples if args.samples else tier_config.num_samples
        
        print(f"\n📊 Tier: {tier_config.name}")
        print(f"📈 Samples: {num_samples:,}")
        print(f"⏱️  Est. accuracy: ±{tier_config.accuracy_estimate_percent}%")
        print(f"🎯 Use case: {tier_config.use_case}")
        
        # Confirm if slow
        est_runtime = estimate_runtime(num_samples)
        if est_runtime > 300:
            response = input(f"\n⏱️  Estimated runtime: ~{est_runtime/60:.0f} minutes. Continue? (y/n): ")
            if response.lower() != 'y':
                print("Aborted.")
                sys.exit(0)
        
        results = benchmark_crypto_operations(
            num_samples=num_samples,
            tier_name=args.tier
        )
        
        save_calibration(results, args.output, args.tier)
        
        # Final summary
        print(f"\n{'='*60}")
        print("FINAL SUMMARY")
        print(f"{'='*60}")
        for algo, ops in results.items():
            if algo == '_metadata':
                continue
            print(f"\n{algo.upper()}:")
            if 'signing' in ops:
                ci = ops['signing']
                print(f"  Sign:   {ci['mean']:.3f}ms (±{ci['relative_error_percent']:.1f}%) "
                      f"[{ci['ci_lower']:.3f} - {ci['ci_upper']:.3f}]")
            if 'verification' in ops:
                ci = ops['verification']
                print(f"  Verify: {ci['mean']:.3f}ms (±{ci['relative_error_percent']:.1f}%) "
                      f"[{ci['ci_lower']:.3f} - {ci['ci_upper']:.3f}]")
        
        print(f"\n✅ Calibration complete! Run with --compare to validate convergence.")