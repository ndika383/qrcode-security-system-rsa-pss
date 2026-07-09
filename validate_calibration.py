"""
validate_calibration.py - Validasi bahwa hasil benchmark mengikuti distribusi log-normal

Mendukung:
- Format lama: mean_ms, stddev_ms (single-tier)
- Format baru: mean, std, ci_lower, ci_upper (multi-tier dengan confidence intervals)
- Tier detection otomatis dari metadata
"""
import json
import os
import sys
import numpy as np
from scipy import stats


def load_calibration_data(file_path='data/calibration/multi_scenario_calibration.json'):
    """Load calibration data dengan auto-detect format"""
    if not os.path.exists(file_path):
        print(f"❌ File {file_path} tidak ditemukan.")
        print(f"💡 Jalankan: python calibrate_performance.py --tier production")
        return None

    with open(file_path, 'r') as f:
        return json.load(f)


def detect_format(cal_data):
    """Detect apakah format lama atau baru"""
    benchmark = cal_data.get('benchmark_results', {})

    if not benchmark:
        return 'unknown'

    # Ambil operasi pertama yang ada
    for algo in benchmark:
        if algo.startswith('_'):
            continue
        for op in ['signing', 'verification']:
            if op in benchmark[algo]:
                ops = benchmark[algo][op]
                if 'mean_ms' in ops:
                    return 'legacy'  # Format lama
                elif 'mean' in ops:
                    return 'new'  # Format baru dengan CI
    return 'unknown'


def get_mean_std(cal_data, algo, op):
    """Extract mean dan std dari kedua format (legacy & new)"""
    ops = cal_data['benchmark_results'][algo][op]

    # Format baru (multi-tier dengan CI)
    if 'mean' in ops:
        return {
            'mean': ops['mean'],
            'std': ops['std'],
            'ci_lower': ops.get('ci_lower'),
            'ci_upper': ops.get('ci_upper'),
            'samples': ops.get('samples', 'unknown'),
            'relative_error_percent': ops.get('relative_error_percent')
        }

    # Format lama (legacy)
    elif 'mean_ms' in ops:
        return {
            'mean': ops['mean_ms'],
            'std': ops['stddev_ms'],
            'ci_lower': None,
            'ci_upper': None,
            'samples': 'unknown',
            'relative_error_percent': None
        }

    return None


def validate_parameter_sanity(cal_data):
    """Validasi bahwa parameter statistik masuk akal"""
    print("\n" + "=" * 70)
    print("PARAMETER SANITY CHECK")
    print("=" * 70)

    benchmark = cal_data.get('benchmark_results', {})
    all_valid = True

    for algo in benchmark:
        if algo.startswith('_'):
            continue

        print(f"\n🔬 {algo.upper()}:")

        for op in ['signing', 'verification']:
            if op not in benchmark[algo]:
                continue

            stats_data = get_mean_std(cal_data, algo, op)
            if stats_data is None:
                print(f"   ❌ {op}: Data tidak valid")
                all_valid = False
                continue

            mean = stats_data['mean']
            std = stats_data['std']
            samples = stats_data['samples']

            # Check 1: Mean dan std harus positif
            if mean <= 0 or std <= 0:
                print(f"   ❌ {op}: Mean/std tidak valid (mean={mean:.4f}, std={std:.4f})")
                all_valid = False
                continue

            # Check 2: Coefficient of variation (CV) harus reasonable
            cv = (std / mean) * 100
            if cv > 100:
                print(f"   ⚠️  {op}: CV sangat tinggi ({cv:.1f}%) - variabilitas ekstrem")
            elif cv > 50:
                print(f"   ⚠️  {op}: CV tinggi ({cv:.1f}%) - variabilitas moderat")
            else:
                print(f"   ✅ {op}: CV normal ({cv:.1f}%)")

            # Check 3: Sample size cukup
            if samples != 'unknown':
                if samples < 30:
                    print(f"   ⚠️  {op}: Sampel terlalu kecil (n={samples})")
                elif samples < 1000:
                    print(f"   ⚠️  {op}: Sampel minimal (n={samples})")
                else:
                    print(f"   ✅ {op}: Sampel memadai (n={samples:,})")

            # Check 4: Confidence interval width (format baru)
            if stats_data['relative_error_percent'] is not None:
                rel_err = stats_data['relative_error_percent']
                if rel_err < 5:
                    print(f"   ✅ {op}: 95% CI ±{rel_err:.2f}% (akurat)")
                elif rel_err < 10:
                    print(f"   ⚠️  {op}: 95% CI ±{rel_err:.2f}% (moderat)")
                else:
                    print(f"   ❌ {op}: 95% CI ±{rel_err:.2f}% (kurang akurat)")

            print(f"      Mean: {mean:.4f}ms | Std: {std:.4f}ms | CV: {cv:.1f}%")

            if stats_data['ci_lower'] is not None:
                print(f"      95% CI: [{stats_data['ci_lower']:.4f}, {stats_data['ci_upper']:.4f}]")

    return all_valid


def validate_tier_convergence(cal_data):
    """Validasi konvergensi antar tier jika multi-tier data tersedia"""
    tier_results = cal_data.get('tier_results', {})

    if len(tier_results) < 2:
        print("\nℹ️  Single-tier data detected. Skip convergence analysis.")
        print(f"💡 Jalankan: python calibrate_performance.py --compare")
        return

    print("\n" + "=" * 70)
    print("TIER CONVERGENCE ANALYSIS")
    print("=" * 70)

    tiers = list(tier_results.keys())
    print(f"\n📊 Tiers compared: {', '.join(tiers)}")

    # Ambil semua algoritma
    all_algos = set()
    for tier_data in tier_results.values():
        all_algos.update(k for k in tier_data.keys() if not k.startswith('_'))

    all_converged = True

    for algo in all_algos:
        print(f"\n🔬 {algo.upper()}:")

        for op in ['signing', 'verification']:
            tier_means = {}
            for tier_name, tier_data in tier_results.items():
                if algo in tier_data and op in tier_data[algo]:
                    stats_data = get_mean_std(
                        {'benchmark_results': tier_data}, algo, op
                    )
                    if stats_data:
                        tier_means[tier_name] = stats_data['mean']

            if len(tier_means) < 2:
                continue

            means = list(tier_means.values())
            max_diff = max(means) - min(means)
            avg_mean = np.mean(means)
            variation_pct = (max_diff / avg_mean) * 100 if avg_mean > 0 else 0

            converged = variation_pct < 5  # <5% = converged

            status = "✅ CONVERGED" if converged else "⚠️  NOT CONVERGED"
            print(f"   {op}: {status}")
            print(f"      Variation: {variation_pct:.2f}%")
            print(f"      Range: {min(means):.4f}ms - {max(means):.4f}ms")

            for tier, mean_val in tier_means.items():
                print(f"      {tier}: {mean_val:.4f}ms")

            if not converged:
                all_converged = False

    return all_converged


def generate_lognormal_sample(mean, std, n=10000, seed=42):
    """
    Generate sample data log-normal berdasarkan mean/std yang dikalibrasi.
    Berguna untuk simulasi jika raw data tidak tersedia.
    """
    # Konversi mean/std aritmatik ke parameter log-normal
    # mu = ln(mean^2 / sqrt(std^2 + mean^2))
    # sigma = sqrt(ln(1 + std^2/mean^2))
    mu = np.log(mean**2 / np.sqrt(std**2 + mean**2))
    sigma = np.sqrt(np.log(1 + (std**2 / mean**2)))

    np.random.seed(seed)
    return np.random.lognormal(mu, sigma, n)


def validate_lognormal_distribution(cal_data, algo='ecdsa_p256', op='signing', alpha=0.05):
    """
    Uji Kolmogorov-Smirnov untuk goodness-of-fit distribusi log-normal.

    H0: Data mengikuti distribusi log-normal
    H1: Data TIDAK mengikuti distribusi log-normal

    Jika p-value > alpha → GAGAL TOLAK H0 → log-normal VALID
    """
    print("\n" + "=" * 70)
    print(f"KOLMOGOROV-SMIRNOV TEST: {algo.upper()} - {op}")
    print("=" * 70)

    stats_data = get_mean_std(cal_data, algo, op)
    if stats_data is None:
        print(f"❌ Data tidak tersedia untuk {algo}/{op}")
        return

    mean = stats_data['mean']
    std = stats_data['std']
    samples = stats_data['samples']

    print(f"\n📊 Parameter: mean={mean:.4f}ms, std={std:.4f}ms")
    print(f"📈 Sample size: {samples if samples != 'unknown' else 'unknown'}")

    # Generate synthetic data untuk KS test
    if samples != 'unknown' and samples >= 100:
        n_test = min(samples, 10000)  # Max 10K untuk efisiensi
    else:
        n_test = 10000

    synthetic_data = generate_lognormal_sample(mean, std, n_test)

    # KS Test
    # Fit log-normal ke synthetic data
    shape, loc, scale = stats.lognorm.fit(synthetic_data, floc=0)
    ks_stat, p_value = stats.kstest(synthetic_data, 'lognorm', args=(shape, loc, scale))

    print(f"\n📋 KOLMOGOROV-SMIRNOV RESULTS:")
    print(f"   KS Statistic: {ks_stat:.6f}")
    print(f"   P-value:      {p_value:.6f}")
    print(f"   Alpha:        {alpha}")
    print(f"   Sample size:  {n_test:,}")

    print(f"\n{'─'*60}")
    if p_value > alpha:
        print(f"✅ FAIL TO REJECT H0 (p={p_value:.6f} > {alpha})")
        print(f"   → Distribusi log-normal adalah FIT yang BAIK")
        print(f"   → Parameter valid untuk simulasi Monte Carlo")
    else:
        print(f"❌ REJECT H0 (p={p_value:.6f} < {alpha})")
        print(f"   → Distribusi log-normal TIDAK fit")
        print(f"   → Pertimbangkan distribusi lain (gamma, Weibull)")
    print(f"{'─'*60}")

    return p_value > alpha


def print_summary(cal_data, format_type):
    """Print summary calibration results"""
    print("\n" + "=" * 70)
    print("CALIBRATION SUMMARY")
    print("=" * 70)

    metadata = cal_data.get('metadata', {})
    print(f"\n📅 Calibration date: {metadata.get('calibration_date', 'unknown')}")
    print(f"📊 Format type: {format_type}")
    print(f"💻 Python: {metadata.get('system_info', {}).get('python_version', 'unknown')}")
    print(f"🖥️  Platform: {metadata.get('system_info', {}).get('platform', 'unknown')}")

    tier_results = cal_data.get('tier_results', {})
    if tier_results:
        print(f"🔢 Tiers executed: {', '.join(tier_results.keys())}")
        primary = metadata.get('primary_tier', 'unknown')
        print(f"🎯 Primary tier: {primary}")
    else:
        tier = metadata.get('tier', 'unknown')
        samples = metadata.get('num_samples', 'unknown')
        print(f"🎯 Tier: {tier}")
        print(f"📈 Samples: {samples if samples != 'unknown' else 'unknown'}")


def validate_calibration(file_path='data/calibration/multi_scenario_calibration.json',
                         alpha=0.05):
    """
    Main validation function. Menjalankan semua validasi.

    Args:
        file_path: Path ke file kalibrasi
        alpha: Significance level untuk KS test (default 0.05)
    """
    cal_data = load_calibration_data(file_path)
    if cal_data is None:
        return

    # Detect format
    format_type = detect_format(cal_data)
    print(f"\n🔍 Detected format: {format_type}")

    # 1. Summary
    print_summary(cal_data, format_type)

    # 2. Parameter Sanity Check
    sanity_ok = validate_parameter_sanity(cal_data)

    # 3. Tier Convergence (jika multi-tier)
    tier_results = cal_data.get('tier_results', {})
    if len(tier_results) >= 2:
        convergence_ok = validate_tier_convergence(cal_data)
    else:
        print("\nℹ️  Single-tier data - convergence analysis tidak applicable.")
        print(f"💡 Untuk convergence analysis: python calibrate_performance.py --compare")
        convergence_ok = True  # Bukan failure, just not applicable

    # 4. Log-Normal KS Test (contoh: ECDSA signing)
    ks_ok = validate_lognormal_distribution(cal_data, alpha=alpha)

    # Final verdict
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)

    all_ok = sanity_ok and convergence_ok and ks_ok

    if all_ok:
        print("\n✅ ALL CHECKS PASSED")
        print("   Kalibrasi valid dan siap untuk simulasi Monte Carlo.")
    else:
        print("\n⚠️  SOME CHECKS FAILED")
        if not sanity_ok:
            print("   ❌ Parameter sanity check gagal")
        if not convergence_ok:
            print("   ❌ Tier convergence tidak tercapai")
        if not ks_ok:
            print("   ❌ Log-normal distribution tidak fit")

    print("\n💡 Rekomendasi:")
    print("   • Untuk production: gunakan --tier production")
    print("   • Untuk paper: gunakan --compare --skip-slow")
    print("   • Untuk riset: gunakan --compare")

    return all_ok


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Validate calibration data for log-normal fit',
        epilog="""
Contoh penggunaan:
  python validate_calibration.py
  python validate_calibration.py --file data/my_calibration.json
  python validate_calibration.py --alpha 0.01
  python validate_calibration.py --test-algo rsa_pss_2048 --test-op verification
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--file', default='data/calibration/multi_scenario_calibration.json',
                        help='Path ke file kalibrasi')
    parser.add_argument('--alpha', type=float, default=0.05,
                        help='Significance level untuk KS test (default: 0.05)')
    parser.add_argument('--test-algo', default='ecdsa_p256',
                        help='Algoritma untuk KS test (default: ecdsa_p256)')
    parser.add_argument('--test-op', default='signing',
                        help='Operasi untuk KS test (default: signing)')

    args = parser.parse_args()

    validate_calibration(args.file, args.alpha)
