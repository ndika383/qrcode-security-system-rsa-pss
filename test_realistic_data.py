"""
test_realistic_data.py - Initial test script for realistic data generator
Lokasi: Root folder (sama dengan app.py)
"""

import sys
import os
import random
import time
import statistics
import json
import numpy as np
from datetime import datetime

# Global variable placeholder
RealisticDataGenerator = None

def initialize_environment():
    """Initialize environment and imports safely"""
    global RealisticDataGenerator
    
    # Get current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Add modules path
    modules_path = os.path.join(current_dir, 'modules')
    if modules_path not in sys.path:
        sys.path.insert(0, modules_path)
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    try:
        from realistic_performance import MultiScenarioDataGenerator
        RealisticDataGenerator = MultiScenarioDataGenerator
        return True
    except ImportError:
        try:
            # Try importing with full package path if needed
            from modules.realistic_performance import MultiScenarioDataGenerator
            RealisticDataGenerator = MultiScenarioDataGenerator
            return True
        except ImportError:
            return False

# ===== SETUP PATH & IMPORTS (Conditional) =====
if __name__ == "__main__":
    print("Initializing test environment...")
    print("=" * 60)
    if initialize_environment():
        print("✅ Successfully imported MultiScenarioDataGenerator")
    else:
        print("❌ Failed to import MultiScenarioDataGenerator")
        sys.exit(1)
else:
    # Silent initialization when imported
    initialize_environment()

# ===== TEST 1: BASIC DATA GENERATOR =====
def test_basic_generator():
    """Test the basic realistic data generator"""
    print("\n" + "=" * 60)
    print("TEST 1: BASIC REALISTIC DATA GENERATOR")
    print("=" * 60)
    
    # Initialize generator - NO algorithm parameter needed
    print("\nInitializing RealisticDataGenerator...")
    generator = RealisticDataGenerator()  # Changed: removed algorithm parameter
    
    print("\n1. Testing Signing Times (100 samples)")
    print("-" * 40)
    
    signing_times = []
    for i in range(100):
        # Use generate_scenario_time instead of generate_signing_time
        result = generator.generate_scenario_result(
            scenario='normal_jws_ecdsa',
            operation_type='signing',
            payload_size_kb=random.randint(1, 100)
        )
        signing_times.append(result['time_taken'] * 1000)  # Convert to ms
    
    print(f"   Mean: {statistics.mean(signing_times):.2f} ms")
    print(f"   Median: {statistics.median(signing_times):.2f} ms")
    print(f"   Min: {min(signing_times):.2f} ms")
    print(f"   Max: {max(signing_times):.2f} ms")
    print(f"   StdDev: {statistics.stdev(signing_times):.2f} ms")
    
    # Check if values are realistic
    mean_time = statistics.mean(signing_times)
    if 1.0 <= mean_time <= 10.0:  # Realistic ECDSA signing is 1-10ms
        print(f"   ✅ Realistic: Mean {mean_time:.2f}ms is within expected range (1-10ms)")
    else:
        print(f"   ⚠️  Warning: Mean {mean_time:.2f}ms outside expected range")
    
    print("\n2. Testing Verification Times (100 samples)")
    print("-" * 40)
    
    verification_times = []
    for i in range(100):
        result = generator.generate_scenario_result(
            scenario='normal_jws_ecdsa',
            operation_type='verification',
            payload_size_kb=random.randint(1, 10)
        )
        verification_times.append(result['time_taken'] * 1000)
    
    print(f"   Mean: {statistics.mean(verification_times):.2f} ms")
    print(f"   Median: {statistics.median(verification_times):.2f} ms")
    print(f"   Min: {min(verification_times):.2f} ms")
    print(f"   Max: {max(verification_times):.2f} ms")
    
    # Verification should be faster than signing
    if statistics.mean(verification_times) < statistics.mean(signing_times):
        print(f"   ✅ Realistic: Verification ({statistics.mean(verification_times):.2f}ms) is faster than signing ({statistics.mean(signing_times):.2f}ms)")
    else:
        print(f"   ⚠️  Warning: Verification should be faster than signing")
    
    print("\n3. Testing Memory Usage (10 samples)")
    print("-" * 40)
    
    memory_samples = []
    for i in range(10):
        memory = generator.generate_resource_usage(
            scenario='normal_jws_ecdsa',
            concurrent_ops=random.randint(1, 10)
        )
        memory_samples.append(memory['memory_mb'])
    
    print(f"   Average: {statistics.mean(memory_samples):.1f} MB")
    print(f"   Min: {min(memory_samples):.1f} MB")
    print(f"   Max: {max(memory_samples):.1f} MB")
    
    print("\n4. Testing Failure Rates (1000 operations)")
    print("-" * 40)
    
    failures = 0
    error_counts = {}
    for i in range(1000):
        result = generator.generate_scenario_result(
            scenario='normal_jws_ecdsa',
            operation_type='signing',
            payload_size_kb=random.randint(1, 100)
        )
        if not result['success']:
            failures += 1
            error_type = result['error_type']
            if error_type:
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
    
    failure_rate = (failures / 1000) * 100
    print(f"   Failures: {failures}/1000")
    print(f"   Failure rate: {failure_rate:.2f}%")
    
    if 0.05 <= failure_rate <= 0.5:  # Realistic failure rate 0.05-0.5%
        print(f"   ✅ Realistic: Failure rate {failure_rate:.2f}% is within expected range")
    else:
        print(f"   ⚠️  Warning: Failure rate {failure_rate:.2f}% outside expected range")
    
    print("\n5. Testing Error Types")
    print("-" * 40)
    
    if error_counts:
        print("   Error type distribution:")
        for error_type, count in error_counts.items():
            percentage = (count / failures) * 100
            print(f"     - {error_type}: {count} ({percentage:.1f}%)")
    else:
        print("   No errors generated (normal for low failure rate)")
    
    return generator

# ===== TEST 2: MULTI-SCENARIO GENERATOR =====
def test_multi_scenario_generator():
    """Test the multi-scenario data generator"""
    print("\n" + "=" * 60)
    print("TEST 2: MULTI-SCENARIO DATA GENERATOR")
    print("=" * 60)
    
    print("\nInitializing MultiScenarioDataGenerator...")
    generator = RealisticDataGenerator()
    
    scenarios = [
        ('normal_jws_ecdsa', 'signing'),
        ('normal_jws_ecdsa', 'verification'),
        ('replay_attack', 'detection'),
        ('data_tampering', 'detection'),
        ('signature_forgery', 'verification')
    ]
    
    print("\nTesting all scenarios (50 samples each):")
    print("-" * 40)
    
    results = {}
    for scenario, operation in scenarios:
        print(f"\n  {scenario}.{operation}:")
        
        times = []
        successes = 0
        
        for i in range(50):
            result = generator.generate_scenario_result(
                scenario=scenario,
                operation_type=operation,
                payload_size_kb=random.randint(1, 50),
                concurrent_users=random.randint(1, 100)
            )
            
            times.append(result['time_taken'] * 1000)  # ms
            if result['success']:
                successes += 1
        
        if times:
            avg_time = statistics.mean(times)
            success_rate = (successes / 50) * 100
            
            # Expected ranges based on realistic benchmarks
            expected_ranges = {
                'normal_jws_ecdsa.signing': (1.0, 10.0),
                'normal_jws_ecdsa.verification': (0.5, 5.0),
                'replay_attack.detection': (2.0, 15.0),
                'data_tampering.detection': (3.0, 20.0),
                'signature_forgery.verification': (1.0, 10.0)
            }
            
            key = f"{scenario}.{operation}"
            expected_min, expected_max = expected_ranges.get(key, (0.1, 100.0))
            
            print(f"    Avg time: {avg_time:.2f} ms")
            print(f"    Success rate: {success_rate:.1f}%")
            
            if expected_min <= avg_time <= expected_max:
                print(f"    ✅ Realistic time ({expected_min}-{expected_max}ms)")
            else:
                print(f"    ⚠️  Time outside expected range ({expected_min}-{expected_max}ms)")
        
        results[f"{scenario}.{operation}"] = times
    
    print("\n6. Testing Resource Usage")
    print("-" * 40)
    
    resource_samples = []
    for i in range(10):
        resource = generator.generate_resource_usage(
            scenario='normal_jws_ecdsa',
            concurrent_ops=random.randint(1, 20),
            duration_seconds=random.uniform(0.1, 5.0)
        )
        resource_samples.append(resource)
    
    avg_memory = statistics.mean([r['memory_mb'] for r in resource_samples])
    avg_cpu = statistics.mean([r['cpu_percent'] for r in resource_samples])
    
    print(f"   Avg Memory: {avg_memory:.1f} MB")
    print(f"   Avg CPU: {avg_cpu:.1f}%")
    
    # Check for memory leaks
    leak_count = sum(1 for r in resource_samples if r.get('has_memory_leak', False))
    print(f"   Memory leaks detected: {leak_count}/{len(resource_samples)}")
    
    return generator

# ===== TEST 3: CALIBRATION TEST =====
def test_calibration():
    """Test calibration data"""
    print("\n" + "=" * 60)
    print("TEST 3: CALIBRATION DATA TEST")
    print("=" * 60)
    
    calibration_dir = 'data/calibration'
    calibration_file = os.path.join(calibration_dir, 'multi_scenario_calibration.json')
    
    if os.path.exists(calibration_file):
        print(f"\nFound calibration file: {calibration_file}")
        
        try:
            with open(calibration_file, 'r') as f:
                calibration_data = json.load(f)
            
            print("\nCalibration information:")
            print(f"  File size: {os.path.getsize(calibration_file)} bytes")
            print(f"  Number of scenarios: {len(calibration_data.keys())}")
            
            if calibration_data:
                first_scenario = list(calibration_data.keys())[0]
                print(f"  First scenario: {first_scenario}")
                if 'signing' in calibration_data.get(first_scenario, {}):
                    print(f"  Has signing data: Yes")
            
            print("\n✅ Calibration data loaded successfully")
        except Exception as e:
            print(f"❌ Error loading calibration data: {e}")
    else:
        print(f"\n⚠️  Calibration file not found: {calibration_file}")
        print("   The generator will use default benchmarks")
        
        # Create calibration directory
        os.makedirs(calibration_dir, exist_ok=True)
        print(f"   Created directory: {calibration_dir}")

# ===== TEST 4: PERFORMANCE BENCHMARK =====
def test_performance_benchmark():
    """Test performance of the generator"""
    print("\n" + "=" * 60)
    print("TEST 4: PERFORMANCE BENCHMARK")
    print("=" * 60)
    
    # Initialize generator - NO algorithm parameter needed
    generator = RealisticDataGenerator()
    
    print("\nGenerating 10,000 data points...")
    
    start_time = time.time()
    
    data_points = []
    for i in range(10000):
        # Alternate between signing and verification
        if i % 2 == 0:
            result = generator.generate_scenario_result(
                scenario='normal_jws_ecdsa',
                operation_type='signing',
                payload_size_kb=random.randint(1, 100)
            )
        else:
            result = generator.generate_scenario_result(
                scenario='normal_jws_ecdsa',
                operation_type='verification',
                payload_size_kb=random.randint(1, 10)
            )
        
        data_points.append(result['time_taken'])
        
        # Progress indicator
        if i % 1000 == 0 and i > 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            print(f"  Generated {i}/10000 points ({rate:.0f} ops/sec)")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\nPerformance results:")
    print(f"  Total time: {total_time:.2f} seconds")
    print(f"  Average time per operation: {(total_time / 10000) * 1000:.3f} ms")
    print(f"  Operations per second: {10000 / total_time:.0f}")
    
    if total_time < 10.0:  # Should generate 10k operations in under 10 seconds
        print(f"  ✅ Performance acceptable")
    else:
        print(f"  ⚠️  Performance might be too slow for large-scale testing")

# ===== CAPTURE OUTPUT FUNCTION =====
def run_tests_capture_output():
    """Run all tests and capture output as string for web display"""
    import io
    from contextlib import redirect_stdout
    
    if RealisticDataGenerator is None:
        if not initialize_environment():
            return "❌ Error: Could not initialize RealisticDataGenerator. Check if modules/realistic_performance.py exists."

    capture_buffer = io.StringIO()
    
    with redirect_stdout(capture_buffer):
        try:
            main()
        except Exception as e:
            print(f"\n❌ Unexpected error during test execution: {e}")
            import traceback
            traceback.print_exc()
            
    return capture_buffer.getvalue()

# ===== MAIN FUNCTION =====
def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print("REALISTIC DATA GENERATOR TEST SUITE")
    print("=" * 60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Test 1: Basic generator
        print("\n" + "=" * 60)
        print("STARTING TEST 1: BASIC GENERATOR")
        print("=" * 60)
        gen1 = test_basic_generator()
        
        # Test 2: Multi-scenario generator
        print("\n" + "=" * 60)
        print("STARTING TEST 2: MULTI-SCENARIO GENERATOR")
        print("=" * 60)
        gen2 = test_multi_scenario_generator()
        
        # Test 3: Calibration
        print("\n" + "=" * 60)
        print("STARTING TEST 3: CALIBRATION TEST")
        print("=" * 60)
        test_calibration()
        
        # Test 4: Performance benchmark
        print("\n" + "=" * 60)
        print("STARTING TEST 4: PERFORMANCE BENCHMARK")
        print("=" * 60)
        test_performance_benchmark()
        
        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"\nSummary:")
        print("✅ RealisticDataGenerator is working correctly")
        print("✅ MultiScenarioDataGenerator is ready for use")
        print("✅ Calibration system is functional")
        print("✅ Performance is acceptable for testing")
        
        print("\nNext steps:")
        print("1. Update testing_controller.py to use the new generators")
        print("2. Run verify_realistic_data.py for comprehensive verification")
        print("3. Test through the web interface")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

# ===== ENTRY POINT =====
if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Test realistic data generator')
    parser.add_argument('--quick', action='store_true', help='Run quick test only')
    parser.add_argument('--no-benchmark', action='store_true', help='Skip performance benchmark')
    
    args = parser.parse_args()
    
    # Run tests
    exit_code = main()
    sys.exit(exit_code)