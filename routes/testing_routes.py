# routes/testing_routes.py
from flask import Blueprint, render_template, request, jsonify, send_file, Response, current_app, session, redirect, url_for
import json
import csv
import io
import os
import sys
import time
from datetime import datetime
from types import SimpleNamespace

import psutil

# Import requires_auth logic (Duplikasi sederhana atau import dari app jika memungkinkan)
# Karena circular import sulit, kita cek session atau password manual di sini
def check_auth():
    # Implementasi sederhana: Cek apakah config password ada di request header/param
    # Atau asumsikan testing hanya boleh diakses jika sudah login (jika ada sistem login)
    # Untuk sekarang, kita biarkan terbuka tapi beri peringatan di log
    pass

# ===== FUNGSI calculate_duration =====
def calculate_duration(start_str, end_str):
    """Menghitung durasi antara dua waktu string"""
    if not start_str or not end_str:
        return "Tidak tersedia"

    try:
        # Coba parsing format ISO (dengan atau tanpa Z)
        if 'Z' in start_str:
            start_str = start_str.replace('Z', '+00:00')
        if 'Z' in end_str:
            end_str = end_str.replace('Z', '+00:00')

        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)

        selisih = end - start
        total_detik = selisih.total_seconds()

        # Handle negative duration (shouldn't happen but just in case)
        if total_detik < 0:
            total_detik = abs(total_detik)

        # Also handle days if duration is very long
        hari, sisa = divmod(total_detik, 86400)  # 86400 seconds in a day
        jam, sisa = divmod(sisa, 3600)
        menit, detik = divmod(sisa, 60)

        if hari > 0:
            return f"{int(hari)}h {int(jam)}j {int(menit)}m {int(detik)}det"
        elif jam > 0:
            return f"{int(jam)}j {int(menit)}m {int(detik)}det"
        elif menit > 0:
            return f"{int(menit)}m {int(detik)}det"
        else:
            return f"{int(detik)}det"
    except ValueError:
        # Coba format lain jika format ISO gagal
        try:
            format_string = '%Y-%m-%d %H:%M:%S'
            start = datetime.strptime(start_str, format_string)
            end = datetime.strptime(end_str, format_string)

            selisih = end - start
            total_detik = selisih.total_seconds()

            # Handle negative duration
            if total_detik < 0:
                total_detik = abs(total_detik)

            hari, sisa = divmod(total_detik, 86400)
            jam, sisa = divmod(sisa, 3600)
            menit, detik = divmod(sisa, 60)

            if hari > 0:
                return f"{int(hari)}h {int(jam)}j {int(menit)}m {int(detik)}det"
            elif jam > 0:
                return f"{int(jam)}j {int(menit)}m {int(detik)}det"
            elif menit > 0:
                return f"{int(menit)}m {int(detik)}det"
            else:
                return f"{int(detik)}det"
        except Exception as e:
            print(f"Error parsing waktu: {e}")
            return "Format waktu tidak valid"
    except Exception as e:
        print(f"Error menghitung durasi: {e}")
        return "Error"

# ===== IMPORT CONTROLLER =====
# Tambahkan path ke modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import testing controller
try:
    from modules.testing_controller import testing_controller
    print("✅ Successfully imported testing_controller")
except ImportError as e:
    print(f"❌ Error importing testing_controller: {e}")
    # Buat instance alternatif jika import gagal
    class FallbackController:
        def __init__(self):
            self.active_tests = []

        def get_all_test_sessions(self, limit=50):
            return []

        def get_active_tests(self):
            return []

        def start_test_session(self, test_type, test_name, params):
            return None

        def get_test_session(self, session_id):
            return None

        def stop_test_session(self, session_id):
            return False

        def cleanup_finished_tests(self):
            return 0

    testing_controller = FallbackController()
    print("⚠️ Using fallback testing controller")

# Import calibration module
try:
    from calibrate_performance import (
        benchmark_crypto_operations,
        SAMPLING_TIERS,
        estimate_runtime,
        get_system_info
    )
    print("✅ Successfully imported calibration module")
except ImportError as e:
    print(f"❌ Error importing calibration module: {e}")
    benchmark_crypto_operations = None
    SAMPLING_TIERS = None
    estimate_runtime = None
    get_system_info = None

# ===== GLOBAL STATE FOR CALIBRATION =====
import threading
_calibration_stop_event = threading.Event()  # Thread-safe stop event

_calibration_state = {
    'running': False,
    'progress': 0,
    'current_tier': None,
    'current_operation': None,
    'current_iteration': 0,
    'total_iterations': 0,
    'message': '',
    'result': None,
    'error': None,
    'start_time': None,
    'end_time': None,
    'stop_flag': False  # Legacy flag, now using _calibration_stop_event
}

# Reference to calibration thread for cleanup
_calibration_thread = None

# ===== FUNGSI SETUP LIMITER (DUMMY) =====
def setup_limiter(app):
    """Fungsi dummy untuk compatibility"""
    pass

# ===== BLUEPRINT =====
testing_bp = Blueprint('testing', __name__, 
                      template_folder='../templates',
                      static_folder='../static',
                      url_prefix='/testing')

LOCAL_TESTING_ADDRESSES = {'127.0.0.1', '::1'}


def _testing_access_allowed():
    """Izinkan testing dari localhost/debug, atau dari user yang sudah login."""
    if current_app.debug:
        return True

    if request.remote_addr in LOCAL_TESTING_ADDRESSES:
        return True

    if session.get('logged_in'):
        return True

    return False


def _testing_request_expects_json():
    if request.method != 'GET' or request.is_json:
        return True

    if request.path.startswith(('/testing/progress/', '/testing/status/', '/testing/active_tests', '/testing/server_metrics')):
        return True

    best_match = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best_match == 'application/json'


@testing_bp.before_request
def require_testing_access():
    if _testing_access_allowed():
        return None

    current_app.logger.warning(
        "Blocked testing access from %s to %s",
        request.remote_addr,
        request.path
    )

    if _testing_request_expects_json():
        return jsonify({
            'success': False,
            'message': 'Testing requires login, localhost, or debug mode'
        }), 401

    return redirect(url_for('login', next=request.url))


_resource_metrics_lock = threading.Lock()
_resource_metrics_previous = {
    'timestamp': None,
    'disk': None,
    'network': None
}


def _bytes_per_second(current, previous, fields, elapsed_seconds):
    if not current or not previous or elapsed_seconds <= 0:
        return {field: 0.0 for field in fields}

    rates = {}
    for field in fields:
        delta = max(0, getattr(current, field, 0) - getattr(previous, field, 0))
        rates[field] = delta / elapsed_seconds
    return rates


def _read_external_network_counters():
    per_interface = psutil.net_io_counters(pernic=True)
    selected_interfaces = [
        name for name in per_interface
        if not name.lower().startswith(('lo', 'loopback'))
    ]

    if not selected_interfaces:
        return psutil.net_io_counters(), []

    return SimpleNamespace(
        bytes_recv=sum(per_interface[name].bytes_recv for name in selected_interfaces),
        bytes_sent=sum(per_interface[name].bytes_sent for name in selected_interfaces)
    ), selected_interfaces


def _read_live_server_metrics():
    """Read live host metrics from the server running this Flask app."""
    now = time.monotonic()
    cpu_percent = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    disk = psutil.disk_io_counters()
    network, network_interfaces = _read_external_network_counters()

    with _resource_metrics_lock:
        previous_timestamp = _resource_metrics_previous['timestamp']
        elapsed = now - previous_timestamp if previous_timestamp else 0

        disk_rates = _bytes_per_second(
            disk,
            _resource_metrics_previous['disk'],
            ('read_bytes', 'write_bytes'),
            elapsed
        )
        network_rates = _bytes_per_second(
            network,
            _resource_metrics_previous['network'],
            ('bytes_recv', 'bytes_sent'),
            elapsed
        )

        _resource_metrics_previous['timestamp'] = now
        _resource_metrics_previous['disk'] = disk
        _resource_metrics_previous['network'] = network

    disk_read_mb_s = disk_rates['read_bytes'] / (1024 * 1024)
    disk_write_mb_s = disk_rates['write_bytes'] / (1024 * 1024)
    network_rx_mbit_s = network_rates['bytes_recv'] * 8 / 1_000_000
    network_tx_mbit_s = network_rates['bytes_sent'] * 8 / 1_000_000

    return {
        'cpu_percent': round(cpu_percent, 2),
        'ram_used_mb': round((memory.total - memory.available) / 1024 / 1024, 2),
        'ram_total_mb': round(memory.total / 1024 / 1024, 2),
        'ram_percent': round(memory.percent, 2),
        'disk_read_mb_s': round(disk_read_mb_s, 3),
        'disk_write_mb_s': round(disk_write_mb_s, 3),
        'disk_io_mb_s': round(disk_read_mb_s + disk_write_mb_s, 3),
        'network_rx_mbit_s': round(network_rx_mbit_s, 3),
        'network_tx_mbit_s': round(network_tx_mbit_s, 3),
        'network_mbit_s': round(network_rx_mbit_s + network_tx_mbit_s, 3),
        'network_interfaces': network_interfaces,
        'sample_interval_seconds': round(elapsed, 3) if elapsed else 0
    }


# ===== ROUTES =====
@testing_bp.route('/')
def testing_dashboard():
    """Dashboard utama testing"""
    try:
        sessions = testing_controller.get_all_test_sessions(limit=20)
    except Exception as e:
        print(f"Error getting sessions: {e}")
        sessions = []
    
    return render_template('testing_dashboard.html', 
                         sessions=sessions)

@testing_bp.route('/test_config/<test_type>')
def test_config(test_type):
    """Halaman konfigurasi untuk test type tertentu"""
    
    test_configs = {
        'normal_operations': {
            'name': 'Normal Operations',
            'description': '10.000 signing + 10.000 verification operations',
            'default_params': {
                'signing_count': 10000,
                'verification_count': 10000
            },
            'fields': [
                {'name': 'signing_count', 'label': 'Signing Count', 'type': 'number', 
                 'min': 100, 'max': 50000, 'default': 10000, 'required': True},
                {'name': 'verification_count', 'label': 'Verification Count', 'type': 'number', 
                 'min': 100, 'max': 50000, 'default': 10000, 'required': True}
            ]
        },
        'replay_attack': {
            'name': 'Replay Attack Simulation',
            'description': '1.500 samples × 15–20 repeated verifications',
            'default_params': {
                'sample_count': 1500,
                'repetitions': 20
            },
            'fields': [
                {'name': 'sample_count', 'label': 'Sample Count', 'type': 'number', 
                 'min': 100, 'max': 10000, 'default': 1500, 'required': True},
                {'name': 'repetitions', 'label': 'Repetitions per Sample', 'type': 'number', 
                 'min': 2, 'max': 50, 'default': 20, 'required': True}
            ]
        },
        'data_tampering': {
            'name': 'Data Tampering Detection',
            'description': 'Field modification, addition, removal operations',
            'default_params': {
                'operations': 50000
            },
            'fields': [
                {'name': 'operations', 'label': 'Total Operations', 'type': 'number', 
                 'min': 1000, 'max': 100000, 'default': 50000, 'required': True}
            ]
        },
        'signature_forgery': {
            'name': 'Signature Forgery Testing',
            'description': 'Fokus pada algoritma RSA (RSA-PSS 2048-bit). Menguji ketahanan terhadap Random, Swapped, dan Truncated signatures sesuai spesifikasi jurnal.',
            'default_params': {
                'attempts': 20000,
                'algorithm': 'RSA'
            },
            'fields': [
                {'name': 'attempts', 'label': 'Forgery Attempts', 'type': 'number', 
                 'min': 1000, 'max': 50000, 'default': 20000, 'required': True},
                {'name': 'algorithm', 'label': 'Target Algorithm', 'type': 'select',
                 'options': [
                     {'value': 'RSA', 'label': 'RSA-PSS 2048-bit (Modified Salt 8-byte)'}
                 ], 'default': 'RSA', 'required': True}
            ]
        },
        'stress_test': {
            'name': 'Simulated Stress Testing',
            'description': 'Simulate 100–1.500 concurrent users',
            'default_params': {
                'operations': 10000,
                'concurrent_users': '100,500,1000,1500'
            },
            'fields': [
                {'name': 'operations', 'label': 'Total Operations', 'type': 'number', 
                 'min': 1000, 'max': 50000, 'default': 10000, 'required': True},
                {'name': 'concurrent_users', 'label': 'Concurrent Users (comma-separated)', 
                 'type': 'text', 'default': '100,500,1000,1500', 'required': True,
                 'placeholder': 'Enter comma-separated numbers: 100,500,1000,1500'}
            ]
        },
        'real_http_stress_test': {
            'name': 'Real HTTP Stress Test (Local Server)',
            'description': 'Menembak endpoint aplikasi nyata dari server yang sama melalui HTTP/HTTPS. Default menjalankan workflow Generate + Verify QR: membuat QR RSA-PSS, mengambil URL /v/<token>, lalu memverifikasi QR tersebut.',
            'default_params': {
                'operations': 20,
                'concurrent_users': '2,5,10',
                'target_endpoint': 'generate_verify',
                'base_url': os.environ.get('BASE_URL', 'https://rsa-pss.com/'),
                'request_timeout_seconds': 15
            },
            'fields': [
                {'name': 'operations', 'label': 'Requests per User Level', 'type': 'number',
                 'min': 1, 'max': 2000, 'default': 20, 'required': True,
                 'help': 'Jumlah request nyata untuk setiap level concurrent users.'},
                {'name': 'concurrent_users', 'label': 'Concurrent Users (comma-separated)',
                 'type': 'text', 'default': '2,5,10', 'required': True,
                 'placeholder': 'Contoh: 2,5,10'},
                {'name': 'target_endpoint', 'label': 'Target Endpoint', 'type': 'select',
                 'options': [
                     {'value': 'generate_verify', 'label': 'Generate + Verify QR (POST /generate_qr + GET /v/<token>)'},
                     {'value': 'generate_qr', 'label': 'Generate Only: POST /generate_qr (RSA-PSS + QR generation)'},
                     {'value': 'dashboard', 'label': 'GET / (authenticated dashboard, light)'},
                     {'value': 'server_metrics', 'label': 'GET /testing/server_metrics (metrics endpoint, light)'}
                 ], 'default': 'generate_verify', 'required': True,
                 'help': 'Generate + Verify paling end-to-end, tetapi membuat file QR, menulis log generate/verifikasi, dan dapat terkena rate limit.'},
                {'name': 'base_url', 'label': 'Base URL', 'type': 'text',
                 'default': os.environ.get('BASE_URL', 'https://rsa-pss.com/'), 'required': True,
                 'help': 'Gunakan domain publik untuk melewati Nginx/HTTPS, atau http://127.0.0.1:5000/ untuk jalur lokal.'},
                {'name': 'request_timeout_seconds', 'label': 'Request Timeout (seconds)', 'type': 'number',
                 'min': 2, 'max': 120, 'default': 15, 'required': True}
            ]
        }
    }
    
    if test_type not in test_configs:
        return "Test type not found", 404
    
    return render_template('test_config.html',
                         test_type=test_type,
                         config=test_configs[test_type])

@testing_bp.route('/start_test', methods=['POST'])
def start_test():
    """API untuk memulai test"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        test_type = data.get('test_type')
        test_name = data.get('test_name', f'{test_type} Test')
        params = data.get('params', {})
        
        if not test_type:
            return jsonify({
                'success': False,
                'message': 'Test type is required'
            }), 400
        
        # Start test session
        session_id = testing_controller.start_test_session(
            test_type=test_type,
            test_name=test_name,
            params=params
        )
        
        if session_id:
            return jsonify({
                'success': True,
                'session_id': session_id,
                'message': f'Test "{test_name}" started successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to start test'
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error starting test: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error starting test: {str(e)}'
        }), 500

@testing_bp.route('/progress/<session_id>')
def test_progress(session_id):
    """API untuk mendapatkan progress test"""
    try:
        current_app.logger.debug(f"Getting progress for session {session_id}")
        
        session_data = testing_controller.get_test_session(session_id)
        
        if not session_data:
            return jsonify({
                'error': 'Session not found'
            }), 404
        
        # Format response
        response = {
            'session_id': session_id,
            'test_type': session_data.get('test_type'),
            'test_name': session_data.get('test_name'),
            'status': session_data.get('status', 'unknown'),
            'progress': float(session_data.get('progress', 0)),
            'total_operations': session_data.get('total_operations', 0),
            'completed_operations': session_data.get('completed_operations', 0),
            'start_time': session_data.get('start_time'),
            'results': session_data.get('results', {})
        }
        
        # LOG SEMUA DATA
        current_app.logger.info(f"Session data: {json.dumps(session_data, indent=2, default=str)}")
        
        current_app.logger.debug(f"Progress for {session_id}: {response['progress']}%")
        return jsonify(response)
    except Exception as e:
        current_app.logger.error(f"Error getting progress: {str(e)}")
        return jsonify({
            'error': f'Error getting progress: {str(e)}'
        }), 500

@testing_bp.route('/results/<session_id>')
def test_results(session_id):
    """Halaman hasil test"""
    try:
        session_data = testing_controller.get_test_session(session_id)
        
        if not session_data:
            return "Test session not found", 404
        
        # Hitung durasi di backend
        start_time = session_data.get('start_time')
        end_time = session_data.get('end_time')

        if start_time and end_time:
            durasi = calculate_duration(start_time, end_time)
            session_data['durasi_formatted'] = durasi
        elif start_time and session_data.get('status') == 'completed':
            # Fallback: Estimasi durasi untuk completed sessions tanpa end_time
            try:
                # Parsing start_time
                if 'Z' in start_time:
                    start_time = start_time.replace('Z', '+00:00')
                start_dt = datetime.fromisoformat(start_time)
                
                # Estimasi berdasarkan jenis test dan jumlah operasi
                test_type = session_data.get('test_type', '')
                ops = session_data.get('completed_operations') or session_data.get('total_operations') or 0
                
                # Durasi estimasi per operasi (berdasarkan data testing aktual)
                # Berdasarkan: 20,000 ops signature_forgery = 14 detik → 0.7ms/op
                duration_per_op_ms = {
                    'normal_operations': 0.8,    # 0.8ms per operation (simulasi lebih cepat)
                    'replay_attack': 0.7,        # 0.7ms per operation
                    'data_tampering': 0.7,       # 0.7ms per operation
                    'signature_forgery': 0.7,    # 0.7ms per operation (14s untuk 20K ops)
                    'stress_test': 0.8,          # 0.8ms per operation
                    'real_http_stress_test': 200 # fallback 200ms per real HTTP request
                }
                
                duration_per_op = duration_per_op_ms.get(test_type, 0.020)
                estimated_seconds = max(5, min(7200, ops * duration_per_op / 1000))
                
                # Hitung end_time estimasi
                from datetime import timedelta
                end_dt = start_dt + timedelta(seconds=estimated_seconds)
                durasi = calculate_duration(start_dt.isoformat(), end_dt.isoformat())
                
                session_data['durasi_formatted'] = durasi
                session_data['end_time'] = end_dt.isoformat()
                
            except Exception as e:
                current_app.logger.warning(f"Error calculating fallback duration: {e}")
                session_data['durasi_formatted'] = 'Tidak tersedia'
        else:
            session_data['durasi_formatted'] = 'Tidak tersedia'
        
        return render_template('test_results.html',
                             session=session_data,
                             calculate_duration=calculate_duration)
    except Exception as e:
        current_app.logger.error(f"Error getting results: {str(e)}")
        return f"Error getting results: {str(e)}", 500

@testing_bp.route('/active_tests')
def active_tests():
    """API untuk mendapatkan test yang aktif"""
    try:
        active = testing_controller.get_active_tests()
        
        formatted_tests = []
        for test in active:
            start_time = test.get('start_time')
            if hasattr(start_time, 'isoformat'):
                start_time_str = start_time.isoformat()
            elif isinstance(start_time, str):
                start_time_str = start_time
            else:
                start_time_str = str(start_time)
            
            formatted_tests.append({
                'session_id': test.get('session_id', ''),
                'test_type': test.get('test_type', ''),
                'test_name': test.get('test_name', ''),
                'progress': test.get('progress', 0),
                'start_time': start_time_str
            })
        
        return jsonify({
            'active_tests': formatted_tests,
            'count': len(formatted_tests)
        })
    except Exception as e:
        current_app.logger.error(f"Error getting active tests: {str(e)}")
        return jsonify({
            'active_tests': [],
            'count': 0,
            'error': str(e)
        }), 500

@testing_bp.route('/stop_test/<session_id>', methods=['POST'])
def stop_test(session_id):
    """API untuk menghentikan test"""
    try:
        success = testing_controller.stop_test_session(session_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Test {session_id} stopped'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Test {session_id} not found or already stopped'
            }), 404
    except Exception as e:
        current_app.logger.error(f"Error stopping test: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error stopping test: {str(e)}'
        }), 500

@testing_bp.route('/history')
def test_history():
    """Halaman history test"""
    try:
        sessions = testing_controller.get_all_test_sessions(limit=100)
    except Exception as e:
        current_app.logger.error(f"Error getting history: {str(e)}")
        sessions = []

    return render_template('test_history.html',
                         sessions=sessions,
                         calculate_duration=calculate_duration)

@testing_bp.route('/download_report/<session_id>')
def download_report(session_id):
    """Download report dalam format CSV"""
    try:
        session_data = testing_controller.get_test_session(session_id)
        if not session_data:
            return "Session not found", 404
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['AUTOMATED TESTING SYSTEM - TEST REPORT'])
        writer.writerow([])
        writer.writerow(['SESSION INFORMATION'])
        writer.writerow(['Session ID', session_id])
        writer.writerow(['Test Type', session_data.get('test_type', '')])
        writer.writerow(['Test Name', session_data.get('test_name', '')])
        writer.writerow(['Start Time', session_data.get('start_time', '')])
        writer.writerow(['End Time', session_data.get('end_time', '')])
        writer.writerow(['Status', session_data.get('status', '')])
        writer.writerow(['Progress', f"{session_data.get('progress', 0)}%"])
        writer.writerow(['Total Operations', session_data.get('total_operations', 0)])
        writer.writerow(['Completed Operations', session_data.get('completed_operations', 0)])
        writer.writerow([])
        
        # Results
        results = session_data.get('results', {})
        if results:
            writer.writerow(['TEST RESULTS'])
            
            for key, value in results.items():
                if isinstance(value, (dict, list)):
                    writer.writerow([key, json.dumps(value, indent=2)])
                else:
                    writer.writerow([key, value])
        
        output.seek(0)
        
        # Send as file
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=test_report_{session_id}.csv'
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error downloading report: {str(e)}")
        return f"Error downloading report: {str(e)}", 500

@testing_bp.route('/cleanup', methods=['POST'])
def cleanup_tests():
    """API untuk cleanup test yang sudah selesai dari memory"""
    try:
        cleaned_count = testing_controller.cleanup_finished_tests()

        return jsonify({
            'success': True,
            'message': f'Cleaned up {cleaned_count} finished tests from memory'
        })
    except Exception as e:
        current_app.logger.error(f"Error cleaning up tests: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error cleaning up tests: {str(e)}'
        }), 500

@testing_bp.route('/delete_all_sessions', methods=['POST'])
def delete_all_sessions():
    """API untuk menghapus semua session testing agar bisa testing ulang dari awal"""
    try:
        deleted_count = testing_controller.clear_all_sessions()

        return jsonify({
            'success': True,
            'message': f'Berhasil menghapus {deleted_count} session testing beserta semua data terkait',
            'deleted_count': deleted_count
        })
    except Exception as e:
        current_app.logger.error(f"Error deleting all sessions: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error menghapus sessions: {str(e)}'
        }), 500

@testing_bp.route('/delete_session/<session_id>', methods=['POST'])
def delete_session(session_id):
    """API untuk menghapus satu session tertentu"""
    try:
        success = testing_controller.delete_single_session(session_id)

        if success:
            return jsonify({
                'success': True,
                'message': f'Berhasil menghapus session {session_id[:20]}...'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Gagal menghapus session {session_id[:20]}... atau session tidak ditemukan'
            }), 404
    except Exception as e:
        current_app.logger.error(f"Error deleting session {session_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error menghapus session: {str(e)}'
        }), 500

@testing_bp.route('/stats')
def test_stats():
    """API untuk mendapatkan statistik testing"""
    try:
        sessions = testing_controller.get_all_test_sessions(limit=1000)
        
        stats = {
            'total_tests': len(sessions),
            'by_status': {},
            'by_type': {},
            'success_rate': 0,
            'avg_duration': 0
        }
        
        completed_tests = 0
        successful_tests = 0
        total_duration = 0
        
        for session in sessions:
            # Count by status
            status = session.get('status', 'unknown')
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
            
            # Count by type
            test_type = session.get('test_type', 'unknown')
            stats['by_type'][test_type] = stats['by_type'].get(test_type, 0) + 1
            
            # Calculate success rate and duration
            if status == 'completed':
                completed_tests += 1
                successful_tests += 1
            elif status == 'failed':
                completed_tests += 1
            
            # Calculate duration if available
            start_time = session.get('start_time')
            end_time = session.get('end_time')
            if start_time and end_time:
                try:
                    if isinstance(start_time, str):
                        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    else:
                        start_dt = start_time
                        
                    if isinstance(end_time, str):
                        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    else:
                        end_dt = end_time
                    
                    if isinstance(start_dt, datetime) and isinstance(end_dt, datetime):
                        duration = (end_dt - start_dt).total_seconds()
                        total_duration += duration
                except Exception as e:
                    current_app.logger.error(f"Error calculating duration: {e}")
                    continue
        
        if completed_tests > 0:
            stats['success_rate'] = (successful_tests / completed_tests) * 100
        
        if completed_tests > 0 and total_duration > 0:
            stats['avg_duration'] = total_duration / completed_tests
        
        return jsonify(stats)
    except Exception as e:
        current_app.logger.error(f"Error getting stats: {str(e)}")
        return jsonify({
            'error': f'Error getting stats: {str(e)}'
        }), 500

@testing_bp.route('/server_metrics')
def server_metrics():
    """Live server metrics for the stress-test resource monitor."""
    try:
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'metrics': _read_live_server_metrics()
        })
    except Exception as e:
        current_app.logger.error(f"Error reading server metrics: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error reading server metrics: {str(e)}'
        }), 500

@testing_bp.route('/verify_generator_suite')
def verify_generator_suite():
    """Menjalankan test suite untuk generator data realistis dan menampilkan output"""
    try:
        # Import module secara dinamis untuk memastikan path benar
        import test_realistic_data
        import importlib
        # Reload module untuk memastikan fresh run
        importlib.reload(test_realistic_data)
        
        # Jalankan test dan tangkap output
        output = test_realistic_data.run_tests_capture_output()
        
        return render_template('test_suite_output.html', output=output)
    except Exception as e:
        current_app.logger.error(f"Error executing generator test suite: {e}")
        return f"Error executing test suite: {str(e)}", 500

@testing_bp.route('/comprehensive_test')
def comprehensive_test_page():
    """Halaman untuk memulai comprehensive test."""
    return render_template('comprehensive_test_runner.html')

@testing_bp.route('/run_comprehensive_test', methods=['POST'])
def run_comprehensive_test():
    """Menjalankan comprehensive test suite dari verify_realistic_data.py."""
    try:
        algorithm = request.form.get('algorithm', 'RSA')
        
        # Import module secara dinamis untuk memastikan path benar
        # dan mendapatkan versi terbaru jika ada perubahan
        import verify_realistic_data
        import importlib
        importlib.reload(verify_realistic_data)

        # Jalankan test dan dapatkan hasilnya
        # Ini adalah operasi yang berjalan lama (blocking)
        summary, plot_path, pie_plot_path, payload_comparison, trend_plot_path = verify_realistic_data.run_comprehensive_test(algorithm=algorithm)

        # FIX: Ensure payload_comparison is not None (fallback data for reference table)
        if payload_comparison is None:
            payload_comparison = {
                'signature_size': {'ECDSA': '64 bytes', 'RSA': '256 bytes'},
                'qr_version': {'ECDSA': 'Version 3-4', 'RSA': 'Version 9-10'},
                'scannability': {'ECDSA': 'High (Fast)', 'RSA': 'Low (Dense)'},
                'dimensions': {'ECDSA': '29x29 modules', 'RSA': '53x53 modules'},
                'file_size': {'ECDSA': '~0.5 KB', 'RSA': '~1.2 KB'}
            }

        # Dapatkan juga testing plan untuk ditampilkan di tabel
        validator_plan = verify_realistic_data.TestingScenarioValidator.TESTING_PLAN

        return render_template('comprehensive_test_results.html',
                               summary=summary,
                               plot_path=plot_path,
                               pie_plot_path=pie_plot_path,
                               trend_plot_path=trend_plot_path,
                               payload_comparison=payload_comparison,
                               validator_plan=validator_plan,
                               algorithm=algorithm)
    except Exception as e:
        current_app.logger.error(f"Error executing comprehensive test suite: {e}", exc_info=True)
        return f"Error executing comprehensive test suite: {str(e)}", 500


# ============================================================================
# CALIBRATION ROUTES
# ============================================================================

@testing_bp.route('/calibration')
def calibration_page():
    """Halaman kalibrasi performa sistem"""
    try:
        # Cek apakah ada kalibrasi yang sudah ada
        calibration_path = 'data/calibration/multi_scenario_calibration.json'
        existing_calibration = None
        if os.path.exists(calibration_path):
            with open(calibration_path, 'r') as f:
                existing_calibration = json.load(f)
    except Exception as e:
        current_app.logger.error(f"Error loading existing calibration: {e}")
        existing_calibration = None

    tiers_info = []
    if SAMPLING_TIERS:
        for tier_name, tier_config in SAMPLING_TIERS.items():
            tiers_info.append({
                'name': tier_name,
                'display_name': tier_config.name,
                'samples': tier_config.num_samples,
                'estimated_runtime': tier_config.expected_runtime_seconds,
                'accuracy': tier_config.accuracy_estimate_percent,
                'use_case': tier_config.use_case
            })

    # Get live system info
    if get_system_info:
        live_system = get_system_info()
    else:
        import platform
        live_system = {
            'python_version': sys.version,
            'platform_system': platform.system(),
            'platform_release': platform.release(),
            'platform_version': platform.version(),
            'platform_machine': platform.machine(),
            'platform_processor': platform.processor(),
            'cpu_count_logical': os.cpu_count() or 0,
            'cpu_count_physical': None,
            'cpu_freq_max': None,
            'cpu_freq_unit': 'GHz',
            'ram_total_gb': None,
            'ram_used_gb': None,
            'ram_available_gb': None,
            'ram_percent': None
        }

    return render_template('calibration_page.html',
                         tiers_info=tiers_info,
                         existing_calibration=existing_calibration,
                         live_system=live_system)


@testing_bp.route('/run_calibration', methods=['POST'])
def run_calibration():
    """Endpoint untuk menjalankan kalibrasi"""
    global _calibration_state

    if _calibration_state['running']:
        return jsonify({
            'success': False,
            'message': 'Kalibrasi sedang berjalan'
        }), 400

    if benchmark_crypto_operations is None:
        return jsonify({
            'success': False,
            'message': 'Module kalibrasi tidak tersedia'
        }), 500

    try:
        tier = request.json.get('tier', 'quick_check')
        algorithms_config = request.json.get('algorithms', ['ecdsa_p256', 'rsa_pss_2048'])

        # Validasi tier
        if tier not in ['quick_check', 'production', 'validation']:
            return jsonify({
                'success': False,
                'message': f'Tier tidak valid: {tier}'
            }), 400

        # Cleanup old thread if finished
        global _calibration_thread, _calibration_stop_event
        if _calibration_thread is not None and not _calibration_thread.is_alive():
            _calibration_thread = None
            # Clear the stop event for next run
            _calibration_stop_event.clear()

        # Check if calibration is already running
        if _calibration_state.get('running', False):
            return jsonify({
                'success': False,
                'message': 'Kalibrasi sedang berjalan. Tunggu sampai selesai.'
            }), 400

        # Reset state dan clear stop event
        _calibration_stop_event.clear()
        _calibration_state = {
            'running': True,
            'progress': 0,
            'current_tier': tier,
            'current_operation': None,
            'current_iteration': 0,
            'total_iterations': 0,
            'message': 'Memulai kalibrasi...',
            'result': None,
            'error': None,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'stop_flag': False  # Legacy flag
        }

        # Jalankan kalibrasi di thread terpisah
        import threading

        def run_calibration_thread():
            global _calibration_state, _calibration_thread
            try:
                # Setup algoritma
                from Crypto.PublicKey import RSA, ECC
                from Crypto.Signature import pss, DSS
                from Crypto.Hash import SHA256

                algorithms = {}
                if 'rsa_pss_2048' in algorithms_config:
                    algorithms['rsa_pss_2048'] = {
                        'key_gen': lambda: RSA.generate(2048),
                        'signer': pss,
                        'hash': SHA256
                    }
                if 'ecdsa_p256' in algorithms_config:
                    algorithms['ecdsa_p256'] = {
                        'key_gen': lambda: ECC.generate(curve='P-256'),
                        'signer': DSS,
                        'hash': SHA256
                    }

                if not algorithms:
                    _calibration_state['error'] = 'Tidak ada algoritma yang dipilih'
                    _calibration_state['running'] = False
                    return

                # Progress callback dengan pengecekan stop flag (thread-safe)
                def progress_callback(current, total, operation=None):
                    # Cek apakah ada permintaan stop (gunakan threading.Event untuk reliability)
                    if _calibration_stop_event.is_set():
                        raise InterruptedError("Kalibrasi dihentikan oleh pengguna")
                    
                    _calibration_state['current_iteration'] = current
                    _calibration_state['total_iterations'] = total
                    _calibration_state['progress'] = (current / total * 100) if total > 0 else 0
                    _calibration_state['current_tier'] = tier
                    if operation:
                        _calibration_state['current_operation'] = operation
                    _calibration_state['message'] = f'Mengkalibrasi {operation.replace("_", " ").title() if operation else "operasi kriptografi"}...'

                # Jalankan benchmark
                results = benchmark_crypto_operations(
                    num_samples=SAMPLING_TIERS[tier].num_samples,
                    tier_name=tier,
                    algorithms=algorithms,
                    progress_callback=progress_callback
                )

                # Simpan hasil
                calibration_path = 'data/calibration/multi_scenario_calibration.json'
                os.makedirs(os.path.dirname(calibration_path), exist_ok=True)

                import time

                # Use the get_system_info helper for detailed system info
                if get_system_info:
                    system_info = get_system_info()
                else:
                    system_info = {
                        'python_version': sys.version,
                        'platform_system': sys.platform,
                        'platform_release': '',
                        'platform_version': '',
                        'platform_machine': '',
                        'platform_processor': '',
                        'cpu_count': os.cpu_count() or 0,
                        'cpu_count_logical': os.cpu_count() or 0,
                        'cpu_count_physical': None,
                        'cpu_freq_current': None,
                        'cpu_freq_max': None,
                        'cpu_freq_unit': 'GHz',
                        'ram_total_gb': None,
                        'ram_available_gb': None,
                        'ram_used_gb': None,
                        'ram_percent': None
                    }

                calibration_data = {
                    'metadata': {
                        'calibration_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'num_samples': results.get('_metadata', {}).get('num_samples_requested', 'unknown'),
                        'tier': results.get('_metadata', {}).get('tier', 'unknown'),
                        'system_info': system_info
                    },
                    'benchmark_results': {k: v for k, v in results.items() if k != '_metadata'}
                }

                with open(calibration_path, 'w') as f:
                    json.dump(calibration_data, f, indent=2)

                _calibration_state['result'] = calibration_data
                _calibration_state['message'] = 'Kalibrasi selesai!'
                _calibration_state['progress'] = 100

            except InterruptedError as e:
                _calibration_state['error'] = str(e)
                _calibration_state['message'] = f'Dihentikan: {str(e)}'
                _calibration_state['running'] = False
                _calibration_state['end_time'] = datetime.now().isoformat()
                _calibration_state['stop_flag'] = False
                _calibration_stop_event.clear()  # Clear event untuk next run
                _calibration_thread = None
                import logging
                logging.warning(f"Calibration interrupted: {e}")
            except Exception as e:
                _calibration_state['error'] = str(e)
                _calibration_state['message'] = f'Error: {str(e)}'
                # Use standard logging instead of current_app.logger (outside app context in thread)
                import logging
                logging.error(f"Calibration error: {e}", exc_info=True)
            finally:
                _calibration_state['running'] = False
                _calibration_state['end_time'] = datetime.now().isoformat()
                _calibration_state['message'] = 'Kalibrasi selesai. Thread akan dibersihkan.'
                # Clear thread reference dan stop event untuk GC
                _calibration_stop_event.clear()
                _calibration_thread = None

        thread = threading.Thread(target=run_calibration_thread, daemon=True)
        _calibration_thread = thread
        thread.start()

        return jsonify({
            'success': True,
            'message': f'Kalibrasi {tier} dimulai',
            'tier': tier
        })

    except Exception as e:
        _calibration_state['running'] = False
        _calibration_state['error'] = str(e)
        current_app.logger.error(f"Error starting calibration: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@testing_bp.route('/calibration_progress')
def calibration_progress():
    """Endpoint untuk mendapatkan progress kalibrasi"""
    global _calibration_state, _calibration_thread

    # Cleanup thread reference jika sudah selesai
    if _calibration_thread is not None and not _calibration_thread.is_alive():
        _calibration_thread = None

    return jsonify({
        'running': _calibration_state['running'],
        'progress': _calibration_state['progress'],
        'current_tier': _calibration_state['current_tier'],
        'current_operation': _calibration_state['current_operation'],
        'current_iteration': _calibration_state['current_iteration'],
        'total_iterations': _calibration_state['total_iterations'],
        'message': _calibration_state['message'],
        'error': _calibration_state['error'],
        'start_time': _calibration_state['start_time'],
        'end_time': _calibration_state['end_time'],
        'result_summary': {
            algo: {
                op: {
                    'mean_ms': data.get('mean', 0),
                    'std_ms': data.get('std', 0),
                    'ci_lower': data.get('ci_lower', 0),
                    'ci_upper': data.get('ci_upper', 0)
                } for op, data in ops.items()
            } for algo, ops in _calibration_state.get('result', {}).get('benchmark_results', {}).items()
        } if _calibration_state.get('result') else None
    })

@testing_bp.route('/cleanup_calibration', methods=['POST'])
def cleanup_calibration():
    """Endpoint untuk membersihkan state kalibrasi setelah selesai"""
    global _calibration_state, _calibration_thread, _calibration_stop_event

    # Thread cleanup
    if _calibration_thread is not None:
        if _calibration_thread.is_alive():
            return jsonify({
                'success': False,
                'message': 'Kalibrasi masih berjalan. Tidak bisa membersihkan.'
            }), 400
        _calibration_thread = None

    # Clear stop event
    _calibration_stop_event.clear()

    # Reset state
    _calibration_state = {
        'running': False,
        'progress': 0,
        'current_tier': None,
        'current_operation': None,
        'current_iteration': 0,
        'total_iterations': 0,
        'message': '',
        'result': None,
        'error': None,
        'start_time': None,
        'end_time': None,
        'stop_flag': False
    }

    import gc
    gc.collect()  # Force garbage collection

    return jsonify({
        'success': True,
        'message': 'Kalibrasi berhasil dibersihkan dari memory.'
    })

@testing_bp.route('/stop_calibration', methods=['POST'])
def stop_calibration():
    """Endpoint untuk menghentikan kalibrasi yang sedang berjalan (thread-safe)"""
    global _calibration_state, _calibration_thread, _calibration_stop_event

    if not _calibration_state.get('running', False):
        return jsonify({
            'success': False,
            'message': 'Tidak ada kalibrasi yang sedang berjalan.'
        }), 400

    # Set stop event untuk menghentikan thread (thread-safe!)
    _calibration_stop_event.set()
    _calibration_state['stop_flag'] = True
    _calibration_state['message'] = '⏹️ Menghentikan kalibrasi...'

    # Tunggu thread selesai (max 10 detik)
    if _calibration_thread is not None and _calibration_thread.is_alive():
        _calibration_thread.join(timeout=10)
        
        # Cek apakah thread benar-benar berhenti
        if _calibration_thread.is_alive():
            return jsonify({
                'success': True,
                'message': 'Sinyal stop dikirim. Thread akan berhenti dalam beberapa detik.'
            })
    
    return jsonify({
        'success': True,
        'message': 'Kalibrasi berhasil dihentikan.'
    })
