# verify_realistic_data.py

import time
import matplotlib.pyplot as plt
import os
import numpy as np
from modules.realistic_performance import RealisticDataGenerator

class TestingScenarioValidator:
    """
    Validates different security scenarios using a realistic data generator.
    The number of operations for each test is defined in TESTING_PLAN.
    """
    TESTING_PLAN = {
        'normal_operations': {'total_operations': 20000},
        'replay_attack': {'total_operations': 25000},      # Diubah dari 25500 menjadi 25000
        'data_tampering': {'total_operations': 50000},
        'signature_forgery': {'total_operations': 20000},
        'stress_testing': {'total_operations': 10000}
    }

    def __init__(self, algorithm='RSA'):
        self.generator = RealisticDataGenerator() # Algoritma default diubah ke RSA
        self.algorithm = algorithm

    def run_scenario(self, scenario_name):
        """Runs a single testing scenario and returns a summary."""
        plan = self.TESTING_PLAN.get(scenario_name, {}) # Algoritma default diubah ke RSA
        num_operations = plan.get('total_operations', 0)
        if num_operations == 0:
            return {'total_time': 0, 'detection_rate': 0, 'response_times': []}

        total_time = 0
        success_count = 0
        response_times = []
        
        op_map = {
            'normal_operations': 'verification',
            'replay_attack': 'detection',
            'data_tampering': 'detection',
            'signature_forgery': 'verification',
            'stress_test': 'verification'
        }
        operation_type = op_map.get(scenario_name, 'verification')

        for i in range(num_operations):
            kwargs = {}
            if scenario_name == 'stress_test':
                kwargs['concurrent_users'] = 1 + int((i / num_operations) * 1500)

            result = self.generator.generate_scenario_result(scenario_name, operation_type, **kwargs)
            
            # Simulasi perbedaan performa Algoritma
            if self.algorithm == 'RSA':
                if operation_type == 'verification':
                    # RSA Verification biasanya lebih cepat dari ECDSA (misal 0.6x waktu ECDSA)
                    result['time_taken'] *= 0.6
                elif operation_type == 'detection':
                    # Detection campuran (IO + Verify). RSA verify cepat, tapi signature besar (IO lambat).
                    result['time_taken'] *= 0.9
            
            total_time += result['time_taken']
            response_times.append(result['time_taken'])
            if result['success']:
                success_count += 1
        
        rate = (success_count / num_operations) * 100 if num_operations > 0 else 0
        
        rate_key = 'detection_rate'
        if scenario_name == 'normal_operations':
            rate_key = 'overall_success_rate'
        elif scenario_name == 'signature_forgery':
            rate_key = 'rejection_rate'

        return {
            rate_key: rate,
            'total_time': total_time,
            'response_times': response_times
        }

def run_comprehensive_test(algorithm='RSA'):
    """
    Runs the full suite of tests and generates a summary and a plot.
    If algorithm is 'BOTH', runs for both and returns comparison.
    """ # Algoritma default diubah ke RSA
    
    # Helper for moving average to smooth out the line chart
    def moving_average(data, window_size=500):
        if not data or len(data) < window_size:
            return data
        return np.convolve(data, np.ones(window_size)/window_size, mode='valid')
    
    if algorithm == 'BOTH':
        print("Starting Comprehensive Comparison (ECDSA vs RSA)...")
        
        # Run ECDSA
        validator_ecdsa = TestingScenarioValidator('ECDSA')
        summary_ecdsa = {}
        for scenario in validator_ecdsa.TESTING_PLAN:
            summary_ecdsa[scenario] = validator_ecdsa.run_scenario(scenario)
            
        # Run RSA
        validator_rsa = TestingScenarioValidator('RSA')
        summary_rsa = {}
        for scenario in validator_rsa.TESTING_PLAN:
            summary_rsa[scenario] = validator_rsa.run_scenario(scenario)
            
        # Generate Comparison Plot
        scenarios = [s.replace('_', ' ').title() for s in summary_ecdsa.keys()]
        
        throughput_ecdsa = []
        throughput_rsa = []
        
        for scenario in summary_ecdsa:
            ops = validator_ecdsa.TESTING_PLAN[scenario]['total_operations']
            throughput_ecdsa.append(ops / summary_ecdsa[scenario]['total_time'] if summary_ecdsa[scenario]['total_time'] > 0 else 0)
            throughput_rsa.append(ops / summary_rsa[scenario]['total_time'] if summary_rsa[scenario]['total_time'] > 0 else 0)

        x = np.arange(len(scenarios))
        width = 0.35
        
        fig, ax = plt.subplots(figsize=(14, 8))
        rects1 = ax.bar(x - width/2, throughput_ecdsa, width, label='ECDSA (P-256)', color='#0d6efd')
        rects2 = ax.bar(x + width/2, throughput_rsa, width, label='RSA (2048)', color='#198754')
        
        ax.set_ylabel('Throughput (operations/sec)')
        ax.set_title('Algorithm Comparison: ECDSA vs RSA Performance', fontsize=16)
        ax.set_xticks(x)
        ax.set_xticklabels(scenarios, rotation=15, ha="right")
        ax.legend()
        
        ax.bar_label(rects1, padding=3, fmt='%.0f')
        ax.bar_label(rects2, padding=3, fmt='%.0f')
        
        # Generate Trend Plot (Line Chart)
        fig_trend, ax_trend = plt.subplots(figsize=(14, 6))
        
        # Collect all response times
        times_ecdsa = []
        for s in validator_ecdsa.TESTING_PLAN:
            times_ecdsa.extend(summary_ecdsa[s]['response_times'])
            
        times_rsa = []
        for s in validator_rsa.TESTING_PLAN:
            times_rsa.extend(summary_rsa[s]['response_times'])
            
        ax_trend.plot(moving_average(times_ecdsa), label='ECDSA P-256', color='#0d6efd', alpha=0.7, linewidth=1.5)
        ax_trend.plot(moving_average(times_rsa), label='RSA 2048', color='#198754', alpha=0.7, linewidth=1.5)
        
    else:
        validator = TestingScenarioValidator(algorithm)
        summary = {}
        print(f"Starting Comprehensive Scenario Validation ({algorithm})...")
        for scenario in validator.TESTING_PLAN:
            print(f"  - Running scenario: {scenario}...")
            summary[scenario] = validator.run_scenario(scenario)
        print("Comprehensive test finished.")

        scenarios = [s.replace('_', ' ').title() for s in summary.keys()]
        throughputs = []
        for scenario, data in summary.items():
            ops = validator.TESTING_PLAN[scenario]['total_operations']
            time_taken = data['total_time']
            throughput = ops / time_taken if time_taken > 0 else 0
            throughputs.append(throughput)

        fig, ax = plt.subplots(figsize=(12, 7))
        bars = ax.bar(scenarios, throughputs, color=['#0d6efd', '#ffc107', '#dc3545', '#0dcaf0', '#198754'])
        
        ax.set_ylabel('Throughput (operations/sec)')
        ax.set_title(f'Comprehensive Test: Throughput per Scenario ({algorithm})', fontsize=16)
        ax.set_xticklabels(scenarios, rotation=15, ha="right")
        
        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2.0, yval, f'{int(yval)}', va='bottom', ha='center')
            
        # Generate Trend Plot (Line Chart)
        fig_trend, ax_trend = plt.subplots(figsize=(14, 6))
        
        all_times = []
        for s in validator.TESTING_PLAN:
            all_times.extend(summary[s]['response_times'])
            
        ax_trend.plot(moving_average(all_times), label=f'{algorithm}', color='#0d6efd', linewidth=1.5)

    plt.tight_layout()
    
    plot_dir = "static/testing"
    os.makedirs(plot_dir, exist_ok=True)
    filename = "comprehensive_comparison.png" if algorithm == 'BOTH' else "comprehensive_summary.png"
    plot_path = os.path.join(plot_dir, filename)
    plt.savefig(plot_path)
    plt.close(fig)
    
    # Save Trend Plot
    trend_filename = "comprehensive_trend.png"
    trend_path = os.path.join(plot_dir, trend_filename)
    
    ax_trend.set_title('Response Time Trend (Moving Average)', fontsize=16)
    ax_trend.set_xlabel('Operations (Smoothed)', fontsize=12)
    ax_trend.set_ylabel('Response Time (seconds)', fontsize=12)
    ax_trend.legend()
    ax_trend.grid(True, alpha=0.3)
    
    fig_trend.tight_layout()
    fig_trend.savefig(trend_path)
    plt.close(fig_trend)
    
    relative_plot_path = f"testing/{filename}"
    relative_trend_path = f"testing/{trend_filename}"

    pie_plot_path = None
    if algorithm == 'BOTH':
        # Generate Pie Charts for Time Distribution
        fig_pie, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        
        scenarios_labels = [s.replace('_', ' ').title() for s in summary_ecdsa.keys()]
        colors = ['#0d6efd', '#ffc107', '#dc3545', '#0dcaf0', '#198754']
        
        # ECDSA Pie
        times_ecdsa = [summary_ecdsa[s]['total_time'] for s in summary_ecdsa.keys()]
        ax1.pie(times_ecdsa, labels=scenarios_labels, autopct='%1.1f%%', startangle=140, colors=colors)
        ax1.set_title('ECDSA: Time Distribution by Scenario', fontsize=14, fontweight='bold')
        
        # RSA Pie
        times_rsa = [summary_rsa[s]['total_time'] for s in summary_rsa.keys()]
        ax2.pie(times_rsa, labels=scenarios_labels, autopct='%1.1f%%', startangle=140, colors=colors)
        ax2.set_title('RSA: Time Distribution by Scenario', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        pie_filename = "comprehensive_pie_comparison.png"
        pie_full_path = os.path.join(plot_dir, pie_filename)
        plt.savefig(pie_full_path)
        plt.close(fig_pie)
        
        pie_plot_path = f"testing/{pie_filename}"
        
        # Data perbandingan payload (Estimasi berdasarkan karakteristik algoritma)
        payload_comparison = {
            'signature_size': {'ECDSA': '64-72 bytes (Small)', 'RSA': '256 bytes (Large)'},
            'qr_version': {'ECDSA': 'Version 8-10 (Low Density)', 'RSA': 'Version 16-18 (High Density)'},
            'scannability': {'ECDSA': 'Excellent (Cepat & Mudah)', 'RSA': 'Medium (Butuh Fokus)'},
            'dimensions': {'ECDSA': '~200x200 px', 'RSA': '~350x350 px'},
            'file_size': {'ECDSA': '~2-3 KB', 'RSA': '~5-7 KB'}
        }
        
        return {'ECDSA': summary_ecdsa, 'RSA': summary_rsa}, relative_plot_path, pie_plot_path, payload_comparison, relative_trend_path
    else:
        return summary, relative_plot_path, None, None, relative_trend_path
