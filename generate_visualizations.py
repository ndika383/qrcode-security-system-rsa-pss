"""
generate_visualizations.py - Grafik visualisasi dari data testing riil
Output: PNG files di folder static/ pada direktori aplikasi
"""

import sqlite3
import json
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
db_path = BASE_DIR / 'data' / 'testing' / 'testing_results.db'
output_dir = BASE_DIR / 'static'
os.makedirs(output_dir, exist_ok=True)

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['figure.dpi'] = 150
plt.rcParams['savefig.bbox'] = 'tight'

# Load data
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("""
    SELECT test_type, results_json, total_operations, test_name
    FROM test_sessions 
    WHERE status='completed' AND results_json IS NOT NULL AND results_json != '{}'
    ORDER BY test_type, id
""")
rows = cursor.fetchall()
conn.close()

print("=" * 70)
print("GENERATING VISUALIZATIONS FROM REAL TESTING DATA")
print("=" * 70)

# ============================================================
# FIGURE 1: Normal Operations - Signing vs Verification Time
# ============================================================
print("\n[1/5] Generating Figure 1: Normal Operations Performance...")

normal_sessions = [(json.loads(r[1]), r[2]) for r in rows if r[0] == 'normal_operations']

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

session_labels = ['200 ops', '2,000 ops', '20,000 ops', '20,000 ops\n(Feb)']
signing_means = []
verify_means = []

for results, total_ops in normal_sessions:
    signing_means.append(results.get('avg_signing_time', 0) * 1000)
    verify_means.append(results.get('avg_verification_time', 0) * 1000)

x = np.arange(len(session_labels))
width = 0.35

bars1 = axes[0].bar(x - width/2, signing_means, width, label='Signing Time',
                     color='#2196F3', edgecolor='white', linewidth=0.5)
bars2 = axes[0].bar(x + width/2, verify_means, width, label='Verification Time',
                     color='#FF5722', edgecolor='white', linewidth=0.5)

axes[0].set_xlabel('Test Session Size', fontsize=11, fontweight='bold')
axes[0].set_ylabel('Time (ms)', fontsize=11, fontweight='bold')
axes[0].set_title('Average Signing vs Verification Time\nby Session Size', fontsize=12, fontweight='bold')
axes[0].set_xticks(x)
axes[0].set_xticklabels(session_labels)
axes[0].legend(fontsize=10)
axes[0].grid(axis='y', alpha=0.3)

for bar in bars1:
    height = bar.get_height()
    axes[0].annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9)
for bar in bars2:
    height = bar.get_height()
    axes[0].annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9)

signing_success = [100.0, 100.0, 100.0, 100.0]
verify_success = [100.0, 100.0, 100.0, 100.0]

axes[1].bar(x - width/2, signing_success, width, label='Signing Success Rate',
             color='#4CAF50', edgecolor='white', linewidth=0.5)
axes[1].bar(x + width/2, verify_success, width, label='Verification Success Rate',
             color='#9C27B0', edgecolor='white', linewidth=0.5)

axes[1].set_xlabel('Test Session Size', fontsize=11, fontweight='bold')
axes[1].set_ylabel('Success Rate (%)', fontsize=11, fontweight='bold')
axes[1].set_title('Success Rate by Session Size', fontsize=12, fontweight='bold')
axes[1].set_xticks(x)
axes[1].set_xticklabels(session_labels)
axes[1].legend(fontsize=10)
axes[1].set_ylim(95, 101)
axes[1].grid(axis='y', alpha=0.3)

p95_signing = []
p95_verify = []
for results, total_ops in normal_sessions:
    p95_signing.append(results.get('p95_signing_time', 0) * 1000)
    p95_verify.append(results.get('p95_verification_time', 0) * 1000)

axes[2].bar(x - width/2, p95_signing, width, label='P95 Signing',
             color='#FF9800', edgecolor='white', linewidth=0.5)
axes[2].bar(x + width/2, p95_verify, width, label='P95 Verification',
             color='#00BCD4', edgecolor='white', linewidth=0.5)

axes[2].set_xlabel('Test Session Size', fontsize=11, fontweight='bold')
axes[2].set_ylabel('P95 Latency (ms)', fontsize=11, fontweight='bold')
axes[2].set_title('P95 Latency Comparison', fontsize=12, fontweight='bold')
axes[2].set_xticks(x)
axes[2].set_xticklabels(session_labels)
axes[2].legend(fontsize=10)
axes[2].grid(axis='y', alpha=0.3)

plt.tight_layout()
fig_path = os.path.join(output_dir, 'fig1_normal_operations.png')
plt.savefig(fig_path, dpi=200)
plt.close()
print(f"  Saved: fig1_normal_operations.png")

# ============================================================
# FIGURE 2: All Scenarios Performance Comparison
# ============================================================
print("\n[2/5] Generating Figure 2: Multi-Scenario Performance...")

scenario_names = []
mean_times = []
min_times = []
max_times = []

for r in rows:
    results = json.loads(r[1])
    ttype = r[0]
    
    if ttype == 'normal_operations' and r[2] == 20000:
        scenario_names.append('Normal\nOperations')
        mean_times.append(results.get('avg_signing_time', 0) * 1000)
        min_times.append(results.get('min_signing_time', 0) * 1000)
        max_times.append(results.get('max_signing_time', 0) * 1000)
        break

for r in rows:
    results = json.loads(r[1])
    if r[0] == 'replay_attack':
        det_times = results.get('detection_times', [])
        if det_times:
            scenario_names.append('Replay\nAttack')
            mean_times.append(statistics.mean(det_times))
            min_times.append(min(det_times))
            max_times.append(max(det_times))
        break

for r in rows:
    results = json.loads(r[1])
    if r[0] == 'data_tampering':
        det_times = results.get('detection_times', [])
        if det_times:
            scenario_names.append('Data\nTampering')
            mean_times.append(statistics.mean(det_times))
            min_times.append(min(det_times))
            max_times.append(max(det_times))
        break

for r in rows:
    results = json.loads(r[1])
    if r[0] == 'signature_forgery':
        ver_times = results.get('verification_times', [])
        if ver_times:
            scenario_names.append('Signature\nForgery')
            mean_times.append(statistics.mean(ver_times))
            min_times.append(min(ver_times))
            max_times.append(max(ver_times))
        break

for r in rows:
    results = json.loads(r[1])
    if r[0] == 'stress_test' and r[2] == 4000:
        stress_times = results.get('stress_times', [])
        if stress_times:
            scenario_names.append('Stress\nTest')
            mean_times.append(statistics.mean(stress_times))
            min_times.append(min(stress_times))
            max_times.append(max(stress_times))
        break

fig, ax = plt.subplots(figsize=(12, 6))
x = np.arange(len(scenario_names))
width = 0.5

colors = ['#2196F3', '#FF5722', '#FF9800', '#4CAF50', '#9C27B0'][:len(scenario_names)]
bars = ax.bar(x, mean_times, width, color=colors, edgecolor='white', linewidth=0.5, alpha=0.85)

yerr = [
    [m - mn for m, mn in zip(mean_times, min_times)],
    [mx - m for m, mx in zip(mean_times, max_times)]
]
ax.errorbar(x, mean_times, yerr=yerr, fmt='none', color='black', 
            capsize=5, capthick=1.5, linewidth=1.5, alpha=0.6)

for bar, mean in zip(bars, mean_times):
    ax.annotate(f'{mean:.1f} ms', xy=(bar.get_x() + bar.get_width()/2, mean),
                xytext=(0, 8), textcoords="offset points", ha='center', 
                fontweight='bold', fontsize=11)

ax.set_xlabel('Test Scenario', fontsize=12, fontweight='bold')
ax.set_ylabel('Mean Time (ms)', fontsize=12, fontweight='bold')
ax.set_title('Performance Comparison Across All Test Scenarios\n(with Min-Max Range)', 
             fontsize=13, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(scenario_names, fontsize=10)
ax.grid(axis='y', alpha=0.3)
ax.set_yscale('log')
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f'))

plt.tight_layout()
fig_path = os.path.join(output_dir, 'fig2_all_scenarios.png')
plt.savefig(fig_path, dpi=200)
plt.close()
print(f"  Saved: fig2_all_scenarios.png")

# ============================================================
# FIGURE 3: Detection Rates (Security Effectiveness)
# ============================================================
print("\n[3/5] Generating Figure 3: Detection Rates...")

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

metrics = ['Replay\nAttack\nDetection', 'Tampering\nDetection', 'Forgery\nRejection', 'Signing\nSuccess', 'Verification\nSuccess']

# Real data from testing
# Replay: 28586 detected / (28586+1414) = 95.3% detection rate
# But we also have production data showing 100%
# Use the larger completed session data
replay_detected = 28586
replay_missed = 1414
replay_rate = (replay_detected / (replay_detected + replay_missed)) * 100

# Tampering: 3611 detected / 5000 = 72.22%
tampering_rate = (3611 / 5000) * 100

# Forgery: 19639 rejected / 20000 = 98.20%
forgery_rate = (19639 / 20000) * 100

values = [replay_rate, tampering_rate, forgery_rate, 100.0, 100.0]
targets = [98.0, 85.0, 99.9, 99.0, 99.0]

x = np.arange(len(metrics))
width = 0.35

bars1 = axes[0].bar(x - width/2, values, width, label='Achieved',
                     color='#4CAF50', edgecolor='white', linewidth=0.5)
bars2 = axes[0].bar(x + width/2, targets, width, label='Target',
                     color='#FF9800', edgecolor='white', linewidth=0.5, alpha=0.7)

axes[0].set_ylabel('Rate (%)', fontsize=11, fontweight='bold')
axes[0].set_title('Detection Rates: Achieved vs Target', fontsize=12, fontweight='bold')
axes[0].set_xticks(x)
axes[0].set_xticklabels(metrics, fontsize=9)
axes[0].set_ylim(0, 105)
axes[0].legend(fontsize=10)
axes[0].grid(axis='y', alpha=0.3)

for bar in bars1:
    height = bar.get_height()
    axes[0].annotate(f'{height:.1f}%', xy=(bar.get_x() + bar.get_width()/2, height),
                     xytext=(0, 3), textcoords="offset points", ha='center', 
                     fontweight='bold', fontsize=9)
for bar in bars2:
    height = bar.get_height()
    axes[0].annotate(f'{height:.1f}%', xy=(bar.get_x() + bar.get_width()/2, height),
                     xytext=(0, 3), textcoords="offset points", ha='center', 
                     fontsize=8)

# Right: Tampering detection by type
for r in rows:
    if r[0] == 'data_tampering':
        results = json.loads(r[1])
        det_by_type = results.get('detection_by_type', {})
        
        types = []
        rates = []
        for tname, tdata in det_by_type.items():
            types.append(tname.replace('_', '\n').title())
            rates.append(tdata.get('detection_rate', 0))
        break

sorted_pairs = sorted(zip(types, rates), key=lambda p: p[1], reverse=True)
types = [p[0] for p in sorted_pairs]
rates = [p[1] for p in sorted_pairs]

colors = ['#4CAF50' if r >= 85 else '#FF9800' if r >= 70 else '#F44336' for r in rates]
axes[1].barh(range(len(types)), rates, color=colors, edgecolor='white', linewidth=0.5, alpha=0.85)
axes[1].set_yticks(range(len(types)))
axes[1].set_yticklabels(types, fontsize=9)
axes[1].set_xlabel('Detection Rate (%)', fontsize=11, fontweight='bold')
axes[1].set_title('Tampering Detection Rate by Type', fontsize=12, fontweight='bold')
axes[1].set_xlim(0, 100)
axes[1].grid(axis='x', alpha=0.3)
axes[1].invert_yaxis()

for i, rate in enumerate(rates):
    axes[1].annotate(f'{rate:.1f}%', xy=(rate + 1, i), va='center', fontsize=9, fontweight='bold')

axes[1].axvline(x=85, color='red', linestyle='--', alpha=0.5, linewidth=1.5)
axes[1].annotate('Target (85%)', xy=(85, len(types)-0.5), xytext=(87, len(types)-0.5),
                 fontsize=8, color='red')

plt.tight_layout()
fig_path = os.path.join(output_dir, 'fig3_detection_rates.png')
plt.savefig(fig_path, dpi=200)
plt.close()
print(f"  Saved: fig3_detection_rates.png")

# ============================================================
# FIGURE 4: Stress Test Scalability
# ============================================================
print("\n[4/5] Generating Figure 4: Scalability Analysis...")

for r in rows:
    if r[0] == 'stress_test' and r[2] == 40000:
        results = json.loads(r[1])
        resp_by_users = results.get('response_time_by_user_count', {})
        error_by_users = results.get('error_rate_by_user_count', {})
        success_by_users = results.get('success_rate_by_user_count', {})
        break

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

user_counts = sorted([int(k) for k in resp_by_users.keys()])
resp_times = [resp_by_users[str(u)] * 1000 for u in user_counts]
error_rates = [error_by_users[str(u)] for u in user_counts]
success_rates = [success_by_users[str(u)] for u in user_counts]

axes[0].plot(user_counts, resp_times, 'o-', color='#2196F3', linewidth=2.5, markersize=8)
axes[0].fill_between(user_counts, resp_times, alpha=0.1, color='#2196F3')
axes[0].set_xlabel('Concurrent Users', fontsize=11, fontweight='bold')
axes[0].set_ylabel('Avg Response Time (ms)', fontsize=11, fontweight='bold')
axes[0].set_title('Response Time vs Concurrent Users', fontsize=12, fontweight='bold')
axes[0].grid(alpha=0.3)
for u, rt in zip(user_counts, resp_times):
    axes[0].annotate(f'{rt:.1f} ms', xy=(u, rt), xytext=(0, 8), 
                     textcoords="offset points", ha='center', fontsize=9, fontweight='bold')

axes[1].plot(user_counts, error_rates, 's-', color='#F44336', linewidth=2.5, markersize=8)
axes[1].fill_between(user_counts, error_rates, alpha=0.1, color='#F44336')
axes[1].axhline(y=2.0, color='orange', linestyle='--', alpha=0.7, linewidth=1.5)
axes[1].annotate('Target (<2%)', xy=(100, 2.0), xytext=(200, 2.5),
                 fontsize=9, color='orange')
axes[1].set_xlabel('Concurrent Users', fontsize=11, fontweight='bold')
axes[1].set_ylabel('Error Rate (%)', fontsize=11, fontweight='bold')
axes[1].set_title('Error Rate vs Concurrent Users', fontsize=12, fontweight='bold')
axes[1].grid(alpha=0.3)
for u, er in zip(user_counts, error_rates):
    axes[1].annotate(f'{er:.1f}%', xy=(u, er), xytext=(0, 8),
                     textcoords="offset points", ha='center', fontsize=9, fontweight='bold')

axes[2].plot(user_counts, success_rates, '^-', color='#4CAF50', linewidth=2.5, markersize=8)
axes[2].fill_between(user_counts, success_rates, alpha=0.1, color='#4CAF50')
axes[2].axhline(y=98.0, color='orange', linestyle='--', alpha=0.7, linewidth=1.5)
axes[2].annotate('Target (>98%)', xy=(100, 98.0), xytext=(200, 97.5),
                 fontsize=9, color='orange')
axes[2].set_xlabel('Concurrent Users', fontsize=11, fontweight='bold')
axes[2].set_ylabel('Success Rate (%)', fontsize=11, fontweight='bold')
axes[2].set_title('Success Rate vs Concurrent Users', fontsize=12, fontweight='bold')
axes[2].grid(alpha=0.3)
for u, sr in zip(user_counts, success_rates):
    axes[2].annotate(f'{sr:.1f}%', xy=(u, sr), xytext=(0, 8),
                     textcoords="offset points", ha='center', fontsize=9, fontweight='bold')

plt.tight_layout()
fig_path = os.path.join(output_dir, 'fig4_scalability.png')
plt.savefig(fig_path, dpi=200)
plt.close()
print(f"  Saved: fig4_scalability.png")

# ============================================================
# FIGURE 5: Operations Summary Pie Chart
# ============================================================
print("\n[5/5] Generating Figure 5: Testing Summary...")

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

scenario_ops = {
    'Normal\nOperations': 62200,
    'Replay\nAttack': 60000,
    'Data\nTampering': 5000,
    'Signature\nForgery': 20000,
    'Stress\nTest': 124000
}

colors = ['#2196F3', '#FF5722', '#FF9800', '#4CAF50', '#9C27B0']
wedges, texts, autotexts = axes[0].pie(
    scenario_ops.values(), labels=scenario_ops.keys(), autopct='%1.1f%%',
    colors=colors, startangle=90, textprops={'fontsize': 10, 'fontweight': 'bold'}
)
for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontweight('bold')
    autotext.set_fontsize(10)
axes[0].set_title('Distribution of Operations by Scenario\n(Total: 271,200)', 
                  fontsize=12, fontweight='bold')

status_counts = {'Completed': 9, 'Failed': 2, 'Stopped': 3}
status_colors = ['#4CAF50', '#F44336', '#FF9800']
wedges, texts, autotexts = axes[1].pie(
    status_counts.values(), labels=status_counts.keys(), autopct='%1.1f%%',
    colors=status_colors, startangle=90, textprops={'fontsize': 11, 'fontweight': 'bold'}
)
for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontweight('bold')
axes[1].set_title('Session Completion Status\n(Total: 14 Sessions)', 
                  fontsize=12, fontweight='bold')

plt.tight_layout()
fig_path = os.path.join(output_dir, 'fig5_testing_summary.png')
plt.savefig(fig_path, dpi=200)
plt.close()
print(f"  Saved: fig5_testing_summary.png")

print("\n" + "=" * 70)
print("ALL 5 FIGURES GENERATED SUCCESSFULLY!")
print("=" * 70)
for f in ['fig1_normal_operations.png', 'fig2_all_scenarios.png', 
          'fig3_detection_rates.png', 'fig4_scalability.png', 'fig5_testing_summary.png']:
    path = os.path.join(output_dir, f)
    if os.path.exists(path):
        size_kb = os.path.getsize(path) / 1024
        print(f"  {f}: {size_kb:.1f} KB")
