import json
import os
import random
import numpy as np

class MultiScenarioDataGenerator:
    def __init__(self):
        self.REALISTIC_BENCHMARKS = {
            'normal_jws_ecdsa': {
                'signing': {'mean_ms': 2.5, 'stddev_ms': 1.2},
                'verification': {'mean_ms': 1.2, 'stddev_ms': 0.6}
            },
            'replay_attack': {
                'detection': {
                    'patterns': {'simple_replay': 0.60, 'timing_attack': 0.25, 'session_hijack': 0.10, 'advanced_replay': 0.05},
                    'detection_rate': 0.95,
                    'false_positive_rate': 0.01,
                    'false_negative_rate': 0.02
                }
            },
            'data_tampering': {
                'detection': {
                    'tampering_types': {'field_modification': 0.40, 'field_addition': 0.20, 'field_removal': 0.15, 'data_type_change': 0.10, 'timestamp_tampering': 0.08, 'signature_injection': 0.05, 'encryption_bypass': 0.02},
                    'detection_rate': 0.92,
                    'severity_weights': {'low': 0.5, 'medium': 0.3, 'high': 0.15, 'critical': 0.05}
                }
            },
            'signature_forgery': {
                'verification': {
                    'forgery_types': {'random_signature': 0.30, 'modified_valid': 0.20, 'replay_valid': 0.15, 'algorithm_weakness': 0.15, 'key_recovery': 0.10, 'quantum_attack': 0.10},
                    'algorithms': {'ECDSA': 0.3, 'RSA-PSS': 0.3, 'Ed25519': 0.2, 'BLS': 0.1, 'Schnorr': 0.1},
                    'rejection_rate': 0.985
                }
            },
            'stress_test': {
                'base_response_ms': 2,
                'concurrent_factor': 0.0001,
                'error_rate_base': 0.01,
                'error_rate_per_user': 0.00002,
                'resource_scaling': {
                    'cpu_per_user': 0.05,
                    'memory_mb_per_user': 0.5,
                    'network_kbps_per_user': 2
                }
            }
        }
        self.benchmarks = self._load_calibration()

    def generate_scenario_result(self, scenario, operation_type, **kwargs):
        """
        Generate realistic scenario result based on calibrated benchmarks.
        
        Args:
            scenario: Scenario name (e.g., 'replay_attack', 'data_tampering', 'signature_forgery', 'normal_jws_ecdsa')
            operation_type: Operation type (e.g., 'detection', 'verification', 'signing')
            **kwargs: Additional parameters like payload_size_kb, concurrent_users, etc.
        
        Returns:
            dict: Result with 'time_taken', 'success', and additional scenario-specific fields
        """
        # Map scenario names to benchmark keys
        scenario_map = {
            'normal_operations': 'normal_jws_ecdsa',
            'replay_attack': 'replay_attack',
            'data_tampering': 'data_tampering',
            'signature_forgery': 'signature_forgery',
            'stress_test': 'stress_test'
        }
        
        benchmark_key = scenario_map.get(scenario, scenario)
        benchmark = self.benchmarks.get(benchmark_key, {})
        
        # Generate result based on scenario type
        if benchmark_key in ['normal_jws_ecdsa', 'normal_rsa']:
            return self._generate_normal_operation_result(benchmark, operation_type, **kwargs)
        elif benchmark_key == 'replay_attack':
            return self._generate_replay_attack_result(benchmark, **kwargs)
        elif benchmark_key == 'data_tampering':
            return self._generate_data_tampering_result(benchmark, **kwargs)
        elif benchmark_key == 'signature_forgery':
            return self._generate_signature_forgery_result(benchmark, operation_type, **kwargs)
        elif benchmark_key == 'stress_test':
            return self._generate_stress_test_result(benchmark, **kwargs)
        else:
            # Fallback: generate generic result
            return self._generate_generic_result(**kwargs)

    def _generate_normal_operation_result(self, benchmark, operation_type, **kwargs):
        """Generate normal signing/verification operation result"""
        operation_data = benchmark.get(operation_type, {'mean_ms': 2.0, 'stddev_ms': 1.0})
        mean_ms = operation_data.get('mean_ms', 2.0)
        stddev_ms = operation_data.get('stddev_ms', 1.0)
        
        # Generate time from normal distribution (ensure positive)
        time_ms = max(0.1, np.random.normal(mean_ms, stddev_ms))
        time_taken = time_ms / 1000.0  # Convert to seconds
        
        # Normal operations should almost always succeed
        success = random.random() < 0.999
        
        return {
            'time_taken': time_taken,
            'success': success,
            'time_ms': time_ms,
            'operation_type': operation_type
        }

    def _generate_replay_attack_result(self, benchmark, **kwargs):
        """Generate replay attack detection result"""
        detection_config = benchmark.get('detection', {})
        detection_rate = detection_config.get('detection_rate', 0.95)
        false_positive_rate = detection_config.get('false_positive_rate', 0.01)
        
        # Detection time: typically 10-50ms
        time_taken = random.uniform(0.01, 0.05)
        
        # Determine if attack detected
        detected = random.random() < detection_rate
        success = detected  # Success means attack was detected
        
        # Determine if false positive
        is_false_positive = random.random() < false_positive_rate
        
        return {
            'time_taken': time_taken,
            'success': success,
            'detected': detected,
            'false_positive': is_false_positive,
            'detection_rate': detection_rate
        }

    def _generate_data_tampering_result(self, benchmark, **kwargs):
        """Generate data tampering detection result"""
        detection_config = benchmark.get('detection', {})
        detection_rate = detection_config.get('detection_rate', 0.92)
        
        # Detection time: typically 10-30ms
        time_taken = random.uniform(0.01, 0.03)
        
        # Determine if tampering detected
        detected = random.random() < detection_rate
        success = detected  # Success means tampering was detected
        
        # Determine severity
        severity_weights = detection_config.get('severity_weights', {'low': 0.5, 'medium': 0.3, 'high': 0.15, 'critical': 0.05})
        severity = random.choices(
            list(severity_weights.keys()),
            weights=list(severity_weights.values()),
            k=1
        )[0]
        
        return {
            'time_taken': time_taken,
            'success': success,
            'detected': detected,
            'severity': severity,
            'detection_rate': detection_rate
        }

    def _generate_signature_forgery_result(self, benchmark, operation_type, **kwargs):
        """Generate signature forgery verification result"""
        verification_config = benchmark.get('verification', {})
        rejection_rate = verification_config.get('rejection_rate', 0.985)
        
        # Verification time: typically 5-15ms
        time_taken = random.uniform(0.005, 0.015)
        
        # Determine if forgery rejected
        rejected = random.random() < rejection_rate
        success = rejected  # Success means forgery was rejected
        
        return {
            'time_taken': time_taken,
            'success': success,
            'rejected': rejected,
            'rejection_rate': rejection_rate
        }

    def _generate_stress_test_result(self, benchmark, **kwargs):
        """Generate stress test result with concurrent users"""
        concurrent_users = kwargs.get('concurrent_users', 100)
        
        stress_config = benchmark
        base_response_ms = stress_config.get('base_response_ms', 2)
        concurrent_factor = stress_config.get('concurrent_factor', 0.0001)
        error_rate_base = stress_config.get('error_rate_base', 0.01)
        error_rate_per_user = stress_config.get('error_rate_per_user', 0.00002)
        
        # Calculate response time based on concurrent users
        time_ms = base_response_ms + (concurrent_users * concurrent_factor * 100)
        # Add some variance (±20%)
        time_ms *= random.uniform(0.8, 1.2)
        time_taken = time_ms / 1000.0
        
        # Calculate error rate
        error_rate = error_rate_base + (concurrent_users * error_rate_per_user)
        error_rate = min(error_rate, 0.5)  # Cap at 50%
        success = random.random() > error_rate
        
        return {
            'time_taken': time_taken,
            'success': success,
            'concurrent_users': concurrent_users,
            'error_rate': error_rate,
            'response_time_ms': time_ms
        }

    def _generate_generic_result(self, **kwargs):
        """Generate generic fallback result"""
        time_taken = random.uniform(0.001, 0.1)
        success = random.random() < 0.95
        
        return {
            'time_taken': time_taken,
            'success': success
        }

    def generate_resource_usage(self, scenario, concurrent_ops=1, duration_seconds=0.01):
        """
        Generate realistic resource usage metrics (CPU, memory, network).
        
        Args:
            scenario: Scenario name (e.g., 'replay_attack', 'data_tampering', 'signature_forgery')
            concurrent_ops: Number of concurrent operations
            duration_seconds: Duration of the operation in seconds
            
        Returns:
            dict: Resource usage metrics with 'memory_mb', 'cpu_percent', and 'network_kbps'
        """
        # Base resource usage per scenario type
        scenario_resource_profile = {
            'normal_jws_ecdsa': {'base_memory_mb': 15, 'base_cpu_percent': 5, 'base_network_kbps': 50},
            'normal_rsa': {'base_memory_mb': 25, 'base_cpu_percent': 10, 'base_network_kbps': 80},
            'replay_attack': {'base_memory_mb': 20, 'base_cpu_percent': 8, 'base_network_kbps': 60},
            'data_tampering': {'base_memory_mb': 30, 'base_cpu_percent': 12, 'base_network_kbps': 70},
            'signature_forgery': {'base_memory_mb': 25, 'base_cpu_percent': 15, 'base_network_kbps': 65},
            'stress_test': {'base_memory_mb': 50, 'base_cpu_percent': 25, 'base_network_kbps': 100}
        }
        
        # Get scenario profile
        scenario_map = {
            'normal_operations': 'normal_jws_ecdsa',
            'replay_attack': 'replay_attack',
            'data_tampering': 'data_tampering',
            'signature_forgery': 'signature_forgery',
            'stress_test': 'stress_test'
        }
        
        scenario_key = scenario_map.get(scenario, scenario)
        profile = scenario_resource_profile.get(scenario_key, {'base_memory_mb': 20, 'base_cpu_percent': 10, 'base_network_kbps': 60})
        
        # Calculate resource usage
        base_memory = profile['base_memory_mb']
        base_cpu = profile['base_cpu_percent']
        base_network = profile['base_network_kbps']
        
        # Scale with concurrent operations (with diminishing returns)
        concurrent_factor = min(concurrent_ops, 100) ** 0.5  # Square root scaling
        
        # Add variance (±20%)
        memory_mb = base_memory + (concurrent_factor * 0.5)
        memory_mb *= random.uniform(0.9, 1.1)
        
        cpu_percent = base_cpu + (concurrent_factor * 0.3)
        cpu_percent *= random.uniform(0.9, 1.1)
        cpu_percent = min(cpu_percent, 100.0)  # Cap at 100%
        
        network_kbps = base_network + (concurrent_factor * 2)
        network_kbps *= random.uniform(0.9, 1.1)
        
        return {
            'memory_mb': round(memory_mb, 2),
            'cpu_percent': round(cpu_percent, 2),
            'network_kbps': round(network_kbps, 2),
            'concurrent_ops': concurrent_ops,
            'duration_seconds': duration_seconds
        }

    def _load_calibration(self):
        """Load calibration data dan merge dengan default benchmarks"""
        path = 'data/calibration/multi_scenario_calibration.json'
        if not os.path.exists(path):
            print("⚠️ Menggunakan benchmark default (File kalibrasi tidak ditemukan).")
            return self.REALISTIC_BENCHMARKS

        try:
            with open(path, 'r') as f:
                cal = json.load(f)
            
            bench = cal['benchmark_results']
            calibrated = self.REALISTIC_BENCHMARKS.copy()
            
            # Override ECDSA
            if 'ecdsa_p256' in bench:
                calibrated['normal_jws_ecdsa']['signing']['mean_ms'] = bench['ecdsa_p256']['signing']['mean']
                calibrated['normal_jws_ecdsa']['signing']['stddev_ms'] = bench['ecdsa_p256']['signing']['std']
                calibrated['normal_jws_ecdsa']['verification']['mean_ms'] = bench['ecdsa_p256']['verification']['mean']
                calibrated['normal_jws_ecdsa']['verification']['stddev_ms'] = bench['ecdsa_p256']['verification']['std']

            # Tambahkan RSA dari kalibrasi
            if 'rsa_pss_2048' in bench:
                calibrated['normal_rsa'] = {
                    'signing': {
                        'mean_ms': bench['rsa_pss_2048']['signing']['mean'],
                        'stddev_ms': bench['rsa_pss_2048']['signing']['std']
                    },
                    'verification': {
                        'mean_ms': bench['rsa_pss_2048']['verification']['mean'],
                        'stddev_ms': bench['rsa_pss_2048']['verification']['std']
                    }
                }
            
            print(f"✅ Kalibrasi dimuat (Tanggal: {cal['metadata']['calibration_date']})")
            return calibrated
        except Exception as e:
            print(f"❌ Gagal memuat kalibrasi: {e}")
            return self.REALISTIC_BENCHMARKS


# Alias for backward compatibility
RealisticDataGenerator = MultiScenarioDataGenerator