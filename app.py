from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, Response, jsonify, make_response
from Crypto.PublicKey import RSA, ECC
from Crypto.Signature import pss, DSS
from Crypto.Hash import SHA256
import json, base64, secrets, os, time, io, math, csv, zipfile, random, string, tracemalloc, statistics, zlib, sqlite3
import socket
from urllib.parse import urlparse, urlunparse
import qrcode
from qrcode.constants import ERROR_CORRECT_Q, ERROR_CORRECT_M
import cv2
from pyzbar.pyzbar import decode
from datetime import datetime, timedelta, timezone
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from limits.storage import RedisStorage
from PIL import Image
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import RequestEntityTooLarge
import logging
from logging.handlers import RotatingFileHandler
from functools import wraps
import shutil
import tempfile
import threading
from collections import OrderedDict, defaultdict
import uuid
import os
os.environ['CSV_MAX_FIELD_SIZE'] = '10000000'  # 10MB

# Import testing blueprint
from routes.testing_routes import testing_bp, setup_limiter

# ==================== KONFIGURASI ====================
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD', 'change-this-password') # Segera ganti via Environment Variable
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2) # Sesi kadaluarsa dalam 2 jam
    SESSION_COOKIE_HTTPONLY = True # Mencegah pencurian cookie via XSS
    SESSION_COOKIE_SAMESITE = 'Lax' # Proteksi CSRF
    SESSION_COOKIE_SECURE = os.environ.get('REQUIRE_HTTPS', 'False').lower() == 'true' # Pastikan cookie hanya dikirim lewat HTTPS
    UPLOAD_FOLDER = 'static/uploads'
    QR_FOLDER = 'static/qr'
    QR_MASSAL_FOLDER = 'static/qr_massal'
    DATA_FOLDER = 'static/data'
    TASK_RESULTS_FOLDER = 'data/task_results'
    TASK_METADATA_FOLDER = 'data/task_metadata'
    QR_DOWNLOAD_FOLDER = 'data/downloads'
    VERIFY_PAYLOAD_FOLDER = 'data/verify_payloads'
    FAKE_QR_FOLDER = 'static/qr_fake'
    LOGS_FOLDER = 'logs'
    
    CSV_LOG_GENERATE = 'logs/log_generate.csv'
    CSV_LOG_VERIFIKASI = 'logs/log_verifikasi.csv'
    AUDIT_LOG = 'logs/audit_log.csv'
    NONCE_LOG = 'logs/used_nonces.txt'
    SECURITY_STATE_DB = 'logs/security_state.db'
    RSA_KEY_FILE = 'rsa_key.pem'
    ECDSA_KEY_FILE = 'ecdsa_key.pem'
    MODIFICATION_LOG = 'logs/modification_logs.json'
    BATCH_MODIFICATION_LOG = 'logs/batch_modification_logs.json'
    STATS_FILE = 'logs/qr_stats.json'  # File untuk menyimpan statistik
    
    # Rate limiting configuration (Diperlonggar untuk keperluan testing/scanner)
    RATELIMIT_DEFAULT = "1000 per hour"
    RATELIMIT_GENERATE = "60 per minute"
    RATELIMIT_TESTING_PROGRESS = "1000 per minute"  # Lebih longgar untuk progress
    RATELIMIT_DASHBOARD = "60 per minute"  # TAMBAHKAN: Lebih longgar untuk dashboard
    
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000/')  # Default ke localhost, akan dideteksi otomatis
    TRUST_PROXY_HEADERS = os.environ.get('TRUST_PROXY_HEADERS', 'False').lower() == 'true'
    VERIFY_PAYLOAD_RETENTION_DAYS = int(os.environ.get('VERIFY_PAYLOAD_RETENTION_DAYS', '30'))
    QR_PAYLOAD_MAX_AGE_SECONDS = int(os.environ.get('QR_PAYLOAD_MAX_AGE_SECONDS', str(7 * 24 * 3600)))
    QR_NONCE_BYTES = int(os.environ.get('QR_NONCE_BYTES', '8'))
    VERIFICATION_FEATURE_ENABLED = os.environ.get('VERIFICATION_FEATURE_ENABLED', 'False').lower() == 'true'
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'csv'}
    # Meningkatkan batas ukuran request untuk mencegah error 413 saat upload batch banyak file
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB (Mendukung upload batch file besar)
    # Werkzeug membatasi multipart ke 1000 part secara default; satu file upload = satu part.
    MAX_FORM_PARTS = int(os.environ.get('MAX_FORM_PARTS', '20000'))  # 0 = tidak terbatas
    MAX_FORM_MEMORY_SIZE = int(os.environ['MAX_FORM_MEMORY_SIZE']) if os.environ.get('MAX_FORM_MEMORY_SIZE') else None
    MAX_FILES_MASSAL = 0  # 0 = tidak terbatas
    MAX_TOTAL_SIZE_MASSAL = 0  # 0 = tidak terbatas

# ==================== INISIALISASI APLIKASI ====================
app = Flask(__name__)
app.config.from_object(Config)

configured_max_form_parts = app.config.get('MAX_FORM_PARTS')
app.request_class.max_form_parts = None if configured_max_form_parts == 0 else configured_max_form_parts
app.request_class.max_form_memory_size = app.config.get('MAX_FORM_MEMORY_SIZE')

if app.config['TRUST_PROXY_HEADERS']:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Register blueprint testing
app.register_blueprint(testing_bp, url_prefix='/testing')


def is_verification_feature_enabled():
    return app.config.get('VERIFICATION_FEATURE_ENABLED', False)


def verification_disabled_view(message=None, status_code=200):
    return render_template(
        'verification_disabled.html',
        message=message or 'Fitur verifikasi sedang dinonaktifkan sementara sampai diaktifkan kembali.',
        verification_enabled=False
    ), status_code


# Setup logging
os.makedirs(app.config['LOGS_FOLDER'], exist_ok=True)
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1024*1024, backupCount=10)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Aplikasi QR Code Security dimulai')

# Setup rate limiting dengan exception untuk testing progress
try:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[app.config['RATELIMIT_DEFAULT']],
        storage_uri=app.config['REDIS_URL'],
        strategy="fixed-window"
    )
    limiter.init_app(app)
except Exception as e:
    app.logger.warning(f"Redis tidak tersedia, menggunakan memory storage: {e}")
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[app.config['RATELIMIT_DEFAULT']],
        storage_uri="memory://"
    )
    limiter.init_app(app)

# Setup limiter khusus untuk testing endpoints
setup_limiter(app)

# Tambahkan request filter untuk mengecualikan endpoint progress testing
@limiter.request_filter
def exempt_testing_progress():
    """Filter untuk mengecualikan endpoint progress testing dari rate limiting"""
    from flask import request

    # Cek jika request adalah ke endpoint progress testing
    if request.path and '/testing/progress/' in request.path:
        return True

    # Cek jika request adalah ke endpoint status testing
    if request.path and '/testing/status/' in request.path:
        return True

    # TAMBAHKAN: Pengecualian untuk calibration progress (dipanggil setiap 1 detik)
    if request.path and '/testing/calibration_progress' in request.path:
        return True

    # TAMBAHKAN: Pengecualian untuk stop calibration
    if request.path and '/testing/stop_calibration' in request.path:
        return True

    # TAMBAHKAN: Pengecualian untuk cleanup calibration
    if request.path and '/testing/cleanup_calibration' in request.path:
        return True

    # Pengecualian untuk beban Real HTTP Stress Test yang ditembakkan dari server
    # ini sendiri. Digate GANDA: harus User-Agent penembak DAN berasal dari
    # localhost, sehingga klien eksternal tidak dapat memalsukan header ini untuk
    # menembus rate limit produksi (request publik selalu lewat Nginx sehingga
    # remote_addr-nya bukan 127.0.0.1).
    if (request.headers.get('User-Agent', '') == 'QRRealHTTPStress/1.0'
            and request.remote_addr in ('127.0.0.1', '::1')):
        return True

    # TAMBAHKAN: Pengecualian untuk dashboard
    if request.path and '/dashboard' in request.path:
        return True

    # TAMBAHKAN: Pengecualian untuk active_tests polling (dipanggil setiap 10 detik)
    if request.path and '/testing/active_tests' in request.path:
        return True

    # Pengecualian untuk dashboard dan route statistik
    dashboard_routes = [
        '/dashboard',
        '/api/auto_recalculate_stats',
        '/recalculate_stats',
        '/reset_stats',
        '/reset_nonce_log_manual'
    ]

    for route in dashboard_routes:
        if request.path and route in request.path:
            return True

    # TAMBAHKAN: Pengecualian untuk halaman utama
    if request.path == '/' or request.path == '/index':
        return True

    return False

# Buat folder yang diperlukan
for folder in [app.config['UPLOAD_FOLDER'], app.config['QR_FOLDER'], 
               app.config['QR_MASSAL_FOLDER'], app.config['DATA_FOLDER'],
               app.config['TASK_RESULTS_FOLDER'],
               app.config['TASK_METADATA_FOLDER'],
               app.config['QR_DOWNLOAD_FOLDER'],
               app.config['VERIFY_PAYLOAD_FOLDER'],
               app.config['FAKE_QR_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# ==================== FUNGSI UTILITAS ====================
def sanitize_filename(filename):
    filename = secure_filename(filename)
    return os.path.basename(filename)

def sanitize_for_csv(value):
    """Amankan nilai untuk format CSV manual yang sudah dibungkus tanda kutip."""
    if value is None:
        return ''
    return str(value).replace('"', '""').replace('\r', ' ').replace('\n', ' ').strip()

def allowed_file(filename, allowed_extensions=None):
    if allowed_extensions is None:
        allowed_extensions = app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def count_files_fast(directory, extensions):
    """Hitung file dengan cepat menggunakan os.scandir"""
    if not os.path.exists(directory):
        return 0
    count = 0
    if isinstance(extensions, str):
        extensions = (extensions,)
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.lower().endswith(extensions):
                    count += 1
    except Exception:
        pass
    return count

def get_qr_archive_sources():
    """Daftar sumber QR yang akan dimasukkan ke arsip download."""
    return [
        ('qr_tunggal', app.config['QR_FOLDER']),
        ('qr_massal', app.config['QR_MASSAL_FOLDER']),
        ('qr_modifikasi', app.config['FAKE_QR_FOLDER'])
    ]

def iter_qr_png_files():
    """Yield tuple (kategori, nama_file, path_file) untuk semua QR PNG yang ada."""
    for category, directory in get_qr_archive_sources():
        if not os.path.isdir(directory):
            continue

        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.lower().endswith('.png'):
                        yield category, entry.name, entry.path
        except Exception as e:
            app.logger.warning(f'Gagal membaca folder QR {directory}: {e}')

def get_qr_file_counts():
    counts = {
        'qr_tunggal': count_files_fast(app.config['QR_FOLDER'], '.png'),
        'qr_massal': count_files_fast(app.config['QR_MASSAL_FOLDER'], '.png'),
        'qr_modifikasi': count_files_fast(app.config['FAKE_QR_FOLDER'], '.png')
    }
    counts['total'] = sum(counts.values())
    return counts

LOG_QR_PREVIEW_HEADER = 'Preview QR'

def build_qr_data_filename_index():
    """Index nama file data QR berdasarkan ID yang tersimpan di nama file."""
    index = defaultdict(list)
    data_dir = app.config['DATA_FOLDER']

    if not os.path.isdir(data_dir):
        return index

    try:
        with os.scandir(data_dir) as entries:
            for entry in entries:
                if not entry.is_file() or not entry.name.endswith('.json'):
                    continue

                stem = entry.name[:-5]
                if not stem.startswith('qr_') or '_' not in stem[3:]:
                    continue

                userid_key = stem[3:].rsplit('_', 1)[0]
                if userid_key:
                    index[userid_key].append(entry.name)
    except Exception as e:
        app.logger.warning(f'Gagal membuat index preview QR: {e}')

    return index

def coerce_log_time_to_epoch(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    try:
        if isinstance(value, pd.Timestamp):
            dt = value.to_pydatetime()
        elif isinstance(value, datetime):
            dt = value
        else:
            dt = pd.to_datetime(value, errors='coerce')
            if pd.isna(dt):
                return None
            dt = dt.to_pydatetime()

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None

def get_qr_static_candidates_for_source(source):
    preferred = []
    if source == 'Tunggal':
        preferred.append(('qr', app.config['QR_FOLDER']))
    elif source == 'Massal':
        preferred.append(('qr_massal', app.config['QR_MASSAL_FOLDER']))

    for candidate in [
        ('qr', app.config['QR_FOLDER']),
        ('qr_massal', app.config['QR_MASSAL_FOLDER'])
    ]:
        if candidate not in preferred:
            preferred.append(candidate)

    return preferred

def resolve_qr_preview_for_log_row(row, data_index):
    """Cari file QR PNG yang paling cocok untuk satu baris log generate."""
    empty_preview = {
        'available': False,
        'message': 'File QR tidak ditemukan'
    }

    userid = str(row.get('ID', '') or '').strip()
    if not userid:
        return empty_preview

    lookup_keys = []
    for key in [secure_filename(userid), userid]:
        if key and key not in lookup_keys:
            lookup_keys.append(key)

    data_filenames = []
    seen = set()
    for key in lookup_keys:
        for filename in data_index.get(key, []):
            if filename not in seen:
                data_filenames.append(filename)
                seen.add(filename)

    if not data_filenames:
        return empty_preview

    source = str(row.get('Sumber', '') or '').strip()
    name = str(row.get('Nama', '') or '').strip()
    target_epoch = coerce_log_time_to_epoch(row.get('Waktu'))
    best_candidate = None

    for data_filename in data_filenames:
        data_path = os.path.join(app.config['DATA_FOLDER'], data_filename)
        qr_filename = f"{data_filename[:-5]}.png"

        qr_path = None
        static_folder = None
        source_penalty = 1
        for candidate_static_folder, candidate_dir in get_qr_static_candidates_for_source(source):
            candidate_path = os.path.join(candidate_dir, qr_filename)
            if os.path.exists(candidate_path):
                qr_path = candidate_path
                static_folder = candidate_static_folder
                if (source == 'Tunggal' and static_folder == 'qr') or (source == 'Massal' and static_folder == 'qr_massal'):
                    source_penalty = 0
                break

        if not qr_path or not static_folder:
            continue

        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                qr_data = json.load(f)
        except Exception:
            qr_data = {}

        id_penalty = 0 if str(qr_data.get('id', '')).strip() == userid else 1
        name_penalty = 0 if not name or str(qr_data.get('nama', '')).strip() == name else 1

        try:
            file_epoch = os.path.getmtime(qr_path)
        except OSError:
            file_epoch = 0

        time_score = abs(file_epoch - target_epoch) if target_epoch else -file_epoch
        score = (id_penalty, name_penalty, source_penalty, time_score)

        if best_candidate is None or score < best_candidate['score']:
            best_candidate = {
                'score': score,
                'available': True,
                'url': url_for('static', filename=f'{static_folder}/{qr_filename}'),
                'filename': qr_filename,
                'folder': static_folder,
                'alt': f"QR Code {name or userid}"
            }

    if not best_candidate:
        return empty_preview

    best_candidate.pop('score', None)
    return best_candidate

def attach_qr_previews_to_log_rows(rows):
    if not rows:
        return rows

    data_index = build_qr_data_filename_index()
    for row in rows:
        row[LOG_QR_PREVIEW_HEADER] = resolve_qr_preview_for_log_row(row, data_index)
    return rows

def cleanup_old_qr_downloads(max_age_seconds=6 * 3600):
    download_dir = app.config.get('QR_DOWNLOAD_FOLDER')
    if not download_dir or not os.path.isdir(download_dir):
        return

    now = time.time()
    try:
        with os.scandir(download_dir) as entries:
            for entry in entries:
                if not entry.is_file() or not entry.name.endswith('.zip'):
                    continue

                try:
                    if now - entry.stat().st_mtime > max_age_seconds:
                        os.remove(entry.path)
                except OSError:
                    pass
    except Exception as e:
        app.logger.warning(f'Gagal membersihkan ZIP QR lama: {e}')

def get_local_ip():
    """Mendapatkan IP address lokal komputer"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # IP tidak perlu bisa dihubungi, hanya untuk routing
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def normalize_base_url(base_url):
    """Normalisasi base URL agar aman digabung dengan path verifikasi."""
    if not base_url:
        return ''
    base_url = base_url.strip()
    if not base_url.endswith('/'):
        base_url += '/'
    return base_url

def get_public_base_url():
    """Ambil base URL publik untuk QR, dengan prioritas konfigurasi production."""
    configured_base_url = normalize_base_url(app.config.get('BASE_URL', ''))
    if configured_base_url and 'localhost' not in configured_base_url and '127.0.0.1' not in configured_base_url:
        return configured_base_url

    try:
        base_url = request.url_root
    except RuntimeError:
        base_url = configured_base_url or f'http://{get_local_ip()}:5000/'

    if 'localhost' in base_url or '127.0.0.1' in base_url:
        try:
            local_ip = get_local_ip()
            if local_ip != '127.0.0.1':
                parsed = urlparse(base_url)
                port = parsed.port
                netloc = f"{local_ip}:{port}" if port else local_ip
                base_url = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        except Exception as e:
            app.logger.warning(f"Gagal mengganti localhost dengan IP: {e}")

    return normalize_base_url(base_url)

def get_upload_limit_message():
    max_content_mb = int(app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024))
    max_form_parts = app.config.get('MAX_FORM_PARTS')
    if max_form_parts == 0:
        part_limit_text = 'jumlah file/field tidak dibatasi aplikasi'
    else:
        part_limit_text = f'maksimal {max_form_parts} file/field per upload'

    return (
        f"Request upload terlalu besar atau jumlah file terlalu banyak. "
        f"Batas saat ini: total upload {max_content_mb}MB dan {part_limit_text}. "
        "Kurangi jumlah file, bagi menjadi beberapa batch, atau sesuaikan konfigurasi server."
    )

def validate_single_upload(file):
    """Validasi upload file untuk verifikasi tunggal"""
    try:
        if file.filename == '':
            return False, "File tidak dipilih"
            
        current_pos = file.tell()
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(current_pos)
        
        if file_size > 10 * 1024 * 1024:
            return False, f"File terlalu besar (maksimal 10MB per file)"
        
        return True, "Validasi berhasil"
        
    except Exception as e:
        app.logger.error(f"Error dalam validasi upload tunggal: {e}")
        return False, f"Error validasi: {str(e)}"

def validate_massal_upload(uploaded_files):
    """Validasi upload file untuk verifikasi massal - TIDAK ADA BATASAN"""
    try:
        total_size = 0
        file_count = 0
        
        for file in uploaded_files:
            if file.filename == '':
                continue
                
            current_pos = file.tell()
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(current_pos)
            
            # Hanya validasi per file (maksimal 10MB per file)
            if file_size > 10 * 1024 * 1024:
                return False, f"File {file.filename} terlalu besar (maksimal 10MB per file)"
        
            total_size += file_size
            # Validasi total ukuran (maksimal 10GB)
            if total_size > 10 * 1024 * 1024 * 1024:
                return False, f"Total ukuran file melebihi 10GB"
        
        return True, "Validasi berhasil"
        
    except Exception as e:
        app.logger.error(f"Error dalam validasi upload: {e}")
        return False, f"Error validasi: {str(e)}"

# ==================== FUNGSI UTILITAS UNTUK URL VERIFIKASI (DIOPTIMALKAN UNTUK KAMERA HP) ====================
def encode_payload_for_verify_url(payload_data):
    payload_json = json.dumps(payload_data, separators=(',', ':'))
    compressed_data = zlib.compress(payload_json.encode('utf-8'), level=9)
    return base64.urlsafe_b64encode(compressed_data).decode('utf-8').rstrip('=')

def decode_payload_from_verify_url(encoded_data):
    if '?' in encoded_data:
        encoded_data = encoded_data.split('?')[0]

    padding = 4 - len(encoded_data) % 4
    if padding != 4:
        encoded_data += '=' * padding

    try:
        decoded_bytes = base64.urlsafe_b64decode(encoded_data)
        try:
            decompressed_data = zlib.decompress(decoded_bytes).decode('utf-8')
            return json.loads(decompressed_data)
        except zlib.error:
            return json.loads(decoded_bytes.decode('utf-8'))
    except Exception:
        try:
            decoded_data = base64.b64decode(encoded_data).decode('utf-8')
            return json.loads(decoded_data)
        except Exception:
            return json.loads(encoded_data)

def get_verify_payload_path(token):
    safe_token = secure_filename(str(token or ''))
    if not safe_token:
        return None

    shard = safe_token[:2] if len(safe_token) >= 2 else 'xx'
    return os.path.join(app.config['VERIFY_PAYLOAD_FOLDER'], shard, f'{safe_token}.json')

def save_verify_payload(payload_data):
    token = secrets.token_urlsafe(16).rstrip('=')

    for _ in range(5):
        payload_path = get_verify_payload_path(token)
        if payload_path and not os.path.exists(payload_path):
            break
        token = secrets.token_urlsafe(16).rstrip('=')
    else:
        raise RuntimeError('Gagal membuat token verifikasi unik')

    os.makedirs(os.path.dirname(payload_path), exist_ok=True)
    payload_record = {
        'token': token,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'payload': payload_data
    }

    tmp_path = f'{payload_path}.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(payload_record, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp_path, payload_path)
    return token

def load_verify_payload(token):
    payload_path = get_verify_payload_path(token)
    if not payload_path or not os.path.exists(payload_path):
        return None

    try:
        with open(payload_path, 'r', encoding='utf-8') as f:
            payload_record = json.load(f)
        return payload_record.get('payload')
    except Exception as e:
        app.logger.warning(f'Gagal memuat payload short verify {token}: {e}')
        return None

def generate_verification_url(payload_data, base_url_override=None):
    """Membuat URL verifikasi untuk QR Code yang dapat dibaca kamera HP"""
    try:
        if base_url_override:
            base_url = normalize_base_url(base_url_override)
        else:
            base_url = get_public_base_url()

        token = save_verify_payload(payload_data)
        verification_url = f"{base_url}v/{token}"
        return verification_url, token
    except Exception as e:
        app.logger.error(f"Error generating short verification URL: {e}")
        try:
            encoded_data = encode_payload_for_verify_url(payload_data)
            base_url = normalize_base_url(base_url_override) if base_url_override else get_public_base_url()
            return f"{base_url}verify/{encoded_data}", encoded_data
        except Exception as fallback_error:
            app.logger.error(f"Error generating fallback verification URL: {fallback_error}")
            return json.dumps(payload_data), None

def create_qr_with_url(payload_data, save_path=None, base_url=None):
    """Membuat QR Code dengan URL verifikasi yang dioptimalkan untuk kamera HP"""
    try:
        # Buat URL verifikasi yang lebih pendek
        qr_url, encoded_data = generate_verification_url(payload_data, base_url_override=base_url)
        
        # OPTIMASI UKURAN QR CODE:
        # 1. Kurangi box_size dari 4 menjadi 2 (50% lebih kecil)
        # 2. Kurangi error_correction dari Q (25%) ke M (15%) untuk mengurangi redundancy
        # 3. Kurangi border dari 2 menjadi 1
        
        qr = qrcode.QRCode(
            version=None,  # Otomatis pilih versi
            error_correction=ERROR_CORRECT_Q,  # Sesuai Jurnal: 25% (Level Q)
            box_size=2,  # Ukuran box dikurangi (semula 4)
            border=1  # Border dikurangi (semula 2)
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # Buat gambar dengan kontras tinggi untuk kamera
        img = qr.make_image(fill_color="black", back_color="white", contrast=1.3)
        
        # Simpan jika path diberikan
        if save_path:
            # Kompres gambar untuk mengurangi ukuran file
            img.save(save_path, optimize=True, quality=85)
        return img, qr_url, encoded_data
    except Exception as e:
        app.logger.error(f"Error creating QR with URL: {e}")
        # Fallback: buat QR dengan data biasa (untuk kompatibilitas)
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=2,
            border=1
        )
        qr.add_data(json.dumps(payload_data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        if save_path:
            img.save(save_path, optimize=True, quality=85)
        return img, json.dumps(payload_data), None

def extract_payload_from_qr_string(qr_string):
    """Fungsi utilitas untuk ekstrak dan dekompresi payload dari QR string/URL (diperlukan untuk massal async)"""
    try:
        if qr_string.startswith('http'):
            import urllib.parse
            parsed_url = urllib.parse.urlparse(qr_string)
            path_parts = parsed_url.path.split('/')
            if len(path_parts) >= 2 and path_parts[-2] == 'v':
                return load_verify_payload(path_parts[-1])
            if len(path_parts) >= 2 and path_parts[-2] == 'verify':
                return decode_payload_from_verify_url(path_parts[-1])
        try:
            return json.loads(qr_string)
        except json.JSONDecodeError:
            return decode_payload_from_verify_url(qr_string)
    except Exception as e:
        app.logger.error(f"Error extract_payload_from_qr_string: {e}")
        return None

def resolve_scan_verification_target(qr_string):
    """Ubah hasil scan QR menjadi URL verifikasi internal yang aman untuk dibuka."""
    scan_text = (qr_string or '').strip()
    if not scan_text:
        raise ValueError("Data QR kosong")

    base_url = get_public_base_url()
    public_base = urlparse(base_url)
    request_base = urlparse(request.url_root)
    allowed_hosts = {
        host for host in [
            public_base.hostname,
            request_base.hostname,
            app.config.get('SERVER_NAME')
        ] if host
    }

    def build_public_url(parsed):
        query = f"?{parsed.query}" if parsed.query else ""
        fragment = f"#{parsed.fragment}" if parsed.fragment else ""
        return f"{base_url.rstrip('/')}{parsed.path}{query}{fragment}"

    def is_verify_path(path):
        return path.startswith('/v/') or path.startswith('/verify/')

    if scan_text.startswith('/'):
        parsed = urlparse(scan_text)
        if is_verify_path(parsed.path):
            return build_public_url(parsed)
        raise ValueError("Path QR bukan endpoint verifikasi sistem")

    if scan_text.lower().startswith(('http://', 'https://')):
        parsed = urlparse(scan_text)
        if parsed.hostname in allowed_hosts and is_verify_path(parsed.path):
            return build_public_url(parsed)
        raise ValueError("URL QR bukan endpoint verifikasi sistem")

    payload = None
    try:
        payload = json.loads(scan_text)
    except json.JSONDecodeError:
        try:
            payload = decode_payload_from_verify_url(scan_text)
        except Exception:
            payload = None

    if payload and isinstance(payload, dict):
        encoded_data = encode_payload_for_verify_url(payload)
        return f"{base_url}verify/{encoded_data}"

    raise ValueError("Format QR tidak dikenali")

QR_INDEX_BACKFILL_FLAG = 'qr_record_index_backfilled_v1'
_qr_index_state = {'authoritative': False, 'checked_at': 0.0}
QR_INDEX_RECHECK_SECONDS = 30


def qr_record_index_ready():
    """Index hanya otoritatif setelah seluruh direktori data selesai di-backfill.

    Sebelum itu pencarian tetap memakai pemindaian direktori, sebab index yang
    belum lengkap dapat melaporkan record asli sebagai tidak ada — yang akan
    mengubah hasil klasifikasi verifikasi.
    """
    if _qr_index_state['authoritative']:
        return True
    if time.time() - _qr_index_state['checked_at'] < QR_INDEX_RECHECK_SECONDS:
        return False
    _qr_index_state['checked_at'] = time.time()

    if not ensure_security_state_ready():
        return False
    try:
        with security_state_lock:
            conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=10)
            try:
                row = conn.execute(
                    "SELECT value FROM security_metadata WHERE key = ?",
                    (QR_INDEX_BACKFILL_FLAG,)
                ).fetchone()
            finally:
                conn.close()
        _qr_index_state['authoritative'] = row is not None
    except Exception as e:
        app.logger.warning(f'Gagal memeriksa status index record QR: {e}')
    return _qr_index_state['authoritative']


def index_qr_record(filename, data):
    """Daftarkan satu record QR ke index pencarian."""
    if not filename or not ensure_security_state_ready():
        return False

    qr_id = str(data.get('id', '')).strip() if isinstance(data, dict) else ''
    nonce = str(data.get('nonce', '')).strip() if isinstance(data, dict) else ''
    now = datetime.now(timezone.utc).isoformat()

    try:
        with security_state_lock:
            conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=10)
            try:
                conn.execute(
                    """
                    INSERT INTO qr_record_index (filename, qr_id, nonce, indexed_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(filename) DO UPDATE SET
                        qr_id = excluded.qr_id,
                        nonce = excluded.nonce,
                        indexed_at = excluded.indexed_at
                    """,
                    (filename, qr_id, nonce, now)
                )
                conn.commit()
            finally:
                conn.close()
        return True
    except Exception as e:
        app.logger.warning(f'Gagal mengindeks record QR {filename}: {e}')
        return False


def save_qr_record(data_path, data):
    """Tulis record QR ke disk sekaligus daftarkan ke index pencarian."""
    with open(data_path, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=2)
    index_qr_record(os.path.basename(data_path), data)


def reset_qr_record_index():
    """Kosongkan index dan cabut status otoritatifnya (dipakai saat cleanup total)."""
    if not ensure_security_state_ready():
        return False
    try:
        with security_state_lock:
            conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=20)
            try:
                conn.execute("DELETE FROM qr_record_index")
                conn.execute(
                    "DELETE FROM security_metadata WHERE key = ?",
                    (QR_INDEX_BACKFILL_FLAG,)
                )
                conn.commit()
            finally:
                conn.close()
        _qr_index_state['authoritative'] = False
        _qr_index_state['checked_at'] = 0.0
        return True
    except Exception as e:
        app.logger.warning(f'Gagal mengosongkan index record QR: {e}')
        return False


def lookup_qr_filenames_by_prefixes(prefixes):
    """Padanan `os.listdir` + filter awalan, lewat range scan pada primary key.

    Mengembalikan None bila index tidak dapat dipakai, sehingga pemanggil tahu
    harus jatuh kembali ke pemindaian direktori.
    """
    if not prefixes or not ensure_security_state_ready():
        return None

    try:
        hasil = set()
        with security_state_lock:
            conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=10)
            try:
                for prefix in prefixes:
                    if not prefix:
                        continue
                    batas_atas = prefix[:-1] + chr(ord(prefix[-1]) + 1)
                    rows = conn.execute(
                        "SELECT filename FROM qr_record_index WHERE filename >= ? AND filename < ?",
                        (prefix, batas_atas)
                    ).fetchall()
                    hasil.update(row[0] for row in rows if row[0].endswith('.json'))
            finally:
                conn.close()
        return sorted(hasil)
    except Exception as e:
        app.logger.warning(f'Gagal mencari record QR lewat index: {e}')
        return None


def lookup_qr_filename_by_nonce(nonce):
    if not nonce or not ensure_security_state_ready():
        return None
    try:
        with security_state_lock:
            conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=10)
            try:
                row = conn.execute(
                    "SELECT filename FROM qr_record_index WHERE nonce = ? ORDER BY filename LIMIT 1",
                    (nonce,)
                ).fetchone()
            finally:
                conn.close()
        return row[0] if row else None
    except Exception as e:
        app.logger.warning(f'Gagal mencari record QR via nonce di index: {e}')
        return None


def backfill_qr_record_index(batch_size=2000, progress_callback=None):
    """Isi index dari seluruh isi DATA_FOLDER, lalu tandai index sebagai otoritatif."""
    if not ensure_security_state_ready():
        raise RuntimeError('Security state DB tidak siap; index tidak dapat dibangun.')

    data_dir = app.config['DATA_FOLDER']
    now = datetime.now(timezone.utc).isoformat()
    total = 0
    gagal = 0
    batch = []

    def flush(rows):
        if not rows:
            return
        with security_state_lock:
            conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=30)
            try:
                conn.executemany(
                    """
                    INSERT INTO qr_record_index (filename, qr_id, nonce, indexed_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(filename) DO UPDATE SET
                        qr_id = excluded.qr_id,
                        nonce = excluded.nonce,
                        indexed_at = excluded.indexed_at
                    """,
                    rows
                )
                conn.commit()
            finally:
                conn.close()

    with os.scandir(data_dir) as entries:
        for entry in entries:
            if not entry.is_file() or not entry.name.endswith('.json'):
                continue
            try:
                with open(entry.path, 'r', encoding='utf-8') as f:
                    record = json.load(f)
            except Exception:
                record = None

            if isinstance(record, dict):
                qr_id = str(record.get('id', '')).strip()
                nonce = str(record.get('nonce', '')).strip()
            else:
                # Berkas rusak/kosong tetap didaftarkan tanpa isi. Pada pemindaian
                # direktori berkas seperti ini ikut masuk daftar kandidat dan baru
                # gagal saat dibuka; menghilangkannya dari index akan mengubah
                # klasifikasi dari "Data Palsu" menjadi "Data Tidak Ditemukan".
                qr_id = ''
                nonce = ''
                gagal += 1

            batch.append((entry.name, qr_id, nonce, now))
            total += 1

            if len(batch) >= batch_size:
                flush(batch)
                batch = []
                if progress_callback:
                    progress_callback(total, gagal)

    flush(batch)

    with security_state_lock:
        conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=30)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO security_metadata (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (QR_INDEX_BACKFILL_FLAG, str(total), now)
            )
            conn.commit()
        finally:
            conn.close()

    _qr_index_state['authoritative'] = True
    _qr_index_state['checked_at'] = time.time()
    app.logger.info(
        f'Backfill index record QR selesai: {total} berkas terindeks, {gagal} rusak/kosong'
    )
    return total, gagal


def find_original_qr_data(data):
    """Cari record JSON asli yang benar untuk payload QR.

    Satu ID bisa punya beberapa QR valid dengan nonce/timestamp berbeda, jadi
    pencarian harus memilih exact-match data terlebih dulu, bukan file pertama.
    """
    userid = str(data.get('id', '') if isinstance(data, dict) else '').strip()
    nonce = str(data.get('nonce', '') if isinstance(data, dict) else '').strip()
    if not userid and not nonce:
        return None, [], False

    safe_userid = secure_filename(userid)
    prefixes = {f'qr_{userid}_'}
    if safe_userid:
        prefixes.add(f'qr_{safe_userid}_')

    filenames = lookup_qr_filenames_by_prefixes(prefixes) if qr_record_index_ready() else None
    if filenames is None:
        try:
            filenames = sorted(
                f for f in os.listdir(app.config['DATA_FOLDER'])
                if f.endswith('.json') and any(f.startswith(prefix) for prefix in prefixes)
            )
        except Exception as e:
            app.logger.warning(f'Gagal membaca folder data QR: {e}')
            return None, [], False

    candidates = []
    for filename in filenames:
        path = os.path.join(app.config['DATA_FOLDER'], filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                candidate = json.load(f)
        except Exception as e:
            app.logger.warning(f'Gagal membaca data QR {filename}: {e}')
            continue

        # Record selalu berupa objek JSON. Berkas bertipe lain (array, string)
        # lolos json.load tetapi membuat similarity_score menabrak .keys().
        if not isinstance(candidate, dict):
            app.logger.warning(f'Struktur data QR tidak dikenali, dilewati: {filename}')
            continue

        if candidate == data:
            return candidate, filenames, True
        candidates.append((filename, candidate))

    if not candidates:
        nonce_candidate = find_original_qr_data_by_nonce(data, nonce)
        if nonce_candidate:
            filename, candidate = nonce_candidate
            return candidate, [filename], candidate == data
        return None, filenames, False

    def similarity_score(candidate):
        keys = set(candidate.keys()) | set(data.keys())
        return sum(1 for key in keys if candidate.get(key) == data.get(key))

    _, closest_candidate = max(candidates, key=lambda item: (similarity_score(item[1]), item[0]))
    return closest_candidate, filenames, False

def find_original_qr_data_by_nonce(data, nonce):
    """Fallback saat ID sudah dimodifikasi tetapi nonce masih mengarah ke QR asli."""
    if not nonce:
        return None

    if qr_record_index_ready():
        filename = lookup_qr_filename_by_nonce(nonce)
        if not filename:
            return None
        path = os.path.join(app.config['DATA_FOLDER'], filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                candidate = json.load(f)
        except Exception:
            return None
        if isinstance(candidate, dict) and str(candidate.get('nonce', '')).strip() == nonce:
            return filename, candidate
        return None

    try:
        filenames = sorted(
            f for f in os.listdir(app.config['DATA_FOLDER'])
            if f.endswith('.json')
        )
    except Exception as e:
        app.logger.warning(f'Gagal membaca folder data QR untuk pencarian nonce: {e}')
        return None

    for filename in filenames:
        path = os.path.join(app.config['DATA_FOLDER'], filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                candidate = json.load(f)
        except Exception:
            continue

        if isinstance(candidate, dict) and str(candidate.get('nonce', '')).strip() == nonce:
            return filename, candidate

    return None

def get_qr_nonce_bytes():
    try:
        return max(4, int(app.config.get('QR_NONCE_BYTES', 8)))
    except (TypeError, ValueError):
        return 8

def generate_qr_nonce(existing_nonces=None):
    existing_nonces = existing_nonces if existing_nonces is not None else set()
    for _ in range(100):
        nonce = secrets.token_hex(get_qr_nonce_bytes())
        if nonce not in existing_nonces:
            return nonce
    return secrets.token_hex(max(get_qr_nonce_bytes(), 16))

def is_valid_nonce_format(nonce):
    return (
        isinstance(nonce, str)
        and len(nonce) >= 8
        and len(nonce) % 2 == 0
        and all(c in '0123456789abcdef' for c in nonce.lower())
    )

def build_replay_store_key(data):
    nonce = str(data.get('nonce', '') if isinstance(data, dict) else '').strip()
    serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    payload_hash = SHA256.new(serialized.encode('utf-8')).hexdigest()
    return f"{nonce}:{payload_hash}"

def is_payload_expired(data, max_age_seconds=None):
    try:
        if max_age_seconds is None:
            max_age_seconds = int(app.config.get('QR_PAYLOAD_MAX_AGE_SECONDS', 7 * 24 * 3600))
        if max_age_seconds <= 0:
            return False

        data_timestamp = datetime.fromisoformat(str(data.get('timestamp', '')).replace('Z', '+00:00'))
        current_time = datetime.now(timezone.utc)
        return (current_time - data_timestamp).total_seconds() > max_age_seconds
    except Exception:
        app.logger.warning("Gagal memproses timestamp data")
        return True

def build_changed_fields(original_data, data):
    changed_fields = {}
    if not isinstance(original_data, dict) or not isinstance(data, dict):
        return changed_fields

    for key in original_data:
        if key in data and data[key] != original_data[key]:
            changed_fields[key] = {
                'asli': original_data[key],
                'sekarang': data[key]
            }
        elif key not in data:
            changed_fields[f"removed_{key}"] = {
                'asli': original_data[key],
                'sekarang': None
            }

    for key in data:
        if key not in original_data:
            changed_fields[f"extra_{key}"] = {
                'asli': None,
                'sekarang': data[key]
            }

    return changed_fields

def summarize_changed_fields(changed_fields, signature_valid):
    details = []
    for key in list(changed_fields.keys())[:2]:
        clean_key = key.replace('removed_', '').replace('extra_', '')
        if key.startswith('removed_'):
            details.append(f"Field '{clean_key}' dihapus")
        elif key.startswith('extra_'):
            details.append(f"Field '{clean_key}' ditambahkan")
        else:
            details.append(f"Field '{clean_key}' diubah")

    if not signature_valid:
        details.append("signature tidak cocok")

    return '; '.join(details[:3])

def signature_failure_message(sig_error):
    return f"⚠️ {sig_error}" if sig_error else "⚠️ Signature Invalid"

def classify_qr_verification(data, signature_valid, sig_error="", original_data_override=None):
    """Klasifikasi hasil verifikasi tanpa false positive replay untuk data palsu.

    Replay hanya sah untuk payload asli yang signature-nya valid. Payload yang
    sudah berubah harus dilaporkan sebagai data palsu/dimodifikasi walaupun nonce
    sama dengan QR asli.
    """
    if original_data_override is not None:
        original_data = original_data_override
        data_files = ["cached"]
        exact_original_match = original_data == data
    else:
        original_data, data_files, exact_original_match = find_original_qr_data(data)
    changed_fields = {}
    message = ""
    valid = False
    is_replay = False
    is_expired = False

    if data_files:
        if exact_original_match:
            nonce = data.get('nonce', '')

            if not is_valid_nonce_format(nonce):
                message = "⚠️ Nonce tidak valid"
            elif not signature_valid or sig_error:
                message = signature_failure_message(sig_error)
            else:
                replay_store_key = build_replay_store_key(data)
                legacy_usage_count = get_nonce_usage_count_db(nonce) or 0
                usage_count, verification_count = record_nonce_usage_and_get_count(replay_store_key)
                verification_count = max(verification_count, legacy_usage_count + 1)
                is_expired = is_payload_expired(data)
                if usage_count >= 1 or legacy_usage_count >= 1:
                    message = f"🔁 Replay Attack Terdeteksi ({verification_count} kali verifikasi)"
                    is_replay = True
                elif is_expired:
                    message = "⏰ QR Code Kedaluwarsa"
                else:
                    message = "✅ Valid dan Authentik"
                    valid = True
        else:
            changed_fields = build_changed_fields(original_data, data)
            details = summarize_changed_fields(changed_fields, signature_valid)
            if changed_fields and details:
                message = f"❌ Data Telah Dimodifikasi ({details})"
            elif not signature_valid or sig_error:
                message = "❌ Data Palsu (signature tidak cocok)"
            else:
                message = "❌ Data Palsu"
    else:
        if not signature_valid or sig_error:
            message = "❌ Data Palsu (signature tidak cocok)"
        else:
            message = "⛔ Data Tidak Ditemukan di Database"

    return {
        "original_data": original_data,
        "data_files": data_files,
        "exact_original_match": exact_original_match,
        "changed_fields": changed_fields,
        "message": message,
        "valid": valid,
        "is_replay": is_replay,
        "is_expired": is_expired
    }


# Pelaporan hasil verifikasi memakai dua sumbu yang berdiri sendiri:
#
#   1. Keabsahan signature — fakta kriptografis, sah atau tidak.
#   2. Keberlakuan QR      — keputusan kebijakan: berlaku, atau tidak berlaku
#                            beserta alasannya.
#
# Keduanya tidak boleh diruntuhkan menjadi satu angka. QR kedaluwarsa dan QR
# replay sama-sama bersignature sah; yang membedakan hanya alasan tidak
# berlakunya. Menggabungkannya dengan QR palsu ke dalam satu penghitung membuat
# dokumen otentik yang lewat umur tampak setara dengan pemalsuan.
OUTCOME_BERLAKU = 'berlaku'
OUTCOME_KEDALUWARSA = 'kedaluwarsa'
OUTCOME_REPLAY = 'replay'
OUTCOME_DIMODIFIKASI = 'dimodifikasi'
OUTCOME_TIDAK_DITEMUKAN = 'tidak_ditemukan'
OUTCOME_SIGNATURE_INVALID = 'signature_invalid'
OUTCOME_ERROR = 'error_pemrosesan'
OUTCOME_LAINNYA = 'lainnya'

OUTCOME_LABELS = {
    OUTCOME_BERLAKU: 'Berlaku',
    OUTCOME_KEDALUWARSA: 'Signature sah, tidak berlaku (kedaluwarsa)',
    OUTCOME_REPLAY: 'Signature sah, tidak berlaku (replay)',
    OUTCOME_DIMODIFIKASI: 'Tidak berlaku (data dimodifikasi/palsu)',
    OUTCOME_TIDAK_DITEMUKAN: 'Tidak berlaku (tidak ada di basis data)',
    OUTCOME_SIGNATURE_INVALID: 'Tidak berlaku (signature tidak sah)',
    OUTCOME_ERROR: 'Error pemrosesan',
    OUTCOME_LAINNYA: 'Lainnya',
}

# Hanya kategori yang benar-benar merupakan keputusan kebijakan. Error
# pemrosesan sengaja dikecualikan: berkas yang gagal dibaca bukan QR yang
# ditolak, melainkan QR yang belum sempat dinilai.
OUTCOME_TIDAK_BERLAKU = (
    OUTCOME_KEDALUWARSA,
    OUTCOME_REPLAY,
    OUTCOME_DIMODIFIKASI,
    OUTCOME_TIDAK_DITEMUKAN,
    OUTCOME_SIGNATURE_INVALID,
)


def classify_verification_outcome(result):
    """Turunkan kategori keberlakuan dari satu baris hasil verifikasi."""
    if not isinstance(result, dict):
        return OUTCOME_LAINNYA

    status = str(result.get('status', ''))

    if result.get('valid'):
        return OUTCOME_BERLAKU
    if result.get('is_replay') or '🔁' in status:
        return OUTCOME_REPLAY
    if result.get('is_expired') or 'Kedaluwarsa' in status:
        return OUTCOME_KEDALUWARSA
    if 'Error' in status:
        return OUTCOME_ERROR
    if 'Dimodifikasi' in status or 'Data Palsu' in status:
        return OUTCOME_DIMODIFIKASI
    if 'Tidak Ditemukan' in status:
        return OUTCOME_TIDAK_DITEMUKAN
    if 'Signature Invalid' in status or 'signature' in status.lower() or 'Nonce tidak valid' in status:
        return OUTCOME_SIGNATURE_INVALID
    return OUTCOME_LAINNYA


def summarize_verification_outcomes(results):
    """Ringkasan dua sumbu atas sekumpulan hasil verifikasi."""
    ringkasan = {key: 0 for key in OUTCOME_LABELS}
    signature_sah = 0
    dinilai = 0

    for result in results or []:
        kategori = classify_verification_outcome(result)
        ringkasan[kategori] += 1
        if kategori != OUTCOME_ERROR:
            dinilai += 1
            if isinstance(result, dict) and result.get('signature_valid'):
                signature_sah += 1

    total = len(results or [])
    ringkasan['total'] = total
    ringkasan['dinilai'] = dinilai
    ringkasan['signature_sah'] = signature_sah
    # Kunci ini menghitung sumbu kriptografis atas seluruh QR yang dinilai, dan
    # sengaja berbeda dari kategori OUTCOME_SIGNATURE_INVALID yang hanya memuat
    # QR yang alasan utama ketidakberlakuannya adalah signature. QR dimodifikasi
    # juga bersignature tidak sah, sehingga kedua angka ini memang tidak sama.
    ringkasan['signature_tidak_sah'] = max(dinilai - signature_sah, 0)
    ringkasan['tidak_berlaku'] = sum(ringkasan[k] for k in OUTCOME_TIDAK_BERLAKU)
    ringkasan['labels'] = OUTCOME_LABELS

    # Persentase dihitung terhadap QR yang benar-benar dinilai, bukan terhadap
    # seluruh berkas, agar error pemrosesan tidak mengencerkan angkanya.
    basis = dinilai or 1
    ringkasan['pct_berlaku'] = round(ringkasan[OUTCOME_BERLAKU] / basis * 100, 1)
    ringkasan['pct_tidak_berlaku'] = round(ringkasan['tidak_berlaku'] / basis * 100, 1)
    ringkasan['pct_signature_sah'] = round(signature_sah / basis * 100, 1)
    return ringkasan


class FileLock:
    """Simple file locking mechanism for Windows/Linux compatibility"""
    
    def __init__(self, lock_file):
        self.lock_file = lock_file + '.lock'
        self.lock_handle = None
    
    def __enter__(self):
        max_retries = 10
        retry_delay = 0.1
        
        for i in range(max_retries):
            try:
                self.lock_handle = open(self.lock_file, 'x')
                break
            except FileExistsError:
                if i == max_retries - 1:
                    raise TimeoutError(f"Cannot acquire lock for {self.lock_file}")
                time.sleep(retry_delay)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_handle:
            self.lock_handle.close()
            try:
                os.remove(self.lock_file)
            except:
                pass

def file_lock(lock_file):
    """Context manager for file locking (cross-platform)"""
    return FileLock(lock_file)

def load_or_create_rsa_keys():
    """Memuat atau membuat kunci RSA dengan error handling yang lebih baik"""
    key_file = app.config['RSA_KEY_FILE']
    try:
        if os.path.exists(key_file):
            try:
                with open(key_file, "rb") as f:
                    key = RSA.import_key(f.read())
                app.logger.info("RSA key berhasil diload")
            except Exception as e:
                app.logger.error(f"Error loading RSA key: {e}, generating new key")
                key = RSA.generate(2048) # Sesuaikan dengan Jurnal: RSA-2048
                with open(key_file, "wb") as f:
                    f.write(key.export_key())
        else:
            key = RSA.generate(2048) # Sesuaikan dengan Jurnal: RSA-2048
            with open(key_file, "wb") as f:
                f.write(key.export_key())
            app.logger.info("RSA key baru digenerate")
    except Exception as e:
        app.logger.critical(f"Gagal inisialisasi RSA keys: {e}")
        raise
    return key, key.publickey()

def load_or_create_ecdsa_keys():
    """Memuat atau membuat kunci ECDSA (P-256)"""
    key_file = app.config.get('ECDSA_KEY_FILE', 'ecdsa_key.pem')
    try:
        if os.path.exists(key_file):
            try:
                with open(key_file, "rt") as f:
                    key = ECC.import_key(f.read())
                app.logger.info("ECDSA key berhasil diload")
            except Exception as e:
                app.logger.error(f"Error loading ECDSA key: {e}, generating new key")
                key = ECC.generate(curve='P-256')
                with open(key_file, "wt") as f:
                    f.write(key.export_key(format='PEM'))
        else:
            key = ECC.generate(curve='P-256')
            with open(key_file, "wt") as f:
                f.write(key.export_key(format='PEM'))
            app.logger.info("ECDSA key baru digenerate")
    except Exception as e:
        app.logger.critical(f"Gagal inisialisasi ECDSA keys: {e}")
        raise
    return key

security_state_lock = threading.Lock()
security_state_ready = False

def init_security_state_db():
    """Inisialisasi penyimpanan replay/audit yang tahan akses paralel."""
    global security_state_ready
    db_path = app.config['SECURITY_STATE_DB']

    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with security_state_lock:
            conn = sqlite3.connect(db_path, timeout=10)
            try:
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS nonce_state (
                        nonce TEXT PRIMARY KEY,
                        first_used_at TEXT NOT NULL,
                        last_used_at TEXT NOT NULL,
                        usage_count INTEGER NOT NULL DEFAULT 1
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS security_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS qr_record_index (
                        filename TEXT PRIMARY KEY,
                        qr_id TEXT,
                        nonce TEXT,
                        indexed_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute('CREATE INDEX IF NOT EXISTS idx_nonce_last_used ON nonce_state(last_used_at)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_qr_record_nonce ON qr_record_index(nonce)')
                conn.commit()
                security_state_ready = True
                return True
            finally:
                conn.close()
    except Exception as e:
        security_state_ready = False
        app.logger.warning(f"Gagal inisialisasi security state DB, fallback ke file nonce: {e}")
        return False

def ensure_security_state_ready():
    if security_state_ready:
        return True
    return init_security_state_db()

def migrate_nonce_file_to_security_db():
    """Migrasi nonce historis dari file lama ke SQLite satu kali."""
    if not ensure_security_state_ready():
        return

    nonce_file = app.config['NONCE_LOG']
    if not os.path.exists(nonce_file):
        return

    try:
        with security_state_lock:
            conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=20)
            try:
                cursor = conn.execute(
                    "SELECT value FROM security_metadata WHERE key = ?",
                    ('nonce_file_migrated_v1',)
                )
                if cursor.fetchone():
                    return

                counts = {}
                with open(nonce_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        nonce = line.strip()
                        if nonce:
                            counts[nonce] = counts.get(nonce, 0) + 1

                now = datetime.now(timezone.utc).isoformat()
                for nonce, count in counts.items():
                    conn.execute(
                        """
                        INSERT INTO nonce_state (nonce, first_used_at, last_used_at, usage_count)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(nonce) DO UPDATE SET
                            usage_count = CASE
                                WHEN usage_count < excluded.usage_count THEN excluded.usage_count
                                ELSE usage_count
                            END,
                            last_used_at = excluded.last_used_at
                        """,
                        (nonce, now, now, count)
                    )

                conn.execute(
                    """
                    INSERT OR REPLACE INTO security_metadata (key, value, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    ('nonce_file_migrated_v1', str(len(counts)), now)
                )
                conn.commit()
                app.logger.info(f"Migrasi nonce ke SQLite selesai: {len(counts)} nonce unik")
            finally:
                conn.close()
    except Exception as e:
        app.logger.warning(f"Gagal migrasi nonce file ke SQLite: {e}")

def get_nonce_usage_count_db(nonce):
    if not nonce or not ensure_security_state_ready():
        return None

    try:
        with security_state_lock:
            conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=10)
            try:
                cursor = conn.execute(
                    "SELECT usage_count FROM nonce_state WHERE nonce = ?",
                    (nonce,)
                )
                row = cursor.fetchone()
                return int(row[0]) if row else 0
            finally:
                conn.close()
    except Exception as e:
        app.logger.warning(f"Gagal membaca nonce SQLite, fallback ke file: {e}")
        return None

def record_nonce_usage_db(nonce):
    if not nonce or not ensure_security_state_ready():
        return False

    now = datetime.now(timezone.utc).isoformat()
    try:
        with security_state_lock:
            conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=10)
            try:
                conn.execute(
                    """
                    INSERT INTO nonce_state (nonce, first_used_at, last_used_at, usage_count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(nonce) DO UPDATE SET
                        usage_count = usage_count + 1,
                        last_used_at = excluded.last_used_at
                    """,
                    (nonce, now, now)
                )
                conn.commit()
                return True
            finally:
                conn.close()
    except Exception as e:
        app.logger.warning(f"Gagal mencatat nonce SQLite, tetap menulis file nonce: {e}")
        return False

def reset_nonce_log():
    """Reset file nonce log secara berkala"""
    nonce_file = app.config['NONCE_LOG']
    
    try:
        # Cek ukuran file, jika terlalu besar (>5MB) reset
        if os.path.exists(nonce_file) and os.path.getsize(nonce_file) > 5 * 1024 * 1024:
            backup_file = f"{nonce_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(nonce_file, backup_file)
            
            # Reset file
            with open(nonce_file, 'w', encoding='utf-8') as f:
                f.write("")
            
            app.logger.info(f"Nonce log direset (size: {os.path.getsize(nonce_file)} bytes)")
    except Exception as e:
        app.logger.warning(f"Error resetting nonce log: {e}")

def is_nonce_used(nonce):
    """Cek apakah nonce sudah digunakan dengan locking yang lebih baik"""
    db_count = get_nonce_usage_count_db(nonce)
    if db_count is not None:
        return db_count > 0

    nonce_file = app.config['NONCE_LOG']
    
    if not os.path.exists(nonce_file):
        return False
    
    try:
        # Baca file dengan lock yang lebih ketat
        with file_lock(nonce_file):
            with open(nonce_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                used_nonces = set(line.strip() for line in content.splitlines() if line.strip())
        
        return nonce in used_nonces
        
    except Exception as e:
        app.logger.error(f"Error reading nonce file: {e}")
        return False  # Jika error, anggap nonce belum digunakan

def get_nonce_usage_count(nonce):
    """Menghitung berapa kali nonce sudah digunakan"""
    db_count = get_nonce_usage_count_db(nonce)
    if db_count is not None:
        return db_count

    nonce_file = app.config['NONCE_LOG']
    
    if not os.path.exists(nonce_file):
        return 0
    
    try:
        with file_lock(nonce_file):
            with open(nonce_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                nonces = [line.strip() for line in content.splitlines() if line.strip()]
                return nonces.count(nonce)
    except Exception as e:
        app.logger.error(f"Error reading nonce file: {e}")
        return 0

def append_nonce_backup_file(nonce):
    """Simpan jejak nonce ke file backup setelah state utama dicatat."""
    if not nonce:
        return

    nonce_file = app.config['NONCE_LOG']
    os.makedirs(os.path.dirname(nonce_file), exist_ok=True)

    with file_lock(nonce_file):
        with open(nonce_file, 'a', encoding='utf-8') as f:
            f.write(f"{nonce}\n")

    if os.path.getsize(nonce_file) > 5 * 1024 * 1024:
        reset_nonce_log()

def record_nonce_usage_and_get_count(nonce):
    """Catat nonce secara atomik dan kembalikan (count_sebelum, count_sesudah)."""
    if not nonce:
        return 0, 0

    now = datetime.now(timezone.utc).isoformat()

    if ensure_security_state_ready():
        try:
            with security_state_lock:
                conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=10)
                try:
                    conn.execute(
                        """
                        INSERT INTO nonce_state (nonce, first_used_at, last_used_at, usage_count)
                        VALUES (?, ?, ?, 1)
                        ON CONFLICT(nonce) DO UPDATE SET
                            usage_count = usage_count + 1,
                            last_used_at = excluded.last_used_at
                        """,
                        (nonce, now, now)
                    )
                    cursor = conn.execute(
                        "SELECT usage_count FROM nonce_state WHERE nonce = ?",
                        (nonce,)
                    )
                    row = cursor.fetchone()
                    conn.commit()
                    verification_count = int(row[0]) if row else 1
                finally:
                    conn.close()

            try:
                append_nonce_backup_file(nonce)
            except Exception as e:
                app.logger.warning(f"Gagal menulis backup nonce file: {e}")

            return max(verification_count - 1, 0), verification_count
        except Exception as e:
            app.logger.warning(f"Gagal mencatat nonce SQLite, fallback ke file: {e}")

    nonce_file = app.config['NONCE_LOG']
    try:
        os.makedirs(os.path.dirname(nonce_file), exist_ok=True)
        with file_lock(nonce_file):
            previous_count = 0
            if os.path.exists(nonce_file):
                with open(nonce_file, 'r', encoding='utf-8', errors='ignore') as f:
                    previous_count = sum(1 for line in f if line.strip() == nonce)

            with open(nonce_file, 'a', encoding='utf-8') as f:
                f.write(f"{nonce}\n")

        if os.path.getsize(nonce_file) > 5 * 1024 * 1024:
            reset_nonce_log()

        return previous_count, previous_count + 1
    except Exception as e:
        app.logger.error(f"Error logging nonce fallback: {e}")
        return 0, 1

def log_nonce(nonce):
    """Log nonce yang sudah digunakan dengan SQLite atomic dan file backup."""
    try:
        record_nonce_usage_db(nonce)
        append_nonce_backup_file(nonce)
            
    except Exception as e:
        app.logger.error(f"Error logging nonce: {e}")

def direct_verify_probe_response(status_code=200):
    response = make_response('', status_code)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

def ensure_log_files_exist():
    """Membuat file log CSV jika belum ada"""
    logs_folder = app.config['LOGS_FOLDER']
    try:
        os.makedirs(logs_folder, exist_ok=True)
        
        # File log generate
        generate_log = app.config['CSV_LOG_GENERATE']
        if not os.path.exists(generate_log):
            generate_headers = [
                "Sumber", "Waktu", "Nama", "ID", "Versi QR", "Modul", 
                "Resolusi", "Ukuran File (KB)", "Panjang Signature",
                "Waktu Data (detik)", "Waktu Sign (detik)", 
                "Waktu QR (detik)", "Waktu Save (detik)", "Total Waktu (detik)"
            ]
            with open(generate_log, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(generate_headers)
            app.logger.info(f"File log generate dibuat: {generate_log}")
        
        # File log verifikasi
        verifikasi_log = app.config['CSV_LOG_VERIFIKASI']
        if not os.path.exists(verifikasi_log):
            verifikasi_headers = [
                "Sumber", "Waktu", "Nama File", "Status", "Nama", "ID", "Perubahan Data",
                "Waktu Load (detik)", "Waktu Decode (detik)", "Waktu Verify (detik)",
                "Waktu DB (detik)", "Total Waktu (detik)"
            ]
            with open(verifikasi_log, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(verifikasi_headers)
            app.logger.info(f"File log verifikasi dibuat: {verifikasi_log}")
        
        # File nonce log
        nonce_log = app.config['NONCE_LOG']
        if not os.path.exists(nonce_log):
            with open(nonce_log, 'w', encoding='utf-8') as f:
                pass
            app.logger.info(f"File nonce log dibuat: {nonce_log}")

        # File audit log admin
        audit_log = app.config['AUDIT_LOG']
        if not os.path.exists(audit_log):
            with open(audit_log, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Waktu", "Aksi", "Actor", "IP", "User Agent", "Detail"])
            app.logger.info(f"File audit log dibuat: {audit_log}")
            
        # File log modifikasi
        modification_log = app.config['MODIFICATION_LOG']
        if not os.path.exists(modification_log):
            with open(modification_log, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)
            app.logger.info(f"File log modifikasi dibuat: {modification_log}")
            
        # File log batch modifikasi
        batch_modification_log = app.config['BATCH_MODIFICATION_LOG']
        if not os.path.exists(batch_modification_log):
            with open(batch_modification_log, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)
            app.logger.info(f"File log batch modifikasi dibuat: {batch_modification_log}")
            
    except Exception as e:
        app.logger.error(f"Error creating log files: {e}")
        raise

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Silakan login terlebih dahulu untuk mengakses sistem.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"]) # Batasi percobaan password, bukan tampilan form login
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if secrets.compare_digest(password, app.config['AUTH_PASSWORD']): # Mencegah Timing Attack
            session.permanent = True # Mengaktifkan batas waktu sesi (2 jam)
            session['logged_in'] = True
            log_audit_event('login_success', {'path': request.path})
            flash('Berhasil login!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            log_audit_event('login_failed', {'path': request.path}, actor='anonymous')
            flash('Password salah!', 'danger')
    
    if session.get('logged_in'):
        return redirect(url_for('index'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    log_audit_event('logout', {'path': request.path})
    session.pop('logged_in', None)
    flash('Anda telah berhasil logout.', 'info')
    return redirect(url_for('login'))

# ==================== INISIALISASI RSA KEYS ====================
try:
    private_key, public_key = load_or_create_rsa_keys()
    ecdsa_private_key = load_or_create_ecdsa_keys()
    ecdsa_public_key = ecdsa_private_key.public_key()
    app.logger.info("Cryptographic keys (RSA & ECDSA) berhasil diinisialisasi")
except Exception as e:
    app.logger.error(f"Gagal inisialisasi keys: {e}")
    raise

# ==================== FUNGSI TIMER & STATISTIK ====================
class Timer:
    """Class untuk mengukur waktu eksekusi"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.duration = None
    
    def start(self):
        self.start_time = time.perf_counter()
        return self
    
    def stop(self):
        self.end_time = time.perf_counter()
        self.duration = self.end_time - self.start_time
        return self.duration
    
    def get_duration_ms(self):
        return self.duration * 1000 if self.duration else 0

# ==================== FUNGSI PERSISTENSI STATISTIK ====================
def save_stats_to_file(stats_instance):
    """Menyimpan statistik ke file JSON"""
    try:
        def normalize_dimensions(dimensions):
            normalized = []
            for dimension in dimensions:
                try:
                    width, height = dimension
                    normalized.append([int(width), int(height)])
                except Exception:
                    continue
            return normalized

        stats_data = {
            'total_generate_time': float(stats_instance.total_generate_time),
            'total_verify_time': float(stats_instance.total_verify_time),
            'qr_count': int(stats_instance.qr_count),
            'verify_count': int(stats_instance.verify_count),
            'success_verify_count': int(stats_instance.success_verify_count),
            'file_sizes': [float(size) for size in stats_instance.file_sizes],
            'dimensions': normalize_dimensions(stats_instance.dimensions)
        }
        
        stats_file = app.config['STATS_FILE']
        os.makedirs(os.path.dirname(stats_file), exist_ok=True)
        tmp_file = f"{stats_file}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, separators=(',', ':'))
        os.replace(tmp_file, stats_file)
        
        app.logger.debug(f"Statistik disimpan ke {stats_file}")
    except Exception as e:
        app.logger.error(f"Error saving stats: {e}")
        try:
            if 'tmp_file' in locals() and os.path.exists(tmp_file):
                os.remove(tmp_file)
        except Exception:
            pass

def load_stats_from_file(stats_instance):
    """Memuat statistik dari file JSON"""
    stats_file = app.config['STATS_FILE']
    
    if os.path.exists(stats_file):
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
            
            stats_instance.total_generate_time = float(stats_data.get('total_generate_time', 0.0))
            stats_instance.total_verify_time = float(stats_data.get('total_verify_time', 0.0))
            stats_instance.qr_count = int(stats_data.get('qr_count', 0))
            stats_instance.verify_count = int(stats_data.get('verify_count', 0))
            stats_instance.success_verify_count = int(stats_data.get('success_verify_count', 0))
            stats_instance.file_sizes = [float(x) for x in stats_data.get('file_sizes', [])]
            
            # Handle dimensions dengan benar
            dimensions_data = stats_data.get('dimensions', [])
            processed_dims = []
            for dim in dimensions_data:
                if isinstance(dim, list) and len(dim) >= 2:
                    try:
                        width = int(float(dim[0]))
                        height = int(float(dim[1]))
                        processed_dims.append((width, height))
                    except:
                        processed_dims.append((100, 100))
                else:
                    processed_dims.append((100, 100))
            stats_instance.dimensions = processed_dims
            
            app.logger.info(f"Statistik dimuat dari {stats_file}: {stats_instance.qr_count} QR, {stats_instance.verify_count} verify")
            return True
        except Exception as e:
            app.logger.error(f"Error loading stats: {e}")
            return False
    return False

class QRCodeStats:
    """Class untuk menyimpan statistik QR Code dengan penyimpanan persisten"""

    def __init__(self):
        # Inisialisasi dengan nilai default
        self.total_generate_time = 0.0
        self.total_verify_time = 0.0
        self.qr_count = 0
        self.success_verify_count = 0
        self.verify_count = 0
        self.file_sizes = []
        self.dimensions = []
        
        # Coba muat statistik dari file saat instance dibuat
        self._load_from_file()
    
    def _load_from_file(self):
        """Memuat statistik dari file JSON secara internal"""
        stats_file = app.config['STATS_FILE']
        
        if os.path.exists(stats_file):
            try:
                with open(stats_file, 'r', encoding='utf-8') as f:
                    stats_data = json.load(f)
                
                self.total_generate_time = float(stats_data.get('total_generate_time', 0.0))
                self.total_verify_time = float(stats_data.get('total_verify_time', 0.0))
                self.qr_count = int(stats_data.get('qr_count', 0))
                self.verify_count = int(stats_data.get('verify_count', 0))
                self.success_verify_count = int(stats_data.get('success_verify_count', 0))
                self.file_sizes = [float(x) for x in stats_data.get('file_sizes', [])]
                
                # Handle dimensions dengan benar
                dimensions_data = stats_data.get('dimensions', [])
                processed_dims = []
                for dim in dimensions_data:
                    if isinstance(dim, list) and len(dim) >= 2:
                        try:
                            width = int(float(dim[0]))
                            height = int(float(dim[1]))
                            processed_dims.append((width, height))
                        except:
                            processed_dims.append((100, 100))
                    else:
                        processed_dims.append((100, 100))
                self.dimensions = processed_dims
                
                app.logger.info(f"Statistik dimuat dari {stats_file}: {self.qr_count} QR, {self.verify_count} verify")
            except Exception as e:
                app.logger.error(f"Error loading stats from file: {e}")
                # Jika error, gunakan nilai default
                self._reset_to_defaults()
        else:
            # File tidak ada, gunakan nilai default
            app.logger.info(f"File statistik tidak ditemukan: {stats_file}, menggunakan nilai default")
    
    def _reset_to_defaults(self):
        """Reset ke nilai default tanpa menyimpan ke file"""
        self.total_generate_time = 0.0
        self.total_verify_time = 0.0
        self.qr_count = 0
        self.success_verify_count = 0
        self.verify_count = 0
        self.file_sizes = []
        self.dimensions = []
    
    def reset_stats(self):
        """Reset semua statistik ke nilai default DAN SIMPAN KE FILE"""
        self._reset_to_defaults()
        # Simpan ke file setelah reset
        save_stats_to_file(self)
    
    def add_generate_stat(self, generate_time, file_size=None, dimensions=None):
        """Tambahkan statistik generate"""
        try:
            generate_val = float(generate_time) if generate_time is not None else 0.0
            self.total_generate_time += generate_val
            self.qr_count += 1
            
            if file_size is not None:
                self.file_sizes.append(float(file_size))
            
            if dimensions is not None:
                if isinstance(dimensions, (tuple, list)) and len(dimensions) >= 2:
                    self.dimensions.append((int(dimensions[0]), int(dimensions[1])))
                else:
                    self.dimensions.append((100, 100))  # default
            
            # Simpan ke file setelah update
            save_stats_to_file(self)
            app.logger.debug(f"Statistik generate ditambahkan: total={self.qr_count}, avg_time={self.get_average_generate_time()}")
        except Exception as e:
            app.logger.warning(f"Error in add_generate_stat: {e}")
    
    def add_verify_stat(self, verify_time, success=False):
        """Tambahkan statistik verifikasi"""
        try:
            verify_val = float(verify_time) if verify_time is not None else 0.0
            self.total_verify_time += verify_val
            self.verify_count += 1
            if success:
                self.success_verify_count += 1
            # Simpan ke file setelah update
            save_stats_to_file(self)
            app.logger.debug(f"Statistik verify ditambahkan: total={self.verify_count}, avg_time={self.get_average_verify_time()}")
        except Exception as e:
            app.logger.warning(f"Error in add_verify_stat: {e}")

    def add_verify_batch_stats(self, total_verify_time, success_count=0, verify_count=0):
        """Tambahkan statistik verifikasi massal dalam satu kali persist."""
        try:
            verify_val = float(total_verify_time) if total_verify_time is not None else 0.0
            count_val = int(verify_count or 0)
            success_val = int(success_count or 0)
            if count_val <= 0:
                return

            self.total_verify_time += verify_val
            self.verify_count += count_val
            self.success_verify_count += success_val
            save_stats_to_file(self)
            app.logger.debug(
                f"Statistik verify batch ditambahkan: total={self.verify_count}, "
                f"batch_count={count_val}, batch_success={success_val}"
            )
        except Exception as e:
            app.logger.warning(f"Error in add_verify_batch_stats: {e}")
    
    def get_wilson_score(self):
        """Menghitung Wilson Score Interval (95% CI) untuk Success Rate"""
        n = self.verify_count
        if n == 0:
            return {"rate": 0, "lower": 0, "upper": 0}
        
        p = self.success_verify_count / n
        z = 1.96  # 95% confidence level
        
        denominator = 1 + (z**2 / n)
        adj_p = p + (z**2 / (2 * n))
        error = z * math.sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2)))
        
        lower = (adj_p - error) / denominator
        upper = (adj_p + error) / denominator
        
        return {
            "rate": round(p * 100, 2),
            "lower": round(max(0, lower) * 100, 2),
            "upper": round(min(1, upper) * 100, 2)
        }

    def get_average_generate_time(self):
        """Ambil rata-rata waktu generate dengan aman"""
        try:
            if self.qr_count > 0 and self.total_generate_time >= 0:
                return float(self.total_generate_time) / float(self.qr_count)
        except Exception as e:
            app.logger.warning(f"Error in get_average_generate_time: {e}")
        return 0.0
    
    def get_average_verify_time(self):
        """Ambil rata-rata waktu verifikasi dengan aman"""
        try:
            if self.verify_count > 0 and self.total_verify_time >= 0:
                return float(self.total_verify_time) / float(self.verify_count)
        except Exception as e:
            app.logger.warning(f"Error in get_average_verify_time: {e}")
        return 0.0
    
    def get_average_file_size(self):
        """Ambil rata-rata ukuran file dengan aman"""
        try:
            if self.file_sizes:
                valid_sizes = [float(f) for f in self.file_sizes if f is not None and f >= 0]
                if valid_sizes:
                    return sum(valid_sizes) / len(valid_sizes)
        except Exception as e:
            app.logger.warning(f"Error in get_average_file_size: {e}")
        return 0.0
    
    def get_dimension_stats(self):
        """Ambil statistik dimensi dengan error handling lengkap"""
        try:
            if not self.dimensions:
                return {"min": "N/A", "max": "N/A", "avg": "N/A"}
            
            valid_dims = []
            for dim in self.dimensions:
                try:
                    if isinstance(dim, (tuple, list)):
                        if len(dim) >= 2:
                            width = float(dim[0])
                            height = float(dim[1])
                            if width > 0 and height > 0:
                                valid_dims.append((int(width), int(height)))
                    elif isinstance(dim, str):
                        if 'x' in dim:
                            parts = dim.split('x')
                            if len(parts) >= 2:
                                width = float(parts[0].strip())
                                height = float(parts[1].strip())
                                if width > 0 and height > 0:
                                    valid_dims.append((int(width), int(height)))
                except Exception:
                    continue
            
            if not valid_dims:
                return {"min": "N/A", "max": "N/A", "avg": "N/A"}
            
            widths = [d[0] for d in valid_dims]
            heights = [d[1] for d in valid_dims]
            
            avg_width = int(sum(widths) / len(widths)) if widths else 0
            avg_height = int(sum(heights) / len(heights)) if heights else 0
            
            return {
                "min": f"{min(widths)}x{min(heights)}",
                "max": f"{max(widths)}x{max(heights)}",
                "avg": f"{avg_width}x{avg_height}"
            }
            
        except Exception as e:
            app.logger.error(f"Error in get_dimension_stats: {e}")
            return {"min": "N/A", "max": "N/A", "avg": "N/A"}

# Global stats instance
qr_stats = QRCodeStats()

# ==================== GLOBAL VARIABLES FOR TASK MANAGEMENT ====================
# Untuk menyimpan progress task background
background_tasks = OrderedDict()
task_lock = threading.Lock()
generate_task_cache_warmups = set()
MAX_TASK_HISTORY = 10  # Simpan hanya 10 task terakhir

def cleanup_task_saved_files(task_data):
    """Hapus file sementara milik task upload, bukan artefak QR hasil generate."""
    if not task_data or not task_data.get('cleanup_saved_files', True):
        return

    for file_path in task_data.get('saved_files') or []:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            app.logger.warning(f"Gagal menghapus file sementara task {file_path}: {e}")

def prune_oldest_background_task_if_needed():
    if len(background_tasks) < MAX_TASK_HISTORY:
        return

    oldest_task_id = next(iter(background_tasks))
    old_task = background_tasks[oldest_task_id]
    cleanup_task_saved_files(old_task)
    del background_tasks[oldest_task_id]

def get_generated_filenames_for_task(task_id):
    """Ambil daftar file QR dari task server-side, bukan dari cookie session."""
    if not task_id:
        return []

    with task_lock:
        task = background_tasks.get(task_id) or {}
        generated_files = list(task.get('generated_files') or [])
        results = list(task.get('results') or [])

    if not task:
        snapshot = load_generate_task_snapshot(task_id) or {}
        generated_files = list(snapshot.get('generated_files') or [])
        results = list(snapshot.get('results') or [])

    if generated_files:
        return generated_files

    return [
        item.get('filename')
        for item in results
        if isinstance(item, dict) and item.get('filename')
    ]

def get_task_result_path(task_id):
    safe_task_id = secure_filename(str(task_id or ''))
    if not safe_task_id:
        return None
    return os.path.join(app.config['TASK_RESULTS_FOLDER'], f'{safe_task_id}.json')

def get_task_summary_path(task_id):
    safe_task_id = secure_filename(str(task_id or ''))
    if not safe_task_id:
        return None
    return os.path.join(app.config['TASK_METADATA_FOLDER'], f'{safe_task_id}_summary.json')

def build_dimension_stats_from_values(dimensions, avg_dimension=None):
    valid_dims = []
    for dim in dimensions or []:
        try:
            if isinstance(dim, (list, tuple)) and len(dim) >= 2:
                width = int(float(dim[0]))
                height = int(float(dim[1]))
            elif isinstance(dim, str) and 'x' in dim:
                width_text, height_text = dim.lower().replace('px', '').split('x', 1)
                width = int(float(width_text.strip()))
                height = int(float(height_text.strip()))
            else:
                continue
            if width > 0 and height > 0:
                valid_dims.append((width, height))
        except (TypeError, ValueError):
            continue

    if valid_dims:
        widths = [dim[0] for dim in valid_dims]
        heights = [dim[1] for dim in valid_dims]
        return {
            'min': f'{min(widths)}x{min(heights)}',
            'max': f'{max(widths)}x{max(heights)}',
            'avg': avg_dimension or f'{int(sum(widths) / len(widths))}x{int(sum(heights) / len(heights))}'
        }

    return {'min': 'N/A', 'max': 'N/A', 'avg': avg_dimension or 'N/A'}

def slim_generate_massal_stats(massal_stats):
    stats = dict(massal_stats or {})
    dimensions = stats.pop('dimensions', [])
    individual_times = stats.pop('individual_times', [])

    stats.setdefault('dimension_stats', build_dimension_stats_from_values(dimensions, stats.get('avg_dimension')))
    if individual_times:
        stats.setdefault('avg_time_per_qr', sum(individual_times) / len(individual_times))
        stats.setdefault('min_time', min(individual_times))
        stats.setdefault('max_time', max(individual_times))

    return stats

def build_generate_task_summary_snapshot(task_id, task_data):
    task_data = task_data or {}
    results = task_data.get('results') or []
    massal_stats = slim_generate_massal_stats(task_data.get('massal_stats') or {})
    generated_files = task_data.get('generated_files') or []
    generated_file_count = (
        task_data.get('generated_file_count')
        or len(generated_files)
        or massal_stats.get('success_count')
        or massal_stats.get('total_qr')
        or len(results)
        or task_data.get('total')
        or task_data.get('total_files')
        or 0
    )

    return {
        'task_id': task_id,
        'type': task_data.get('type') or 'generate_massal',
        'saved_at': task_data.get('saved_at') or datetime.now(timezone.utc).isoformat(),
        'start_time': task_data.get('start_time'),
        'end_time': task_data.get('end_time'),
        'total': task_data.get('total', len(results)),
        'total_files': task_data.get('total_files', task_data.get('total', len(results))),
        'processed': task_data.get('processed', task_data.get('total', len(results))),
        'current': task_data.get('current', task_data.get('processed', 0)),
        'status': task_data.get('status', 'Selesai'),
        'is_complete': task_data.get('is_complete', True),
        'is_processing': task_data.get('is_processing', False),
        'is_stopped': task_data.get('is_stopped', False),
        'error': task_data.get('error'),
        'massal_stats': massal_stats,
        'original_filename': task_data.get('original_filename'),
        'original_filenames': task_data.get('original_filenames') or [],
        'generated_file_count': int(generated_file_count or 0)
    }

def save_generate_task_summary(task_id, task_data):
    summary_path = get_task_summary_path(task_id)
    if not summary_path:
        return

    try:
        os.makedirs(app.config['TASK_METADATA_FOLDER'], exist_ok=True)
        tmp_path = f'{summary_path}.tmp'
        summary = build_generate_task_summary_snapshot(task_id, task_data)
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False)
        os.replace(tmp_path, summary_path)
    except Exception as e:
        app.logger.warning(f'Gagal menyimpan summary task {task_id}: {e}')

def load_generate_task_summary(task_id):
    if not task_id:
        return None

    with task_lock:
        task = background_tasks.get(task_id)
        if task:
            return build_generate_task_summary_snapshot(task_id, task)

    summary_path = get_task_summary_path(task_id)
    if summary_path and os.path.exists(summary_path):
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)
            summary.setdefault('type', 'generate_massal')
            summary.setdefault('is_complete', True)
            summary.setdefault('is_processing', False)
            summary.setdefault('is_stopped', False)
            summary.setdefault('error', None)
            summary.setdefault('massal_stats', {})
            summary.setdefault('generated_file_count', summary.get('total') or summary.get('total_files') or 0)
            return summary
        except Exception as e:
            app.logger.warning(f'Gagal memuat summary task {task_id}: {e}')

    snapshot = load_generate_task_snapshot(task_id)
    if snapshot:
        save_generate_task_summary(task_id, snapshot)
        return build_generate_task_summary_snapshot(task_id, snapshot)

    metadata = load_generate_task_metadata(task_id)
    if metadata:
        return build_generate_task_summary_snapshot(task_id, metadata)

    return None

def save_generate_task_snapshot(task_id, task_data):
    result_path = get_task_result_path(task_id)
    if not result_path:
        return

    try:
        os.makedirs(app.config['TASK_RESULTS_FOLDER'], exist_ok=True)
        tmp_path = f'{result_path}.tmp'
        snapshot = {
            'task_id': task_id,
            'type': task_data.get('type') or 'generate_massal',
            'saved_at': datetime.now(timezone.utc).isoformat(),
            'start_time': task_data.get('start_time'),
            'end_time': task_data.get('end_time'),
            'total': task_data.get('total', 0),
            'total_files': task_data.get('total_files', task_data.get('total', 0)),
            'processed': task_data.get('processed', 0),
            'current': task_data.get('current', task_data.get('processed', 0)),
            'status': task_data.get('status', 'Selesai'),
            'is_complete': task_data.get('is_complete', True),
            'is_processing': False,
            'is_stopped': task_data.get('is_stopped', False),
            'error': task_data.get('error'),
            'results': task_data.get('results') or [],
            'massal_stats': task_data.get('massal_stats') or {},
            'original_filename': task_data.get('original_filename'),
            'original_filenames': task_data.get('original_filenames') or [],
            'generated_files': task_data.get('generated_files') or [],
            'generated_file_count': task_data.get('generated_file_count', 0)
        }
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False)
        os.replace(tmp_path, result_path)
        if snapshot.get('type') != 'verify_massal':
            save_generate_task_summary(task_id, snapshot)
    except Exception as e:
        app.logger.warning(f'Gagal menyimpan snapshot task {task_id}: {e}')

def load_generate_task_snapshot(task_id):
    result_path = get_task_result_path(task_id)
    if not result_path or not os.path.exists(result_path):
        return None

    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)
        snapshot.setdefault('type', 'generate_massal')
        snapshot.setdefault('is_complete', True)
        snapshot.setdefault('is_processing', False)
        snapshot.setdefault('is_stopped', False)
        snapshot.setdefault('error', None)
        snapshot.setdefault('results', [])
        snapshot.setdefault('massal_stats', {})
        if snapshot.get('type') == 'verify_massal':
            stats = snapshot['massal_stats']
            stats.setdefault('total_files', snapshot.get('total_files') or snapshot.get('total') or len(snapshot.get('results') or []))
            stats.setdefault('success_count', 0)
            stats.setdefault('error_count', 0)
            stats.setdefault('replay_attack_count', 0)
            stats.setdefault('valid_signature_count', 0)
            stats.setdefault('total_time', 0)
            stats.setdefault('avg_time_per_file', 0)
            stats.setdefault('min_time', 0)
            stats.setdefault('max_time', 0)
            stats.setdefault('success_rate', (stats.get('success_count', 0) / stats['total_files'] * 100) if stats.get('total_files') else 0)
            stats.setdefault('time_breakdown', {})
            stats['time_breakdown'].setdefault('load', 0)
            stats['time_breakdown'].setdefault('decode', 0)
            stats['time_breakdown'].setdefault('verify', 0)
            stats['time_breakdown'].setdefault('db', 0)
        snapshot.setdefault('total', snapshot.get('total_files') or len(snapshot.get('results') or []))
        snapshot.setdefault('total_files', snapshot.get('total', 0))
        snapshot.setdefault('processed', snapshot.get('total', 0) if snapshot.get('is_complete') else 0)
        snapshot.setdefault('current', snapshot.get('processed', 0))
        snapshot.setdefault('original_filenames', [])
        snapshot.setdefault('generated_files', [
            item.get('filename')
            for item in snapshot.get('results', [])
            if isinstance(item, dict) and item.get('filename')
        ])
        snapshot.setdefault('generated_file_count', len(snapshot.get('generated_files') or []))
        return snapshot
    except Exception as e:
        app.logger.warning(f'Gagal memuat snapshot task {task_id}: {e}')
        return None

def get_task_metadata_path(task_id):
    safe_task_id = secure_filename(str(task_id or ''))
    if not safe_task_id:
        return None
    return os.path.join(app.config['TASK_METADATA_FOLDER'], f'{safe_task_id}.json')

def count_csv_data_rows(csv_path):
    with open(csv_path, 'r', encoding='utf-8') as f:
        return max(sum(1 for _ in f) - 1, 0)

def build_generate_task(task_id, csv_path, total_rows=None, alg='RSA',
                        base_url=None, original_filename=None,
                        status='Memulai proses...'):
    if total_rows is None:
        total_rows = count_csv_data_rows(csv_path)

    return {
        'total': max(int(total_rows or 0), 0),
        'processed': 0,
        'current': 0,
        'status': status,
        'is_processing': False,
        'is_complete': False,
        'is_stopped': False,
        'start_time': datetime.now().isoformat(),
        'results': None,
        'massal_stats': None,
        'error': None,
        'csv_path': csv_path,
        'original_filename': original_filename or os.path.basename(csv_path),
        'user_id': 'unknown',
        'base_url': base_url or get_public_base_url(),
        'alg': alg or 'RSA'
    }

def save_generate_task_metadata(task_id, task_data):
    metadata_path = get_task_metadata_path(task_id)
    if not metadata_path:
        return

    try:
        os.makedirs(app.config['TASK_METADATA_FOLDER'], exist_ok=True)
        tmp_path = f'{metadata_path}.tmp'
        metadata = {
            'task_id': task_id,
            'saved_at': datetime.now(timezone.utc).isoformat(),
            'csv_path': task_data.get('csv_path'),
            'total': task_data.get('total', 0),
            'original_filename': task_data.get('original_filename'),
            'base_url': task_data.get('base_url'),
            'alg': task_data.get('alg', 'RSA')
        }
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False)
        os.replace(tmp_path, metadata_path)
    except Exception as e:
        app.logger.warning(f'Gagal menyimpan metadata task {task_id}: {e}')

def load_generate_task_metadata(task_id):
    metadata = {}
    metadata_path = get_task_metadata_path(task_id)

    if metadata_path and os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            app.logger.warning(f'Gagal memuat metadata task {task_id}: {e}')
            metadata = {}

    default_csv_path = os.path.join(
        app.config['UPLOAD_FOLDER'],
        'tasks',
        f'task_{secure_filename(str(task_id or ""))}.csv'
    )
    csv_path = metadata.get('csv_path') or default_csv_path

    if not csv_path or not os.path.exists(csv_path):
        return None

    return build_generate_task(
        task_id,
        csv_path,
        total_rows=metadata.get('total'),
        alg=metadata.get('alg', 'RSA'),
        base_url=metadata.get('base_url'),
        original_filename=metadata.get('original_filename') or os.path.basename(csv_path),
        status='Task dipulihkan dari file CSV. Menunggu proses dimulai ulang...'
    )

def ensure_generate_task_loaded(task_id):
    if not task_id:
        return None

    with task_lock:
        task = background_tasks.get(task_id)
        if task:
            return task

    task = load_generate_task_snapshot(task_id)
    if task:
        task.setdefault('status', 'Selesai')
        task.setdefault('is_processing', False)
        task.setdefault('is_complete', True)
    else:
        task = load_generate_task_metadata(task_id)

    if not task:
        return None

    with task_lock:
        existing_task = background_tasks.get(task_id)
        if existing_task:
            return existing_task

        if len(background_tasks) >= MAX_TASK_HISTORY:
            oldest_task_id = next(iter(background_tasks))
            del background_tasks[oldest_task_id]

        background_tasks[task_id] = task

    app.logger.info(f'Task {task_id} dipulihkan dari penyimpanan lokal')
    return task

def warm_generate_task_cache(task_id):
    if not task_id:
        return

    with task_lock:
        task = background_tasks.get(task_id)
        if task and task.get('results') is not None:
            return
        if task_id in generate_task_cache_warmups:
            return
        generate_task_cache_warmups.add(task_id)

    def load_task():
        try:
            ensure_generate_task_loaded(task_id)
        except Exception as e:
            app.logger.warning(f'Gagal memanaskan cache task {task_id}: {e}')
        finally:
            with task_lock:
                generate_task_cache_warmups.discard(task_id)

    cache_thread = threading.Thread(target=load_task, name=f'warm-generate-{task_id[:8]}')
    cache_thread.daemon = True
    cache_thread.start()

def load_task_from_memory_or_snapshot(task_id):
    if not task_id:
        return None

    with task_lock:
        task = background_tasks.get(task_id)
        if task:
            return dict(task)

    return load_generate_task_snapshot(task_id)

def build_generate_task_display_stats(massal_stats, results):
    massal_stats = massal_stats or {}
    results = results or []

    total_qr = int(massal_stats.get('total_qr') or len(results) or 0)
    total_time = float(massal_stats.get('total_time') or 0)
    avg_time = float(massal_stats.get('avg_time_per_qr') or ((total_time / total_qr) if total_qr else 0))
    total_file_size = float(massal_stats.get('total_file_size') or 0)
    avg_file_size = (total_file_size / total_qr) if total_qr else 0

    dim_stats = massal_stats.get('dimension_stats')
    if not isinstance(dim_stats, dict):
        dim_stats = build_dimension_stats_from_values(
            massal_stats.get('dimensions') or [],
            massal_stats.get('avg_dimension')
        )

    return {
        'total_qr': total_qr,
        'avg_time_per_qr': avg_time,
        'avg_file_size_kb': avg_file_size,
        'dim_stats': dim_stats
    }

def build_task_summary(task_id, task_data, source='memory'):
    total = int(task_data.get('total') or task_data.get('total_files') or 0)
    processed = int(task_data.get('processed') or task_data.get('current') or 0)
    percentage = (processed / total * 100) if total else (100 if task_data.get('is_complete') else 0)
    task_type = task_data.get('type') or 'generate_massal'
    original_filenames = task_data.get('original_filenames') or []
    generated_file_count = task_data.get('generated_file_count') or len(task_data.get('generated_files') or [])
    if task_type == 'verify_massal':
        title = 'Verifikasi Massal'
        progress_url = url_for('verify_massal_progress', task_id=task_id)
        result_url = url_for('render_verify_massal_results', task_id=task_id) if task_data.get('is_complete') else None
        download_url = url_for('export_verify_massal_report', task_id=task_id) if task_data.get('is_complete') else None
        file_count = total or len(original_filenames) or len(task_data.get('results') or [])
        file_summary = f'{file_count} file diproses'
    else:
        title = 'Generate QR Massal'
        progress_url = url_for('generate_progress', task_id=task_id)
        result_url = url_for('view_generate_results', task_id=task_id) if task_data.get('is_complete') else None
        download_url = url_for('download_qr_massal', task_id=task_id) if task_data.get('is_complete') else None
        file_count = generated_file_count or total or len(task_data.get('results') or [])
        file_summary = f'{file_count} file QR' if file_count else '-'

    return {
        'task_id': task_id,
        'type': task_type,
        'title': title,
        'source': source,
        'status': task_data.get('status') or '-',
        'total': total,
        'processed': processed,
        'percentage': round(min(max(percentage, 0), 100), 1),
        'is_processing': bool(task_data.get('is_processing')),
        'is_complete': bool(task_data.get('is_complete')),
        'is_stopped': bool(task_data.get('is_stopped')),
        'error': task_data.get('error'),
        'start_time': task_data.get('start_time') or task_data.get('saved_at') or '-',
        'saved_at': task_data.get('saved_at') or '-',
        'original_filename': task_data.get('original_filename') or ', '.join(task_data.get('original_filenames') or []) or '-',
        'file_count': file_count,
        'file_summary': file_summary,
        'generated_file_count': generated_file_count,
        'progress_url': progress_url,
        'result_url': result_url,
        'download_url': download_url
    }

def list_job_summaries(limit=50):
    jobs = {}

    with task_lock:
        for task_id, task_data in background_tasks.items():
            jobs[task_id] = build_task_summary(task_id, dict(task_data), source='memory')

    result_dir = app.config['TASK_RESULTS_FOLDER']
    if os.path.isdir(result_dir):
        for filename in os.listdir(result_dir):
            if not filename.endswith('.json'):
                continue
            task_id = filename[:-5]
            if task_id in jobs:
                continue
            snapshot = load_generate_task_snapshot(task_id)
            if snapshot:
                jobs[task_id] = build_task_summary(task_id, snapshot, source='snapshot')

    metadata_dir = app.config['TASK_METADATA_FOLDER']
    if os.path.isdir(metadata_dir):
        for filename in os.listdir(metadata_dir):
            if not filename.endswith('.json'):
                continue
            task_id = filename[:-5]
            if task_id in jobs:
                continue
            task = load_generate_task_metadata(task_id)
            if task:
                jobs[task_id] = build_task_summary(task_id, task, source='metadata')

    return sorted(
        jobs.values(),
        key=lambda item: item.get('saved_at') if item.get('saved_at') != '-' else item.get('start_time', ''),
        reverse=True
    )[:limit]

# ==================== FUNGSI LOGGING ====================
def _log_to_csv_extended(csv_path, row_data):
    """Log extended untuk informasi waktu yang lebih detail"""
    try:
        # Pastikan folder logs ada
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        headers_map = {
            app.config['CSV_LOG_GENERATE']: [
                "Sumber", "Waktu", "Nama", "ID", "Versi QR", "Modul", 
                "Resolusi", "Ukuran File (KB)", "Panjang Signature",
                "Waktu Data (detik)", "Waktu Sign (detik)", 
                "Waktu QR (detik)", "Waktu Save (detik)", "Total Waktu (detik)"
            ],
            app.config['CSV_LOG_VERIFIKASI']: [
                "Sumber", "Waktu", "Nama File", "Status", "Nama", "ID", "Perubahan Data",
                "Waktu Load (detik)", "Waktu Decode (detik)", "Waktu Verify (detik)",
                "Waktu DB (detik)", "Total Waktu (detik)"
            ]
        }
        
        headers = headers_map.get(csv_path, [])
        
        file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
        
        # TINGKATKAN BATAS FIELD SIZE SEBELUM MENULIS
        csv.field_size_limit(10 * 1024 * 1024)  # 10MB
        
        # Bersihkan data sebelum menulis
        cleaned_row = []
        for item in row_data:
            if isinstance(item, str):
                # Bersihkan karakter non-UTF-8
                item = item.encode('utf-8', 'replace').decode('utf-8', 'replace')
                # Hapus karakter kontrol kecuali yang umum
                item = ''.join(char for char in item if ord(char) >= 32 or char in '\t\n\r')
            cleaned_row.append(str(item) if item is not None else '')
        
        with open(csv_path, mode='a', newline='', encoding='utf-8', errors='replace') as file:
            writer = csv.writer(file)
            
            if not file_exists:
                writer.writerow(headers)
            
            writer.writerow(cleaned_row)
        
        app.logger.debug(f"Log ditulis ke {csv_path}: {len(cleaned_row)} kolom")
        
    except Exception as e:
        app.logger.error(f"Error writing to log {csv_path}: {e}")
        raise

def log_audit_event(action, detail=None, actor='admin'):
    """Catat aksi admin/operator yang sensitif tanpa mencampur log verifikasi."""
    try:
        audit_log = app.config['AUDIT_LOG']
        os.makedirs(os.path.dirname(audit_log), exist_ok=True)
        file_exists = os.path.exists(audit_log) and os.path.getsize(audit_log) > 0
        row = [
            datetime.now(timezone.utc).isoformat(),
            action,
            actor,
            request.headers.get('X-Forwarded-For', request.remote_addr or '-') if request else '-',
            request.headers.get('User-Agent', '-') if request else '-',
            json.dumps(detail or {}, ensure_ascii=False) if isinstance(detail, (dict, list)) else str(detail or '-')
        ]

        with open(audit_log, mode='a', newline='', encoding='utf-8', errors='replace') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Waktu", "Aksi", "Actor", "IP", "User Agent", "Detail"])
            writer.writerow(row)
    except Exception as e:
        app.logger.warning(f"Gagal menulis audit log: {e}")

def get_key_file_info(path):
    try:
        stat_info = os.stat(path)
        mode = stat_info.st_mode & 0o777
        return {
            'path': path,
            'exists': True,
            'size': stat_info.st_size,
            'mode': oct(mode),
            'restricted': (mode & 0o027) == 0,
            'modified': datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
    except FileNotFoundError:
        return {'path': path, 'exists': False, 'size': 0, 'mode': '-', 'restricted': False, 'modified': '-'}

def get_nonce_store_stats():
    stats = {
        'db_ready': bool(security_state_ready),
        'unique_nonce': 0,
        'total_usage': 0,
        'db_path': app.config['SECURITY_STATE_DB'],
        'file_path': app.config['NONCE_LOG']
    }

    if ensure_security_state_ready():
        try:
            with security_state_lock:
                conn = sqlite3.connect(app.config['SECURITY_STATE_DB'], timeout=10)
                try:
                    cursor = conn.execute("SELECT COUNT(*), COALESCE(SUM(usage_count), 0) FROM nonce_state")
                    row = cursor.fetchone()
                    if row:
                        stats['unique_nonce'] = int(row[0] or 0)
                        stats['total_usage'] = int(row[1] or 0)
                finally:
                    conn.close()
        except Exception as e:
            app.logger.warning(f"Gagal membaca statistik nonce SQLite: {e}")

    return stats

def count_verify_payload_files():
    count = 0
    payload_dir = app.config['VERIFY_PAYLOAD_FOLDER']
    if not os.path.isdir(payload_dir):
        return 0

    for _, _, files in os.walk(payload_dir):
        count += sum(1 for filename in files if filename.endswith('.json'))
    return count

def cleanup_old_verify_payloads(max_age_seconds=None):
    payload_dir = app.config['VERIFY_PAYLOAD_FOLDER']
    if not os.path.isdir(payload_dir):
        return 0

    if max_age_seconds is None:
        max_age_seconds = max(app.config['VERIFY_PAYLOAD_RETENTION_DAYS'], 1) * 24 * 3600

    now = time.time()
    deleted = 0
    for root, _, files in os.walk(payload_dir, topdown=False):
        for filename in files:
            if not filename.endswith('.json'):
                continue
            path = os.path.join(root, filename)
            try:
                if now - os.path.getmtime(path) > max_age_seconds:
                    os.remove(path)
                    deleted += 1
            except OSError as e:
                app.logger.warning(f"Gagal membersihkan payload {path}: {e}")
        if root != payload_dir:
            try:
                if not os.listdir(root):
                    os.rmdir(root)
            except OSError:
                pass

    if deleted:
        app.logger.info(f"Cleanup payload verifikasi lama: {deleted} file")
    return deleted

def get_security_profile_context():
    return {
        'crypto': {
            'primary_algorithm': 'RSA-PSS',
            'key_size': 'RSA 2048-bit',
            'hash': 'SHA-256',
            'salt_bytes': 8,
            'nonce': f'{get_qr_nonce_bytes()} byte random, disimpan sebagai {get_qr_nonce_bytes() * 2} karakter hex',
            'timestamp_policy': f'Timestamp payload diperiksa dengan batas kedaluwarsa {app.config["QR_PAYLOAD_MAX_AGE_SECONDS"]} detik saat verifikasi',
            'qr_url_policy': 'QR berisi URL pendek /v/<token>; payload tetap ditandatangani RSA-PSS'
        },
        'keys': {
            'rsa': get_key_file_info(app.config['RSA_KEY_FILE']),
            'ecdsa_legacy': get_key_file_info(app.config['ECDSA_KEY_FILE'])
        },
        'nonce_store': get_nonce_store_stats(),
        'payload': {
            'folder': app.config['VERIFY_PAYLOAD_FOLDER'],
            'retention_days': app.config['VERIFY_PAYLOAD_RETENTION_DAYS'],
            'count': count_verify_payload_files()
        },
        'limits': {
            'default': app.config['RATELIMIT_DEFAULT'],
            'generate': app.config['RATELIMIT_GENERATE'],
            'dashboard': app.config['RATELIMIT_DASHBOARD']
        }
    }

# Serialisasi pembuatan grafik evaluasi.
#
# Fungsi ini dijalankan dari background thread setiap kali QR digenerate.
# Sebelumnya ia memakai state global pyplot (plt.figure/plt.savefig), padahal
# pyplot TIDAK aman untuk multi-thread: bila dua generate berjalan bersamaan,
# plt.figure() milik thread kedua menjadi "figure aktif" sehingga thread
# pertama menggambar lalu menyimpan figure yang salah - hasilnya PNG kosong.
# Kejadian nyata: 2026-07-27 grafik tertimpa gambar putih 3,8 KB saat uji beban.
#
# Perbaikan: (1) API berorientasi objek tanpa state global, (2) lock agar hanya
# satu pembuatan grafik berjalan, (3) lewati bila sudah ada yang berjalan supaya
# thread tidak menumpuk, (4) tulis ke berkas sementara lalu os.replace() agar
# pembaca tidak pernah menerima PNG separuh jadi.
_chart_lock = threading.Lock()

def _update_evaluation_chart():
    # Bila satu pembuatan grafik sedang berjalan, lewati: hasilnya akan sama-sama
    # memakai data CSV terbaru, jadi tidak ada gunanya mengantre.
    if not _chart_lock.acquire(blocking=False):
        app.logger.debug("Grafik evaluasi sedang dibuat, permintaan dilewati")
        return
    try:
        if os.path.exists(app.config['CSV_LOG_GENERATE']):
            df = pd.read_csv(app.config['CSV_LOG_GENERATE'], engine='python', on_bad_lines='skip')

            if len(df) > 0 and 'Panjang Signature' in df.columns and 'Ukuran File (KB)' in df.columns:
                from matplotlib.figure import Figure
                from matplotlib.backends.backend_agg import FigureCanvasAgg

                fig = Figure(figsize=(10, 6))
                FigureCanvasAgg(fig)
                ax = fig.subplots()

                ax.scatter(df['Panjang Signature'], df['Ukuran File (KB)'], alpha=0.6)

                if len(df) > 1:
                    try:
                        z = np.polyfit(df['Panjang Signature'].astype(float), df['Ukuran File (KB)'].astype(float), 1)
                        p = np.poly1d(z)
                        x_range = np.linspace(df['Panjang Signature'].min(), df['Panjang Signature'].max(), 100)
                        ax.plot(x_range, p(x_range), "r--", alpha=0.8)
                    except Exception:
                        pass

                ax.set_xlabel("Panjang Signature (karakter)")
                ax.set_ylabel("Ukuran File QR (KB)")
                ax.set_title("Perbandingan Panjang Signature vs Ukuran QR Code")
                ax.grid(True, alpha=0.3)
                fig.tight_layout()

                chart_path = "static/grafik_evaluasi.png"
                tmp_fd, tmp_path = tempfile.mkstemp(
                    dir=os.path.dirname(chart_path) or ".", suffix=".png")
                os.close(tmp_fd)
                try:
                    fig.savefig(tmp_path, dpi=100)
                    os.chmod(tmp_path, 0o644)
                    os.replace(tmp_path, chart_path)
                except BaseException:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    raise

                app.logger.debug("Grafik evaluasi diperbarui")
    except Exception as e:
        app.logger.error(f"Error update evaluation chart: {e}")
    finally:
        _chart_lock.release()

# ==================== FUNGSI MODIFIKASI QR CODE ====================
def log_modification(original_data, modified_data, modifications, fake_qr_path):
    """Mencatat log modifikasi tunggal"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'original_data': original_data,
        'modified_data': modified_data,
        'modifications': modifications,
        'fake_qr_path': fake_qr_path
    }
    
    log_file = app.config['MODIFICATION_LOG']
    
    # Baca log yang ada, tambahkan entry baru
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    else:
        logs = []
    
    logs.append(log_entry)
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)
    app.logger.info(f"Log modifikasi ditambahkan: {fake_qr_path}")

def log_batch_modification(total_fake_qr, modifications_list):
    """Mencatat log batch modifikasi"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'total_fake_qr': total_fake_qr,
        'modifications': modifications_list
    }
    
    log_file = app.config['BATCH_MODIFICATION_LOG']
    
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    else:
        logs = []
    
    logs.append(log_entry)
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)
    app.logger.info(f"Log batch modifikasi ditambahkan: {total_fake_qr} QR Code")

def create_fake_signature(data, signature_choice, original_signature=None):
    """Membuat signature palsu berdasarkan pilihan"""
    if signature_choice == 'keep':
        return original_signature
    
    elif signature_choice == 'remove':
        return ''
    
    elif signature_choice == 'corrupt':
        if original_signature and original_signature != '':
            try:
                # Corrupt beberapa byte terakhir
                sig_bytes = base64.b64decode(original_signature)
                if len(sig_bytes) > 0:
                    corrupted = bytearray(sig_bytes)
                    # Ubah beberapa byte terakhir
                    for i in range(min(5, len(corrupted))):
                        corrupted[-(i+1)] = (corrupted[-(i+1)] + 1) % 256
                    return base64.b64encode(corrupted).decode('utf-8')
            except Exception:
                # Jika gagal decode, return signature random
                random_sig = secrets.token_bytes(256)
                return base64.b64encode(random_sig).decode('utf-8')
    
    elif signature_choice == 'random':
        # Buat signature random
        random_sig = secrets.token_bytes(256)
        return base64.b64encode(random_sig).decode('utf-8')
    
    return original_signature

# ==================== BUAT FILE LOG JIKA BELUM ADA ====================
ensure_log_files_exist()
init_security_state_db()
migrate_nonce_file_to_security_db()

# Reset nonce log saat startup untuk menghindari false positive replay attack
reset_nonce_log()

# ==================== FUNGSI STATISTIK TAMBAHAN ====================
def calculate_stats_from_logs():
    """Menghitung statistik dari log file yang sudah ada"""
    global qr_stats
    
    try:
        app.logger.info("Menghitung statistik dari log file...")
        
        # Jangan reset statistik dulu, tapi backup nilai lama
        old_qr_count = qr_stats.qr_count
        old_verify_count = qr_stats.verify_count
        
        # Inisialisasi ulang
        qr_stats._reset_to_defaults()
        
        # Hitung dari log generate
        if os.path.exists(app.config['CSV_LOG_GENERATE']):
            try:
                df = pd.read_csv(app.config['CSV_LOG_GENERATE'], engine='python', on_bad_lines='skip')
                
                for _, row in df.iterrows():
                    try:
                        qr_stats.qr_count += 1
                        
                        # Waktu generate
                        if 'Total Waktu (detik)' in df.columns:
                            total_time = float(row.get('Total Waktu (detik)', 0))
                            qr_stats.total_generate_time += total_time
                        
                        # Ukuran file
                        if 'Ukuran File (KB)' in df.columns:
                            file_size = float(row.get('Ukuran File (KB)', 0))
                            qr_stats.file_sizes.append(file_size)
                        
                        # Dimensi
                        if 'Resolusi' in df.columns:
                            resolusi = str(row.get('Resolusi', '100x100'))
                            if 'x' in resolusi:
                                parts = resolusi.split('x')
                                if len(parts) >= 2:
                                    width = int(float(parts[0].strip()))
                                    height = int(float(parts[1].strip()))
                                    qr_stats.dimensions.append((width, height))
                                else:
                                    qr_stats.dimensions.append((100, 100))
                            else:
                                qr_stats.dimensions.append((100, 100))
                    except Exception as e:
                        app.logger.warning(f"Error parsing generate log row: {e}")
                        continue
                
                app.logger.info(f"Ditemukan {qr_stats.qr_count} entri log generate")
            except Exception as e:
                app.logger.error(f"Error reading generate log: {e}")
        
        # Hitung dari log verifikasi
        if os.path.exists(app.config['CSV_LOG_VERIFIKASI']):
            try:
                df = pd.read_csv(app.config['CSV_LOG_VERIFIKASI'], engine='python', on_bad_lines='skip')
                
                for _, row in df.iterrows():
                    try:
                        qr_stats.verify_count += 1
                        
                        # Waktu verifikasi
                        if 'Total Waktu (detik)' in df.columns:
                            total_time = float(row.get('Total Waktu (detik)', 0))
                            qr_stats.total_verify_time += total_time
                    except Exception as e:
                        app.logger.warning(f"Error parsing verify log row: {e}")
                        continue
                
                app.logger.info(f"Ditemukan {qr_stats.verify_count} entri log verifikasi")
            except Exception as e:
                app.logger.error(f"Error reading verify log: {e}")
        
        # Simpan ke file
        save_stats_to_file(qr_stats)
        
        # Log perubahan
        qr_diff = qr_stats.qr_count - old_qr_count
        verify_diff = qr_stats.verify_count - old_verify_count
        
        app.logger.info(f"Statistik dihitung ulang: {qr_stats.qr_count} QR (+{qr_diff}), {qr_stats.verify_count} verify (+{verify_diff})")
        
        return True
        
    except Exception as e:
        app.logger.error(f"Error calculating stats from logs: {e}")
        return False

@app.route('/api/auto_recalculate_stats')
def auto_recalculate_stats():
    """API untuk auto-recalculate stats (dipanggil oleh dashboard)"""
    try:
        # Cek apakah statistik kosong
        if qr_stats.qr_count == 0 and qr_stats.verify_count == 0:
            # Cek apakah ada data di log file sebelum hitung ulang
            has_data = False
            for log_file in [app.config['CSV_LOG_GENERATE'], app.config['CSV_LOG_VERIFIKASI']]:
                if os.path.exists(log_file):
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            # Baca header
                            f.readline()
                            # Cek apakah ada baris kedua (data) yang tidak kosong
                            line = f.readline()
                            if line and line.strip():
                                has_data = True
                                break
                    except:
                        continue
            
            if not has_data:
                # Jika log kosong, return False agar frontend tidak reload
                return jsonify({
                    'success': False,
                    'message': 'Log file kosong',
                    'qr_count': 0,
                    'verify_count': 0
                })

            result = calculate_stats_from_logs()
            if result:
                return jsonify({
                    'success': True,
                    'message': 'Statistik dihitung ulang dari log file',
                    'qr_count': qr_stats.qr_count,
                    'verify_count': qr_stats.verify_count
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Gagal menghitung statistik dari log file'
                })
        else:
            return jsonify({
                'success': True,
                'message': 'Statistik sudah ada',
                'qr_count': qr_stats.qr_count,
                'verify_count': qr_stats.verify_count
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

# ==================== ROUTES UTAMA ====================
@app.route('/')
@app.route('/index')
@login_required
def index():
    return render_template('index.html')

@app.route('/qr_generator')
@app.route('/qr-generator')
@login_required
def qr_generator():
    return render_template('qr_generator.html', stats=qr_stats)

@app.route('/generate_qr', methods=['POST'])
@limiter.limit(app.config['RATELIMIT_GENERATE'])
@login_required
def generate_qr():
    try:
        total_timer = Timer().start()
        
        nama = request.form['nama'].strip()
        userid = request.form['userid'].strip() # Algoritma default diubah ke RSA
        alg = request.form.get('alg', 'RSA') # Default ke RSA sesuai Judul Jurnal
        
        if not nama or not userid:
            flash('Nama dan ID harus diisi!', 'warning')
            return redirect(url_for('qr_generator'))
        
        wib = timezone(timedelta(hours=7))
        data = {
            "nama": nama,
            "id": userid,
            "timestamp": datetime.now(wib).isoformat(),
            "nonce": generate_qr_nonce()
        }
        
        data_timer = Timer().start()
        qr_temp = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_Q, box_size=2, border=1)
        qr_temp.add_data(json.dumps(data, separators=(',', ':')))
        qr_temp.make(fit=True)
        data["qr_modules"] = qr_temp.modules_count
        data["qr_version"] = qr_temp.version
        data_time = data_timer.stop()
        
        serialized = json.dumps(data, sort_keys=True)
        hash_digest = SHA256.new(serialized.encode('utf-8'))
        
        if alg == 'RSA':
            signer = pss.new(private_key, salt_bytes=8) # Inovasi: Salt 8 bytes (Adapted RSA-PSS)
        else:
            # Default ECDSA
            signer = DSS.new(ecdsa_private_key, 'fips-186-3')
        
        sign_timer = Timer().start()
        signature = signer.sign(hash_digest)
        sign_time = sign_timer.stop()
        
        payload = {
            "data": data,
            "signature": base64.b64encode(signature).decode('utf-8'),
            "alg": alg,
            "metadata": { # Tambahkan metadata agar sesuai Appendix B jurnal
                "algorithm": "RSA-PSS" if alg == "RSA" else "ECDSA",
                "key_size": 2048 if alg == "RSA" else 256,
                "hash_function": "SHA-256",
                "salt_length": 8 if alg == "RSA" else 0,
                "mgf": "MGF1-SHA256" if alg == "RSA" else "N/A"
            }
        }
        
        qr_timer = Timer().start()
        # BUAT QR CODE DENGAN URL VERIFIKASI YANG DIOPTIMALKAN UNTUK KAMERA HP
        filename = f"qr_{userid}_{secrets.token_hex(4)}.png"
        filename = sanitize_filename(filename)
        qr_path = os.path.join(app.config['QR_FOLDER'], filename)
        # Gunakan fungsi baru untuk membuat QR dengan URL yang dioptimalkan
        img, qr_url, encoded_data = create_qr_with_url(payload, qr_path)
        qr_time = qr_timer.stop()
        
        # Simpan juga ke folder upload dengan kompresi
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        img.save(upload_path, optimize=True, quality=85)  # KOMPRESI
        
        save_timer = Timer().start()
        data_filename = filename.replace('.png', '.json')
        data_path = os.path.join(app.config['DATA_FOLDER'], data_filename)
        save_qr_record(data_path, data)
        save_time = save_timer.stop()
        
        total_time = total_timer.stop()
        
        img_pil = Image.open(qr_path)
        width, height = img_pil.size
        file_size_kb = os.path.getsize(qr_path) / 1024
        
        # Tambahkan statistik dengan data yang benar
        qr_stats.add_generate_stat(total_time, file_size_kb, (width, height))
        
        # PERBAIKAN: Gunakan datetime.now(timezone.utc) untuk menghindari deprecation warning
        log_row = [
            "Tunggal", datetime.now(timezone.utc).isoformat(), data['nama'], data['id'],
            data['qr_version'], data['qr_modules'], f"{width}x{height}",
            f"{file_size_kb:.2f}", len(payload['signature']),
            f"{data_time:.6f}", f"{sign_time:.6f}", f"{qr_time:.6f}",
            f"{save_time:.6f}", f"{total_time:.6f}"
        ]
        _log_to_csv_extended(app.config['CSV_LOG_GENERATE'], log_row)
        
        # Update chart di background thread agar tidak memblokir response
        chart_thread = threading.Thread(target=_update_evaluation_chart)
        chart_thread.daemon = True
        chart_thread.start()
        
        app.logger.info(f"QR berhasil digenerate untuk {nama} ({userid}) dalam {total_time:.4f} detik")
        
        # Tampilkan informasi URL verifikasi
        return render_template("hasil.html",
            qr_path=f"qr/{filename}",
            qr_url=qr_url, # Kirim URL ke template
            encoded_data=encoded_data, # Kirim data encoded
            short_url=f"{qr_url[:50]}...{qr_url[-10:]}" if len(qr_url) > 60 else qr_url, # Potong URL untuk display visual yang rapi
            file_size=f"{file_size_kb:.2f} KB",
            resolution=f"{width} x {height} px",
            modules=f"{data['qr_modules']} x {data['qr_modules']} modul",
            version=data['qr_version'],
            data_time=f"{data_time:.3f} detik",
            sign_time=f"{sign_time:.3f} detik",
            qr_time=f"{qr_time:.3f} detik",
            save_time=f"{save_time:.3f} detik",
            total_time=f"{total_time:.3f} detik",
            signature_length=len(payload['signature']),
            algorithm=alg,
            stats=qr_stats
        )
        
    except Exception as e:
        app.logger.error(f"Error generate_qr: {e}")
        flash(f'Error saat generate QR: {str(e)}', 'danger')
        return redirect(url_for('qr_generator'))

@app.route('/scanner')
@login_required
def scanner():
    if not is_verification_feature_enabled():
        return verification_disabled_view('Halaman verifikasi saat ini dinonaktifkan sementara.')
    return render_template('scanner.html', hasil_tunggal=None, hasil_massal=None)

@app.route('/verify_qr', methods=['POST'])
def verify_qr():
    if not is_verification_feature_enabled():
        return verification_disabled_view('Verifikasi QR sedang dinonaktifkan sementara.')

    try:
        total_timer = Timer().start()
        
        if 'qrfile' not in request.files:
            flash('Tidak ada file yang diunggah', 'warning')
            return redirect(url_for('scanner'))
        
        uploaded_file = request.files['qrfile']
        if uploaded_file.filename == '':
            flash('Tidak ada file yang dipilih', 'warning')
            return redirect(url_for('scanner'))
        
        if not allowed_file(uploaded_file.filename):
            flash('Format file tidak diizinkan', 'danger')
            return redirect(url_for('scanner'))
        
        is_valid, error_msg = validate_single_upload(uploaded_file)
        if not is_valid:
            flash(error_msg, 'danger')
            return redirect(url_for('scanner'))
        
        load_timer = Timer().start()
        filename = sanitize_filename(uploaded_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        uploaded_file.save(file_path)
        load_time = load_timer.stop()
        
        decode_timer = Timer().start()
        image = cv2.imread(file_path)
        if image is None:
            flash('File gambar tidak valid', 'danger')
            return render_template('scanner.html', 
                                 hasil_tunggal={"valid": False, "message": "File gambar tidak valid"},
                                 hasil_massal=None)
        
        qr_data = decode(image)
        if not qr_data:
            flash('Tidak dapat membaca QR code', 'warning')
            return render_template('scanner.html',
                                 hasil_tunggal={"valid": False, "message": "QR tidak terbaca"},
                                 hasil_massal=None)
        decode_time = decode_timer.stop()
        
        try:
            raw = qr_data[0].data.decode('utf-8')
            payload = extract_payload_from_qr_string(raw)
            if not payload:
                raise ValueError("Format QR tidak sesuai")
        except Exception as e:
            app.logger.warning(f"QR tidak valid: {e}")
            return render_template('scanner.html',
                                 hasil_tunggal={"valid": False, "message": "Format QR tidak valid"},
                                 hasil_massal=None)
        
        if "data" not in payload or "signature" not in payload:
            return render_template('scanner.html', # Algoritma default diubah ke RSA
                                 hasil_tunggal={"valid": False, "message": "Struktur QR tidak lengkap"},
                                 hasil_massal=None)
        
        data = payload["data"]
        signature_b64 = payload["signature"]
        alg = payload.get("alg", "RSA")
        
        try:
            signature = base64.b64decode(signature_b64)
        except Exception:
            return render_template('scanner.html', # Algoritma default diubah ke RSA
                                 hasil_tunggal={"valid": False, "message": "Signature tidak valid"},
                                 hasil_massal=None)
        
        serialized = json.dumps(data, sort_keys=True)
        hash_obj = SHA256.new(serialized.encode('utf-8'))
        
        verify_timer = Timer().start()
        if alg == 'RSA':
            try:
                verifier = pss.new(public_key, salt_bytes=8)
                verifier.verify(hash_obj, signature)
                signature_valid = True
                sig_error = "" # RSA succeeded, no error message
            except (ValueError, TypeError):
                # Fallback ke ECDSA jika RSA gagal
                try:
                    verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                    verifier.verify(hash_obj, signature)
                    signature_valid = True
                    # ECDSA succeeded, but RSA (primary) failed, so set specific error message
                    sig_error = "signature tidak valid (ECDSA)"
                except (ValueError, TypeError):
                    # Both RSA and ECDSA failed
                    sig_error = "signature tidak valid (ECDSA)"
                    signature_valid = False
        elif alg == 'ECDSA':
            try:
                verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                verifier.verify(hash_obj, signature)
                signature_valid = True
                sig_error = "" # ECDSA succeeded, no error message
            except (ValueError, TypeError):
                sig_error = "signature tidak valid (ECDSA)"
                signature_valid = False
        else:
            sig_error = "signature tidak valid (algoritma tidak diketahui)"
            signature_valid = False
            
        verify_time = verify_timer.stop()
        
        changed_fields = {}
        original_data = None
        message = ""
        valid = False
        
        db_timer = Timer().start()
        verification_result = classify_qr_verification(data, signature_valid, sig_error)
        original_data = verification_result["original_data"]
        changed_fields = verification_result["changed_fields"]
        message = verification_result["message"]
        valid = verification_result["valid"]
        db_time = db_timer.stop()
        
        total_time = total_timer.stop()
        
        qr_stats.add_verify_stat(total_time, success=valid)
        
        # PERBAIKAN: Gunakan datetime.now(timezone.utc) untuk menghindari deprecation warning
        log_row = [
            "Tunggal", datetime.now(timezone.utc).isoformat(), filename, message,
            data.get('nama', '-'), data.get('id', '-'),
            json.dumps(changed_fields, ensure_ascii=False) if changed_fields else '-',
            f"{load_time:.6f}", f"{decode_time:.6f}", f"{verify_time:.6f}",
            f"{db_time:.6f}", f"{total_time:.6f}"
        ]
        _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
        
        app.logger.info(f"Verifikasi QR {filename}: {message} - Total waktu: {total_time:.4f} detik")
        
        return render_template(
            "scanner.html",
            hasil_tunggal={
                "valid": valid,
                "data": data,
                "file_info": {
                    "load_time": f"{load_time:.3f} detik",
                    "decode_time": f"{decode_time:.3f} detik",
                    "verify_time": f"{verify_time:.3f} detik",
                    "db_time": f"{db_time:.3f} detik",
                    "total_time": f"{total_time:.3f} detik"
                },
                "message": message,
                "perubahan": changed_fields if changed_fields else None,
                "signature_valid": signature_valid,
                "original_data": original_data,
                "algorithm": alg,
                "stats": qr_stats
            },
            hasil_massal=None
        )
        
    except Exception as e:
        app.logger.error(f"Error verify_qr: {e}")
        flash(f'Error saat verifikasi: {str(e)}', 'danger')
        return redirect(url_for('scanner'))

# ==================== ROUTES UNTUK SCANNER LANGSUNG & KAMERA HP (DIOPTIMALKAN) ====================
@app.route('/verify_direct')
def verify_direct_page():
    """Halaman untuk verifikasi langsung dari scanner"""
    if not is_verification_feature_enabled():
        return verification_disabled_view('Scanner langsung sedang dinonaktifkan sementara.')
    return render_template('verify_direct.html')

@app.route('/scan_hp')
@app.route('/scanner_hp')
@app.route('/mobile_scan')
def scan_hp():
    """Halaman scanner HP yang otomatis membuka URL verifikasi setelah QR terbaca."""
    if not is_verification_feature_enabled():
        return verification_disabled_view('Kamera HP untuk verifikasi sedang dinonaktifkan sementara.')
    return render_template('scan_hp.html')

@app.route('/api/resolve_scan_target', methods=['POST'])
@limiter.limit("120 per minute")
def resolve_scan_target():
    """Validasi hasil scan dan kembalikan URL verifikasi internal untuk redirect."""
    if not is_verification_feature_enabled():
        return jsonify({'success': False, 'error': 'Fitur verifikasi sedang dinonaktifkan sementara.'}), 503

    try:
        payload = request.get_json(silent=True) or {}
        target_url = resolve_scan_verification_target(payload.get('qr_string', ''))
        return jsonify({
            'success': True,
            'target_url': target_url
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        app.logger.error(f"Error resolve_scan_target: {e}")
        return jsonify({
            'success': False,
            'error': 'Gagal memproses hasil scan'
        }), 500

@app.route('/api/decode_qr_string', methods=['POST'])
@limiter.limit("120 per minute")  # Limit khusus yang lebih besar untuk scanner kamera
def decode_qr_string():
    """API untuk mendecode data QR dari string (dari scanner atau kamera)"""
    if not is_verification_feature_enabled():
        return jsonify({'success': False, 'error': 'Fitur verifikasi sedang dinonaktifkan sementara.'}), 503

    try:
        data = request.get_json()
        if not data or 'qr_string' not in data:
            return jsonify({
                'success': False,
                'error': 'Data QR tidak ditemukan'
            })

        qr_string = data['qr_string']

        payload = extract_payload_from_qr_string(qr_string)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Format QR tidak dikenali'
            })
        
        # Validasi payload
        if not payload or "data" not in payload or "signature" not in payload:
            return jsonify({
                'success': False,
                'error': 'Struktur QR tidak lengkap'
            })
        
        data = payload["data"]
        signature_b64 = payload["signature"]
        alg = payload.get("alg", "RSA")
        
        try:
            signature = base64.b64decode(signature_b64)
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Signature tidak valid'
            })
        
        # Verifikasi signature
        serialized = json.dumps(data, sort_keys=True)
        hash_obj = SHA256.new(serialized.encode('utf-8'))

        if alg == 'RSA':
            try:
                verifier = pss.new(public_key, salt_bytes=8)
                verifier.verify(hash_obj, signature)
                signature_valid = True
                sig_error = ""
            except (ValueError, TypeError):
                # Fallback ke ECDSA
                try:
                    verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                    verifier.verify(hash_obj, signature)
                    signature_valid = True
                    sig_error = "signature tidak valid (ECDSA)"
                except (ValueError, TypeError):
                    sig_error = "signature tidak valid (ECDSA)"
                    signature_valid = False
        elif alg == 'ECDSA':
            try:
                verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                verifier.verify(hash_obj, signature)
                signature_valid = True
                sig_error = ""
            except (ValueError, TypeError):
                sig_error = "signature tidak valid (ECDSA)"
                signature_valid = False
        else:
            sig_error = "signature tidak valid (algoritma tidak diketahui)"
            signature_valid = False

        # Cek database dan replay attack dengan logika yang diperbaiki
        changed_fields = {}
        original_data = None
        message = ""
        valid = False
        is_replay = False

        verification_result = classify_qr_verification(data, signature_valid, sig_error)
        original_data = verification_result["original_data"]
        changed_fields = verification_result["changed_fields"]
        message = verification_result["message"]
        valid = verification_result["valid"]
        is_replay = verification_result["is_replay"]
        
        # Log verifikasi
        # PERBAIKAN: Gunakan datetime.now(timezone.utc) untuk menghindari deprecation warning
        log_row = [
            "Direct/Scanner", datetime.now(timezone.utc).isoformat(), "direct_scan", message,
            data.get('nama', '-'), data.get('id', '-'),
            json.dumps(changed_fields, ensure_ascii=False) if changed_fields else '-',
            "0.000000", "0.000000", "0.100000",
            "0.050000", "0.150000"
        ]
        _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)

        # Update statistik
        qr_stats.add_verify_stat(0.15, success=valid)  # Estimasi waktu
        
        return jsonify({
            'success': True,
            'valid': valid,
            'signature_valid': signature_valid,
            'message': message,
            'data': data,
            'original_data': original_data,
            'changed_fields': changed_fields if changed_fields else None,
            'is_replay': is_replay,
            'algorithm': alg,
            'verification_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        app.logger.error(f"Error in decode_qr_string: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/v/<token>', methods=['GET', 'HEAD'])
def verify_short_qr_token(token):
    """Endpoint URL pendek untuk verifikasi QR RSA-PSS dari kamera HP."""
    if not is_verification_feature_enabled():
        if request.method == 'HEAD':
            return Response(status=503)
        return verification_disabled_view('URL verifikasi sedang dinonaktifkan sementara.')

    if request.method == 'HEAD':
        return direct_verify_probe_response(200 if load_verify_payload(token) else 404)

    payload = load_verify_payload(token)
    if not payload:
        total_timer = Timer().start()
        total_time = total_timer.stop()
        log_row = [
            "Kamera HP", datetime.now(timezone.utc).isoformat(), "url_scan", "❌ Token QR tidak ditemukan",
            "-", "-", "-",
            "0.000000", "0.000000", "0.000000", "0.000000", f"{total_time:.6f}"
        ]
        _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
        qr_stats.add_verify_stat(total_time, success=False)

        return render_template('verify_result.html',
            valid=False,
            message="❌ Token QR tidak ditemukan atau payload sudah tidak tersedia",
            data=None,
            verification_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source="Kamera HP"
        )

    encoded_data = encode_payload_for_verify_url(payload)
    return verify_qr_data(encoded_data)

@app.route('/verify/<path:encoded_data>', methods=['GET', 'HEAD'])
def verify_qr_data(encoded_data):
    """Endpoint untuk verifikasi langsung dari URL (untuk kamera HP)"""
    if not is_verification_feature_enabled():
        if request.method == 'HEAD':
            return Response(status=503)
        return verification_disabled_view('URL verifikasi sedang dinonaktifkan sementara.')

    try:
        if request.method == 'HEAD':
            return direct_verify_probe_response()

        total_timer = Timer().start()

        try:
            payload = decode_payload_from_verify_url(encoded_data)
        except Exception:
            total_time = total_timer.stop()
            log_row = [
                "Kamera HP", datetime.now(timezone.utc).isoformat(), "url_scan", "❌ Format QR tidak valid",
                "-", "-", "-",
                "0.000000", "0.000000", "0.000000", "0.000000", f"{total_time:.6f}"
            ]
            _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
            qr_stats.add_verify_stat(total_time, success=False)

            return render_template('verify_result.html',
                valid=False,
                message="❌ Format QR tidak valid",
                data=None,
                verification_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                source="Kamera HP"
            )
        
        # Proses verifikasi
        data = payload.get("data", {})
        signature_b64 = payload.get("signature", "") # Algoritma default diubah ke RSA
        alg = payload.get("alg", "RSA")
        # Setiap GET verifikasi harus melewati nonce store agar scan ulang langsung menjadi replay.
        
        # Verifikasi signature
        verify_timer = Timer().start()
        serialized = json.dumps(data, sort_keys=True)
        hash_obj = SHA256.new(serialized.encode('utf-8'))
        
        signature_valid = False
        sig_error = ""
        try:
            signature = base64.b64decode(signature_b64)
            if alg == 'RSA':
                try:
                    verifier = pss.new(public_key, salt_bytes=8)
                    verifier.verify(hash_obj, signature)
                    signature_valid = True
                    sig_error = ""
                except (ValueError, TypeError):
                    # Fallback
                    try:
                        verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                        verifier.verify(hash_obj, signature)
                        signature_valid = True
                        sig_error = "signature tidak valid (ECDSA)"
                    except (ValueError, TypeError):
                        sig_error = "signature tidak valid (ECDSA)"
                        signature_valid = False
            elif alg == 'ECDSA':
                try:
                    verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                    verifier.verify(hash_obj, signature)
                    signature_valid = True
                    sig_error = ""
                except (ValueError, TypeError):
                    sig_error = "signature tidak valid (ECDSA)"
                    signature_valid = False
            else:
                sig_error = "signature tidak valid (algoritma tidak diketahui)"
                signature_valid = False
        except Exception:
            sig_error = "signature tidak valid (format error)"
            signature_valid = False
        verify_time = verify_timer.stop()
        
        # Cek database dengan logika yang diperbaiki
        db_timer = Timer().start()
        changed_fields = {}
        original_data = None
        message = ""
        valid = False
        
        verification_result = classify_qr_verification(data, signature_valid, sig_error)
        original_data = verification_result["original_data"]
        changed_fields = verification_result["changed_fields"]
        message = verification_result["message"]
        valid = verification_result["valid"]
        db_time = db_timer.stop()
        
        total_time = total_timer.stop()
        
        # Log verifikasi
        log_row = [
            "Kamera HP", datetime.now(timezone.utc).isoformat(), "url_scan", message,
            data.get('nama', '-'), data.get('id', '-'),
            json.dumps(changed_fields, ensure_ascii=False) if changed_fields else '-',
            "0.000000", "0.000000", f"{verify_time:.6f}",
            f"{db_time:.6f}", f"{total_time:.6f}"
        ]
        _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
        
        # Update statistik
        qr_stats.add_verify_stat(total_time, success=valid)
        
        # Tampilkan hasil
        result_context = dict(
            valid=valid,
            message=message,
            data=data,
            original_data=original_data,
            changed_fields=changed_fields,
            signature_valid=signature_valid,
            algorithm=alg,
            verification_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source="Kamera HP"
        )
        response = make_response(render_template('verify_result.html', **result_context))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
        
    except Exception as e:
        try:
            total_time = total_timer.stop()
            log_row = [
                "Kamera HP", datetime.now(timezone.utc).isoformat(), "url_scan", f"❌ Error: {str(e)[:50]}",
                "-", "-", "-", "0.000000", "0.000000", "0.000000", "0.000000", f"{total_time:.6f}"
            ]
            _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
        except: pass
        return render_template('verify_result.html',
            valid=False,
            message=f"❌ Error: {str(e)}",
            data=None,
            verification_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source="Kamera HP"
        )

@app.route('/generate_scanner_qr')
def generate_scanner_qr():
    """Generate QR Code untuk testing scanner dengan URL yang dioptimalkan"""
    try:
        nama = request.args.get('nama', 'Test User')
        userid = request.args.get('id', 'test_001')
        
        wib = timezone(timedelta(hours=7))
        data = {
            "nama": nama,
            "id": userid,
            "timestamp": datetime.now(wib).isoformat(),
            "nonce": generate_qr_nonce()
        } # Algoritma default diubah ke RSA
        
        serialized = json.dumps(data, sort_keys=True)
        hash_digest = SHA256.new(serialized.encode('utf-8'))
        signer = pss.new(private_key, salt_bytes=8)
        signature = signer.sign(hash_digest)
        
        payload = {
            "data": data,
            "signature": base64.b64encode(signature).decode('utf-8'),
            "alg": "RSA",
            "metadata": {
                "algorithm": "RSA-PSS",
                "key_size": 2048,
                "hash_function": "SHA-256",
                "salt_length": 8,
                "mgf": "MGF1-SHA256"
            }
        }
        
        # Buat URL verifikasi
        qr_url, encoded_data = generate_verification_url(payload)
        
        # OPTIMASI: Gunakan parameter yang sama untuk konsistensi
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,  # 15% error correction
            box_size=3,  # Sedikit lebih besar untuk testing scanner (tapi masih lebih kecil)
            border=1
        )
        qr.add_data(qr_url)  # Gunakan URL, bukan JSON
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white", contrast=1.3)
        
        # Simpan ke memory dengan kompresi
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True, quality=85)
        img_bytes.seek(0)
        
        return send_file(img_bytes, mimetype='image/png', 
                        download_name=f'qr_scanner_{userid}.png')
        
    except Exception as e:
        app.logger.error(f"Error generate_scanner_qr: {e}")
        return "Error generating QR", 500

@app.route('/api/get_scanner_test_data')
def get_scanner_test_data():
    """API untuk mendapatkan data test untuk scanner"""
    try:
        wib = timezone(timedelta(hours=7))
        data = {
            "nama": "Test Scanner User",
            "id": "scanner_test_" + secrets.token_hex(4),
            "timestamp": datetime.now(wib).isoformat(),
            "nonce": generate_qr_nonce()
        } # Algoritma default diubah ke RSA
        
        serialized = json.dumps(data, sort_keys=True)
        hash_digest = SHA256.new(serialized.encode('utf-8'))
        signer = pss.new(private_key, salt_bytes=8)
        signature = signer.sign(hash_digest)
        
        payload = {
            "data": data,
            "signature": base64.b64encode(signature).decode('utf-8'),
            "alg": "RSA",
            "metadata": {
                "algorithm": "RSA-PSS",
                "key_size": 2048,
                "hash_function": "SHA-256",
                "salt_length": 8,
                "mgf": "MGF1-SHA256"
            }
        }
        
        # Simpan ke database untuk verifikasi
        filename = f"qr_{data['id']}.json"
        data_path = os.path.join(app.config['DATA_FOLDER'], filename)
        save_qr_record(data_path, data)
        
        # Buat URL verifikasi
        qr_url, encoded_data = generate_verification_url(payload)
        
        return jsonify({
            'success': True,
            'qr_data': json.dumps(payload),
            'qr_url': qr_url,
            'qr_data_b64': encoded_data,
            'short_url': qr_url,  # URL pendek untuk display
            'data': data
        })
        
    except Exception as e:
        app.logger.error(f"Error get_scanner_test_data: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== ROUTES MODIFIKASI QR CODE ====================
@app.route('/modify_qr_page')
@login_required
def modify_qr_page():
    """Halaman utama modifikasi QR Code"""
    try:
        return render_template('modify_qr.html', stats=qr_stats)
    except Exception as e:
        app.logger.error(f"Error in modify_qr_page route: {e}")
        flash(f'Error saat mengakses halaman modifikasi: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/modify_upload', methods=['POST'])
def modify_upload():
    """Upload QR Code untuk dimodifikasi - DIPERBAIKI UNTUK MENANGANI URL DAN JSON"""
    try:
        app.logger.info("Modify upload endpoint dipanggil")
        
        if 'qrfile' not in request.files:
            flash('Tidak ada file yang diunggah', 'warning')
            return redirect(url_for('modify_qr_page'))
        
        file = request.files['qrfile']
        if file.filename == '':
            flash('Tidak ada file yang dipilih', 'warning')
            return redirect(url_for('modify_qr_page'))
        
        app.logger.info(f"File diterima: {file.filename}")
        
        # Validasi ekstensi file
        if not allowed_file(file.filename):
            flash('Format file tidak diizinkan. Hanya PNG, JPG, JPEG, GIF yang diperbolehkan.', 'danger')
            return redirect(url_for('modify_qr_page'))
        
        # Validasi ukuran file (maksimal 10MB)
        try:
            current_pos = file.tell()
            file.seek(0, 2)  # Pindah ke akhir file
            file_size = file.tell()
            file.seek(current_pos)  # Kembali ke posisi awal
        except Exception as e:
            app.logger.error(f"Error membaca ukuran file: {e}")
            flash('Error membaca file', 'danger')
            return redirect(url_for('modify_qr_page'))
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            flash(f'File terlalu besar (maksimal 10MB per file). Ukuran file: {file_size/1024/1024:.2f}MB', 'danger')
            return redirect(url_for('modify_qr_page'))
        
        # Simpan file sementara
        filename = sanitize_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'modify_temp_' + filename)
        
        try:
            file.save(temp_path)
            app.logger.info(f"File disimpan sementara: {temp_path}")
        except Exception as e:
            app.logger.error(f"Error menyimpan file: {e}")
            flash('Error menyimpan file', 'danger')
            # Pastikan tidak ada variabel yang tidak terdefinisi
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return redirect(url_for('modify_qr_page'))
        
        # Decode QR Code dengan support untuk URL dan JSON
        try:
            image = cv2.imread(temp_path)
            if image is None:
                flash('File gambar tidak valid atau corrupt', 'danger')
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return redirect(url_for('modify_qr_page'))
            
            qr_data = decode(image)
            if not qr_data:
                flash('Tidak dapat membaca QR code dari gambar', 'warning')
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return redirect(url_for('modify_qr_page'))
            
            raw = qr_data[0].data.decode('utf-8')
            app.logger.info(f"Data QR mentah: {raw[:100]}...")  # Log sebagian data
            
            payload = extract_payload_from_qr_string(raw)
            if payload:
                app.logger.info("Berhasil mengekstrak payload QR")
            else:
                flash('Format QR tidak valid. Bukan JSON atau URL yang dikenali.', 'danger')
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return redirect(url_for('modify_qr_page'))
            
            # Validasi payload
            if not payload:
                flash('Tidak dapat mengekstrak data dari QR', 'danger')
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return redirect(url_for('modify_qr_page'))
            
            if "data" not in payload or "signature" not in payload:
                flash('Struktur QR tidak lengkap (harus ada data dan signature)', 'danger')
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return redirect(url_for('modify_qr_page'))
            
            data = payload["data"]
            signature = payload["signature"]
            
            app.logger.info(f"Berhasil extract data: {data.get('nama', 'Unknown')} ({data.get('id', 'No ID')})")
            
        except Exception as e:
            app.logger.error(f"Error decode QR: {e}", exc_info=True)
            flash(f'Error membaca QR Code: {str(e)}', 'danger')
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return redirect(url_for('modify_qr_page'))
        
        # Hapus file sementara
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                app.logger.info("File sementara dihapus")
        except Exception as e:
            app.logger.warning(f"Tidak bisa hapus file sementara: {e}")
        
        # Simpan ke session untuk digunakan di form modifikasi
        session['modify_original_data'] = data
        session['modify_original_signature'] = signature
        session['modify_filename'] = filename
        
        app.logger.info(f"Berhasil mempersiapkan data untuk modifikasi: {data.get('nama', 'Unknown')}")
        
        # Render form modifikasi - PERBAIKAN: Gunakan template yang benar
        return render_template('modify_form.html', 
                             data=data, 
                             signature=signature)
        
    except Exception as e:
        app.logger.error(f"Error in modify_upload: {e}", exc_info=True)
        flash(f'Error saat mengunggah QR: {str(e)}', 'danger')
        return redirect(url_for('modify_qr_page'))

@app.route('/apply_modification', methods=['POST'])
def apply_modification():
    """Menerapkan modifikasi dan menghasilkan QR Code palsu"""
    try:
        # Periksa apakah ada data di session
        if 'modify_original_data' not in session:
            flash('Sesi tidak valid. Silakan unggah QR Code lagi.', 'danger')
            return redirect(url_for('modify_qr_page'))
        
        original_data = session.get('modify_original_data')
        original_signature = session.get('modify_original_signature')
        
        # Inisialisasi data modifikasi
        modified_data = original_data.copy()
        modifications = {
            'nama_changed': False,
            'id_changed': False,
            'nonce_changed': False,
            'timestamp_changed': False,
            'signature_modified': False
        }
        
        # Modifikasi nama
        if 'modify_nama' in request.form and request.form['modify_nama'] == 'yes':
            nama_modes = request.form.getlist('nama_modes')
            new_nama = original_data['nama']
            
            if 'random' in nama_modes:
                first_names = ["John", "Jane", "Bob", "Alice", "Charlie", "Diana"]
                last_names = ["Smith", "Doe", "Johnson", "Williams", "Brown", "Jones"]
                new_nama = f"{random.choice(first_names)} {random.choice(last_names)}"
                modifications['nama_changed'] = True
                
            if 'reverse' in nama_modes:
                new_nama = original_data['nama'][::-1]
                modifications['nama_changed'] = True
                
            if 'uppercase' in nama_modes:
                new_nama = original_data['nama'].upper()
                modifications['nama_changed'] = True
                
            if 'lowercase' in nama_modes:
                new_nama = original_data['nama'].lower()
                modifications['nama_changed'] = True
                
            if 'add_text' in nama_modes:
                suffix = request.form.get('nama_suffix', '')
                new_nama = original_data['nama'] + suffix
                modifications['nama_changed'] = True
                
            if 'custom' in nama_modes:
                custom_nama = request.form.get('custom_nama', '')
                if custom_nama:
                    new_nama = custom_nama
                    modifications['nama_changed'] = True
            
            modified_data['nama'] = new_nama
        
        # Modifikasi ID
        if 'modify_id' in request.form and request.form['modify_id'] == 'yes':
            id_modes = request.form.getlist('id_modes')
            new_id = original_data['id']
            
            if 'random' in id_modes:
                new_id = f"fake_{secrets.token_hex(6)}"
                modifications['id_changed'] = True
                
            if 'increment' in id_modes:
                try:
                    # Coba ekstrak angka dari ID
                    import re
                    numbers = re.findall(r'\d+', original_data['id'])
                    if numbers:
                        last_number = int(numbers[-1])
                        new_id = original_data['id'].replace(numbers[-1], str(last_number + 1))
                    else:
                        new_id = original_data['id'] + '_1'
                    modifications['id_changed'] = True
                except:
                    pass
                    
            if 'decrement' in id_modes:
                try:
                    import re
                    numbers = re.findall(r'\d+', original_data['id'])
                    if numbers:
                        last_number = int(numbers[-1])
                        new_id = original_data['id'].replace(numbers[-1], str(last_number - 1))
                    else:
                        new_id = original_data['id'] + '_0'
                    modifications['id_changed'] = True
                except:
                    pass
            
            if 'custom' in id_modes:
                custom_id = request.form.get('custom_id', '')
                if custom_id:
                    new_id = custom_id
                    modifications['id_changed'] = True
            
            modified_data['id'] = new_id
        
        # Modifikasi nonce
        if 'modify_nonce' in request.form and request.form['modify_nonce'] == 'yes':
            nonce_modes = request.form.getlist('nonce_modes')
            new_nonce = original_data['nonce']
            
            if 'random' in nonce_modes:
                new_nonce = generate_qr_nonce()
                modifications['nonce_changed'] = True
                
            if 'increment_hex' in nonce_modes:
                try:
                    new_nonce = hex(int(original_data['nonce'], 16) + 1)[2:].zfill(8)
                    modifications['nonce_changed'] = True
                except:
                    new_nonce = generate_qr_nonce()
                    modifications['nonce_changed'] = True
                    
            if 'zero' in nonce_modes:
                new_nonce = '0' * 8
                modifications['nonce_changed'] = True
                
            if 'reuse' in nonce_modes:
                # Gunakan nonce yang sama (untuk replay attack)
                new_nonce = original_data['nonce']
                modifications['nonce_changed'] = True
                
            if 'custom' in nonce_modes:
                custom_nonce = request.form.get('custom_nonce', '')
                if custom_nonce:
                    new_nonce = custom_nonce
                    modifications['nonce_changed'] = True
            
            modified_data['nonce'] = new_nonce
        
        # Modifikasi timestamp
        if 'modify_timestamp' in request.form and request.form['modify_timestamp'] == 'yes':
            timestamp_modes = request.form.getlist('timestamp_modes')
            new_timestamp = original_data['timestamp']
            
            if 'future' in timestamp_modes:
                try:
                    dt = datetime.fromisoformat(original_data['timestamp'].replace('Z', '+00:00'))
                    new_dt = dt + timedelta(days=30)
                    new_timestamp = new_dt.isoformat()
                    modifications['timestamp_changed'] = True
                except:
                    pass
                    
            if 'past' in timestamp_modes:
                try:
                    dt = datetime.fromisoformat(original_data['timestamp'].replace('Z', '+00:00'))
                    new_dt = dt - timedelta(days=30)
                    new_timestamp = new_dt.isoformat()
                    modifications['timestamp_changed'] = True
                except:
                    pass
                    
            if 'current' in timestamp_modes:
                wib = timezone(timedelta(hours=7))
                new_timestamp = datetime.now(wib).isoformat()
                modifications['timestamp_changed'] = True
                
            if 'custom' in timestamp_modes:
                custom_date = request.form.get('custom_date')
                custom_time = request.form.get('custom_time')
                if custom_date and custom_time:
                    new_timestamp = f"{custom_date}T{custom_time}:00+07:00"
                    modifications['timestamp_changed'] = True
                elif custom_date:
                    new_timestamp = f"{custom_date}T00:00:00+07:00"
                    modifications['timestamp_changed'] = True
            
            modified_data['timestamp'] = new_timestamp
        
        # Tambahan fields (JSON)
        additional_fields = request.form.get('additional_fields', '')
        if additional_fields:
            try:
                extra = json.loads(additional_fields)
                modified_data.update(extra)
            except:
                pass
        
        # Pilihan signature
        signature_choice = request.form.get('signature_choice', 'keep')
        new_signature = create_fake_signature(modified_data, signature_choice, original_signature)
        
        if signature_choice != 'keep':
            modifications['signature_modified'] = True
        
        # Buat payload baru
        payload = {
            "data": modified_data,
            "signature": new_signature,
            "alg": "RSA",
            "metadata": {
                "algorithm": "RSA-PSS",
                "key_size": 2048,
                "hash_function": "SHA-256",
                "salt_length": 8,
                "mgf": "MGF1-SHA256"
            }
        }
        
        # ===== BUAT URL VERIFIKASI UNTUK QR CODE PALSU =====
        qr_url, encoded_data = generate_verification_url(payload)
        
        # Generate QR Code palsu DENGAN URL verifikasi
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=2,
            border=1
        )
        qr.add_data(qr_url)  # Gunakan URL, bukan JSON langsung
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Simpan QR Code palsu
        fake_filename = f"fake_{secrets.token_hex(4)}.png"
        fake_path = os.path.join(app.config['FAKE_QR_FOLDER'], fake_filename)
        img.save(fake_path, optimize=True, quality=85)
        
        # ===== KIRIM qr_url KE TEMPLATE =====
        fake_qr_static_path = f"qr_fake/{fake_filename}"
        
        # Dapatkan info file
        img_pil = Image.open(fake_path)
        width, height = img_pil.size
        file_size = os.path.getsize(fake_path) / 1024
        
        # Tentukan jenis fraud
        fraud_type = "Data Palsu"
        if modifications['nonce_changed'] and original_data['nonce'] == modified_data['nonce']:
            fraud_type = "Replay Attack"
        elif modifications['signature_modified']:
            if signature_choice == 'corrupt':
                fraud_type = "Signature Corrupt"
            elif signature_choice == 'remove':
                fraud_type = "No Signature"
            else:
                fraud_type = "Signature Tampering"
        
        # Catat log
        log_modification(original_data, modified_data, modifications, fake_qr_static_path)
        
        # Update statistik (opsional)
        qr_stats.add_generate_stat(0, file_size, (width, height))
        
        # Hapus data dari session
        session.pop('modify_original_data', None)
        session.pop('modify_original_signature', None)
        session.pop('modify_filename', None)
        
        # Tampilkan halaman hasil
        return render_template('modify_result.html',
                               original_data=original_data,
                               modified_data=modified_data,
                               fake_qr_path=fake_qr_static_path,
                               resolution=f"{width}x{height}",
                               file_size=f"{file_size:.2f} KB",
                               fraud_type=fraud_type,
                               signature_note=signature_choice,
                               signature_choice=signature_choice,
                               modifications=modifications,
                               qr_url=qr_url)
        
    except Exception as e:
        app.logger.error(f"Error in apply_modification: {e}", exc_info=True)
        flash(f'Error saat memproses modifikasi: {str(e)}', 'danger')
        return redirect(url_for('modify_qr_page'))

@app.route('/batch_modify', methods=['POST'])
def batch_modify():
    """Modifikasi batch dari file CSV"""
    try:
        if 'csvfile' not in request.files:
            flash('Tidak ada file CSV yang diunggah', 'warning')
            return redirect(url_for('modify_qr_page'))
        
        file = request.files['csvfile']
        if file.filename == '':
            flash('Tidak ada file yang dipilih', 'warning')
            return redirect(url_for('modify_qr_page'))
        
        if not file.filename.endswith('.csv'):
            flash('File harus berformat CSV', 'danger')
            return redirect(url_for('modify_qr_page'))
        
        # Baca file CSV
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        # Pastikan kolom yang diperlukan ada
        if 'nama' not in csv_input.fieldnames or 'id' not in csv_input.fieldnames:
            flash('CSV harus memiliki kolom "nama" dan "id"', 'danger')
            return redirect(url_for('modify_qr_page'))
        
        # Inisialisasi
        modifications_list = []
        fake_qr_files = []
        
        for idx, row in enumerate(csv_input, start=1):
            try:
                nama = row.get('nama', f'User {idx}')
                userid = row.get('id', f'user_{idx:04d}')
                timestamp = row.get('timestamp')
                nonce = row.get('nonce')
                
                # Buat data palsu
                wib = timezone(timedelta(hours=7))
                if timestamp:
                    try:
                        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except:
                        timestamp = datetime.now(wib).isoformat()
                else:
                    timestamp = datetime.now(wib).isoformat()
                
                if not nonce:
                    nonce = generate_qr_nonce()
                
                data = {
                    "nama": nama,
                    "id": userid,
                    "timestamp": timestamp,
                    "nonce": nonce
                }
                
                # Buat signature random
                random_sig = secrets.token_bytes(256)
                
                payload = {
                    "data": data,
                    "signature": base64.b64encode(random_sig).decode('utf-8'),
                    "alg": "RSA",
                    "metadata": {
                        "algorithm": "RSA-PSS",
                        "key_size": 2048,
                        "hash_function": "SHA-256",
                        "salt_length": 8,
                        "mgf": "MGF1-SHA256"
                    }
                }
        
                # Generate QR Code dengan parameter dioptimalkan
                qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=2, border=1)  # OPTIMASI
                qr.add_data(json.dumps(payload))
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Simpan QR Code dengan kompresi
                fake_filename = f"batch_{userid}_{secrets.token_hex(4)}.png"
                fake_path = os.path.join(app.config['FAKE_QR_FOLDER'], fake_filename)
                img.save(fake_path, optimize=True, quality=85)  # KOMPRESI
                
                fake_qr_static_path = f"qr_fake/{fake_filename}"
                fake_qr_files.append(fake_qr_static_path)
                
                # Catat untuk log batch
                modifications_list.append({
                    'original': {'nama': 'N/A (batch)', 'id': 'N/A'},
                    'modified': data
                })
                
            except Exception as e:
                app.logger.error(f"Error processing row {idx}: {e}")
                continue

        # Catat log batch
        log_batch_modification(len(fake_qr_files), modifications_list)
        
        # Simpan ke session untuk download
        session['batch_fake_files'] = fake_qr_files
        
        flash(f'Berhasil membuat {len(fake_qr_files)} QR Code palsu dari batch', 'success')
        return redirect(url_for('view_modification_logs'))
        
    except Exception as e:
        app.logger.error(f"Error in batch_modify: {e}", exc_info=True)
        flash(f'Error saat memproses batch: {str(e)}', 'danger')
        return redirect(url_for('modify_qr_page'))

@app.route('/modification_logs')
@login_required
def view_modification_logs():
    """Halaman untuk melihat log modifikasi"""
    # Baca log modifikasi tunggal
    logs = []
    log_file = app.config['MODIFICATION_LOG']
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            logs = []
    
    # Baca log batch modifikasi
    batch_logs = []
    batch_log_file = app.config['BATCH_MODIFICATION_LOG']
    if os.path.exists(batch_log_file):
        try:
            with open(batch_log_file, 'r', encoding='utf-8') as f:
                batch_logs = json.load(f)
        except:
            batch_logs = []
    
    return render_template('modification_logs.html', logs=logs, batch_logs=batch_logs)

@app.route('/clear_modification_logs', methods=['POST'])
def clear_modification_logs():
    """Menghapus semua log modifikasi"""
    try:
        log_files = [app.config['MODIFICATION_LOG'], app.config['BATCH_MODIFICATION_LOG']]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                # Backup sebelum hapus
                backup_file = f"{log_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(log_file, backup_file)
                os.remove(log_file)
        
        flash('Semua log modifikasi telah dihapus (backup dibuat)', 'success')
        return redirect(url_for('view_modification_logs'))
        
    except Exception as e:
        app.logger.error(f"Error clearing modification logs: {e}")
        flash(f'Error saat menghapus log: {str(e)}', 'danger')
        return redirect(url_for('view_modification_logs'))

@app.route('/download_batch_fake')
def download_batch_fake():
    """Download semua QR Code palsu dari batch"""
    try:
        fake_files = session.get('batch_fake_files', [])
        if not fake_files:
            flash('Tidak ada file batch untuk diunduh', 'warning')
            return redirect(url_for('modify_qr_page'))
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for fake_file in fake_files:
                # Path lengkap dari static
                full_path = os.path.join('static', fake_file)
                if os.path.exists(full_path):
                    zipf.write(full_path, arcname=os.path.basename(fake_file))
        
        zip_buffer.seek(0)
        
        session.pop('batch_fake_files', None)
        
        app.logger.info(f"Download batch fake QR: {len(fake_files)} files")
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'batch_fake_qr_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        )
        
    except Exception as e:
        app.logger.error(f"Error download_batch_fake: {e}")
        flash(f'Error saat download: {str(e)}', 'danger')
        return redirect(url_for('modify_qr_page'))

@app.route('/verify_qr_massal', methods=['POST'])
def verify_qr_massal():
    if not is_verification_feature_enabled():
        flash('Fitur verifikasi massal sedang dinonaktifkan sementara.', 'warning')
        return redirect(url_for('scanner'))

    try:
        if 'qrfiles' not in request.files:
            flash('Tidak ada file yang diunggah', 'warning')
            return redirect(url_for('scanner'))
        
        uploaded_files = request.files.getlist('qrfiles')
        valid_files = [f for f in uploaded_files if f.filename != '']
        
        if not valid_files:
            flash('Tidak ada file yang dipilih', 'warning')
            return redirect(url_for('scanner'))
        
        # Validasi per file (maksimal 10MB per file)
        for file in valid_files:
            is_valid, error_msg = validate_single_upload(file)
            if not is_valid:
                flash(error_msg, 'danger')
                return redirect(url_for('scanner'))
        
        # PERUBAHAN: Jika jumlah file > 5, gunakan async processing
        if len(valid_files) > 5:
            return start_async_verify_massal(valid_files)
        
        # Jika file <= 5, proses secara langsung (optimasi kamera HP)
        return verify_qr_massal_direct(valid_files)
        
    except RequestEntityTooLarge:
        app.logger.warning("Upload verifikasi massal melebihi batas request", exc_info=True)
        flash(get_upload_limit_message(), 'danger')
        return redirect(url_for('scanner'))
    except Exception as e:
        app.logger.error(f"Error verify_qr_massal: {e}", exc_info=True)
        flash(f'Error saat verifikasi massal: {str(e)}', 'danger')
        return redirect(url_for('scanner'))

def start_async_verify_massal(valid_files):
    """Memulai proses verifikasi massal secara async untuk file banyak"""
    try:
        # Buat task ID
        task_id = str(uuid.uuid4())
        
        # Simpan file sementara
        tasks_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'verify_tasks')
        os.makedirs(tasks_dir, exist_ok=True)
        
        saved_files = []
        for file in valid_files:
            filename = sanitize_filename(f"verify_{task_id}_{file.filename}")
            file_path = os.path.join(tasks_dir, filename)
            file.save(file_path)
            saved_files.append(file_path)
        
        # Inisialisasi task progress
        with task_lock:
            # Hapus task lama jika sudah melebihi batas
            prune_oldest_background_task_if_needed()
            
            background_tasks[task_id] = {
                'type': 'verify_massal',
                'total': len(saved_files),
                'processed': 0,
                'current': 0,
                'status': 'Memulai proses verifikasi...',
                'is_processing': False,
                'is_complete': False,
                'start_time': datetime.now().isoformat(),
                'results': None,
                'massal_stats': None,
                'error': None,
                'is_stopped': False,
                'saved_files': saved_files,
                'original_filenames': [f.filename for f in valid_files],
                'total_files': len(saved_files),
                'cleanup_saved_files': True
            }
        
        # Jalankan proses verifikasi di thread terpisah
        thread = threading.Thread(target=background_verify_massal_process, args=(task_id,))
        thread.daemon = True
        thread.start()
        
        # Tandai task sebagai sedang diproses
        with task_lock:
            background_tasks[task_id]['is_processing'] = True
        
        # Redirect ke halaman progress
        return redirect(url_for('verify_massal_progress', task_id=task_id))
        
    except Exception as e:
        app.logger.error(f"Error start_async_verify_massal: {e}", exc_info=True)
        flash(f'Error saat memulai verifikasi massal: {str(e)}', 'danger')
        return redirect(url_for('scanner'))

def verify_qr_massal_direct(valid_files):
    """Proses verifikasi massal langsung dengan optimasi untuk kamera HP"""
    try:
        total_timer = Timer().start()
        
        hasil_verifikasi = []
        processed_files = set()
        
        massal_stats = {
            "total_files": len(valid_files),
            "success_count": 0,
            "error_count": 0,
            "replay_attack_count": 0,
            "valid_signature_count": 0,
            "total_load_time": 0,
            "total_decode_time": 0,
            "total_verify_time": 0,
            "total_db_time": 0,
            "individual_times": []
        }
        
        for idx, file in enumerate(valid_files, start=1):
            if file.filename in processed_files:
                continue
            
            processed_files.add(file.filename)
            
            file_timer = Timer().start()
            
            filename = sanitize_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            try:
                file.save(file_path)
            except Exception as e:
                app.logger.error(f"Error saving file {filename}: {e}")
                
                # LOG ERROR untuk kasus save file gagal
                log_row = [
                    "Massal", datetime.now(timezone.utc).isoformat(), filename, "❌ Error menyimpan file",
                    "-", "-", "-",
                    "0.000000", "0.000000", "0.000000", "0.000000", f"{file_timer.stop():.6f}"
                ]
                _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                
                hasil_verifikasi.append({
                    "no": idx,
                    "filename": filename,
                    "status": "❌ Error menyimpan file",
                    "data": None,
                    "perubahan": "-",
                    "load_time": "-",
                    "decode_time": "-",
                    "verify_time": "-",
                    "db_time": "-",
                    "total_time": "-"
                })
                massal_stats["error_count"] += 1
                continue
            
            load_timer = Timer().start()
            image = cv2.imread(file_path)
            if image is None:
                load_time = load_timer.stop()
                total_file_time = file_timer.stop()
                
                # LOG ERROR untuk kasus gambar tidak valid
                log_row = [
                    "Massal", datetime.now(timezone.utc).isoformat(), filename, "❌ File gambar tidak valid",
                    "-", "-", "-",
                    f"{load_time:.6f}", "0.000000", "0.000000", "0.000000", f"{total_file_time:.6f}"
                ]
                _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                
                hasil_verifikasi.append({
                    "no": idx,
                    "filename": filename,
                    "status": "❌ File gambar tidak valid",
                    "data": None,
                    "perubahan": "-",
                    "load_time": f"{load_time:.3f}",
                    "decode_time": "-",
                    "verify_time": "-",
                    "db_time": "-",
                    "total_time": f"{total_file_time:.3f}"
                })
                massal_stats["error_count"] += 1
                continue
            
            load_time = load_timer.stop()
            massal_stats["total_load_time"] += load_time
            
            decode_timer = Timer().start()
            qr_data = decode(image)
            if not qr_data:
                decode_time = decode_timer.stop()
                total_file_time = file_timer.stop()
                
                # LOG ERROR untuk kasus QR tidak terbaca
                log_row = [
                    "Massal", datetime.now(timezone.utc).isoformat(), filename, "⛔ Tidak dapat membaca QR",
                    "-", "-", "-",
                    f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                ]
                _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                
                hasil_verifikasi.append({
                    "no": idx,
                    "filename": filename,
                    "status": "⛔ Tidak dapat membaca QR",
                    "data": None,
                    "perubahan": "-",
                    "load_time": f"{load_time:.3f}",
                    "decode_time": f"{decode_time:.3f}",
                    "verify_time": "-",
                    "db_time": "-",
                    "total_time": f"{total_file_time:.3f}"
                })
                massal_stats["error_count"] += 1
                continue
            
            decode_time = decode_timer.stop()
            massal_stats["total_decode_time"] += decode_time
            
            try:
                raw = qr_data[0].data.decode('utf-8')
                payload = extract_payload_from_qr_string(raw)
                if not payload:
                    total_file_time = file_timer.stop()

                    log_row = [
                        "Massal", datetime.now(timezone.utc).isoformat(), filename, "❌ Format URL tidak sesuai",
                        "-", "-", "-",
                        f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                    ]
                    _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)

                    hasil_verifikasi.append({
                        "no": idx,
                        "filename": filename,
                        "status": "❌ Format URL tidak sesuai",
                        "data": None,
                        "perubahan": "-",
                        "load_time": f"{load_time:.3f}",
                        "decode_time": f"{decode_time:.3f}",
                        "verify_time": "-",
                        "db_time": "-",
                        "total_time": f"{total_file_time:.3f}"
                    })
                    massal_stats["error_count"] += 1
                    continue
                
                if "data" not in payload or "signature" not in payload:
                    total_file_time = file_timer.stop()
                    
                    # LOG ERROR untuk kasus format tidak lengkap
                    log_row = [
                        "Massal", datetime.now(timezone.utc).isoformat(), filename, "❌ Format QR tidak lengkap",
                        "-", "-", "-",
                        f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                    ]
                    _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                    
                    hasil_verifikasi.append({
                        "no": idx,
                        "filename": filename,
                        "status": "❌ Format QR tidak lengkap",
                        "data": None,
                        "perubahan": "-",
                        "load_time": f"{load_time:.3f}",
                        "decode_time": f"{decode_time:.3f}",
                        "verify_time": "-",
                        "db_time": "-",
                        "total_time": f"{total_file_time:.3f}"
                    })
                    massal_stats["error_count"] += 1
                    continue
                
                data = payload["data"]
                signature_b64 = payload["signature"]
                alg = payload.get("alg", "RSA")
                
                try:
                    signature = base64.b64decode(signature_b64)
                except:
                    total_file_time = file_timer.stop()
                    
                    # LOG ERROR untuk kasus signature tidak valid
                    log_row = [
                        "Massal", datetime.now(timezone.utc).isoformat(), filename, "❌ Signature tidak valid",
                        "-", "-", "-",
                        f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                    ]
                    _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                    
                    hasil_verifikasi.append({
                        "no": idx,
                        "filename": filename,
                        "status": "❌ Signature tidak valid",
                        "data": None,
                        "perubahan": "-",
                        "load_time": f"{load_time:.3f}",
                        "decode_time": f"{decode_time:.3f}",
                        "verify_time": "-",
                        "db_time": "-",
                        "total_time": f"{total_file_time:.3f}"
                    })
                    massal_stats["error_count"] += 1
                    continue
                
                serialized = json.dumps(data, sort_keys=True)
                hash_obj = SHA256.new(serialized.encode('utf-8'))
                
                verify_timer = Timer().start()
                if alg == 'RSA':
                    try:
                        verifier = pss.new(public_key, salt_bytes=8)
                        verifier.verify(hash_obj, signature)
                        signature_valid = True
                        sig_error = ""
                    except (ValueError, TypeError):
                        try:
                            verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                            verifier.verify(hash_obj, signature)
                            signature_valid = True
                            sig_error = "signature tidak valid (ECDSA)"
                        except (ValueError, TypeError):
                            sig_error = "signature tidak valid (ECDSA)"
                            signature_valid = False
                elif alg == 'ECDSA':
                    try:
                        verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                        verifier.verify(hash_obj, signature)
                        signature_valid = True
                        sig_error = ""
                    except (ValueError, TypeError):
                        sig_error = "signature tidak valid (ECDSA)"
                        signature_valid = False
                else:
                    sig_error = "signature tidak valid (algoritma tidak diketahui)"
                    signature_valid = False
                
                if signature_valid:
                    massal_stats["valid_signature_count"] += 1
                    
                verify_time = verify_timer.stop()
                massal_stats["total_verify_time"] += verify_time
                
                db_timer = Timer().start()
                changed_fields = {}
                message = ""
                is_replay = False
                
                verification_result = classify_qr_verification(data, signature_valid, sig_error)
                original_data = verification_result["original_data"]
                changed_fields = verification_result["changed_fields"]
                message = verification_result["message"]
                valid = verification_result["valid"]
                is_replay = verification_result["is_replay"]

                if is_replay:
                    massal_stats["replay_attack_count"] += 1
                if valid:
                    massal_stats["success_count"] += 1
                else:
                    massal_stats["error_count"] += 1
                
                db_time = db_timer.stop()
                massal_stats["total_db_time"] += db_time
                
                total_file_time = file_timer.stop()
                massal_stats["individual_times"].append(total_file_time)
                
                # LOG HASIL VERIFIKASI
                log_row = [
                    "Massal", datetime.now(timezone.utc).isoformat(), filename, message,
                    data.get('nama', '-'), data.get('id', '-'),
                    json.dumps(changed_fields, ensure_ascii=False) if changed_fields else '-',
                    f"{load_time:.6f}", f"{decode_time:.6f}", f"{verify_time:.6f}",
                    f"{db_time:.6f}", f"{total_file_time:.6f}"
                ]
                _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                
                hasil_verifikasi.append({
                    "no": idx,
                    "filename": filename,
                    "status": message,
                    "data": data,
                    "perubahan": changed_fields if changed_fields else "-",
                    "load_time": f"{load_time:.3f} detik",
                    "decode_time": f"{decode_time:.3f} detik",
                    "verify_time": f"{verify_time:.3f} detik",
                    "db_time": f"{db_time:.3f} detik",
                    "total_time": f"{total_file_time:.3f} detik",
                    "algorithm": alg,
                    "signature_valid": signature_valid,
                    "valid": valid,
                    "is_replay": is_replay
                })
                
            except Exception as e:
                app.logger.error(f"Error processing file {file.filename}: {e}")
                total_file_time = file_timer.stop()
                
                # LOG ERROR untuk kasus umum
                log_row = [
                    "Massal", datetime.now(timezone.utc).isoformat(), filename, f"❌ Error: {str(e)[:50]}",
                    "-", "-", "-",
                    f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                ]
                _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                
                hasil_verifikasi.append({
                    "no": idx,
                    "filename": filename,
                    "status": f"❌ Error: {str(e)[:50]}...",
                    "data": None,
                    "perubahan": "-",
                    "load_time": f"{load_time:.3f}",
                    "decode_time": f"{decode_time:.3f}",
                    "verify_time": "-",
                    "db_time": "-",
                    "total_time": f"{total_file_time:.3f} detik"
                })
                massal_stats["error_count"] += 1
        
        total_massal_time = total_timer.stop()
        
        # Update statistik
        massal_stats["total_time"] = total_massal_time
        if massal_stats["individual_times"]:
            massal_stats["avg_time_per_file"] = sum(massal_stats["individual_times"]) / len(massal_stats["individual_times"])
            massal_stats["min_time"] = min(massal_stats["individual_times"])
            massal_stats["max_time"] = max(massal_stats["individual_times"])
        else:
            massal_stats["avg_time_per_file"] = 0
            massal_stats["min_time"] = 0
            massal_stats["max_time"] = 0
        
        massal_stats["success_rate"] = (massal_stats["success_count"] / massal_stats["total_files"]) * 100 if massal_stats["total_files"] > 0 else 0

        massal_stats["time_breakdown"] = {
            "load": massal_stats["total_load_time"],
            "decode": massal_stats["total_decode_time"],
            "verify": massal_stats["total_verify_time"],
            "db": massal_stats["total_db_time"]
        }

        app.logger.info(f"Verifikasi massal selesai: {len(hasil_verifikasi)} file diproses dalam {total_massal_time:.2f} detik")
        
        return render_template("scanner.html", 
                             hasil_tunggal=None, 
                             hasil_massal=hasil_verifikasi,
                             massal_stats=massal_stats,
                             outcome=summarize_verification_outcomes(hasil_verifikasi),
                             stats=qr_stats)
        
    except Exception as e:
        app.logger.error(f"Error verify_qr_massal_direct: {e}", exc_info=True)
        flash(f'Error saat verifikasi massal: {str(e)}', 'danger')
        return redirect(url_for('scanner'))

def background_verify_massal_process(task_id):
    """Proses background untuk verifikasi massal async"""
    try:
        with task_lock:
            task = background_tasks.get(task_id)
            if not task:
                app.logger.error(f"Task {task_id} tidak ditemukan")
                return
            
            saved_files = task.get('saved_files', [])
            total_files = len(saved_files)
        
        results = []
        massal_stats = {
            "total_files": total_files,
            "success_count": 0,
            "error_count": 0,
            "replay_attack_count": 0,
            "valid_signature_count": 0,
            "total_load_time": 0,
            "total_decode_time": 0,
            "total_verify_time": 0,
            "total_db_time": 0,
            "individual_times": []
        }
        
        for idx, file_path in enumerate(saved_files, start=1):
            try:
                # Update progress
                with task_lock:
                    if task_id in background_tasks:
                        background_tasks[task_id]['current'] = idx
                        background_tasks[task_id]['processed'] = idx - 1
                        background_tasks[task_id]['status'] = f'Memproses file {idx}/{total_files}'
                
                filename = os.path.basename(file_path)
                original_filename = task['original_filenames'][idx-1] if idx-1 < len(task['original_filenames']) else filename
                
                file_timer = Timer().start()
                
                load_timer = Timer().start()
                image = cv2.imread(file_path)
                if image is None:
                    load_time = load_timer.stop()
                    total_file_time = file_timer.stop()
                    
                    # LOG ERROR
                    log_row = [
                        "Massal-Async", datetime.now(timezone.utc).isoformat(), original_filename, "❌ File gambar tidak valid",
                        "-", "-", "-",
                        f"{load_time:.6f}", "0.000000", "0.000000", "0.000000", f"{total_file_time:.6f}"
                    ]
                    _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                    
                    results.append({
                        "no": idx,
                        "filename": original_filename,
                        "status": "❌ File gambar tidak valid",
                        "data": None,
                        "perubahan": "-",
                        "load_time": f"{load_time:.3f}",
                        "decode_time": "-",
                        "verify_time": "-",
                        "db_time": "-",
                        "total_time": f"{total_file_time:.3f}"
                    })
                    massal_stats["error_count"] += 1
                    continue
                
                load_time = load_timer.stop()
                massal_stats["total_load_time"] += load_time
                
                decode_timer = Timer().start()
                qr_data = decode(image)
                if not qr_data:
                    decode_time = decode_timer.stop()
                    total_file_time = file_timer.stop()
                    
                    # LOG ERROR
                    log_row = [
                        "Massal-Async", datetime.now(timezone.utc).isoformat(), original_filename, "⛔ Tidak dapat membaca QR",
                        "-", "-", "-",
                        f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                    ]
                    _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                    
                    results.append({
                        "no": idx,
                        "filename": original_filename,
                        "status": "⛔ Tidak dapat membaca QR",
                        "data": None,
                        "perubahan": "-",
                        "load_time": f"{load_time:.3f}",
                        "decode_time": f"{decode_time:.3f}",
                        "verify_time": "-",
                        "db_time": "-",
                        "total_time": f"{total_file_time:.3f}"
                    })
                    massal_stats["error_count"] += 1
                    continue
                
                decode_time = decode_timer.stop()
                massal_stats["total_decode_time"] += decode_time
                
                try:
                    raw = qr_data[0].data.decode('utf-8')
                    
                    payload = extract_payload_from_qr_string(raw)
                    if not payload:
                        raise ValueError("Format URL atau QR tidak sesuai")
                    
                    if "data" not in payload or "signature" not in payload:
                        total_file_time = file_timer.stop()
                        
                        log_row = [
                            "Massal-Async", datetime.now(timezone.utc).isoformat(), original_filename, "❌ Format QR tidak lengkap",
                            "-", "-", "-",
                            f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                        ]
                        _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                        
                        results.append({
                            "no": idx,
                            "filename": original_filename,
                            "status": "❌ Format QR tidak lengkap",
                            "data": None,
                            "perubahan": "-",
                            "load_time": f"{load_time:.3f}",
                            "decode_time": f"{decode_time:.3f}",
                            "verify_time": "-",
                            "db_time": "-",
                            "total_time": f"{total_file_time:.3f}"
                        })
                        massal_stats["error_count"] += 1
                        continue
                    
                    data = payload["data"]
                    signature_b64 = payload["signature"]
                    alg = payload.get("alg", "RSA")
                    
                    try:
                        signature = base64.b64decode(signature_b64)
                    except:
                        total_file_time = file_timer.stop()
                        
                        log_row = [
                            "Massal-Async", datetime.now(timezone.utc).isoformat(), original_filename, "❌ Signature tidak valid",
                            "-", "-", "-",
                            f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                        ]
                        _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                        
                        results.append({
                            "no": idx,
                            "filename": original_filename,
                            "status": "❌ Signature tidak valid",
                            "data": None,
                            "perubahan": "-",
                            "load_time": f"{load_time:.3f}",
                            "decode_time": f"{decode_time:.3f}",
                            "verify_time": "-",
                            "db_time": "-",
                            "total_time": f"{total_file_time:.3f}"
                        })
                        massal_stats["error_count"] += 1
                        continue
                    
                    serialized = json.dumps(data, sort_keys=True)
                    hash_obj = SHA256.new(serialized.encode('utf-8'))
                    
                    sig_error = ""
                    if alg == 'RSA':
                        verifier = pss.new(public_key, salt_bytes=8) # Konsisten Salt 8
                    elif alg == 'ECDSA':
                        verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                    else:
                        verifier = None
                        sig_error = "signature tidak valid (algoritma tidak diketahui)"
                    
                    verify_timer = Timer().start()
                    if verifier:
                        try:
                            verifier.verify(hash_obj, signature)
                            signature_valid = True
                            massal_stats["valid_signature_count"] += 1
                        except (ValueError, TypeError):
                            sig_error = "signature tidak valid"
                            signature_valid = False
                    else:
                        signature_valid = False
                    verify_time = verify_timer.stop()
                    massal_stats["total_verify_time"] += verify_time
                    
                    # Proses database (sama seperti sebelumnya)
                    db_timer = Timer().start()
                    changed_fields = {}
                    message = ""
                    is_replay = False
                    
                    verification_result = classify_qr_verification(data, signature_valid, sig_error)
                    original_data = verification_result["original_data"]
                    changed_fields = verification_result["changed_fields"]
                    message = verification_result["message"]
                    valid = verification_result["valid"]
                    is_replay = verification_result["is_replay"]

                    if is_replay:
                        massal_stats["replay_attack_count"] += 1
                    if valid:
                        massal_stats["success_count"] += 1
                    else:
                        massal_stats["error_count"] += 1
                    
                    db_time = db_timer.stop()
                    massal_stats["total_db_time"] += db_time
                    
                    total_file_time = file_timer.stop()
                    massal_stats["individual_times"].append(total_file_time)
                    
                    # LOG
                    log_row = [
                        "Massal-Async", datetime.now(timezone.utc).isoformat(), original_filename, message,
                        data.get('nama', '-'), data.get('id', '-'),
                        json.dumps(changed_fields, ensure_ascii=False) if changed_fields else '-',
                        f"{load_time:.6f}", f"{decode_time:.6f}", f"{verify_time:.6f}",
                        f"{db_time:.6f}", f"{total_file_time:.6f}"
                    ]
                    _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                    
                    results.append({
                        "no": idx,
                        "filename": original_filename,
                        "status": message,
                        "data": data,
                        "perubahan": changed_fields if changed_fields else "-",
                        "load_time": f"{load_time:.3f} detik",
                        "decode_time": f"{decode_time:.3f} detik",
                        "verify_time": f"{verify_time:.3f} detik",
                        "db_time": f"{db_time:.3f} detik",
                        "total_time": f"{total_file_time:.3f} detik",
                        "signature_valid": signature_valid,
                        "valid": valid,
                        "is_replay": is_replay
                    })
                    
                except Exception as e:
                    app.logger.error(f"Error processing file {original_filename} in async: {e}")
                    total_file_time = file_timer.stop()
                    
                    log_row = [
                        "Massal-Async", datetime.now(timezone.utc).isoformat(), original_filename, f"❌ Error: {str(e)[:50]}",
                        "-", "-", "-",
                        f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                    ]
                    _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], log_row)
                    
                    results.append({
                        "no": idx,
                        "filename": original_filename,
                        "status": f"❌ Error: {str(e)[:50]}...",
                        "data": None,
                        "perubahan": "-",
                        "load_time": f"{load_time:.3f}",
                        "decode_time": f"{decode_time:.3f}",
                        "verify_time": "-",
                        "db_time": "-",
                        "total_time": f"{total_file_time:.3f} detik"
                    })
                    massal_stats["error_count"] += 1
                    
            except Exception as e:
                app.logger.error(f"Error in async processing for file {idx}: {e}")
                results.append({
                    "no": idx,
                    "filename": f"file_{idx}",
                    "status": f"❌ System Error: {str(e)[:50]}...",
                    "data": None,
                    "perubahan": "-",
                    "load_time": "-",
                    "decode_time": "-",
                    "verify_time": "-",
                    "db_time": "-",
                    "total_time": "-"
                })
                massal_stats["error_count"] += 1
        
        # Update task dengan hasil
        with task_lock:
            if task_id in background_tasks:
                background_tasks[task_id]['is_complete'] = True
                background_tasks[task_id]['is_processing'] = False
                background_tasks[task_id]['status'] = 'Selesai'
                background_tasks[task_id]['results'] = results
                background_tasks[task_id]['massal_stats'] = massal_stats
                background_tasks[task_id]['end_time'] = datetime.now().isoformat()
                
                # Hapus file temporary
                cleanup_task_saved_files(background_tasks[task_id])
                if background_tasks[task_id].get('cleanup_saved_files', True):
                    background_tasks[task_id]['saved_files'] = []
        
    except Exception as e:
        app.logger.error(f"Error in background_verify_massal_process: {e}", exc_info=True)
        with task_lock:
            if task_id in background_tasks:
                background_tasks[task_id]['is_complete'] = True
                background_tasks[task_id]['is_processing'] = False
                background_tasks[task_id]['status'] = 'Error'
                background_tasks[task_id]['error'] = str(e)

@app.route('/verify_massal_progress')
@app.route('/verify_massal_progress/<task_id>')
@login_required
def verify_massal_progress(task_id=None):
    """Halaman untuk menampilkan progress verifikasi massal"""
    if task_id is None:
        # Jika tidak ada task_id, tampilkan halaman utama
        return render_template('verify_massal_progress.html', stats=qr_stats)
    
    # Jika ada task_id, tampilkan progress task tertentu
    task = load_task_from_memory_or_snapshot(task_id)
    
    if not task:
        flash('Task tidak ditemukan atau sudah dihapus', 'warning')
        return redirect(url_for('scanner'))
    
    return render_template('verify_progress.html', task=task, task_id=task_id)

@app.route('/verify_massal_results/<task_id>')
@login_required
def verify_massal_results(task_id):
    """Menampilkan hasil verifikasi massal async"""
    task = load_task_from_memory_or_snapshot(task_id)
    
    if not task:
        flash('Task tidak ditemukan atau sudah dihapus', 'warning')
        return redirect(url_for('scanner'))
    
    if not task.get('is_complete'):
        flash('Proses verifikasi belum selesai', 'warning')
        return redirect(url_for('verify_massal_progress', task_id=task_id))
    
    # Render hasil yang sama seperti verifikasi langsung
    return render_template("scanner.html", 
                         hasil_tunggal=None, 
                         hasil_massal=task.get('results', []),
                         massal_stats=task.get('massal_stats', {}),
                         outcome=summarize_verification_outcomes(task.get('results', [])),
                         stats=qr_stats)

@app.route('/generate_csv', methods=['GET', 'POST'])
@login_required
def generate_csv():
    if request.method == 'POST':
        try:
            jumlah_data = int(request.form.get('jumlah_data', 100))
            jenis_data = request.form.get('jenis_data', 'random')
            
            if jumlah_data <= 0:
                flash('Jumlah data harus lebih dari 0', 'danger')
                return redirect(url_for('generate_csv'))
            
            if jumlah_data > 1000000:
                flash('Maksimal 1.000.000 data per file', 'warning')
                jumlah_data = 1000000
            
            data = []
            
            if jenis_data == 'random':
                first_names = ["John", "Jane", "Robert", "Lisa", "Michael", "Sarah", "David", "Emma", 
                              "James", "Maria", "William", "Anna", "Richard", "Sofia", "Charles"]
                last_names = ["Doe", "Smith", "Johnson", "Brown", "Wilson", "Taylor", "Clark", "Lee", 
                             "Walker", "Hall", "Allen", "Young", "King", "Wright", "Scott"]
                
                for i in range(1, jumlah_data + 1):
                    first = random.choice(first_names)
                    last = random.choice(last_names)
                    nama = f"{first} {last}"
                    user_id = f"user_{jenis_data}_{i:06d}"
                    data.append({"nama": nama, "id": user_id})
                    
            elif jenis_data == 'sequential':
                for i in range(1, jumlah_data + 1):
                    nama = f"User {i}"
                    user_id = f"user_{i:06d}"
                    data.append({"nama": nama, "id": user_id})
                    
            elif jenis_data == 'event':
                events = ["Seminar", "Workshop", "Konferensi", "Pelatihan", "Lokakarya"]
                for i in range(1, jumlah_data + 1):
                    event = random.choice(events)
                    nama = f"Peserta {i} - {event}"
                    user_id = f"peserta_{event.lower()}_{i:06d}"
                    data.append({"nama": nama, "id": user_id})
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['nama', 'id'])
            writer.writeheader()
            writer.writerows(data)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sample_data_{jenis_data}_{jumlah_data}_{timestamp}.csv"
            
            mem = io.BytesIO()
            mem.write(output.getvalue().encode('utf-8'))
            mem.seek(0)
            
            app.logger.info(f"CSV generated: {filename} with {jumlah_data} rows")
            
            return send_file(
                mem,
                mimetype='text/csv',
                as_attachment=True,
                download_name=filename
            )
            
        except ValueError:
            flash('Jumlah data harus berupa angka', 'danger')
            return redirect(url_for('generate_csv'))
        except Exception as e:
            app.logger.error(f"Error generate CSV: {e}")
            flash(f'Error saat generate CSV: {str(e)}', 'danger')
            return redirect(url_for('generate_csv'))
    
    return render_template('generate_csv.html')

@app.route('/generate_smart_csv', methods=['POST'])
def generate_smart_csv():
    try:
        jumlah_data = int(request.form.get('jumlah_data', 100))
        prefix_nama = request.form.get('prefix_nama', 'User').strip()
        prefix_id = request.form.get('prefix_id', 'user').strip().lower()
        start_number = int(request.form.get('start_number', 1))
        include_email = 'include_email' in request.form
        include_phone = 'include_phone' in request.form
        include_department = 'include_department' in request.form
        
        if jumlah_data <= 0:
            flash('Jumlah data harus lebih dari 0', 'danger')
            return redirect(url_for('generate_csv'))
        
        if jumlah_data > 500000:
            flash('Maksimal 500.000 data untuk mode advanced', 'warning')
            jumlah_data = 500000
        
        departments = ["IT", "HR", "Finance", "Marketing", "Operations", "Sales", "R&D"]
        domains = ["company.com", "gmail.com", "yahoo.com", "outlook.com"]
        
        data = []
        fieldnames = ['nama', 'id']
        
        if include_email:
            fieldnames.append('email')
        if include_phone:
            fieldnames.append('phone')
        if include_department:
            fieldnames.append('department')
        
        for i in range(start_number, start_number + jumlah_data):
            row = {
                'nama': f"{prefix_nama} {i}",
                'id': f"{prefix_id}_{i:06d}"
            }
            
            if include_email:
                email_prefix = f"{prefix_id}{i}".lower()
                domain = random.choice(domains)
                row['email'] = f"{email_prefix}@{domain}"
            
            if include_phone:
                phone = "08" + ''.join(random.choices(string.digits, k=10))
                row['phone'] = phone
            
            if include_department:
                row['department'] = random.choice(departments)
            
            data.append(row)
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"smart_data_{jumlah_data}_{timestamp}.csv"
        
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        
        app.logger.info(f"Smart CSV generated: {filename} with {len(fieldnames)} columns")
        
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        app.logger.error(f"Error generate smart CSV: {e}")
        flash(f'Error saat generate CSV: {str(e)}', 'danger')
        return redirect(url_for('generate_csv'))

@app.route('/generate_massive_csv', methods=['POST'])
@limiter.limit("5 per minute")
def generate_massive_csv():
    try:
        jumlah_data = int(request.form.get('massive_amount', 10000))
        chunk_size = 10000
        
        if jumlah_data <= 0:
            flash('Jumlah data harus lebih dari 0', 'danger')
            return redirect(url_for('generate_csv'))
        
        MAX_DATA = 1000000
        if jumlah_data > MAX_DATA:
            flash(f'Maksimal {MAX_DATA:,} data untuk mode massive', 'warning')
            jumlah_data = MAX_DATA
        
        def generate():
            rows_sent = 0
            try:
                yield 'nama,id,timestamp,department,location\n'
                
                departments = ["IT", "HR", "Finance", "Marketing", "Sales"]
                locations = ["Jakarta", "Bandung", "Surabaya", "Medan", "Makassar"]
                
                for chunk_start in range(0, jumlah_data, chunk_size):
                    chunk_end = min(chunk_start + chunk_size, jumlah_data)
                    chunk_data = []
                    
                    for i in range(chunk_start + 1, chunk_end + 1):
                        nama = sanitize_for_csv(f"Test User {i}")
                        user_id = sanitize_for_csv(f"test_{i:08d}")
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        department = sanitize_for_csv(random.choice(departments))
                        location = sanitize_for_csv(random.choice(locations))
                        
                        chunk_data.append(f'"{nama}","{user_id}","{timestamp}","{department}","{location}"\n')
                    
                    yield ''.join(chunk_data)
                    rows_sent = chunk_end
                    app.logger.debug(f"Generated chunk {chunk_start//chunk_size + 1}")
            except GeneratorExit:
                app.logger.info(f"Massive CSV generation stopped by client after {rows_sent:,} rows")
                raise
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"massive_data_{jumlah_data}_{timestamp}.csv"
        
        app.logger.info(f"Massive CSV generation started: {filename} ({jumlah_data:,} rows)")
        
        return Response(
            generate(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'text/csv; charset=utf-8',
                'Cache-Control': 'no-store',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        app.logger.error(f"Error generate massive CSV: {e}")
        flash(f'Error saat generate massive CSV: {str(e)}', 'danger')
        return redirect(url_for('generate_csv'))

@app.route('/preview_csv', methods=['POST'])
def preview_csv():
    try:
        jumlah_data = int(request.form.get('preview_amount', 10))
        jenis_data = request.form.get('preview_type', 'random')
        
        if jumlah_data > 100:
            jumlah_data = 100
        
        data = []
        first_names = ["John", "Jane", "Robert", "Lisa"]
        last_names = ["Doe", "Smith", "Johnson", "Brown"]
        
        for i in range(1, jumlah_data + 1):
            if jenis_data == 'random':
                first = random.choice(first_names)
                last = random.choice(last_names)
                nama = f"{first} {last}"
                user_id = f"user_{i:06d}"
            elif jenis_data == 'sequential':
                nama = f"User {i}"
                user_id = f"user_{i:06d}"
            else:
                nama = f"Peserta {i}"
                user_id = f"peserta_{i:06d}"
            
            data.append({"No": i, "Nama": nama, "ID": user_id})
        
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/generate_from_csv', methods=['POST'])
@login_required
def generate_from_csv():
    try:
        if 'csvfile' not in request.files:
            flash('Tidak ada file CSV yang diunggah', 'warning')
            return redirect(url_for('qr_generator'))
        
        file = request.files['csvfile']
        if file.filename == '':
            flash('Tidak ada file yang dipilih', 'warning')
            return redirect(url_for('qr_generator'))
        
        if not file.filename.endswith('.csv'):
            flash('File harus berformat CSV', 'danger')
            return redirect(url_for('qr_generator'))
        
        # Simpan file CSV ke folder sementara
        task_id = str(uuid.uuid4())
        alg = request.form.get('alg', 'RSA')
        # Algoritma default diubah ke RSA
        # Buat folder tasks jika belum ada
        tasks_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'tasks')
        os.makedirs(tasks_dir, exist_ok=True)
        
        csv_filename = f"task_{task_id}.csv"
        csv_path = os.path.join(tasks_dir, csv_filename)
        file.save(csv_path)
        
        # Baca total baris untuk progress
        with open(csv_path, 'r', encoding='utf-8') as f:
            total_rows = sum(1 for _ in f) - 1  # Kurangi header
        
        # Inisialisasi task progress
        with task_lock:
            # Hapus task lama jika sudah melebihi batas
            if len(background_tasks) >= MAX_TASK_HISTORY:
                # Hapus task terlama
                oldest_task_id = next(iter(background_tasks))
                # Hapus file CSV terkait jika ada
                old_task = background_tasks[oldest_task_id]
                old_csv_path = old_task.get('csv_path')
                if old_csv_path and os.path.exists(old_csv_path):
                    try:
                        os.remove(old_csv_path)
                    except:
                        pass
                del background_tasks[oldest_task_id]
            
            background_tasks[task_id] = build_generate_task(
                task_id,
                csv_path,
                total_rows=total_rows,
                alg=alg,
                # Simpan URL publik agar QR hasil background tetap mengarah ke domain production.
                base_url=get_public_base_url(),
                original_filename=file.filename
            )
            task_metadata = dict(background_tasks[task_id])

        save_generate_task_metadata(task_id, task_metadata)
        
        # Simpan task_id di session
        session['current_task_id'] = task_id
        
        # Redirect ke halaman progress
        return redirect(url_for('generate_progress', task_id=task_id))
        
    except Exception as e:
        app.logger.error(f"Error generate_from_csv: {e}")
        flash(f'Error saat generate dari CSV: {str(e)}', 'danger')
        return redirect(url_for('qr_generator'))

@app.route('/generate_progress')
@login_required
def generate_progress():
    """Halaman untuk menampilkan progress generate massal"""
    task_id = request.args.get('task_id') or session.get('current_task_id')
    
    if not task_id:
        flash('Tidak ada proses generate yang aktif', 'warning')
        return redirect(url_for('qr_generator'))
    
    task = ensure_generate_task_loaded(task_id)
    if not task:
        flash('Proses generate tidak ditemukan atau sudah dihapus', 'warning')
        return redirect(url_for('qr_generator'))
    
    return render_template('generate_progress.html', task_id=task_id)

@app.route('/api/generate_progress_status')
@limiter.exempt  # PENTING: Kecualikan dari rate limiting
@login_required
def generate_progress_status():
    """API untuk mendapatkan status progress"""
    task_id = request.args.get('task_id') or session.get('current_task_id')
    
    if not task_id:
        return jsonify({
            'total': 0,
            'processed': 0,
            'current': 0,
            'status': 'Tidak ada proses',
            'is_processing': False,
            'is_complete': False,
            'is_stopped': False,
            'start_time': None,
            'results': None,
            'massal_stats': None,
            'error': 'Task ID tidak ditemukan'
        })
    
    with task_lock:
        progress = background_tasks.get(task_id, {})

    if not progress:
        progress = ensure_generate_task_loaded(task_id)

    if not progress:
        return jsonify({
            'total': 0,
            'processed': 0,
            'current': 0,
            'status': 'Task tidak ditemukan',
            'is_processing': False,
            'is_complete': False,
            'is_stopped': False,
            'start_time': None,
            'results': None,
            'massal_stats': None,
            'error': 'Task tidak ditemukan'
        })
    
    # Hitung persentase
    total = progress.get('total', 0)
    processed = progress.get('processed', 0)
    if total > 0:
        percentage = (processed / total) * 100
    else:
        percentage = 0

    progress_stats = progress.get('massal_stats')
    if isinstance(progress_stats, dict):
        progress_stats = dict(progress_stats)
        progress_stats.pop('individual_times', None)
    
    # Hitung waktu yang telah berlalu
    elapsed_time = '0:00:00'
    estimated_remaining = 'Menghitung...'
    
    if progress.get('start_time'):
        try:
            start = datetime.fromisoformat(progress['start_time'])
            elapsed = datetime.now() - start
            elapsed_time = str(elapsed).split('.')[0]
            
            # Estimasi waktu tersisa
            if percentage > 0:
                total_seconds = elapsed.total_seconds()
                estimated_total = (total_seconds / percentage) * 100
                remaining_seconds = estimated_total - total_seconds
                if remaining_seconds > 0:
                    estimated_remaining = str(timedelta(seconds=int(remaining_seconds))).split('.')[0]
                else:
                    estimated_remaining = 'Hampir selesai'
        except Exception as e:
            app.logger.warning(f"Error menghitung waktu: {e}")
    
    response = {
        'task_id': task_id,
        'total': total,
        'processed': processed,
        'current': progress.get('current', 0),
        'status': progress.get('status', 'Tidak diketahui'),
        'is_processing': progress.get('is_processing', False),
        'is_complete': progress.get('is_complete', False),
        'is_stopped': progress.get('is_stopped', False),
        'start_time': progress.get('start_time'),
        'results': None,
        'results_count': len(progress.get('results') or []),
        'massal_stats': progress_stats,
        'error': progress.get('error'),
        'percentage': percentage,
        'elapsed_time': elapsed_time,
        'estimated_remaining': estimated_remaining
    }
    
    return jsonify(response)

@app.route('/api/start_generate_process')
@limiter.exempt  # PENTING: Kecualikan dari rate limiting
@login_required
def start_generate_process():
    """API untuk memulai proses generate di background"""
    task_id = request.args.get('task_id') or session.get('current_task_id')
    
    if not task_id:
        return jsonify({'error': 'Tidak ada task ID'})
    
    task = ensure_generate_task_loaded(task_id)
    if not task:
        return jsonify({'error': 'Task tidak ditemukan'})

    with task_lock:
        task = background_tasks.get(task_id)
        if not task:
            return jsonify({'error': 'Task tidak ditemukan'})

        if task.get('is_complete'):
            return jsonify({'status': 'Task sudah selesai', 'task_id': task_id, 'already_complete': True})

        if task.get('is_processing'):
            return jsonify({'status': 'Task sedang berjalan', 'task_id': task_id, 'already_processing': True})

        # Tandai sedang diproses
        task['is_processing'] = True
        task['is_stopped'] = False
        task['error'] = None
        task['current'] = 0
        task['processed'] = 0
        task['status'] = 'Memulai proses...'
        task['start_time'] = datetime.now().isoformat()
    
    # Jalankan proses generate di thread terpisah
    thread = threading.Thread(target=background_generate_process, args=(task_id,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'Proses dimulai', 'task_id': task_id})

@app.route('/api/stop_generate_process')
@limiter.exempt
@login_required
def stop_generate_process():
    """API untuk menghentikan proses generate di background"""
    task_id = request.args.get('task_id') or session.get('current_task_id')
    
    if not task_id:
        return jsonify({'error': 'Tidak ada task ID'})

    task = ensure_generate_task_loaded(task_id)
    if not task:
        return jsonify({'error': 'Task tidak ditemukan'})

    with task_lock:
        task = background_tasks.get(task_id)
        if not task:
            return jsonify({'error': 'Task tidak ditemukan'})
        
        if task.get('is_complete'):
            return jsonify({'status': 'Task sudah selesai', 'task_id': task_id, 'already_complete': True})

        if task.get('is_stopped'):
            return jsonify({'status': 'Proses sedang dihentikan', 'task_id': task_id, 'already_stopping': True})
        
        task['is_stopped'] = True
        task['status'] = 'Menghentikan proses...'
        task['stop_requested_at'] = datetime.now().isoformat()
    
    return jsonify({'status': 'Permintaan stop dikirim', 'task_id': task_id})

def background_generate_process(task_id):
    """Proses generate massal di background dengan QR Code yang dioptimalkan untuk kamera HP"""
    try:
        # Dapatkan task data
        with task_lock:
            task = background_tasks.get(task_id)
            if not task:
                return
            
            csv_path = task.get('csv_path')
            base_url = task.get('base_url')
            alg = task.get('alg', 'RSA') # Algoritma default diubah ke RSA
            if not csv_path or not os.path.exists(csv_path):
                task['error'] = 'File CSV tidak ditemukan'
                task['is_processing'] = False
                task['is_complete'] = True
                return
        
        # Buka aplikasi context untuk akses app.config dan logger
        with app.app_context():
            app.logger.info(f"Memulai background process untuk task {task_id}")
            
            # Update status awal
            with task_lock:
                task['status'] = 'Membaca data CSV...'
                task['processed'] = 0
            
            # Baca data CSV
            rows = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
            
            total_rows = len(rows)
            
            with task_lock:
                task['total'] = total_rows
                task['status'] = f'Memulai generate {total_rows} QR Code...'
            
            # Timer untuk seluruh proses massal
            total_massal_timer = Timer().start()
            
            hasil = []
            wib = timezone(timedelta(hours=7))
            generated_files = []
            generated_nonces = set()
            
            # Statistik untuk generate massal
            massal_stats = {
                "total_qr": 0,
                "success_count": 0,
                "error_count": 0,
                "total_data_time": 0,
                "total_sign_time": 0,
                "total_qr_time": 0,
                "total_save_time": 0,
                "total_file_size": 0,
                "individual_times": [],
                "dimensions": []
            }
            
            for row_num, row in enumerate(rows, start=1):
                # Cek apakah task dihentikan
                with task_lock:
                    if task.get('is_stopped'):
                        app.logger.info(f"Task {task_id} dihentikan oleh pengguna pada baris {row_num}")
                        break

                # Update progress setiap 10 baris atau di akhir
                if row_num % 10 == 0 or row_num == total_rows:
                    with task_lock:
                        task['current'] = row_num
                        task['processed'] = row_num
                        task['status'] = f'Memproses baris {row_num} dari {total_rows}: {row.get("nama", "")[:20]}...'
                
                try:
                    # Timer untuk setiap QR
                    qr_timer = Timer().start()
                    
                    nama = row.get('nama', '').strip()
                    userid = row.get('id', '').strip()
                    
                    if not nama or not userid:
                        app.logger.warning(f"Baris {row_num}: nama atau id kosong, dilewati")
                        massal_stats["error_count"] += 1
                        continue
                    
                    # Timer untuk data
                    data_timer = Timer().start()
                    data = {
                        "nama": nama,
                        "id": userid,
                        "timestamp": datetime.now(wib).isoformat(),
                        "nonce": generate_qr_nonce(generated_nonces)
                    } # Algoritma default diubah ke RSA
                    generated_nonces.add(data["nonce"])
                    
                    qr_temp = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_Q, box_size=2, border=1)
                    qr_temp.add_data(json.dumps(data))
                    qr_temp.make(fit=True)
                    data["qr_modules"] = qr_temp.modules_count
                    data["qr_version"] = qr_temp.version
                    data_time = data_timer.stop()
                    massal_stats["total_data_time"] += data_time
                    
                    serialized = json.dumps(data, sort_keys=True)
                    hash_digest = SHA256.new(serialized.encode('utf-8'))
                    
                    if alg == 'RSA':
                        signer = pss.new(private_key, salt_bytes=8) # FIX: Gunakan salt 8-byte sesuai draf
                    else:
                        signer = DSS.new(ecdsa_private_key, 'fips-186-3')
                    
                    # Timer untuk signature
                    sign_timer = Timer().start()
                    signature = signer.sign(hash_digest)
                    sign_time = sign_timer.stop()
                    massal_stats["total_sign_time"] += sign_time
                    
                    payload = {
                        "data": data,
                        "signature": base64.b64encode(signature).decode('utf-8'), # Algoritma default diubah ke RSA
                        "alg": alg
                    }
                    
                    # BUAT QR CODE DENGAN URL VERIFIKASI YANG DIOPTIMALKAN
                    qr_url, encoded_data = generate_verification_url(payload, base_url_override=base_url)
                    
                    # Timer untuk pembuatan QR
                    qr_gen_timer = Timer().start()
                    qr = qrcode.QRCode(
                        version=None,
                        error_correction=ERROR_CORRECT_Q,
                        box_size=2,  # Dikurangi dari 4 menjadi 2
                        border=1
                    )
                    qr.add_data(qr_url)  # Gunakan URL, bukan JSON
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white", contrast=1.3)
                    qr_time = qr_gen_timer.stop()
                    massal_stats["total_qr_time"] += qr_time
                    
                    # Timer untuk penyimpanan
                    save_timer = Timer().start()
                    filename = f"qr_{userid}_{secrets.token_hex(4)}.png"
                    filename = sanitize_filename(filename)
                    full_path = os.path.join(app.config['QR_MASSAL_FOLDER'], filename)
                    img.save(full_path, optimize=True, quality=85)  # KOMPRESI
                    
                    data_filename = filename.replace('.png', '.json')
                    data_path = os.path.join(app.config['DATA_FOLDER'], data_filename)
                    save_qr_record(data_path, data)
                    save_time = save_timer.stop()
                    massal_stats["total_save_time"] += save_time
                    
                    total_qr_time = qr_timer.stop()
                    massal_stats["individual_times"].append(total_qr_time)
                    
                    img_pil = Image.open(full_path)
                    width, height = img_pil.size
                    file_size_kb = os.path.getsize(full_path) / 1024
                    
                    # Simpan statistik
                    massal_stats["total_qr"] += 1
                    massal_stats["success_count"] += 1
                    massal_stats["total_file_size"] += file_size_kb
                    massal_stats["dimensions"].append((width, height))
                    
                    # Simpan ke statistik global
                    qr_stats.add_generate_stat(total_qr_time, file_size_kb, (width, height))
                    
                    # PERBAIKAN: Gunakan datetime.now(timezone.utc) untuk menghindari deprecation warning
                    log_row = [
                        "Massal", datetime.now(timezone.utc).isoformat(), data['nama'], data['id'],
                        data['qr_version'], data['qr_modules'], f"{width}x{height}",
                        f"{file_size_kb:.2f}", len(payload["signature"]),
                        f"{data_time:.6f}", f"{sign_time:.6f}", f"{qr_time:.6f}",
                        f"{save_time:.6f}", f"{total_qr_time:.6f}"
                    ]
                    _log_to_csv_extended(app.config['CSV_LOG_GENERATE'], log_row)
                    
                    hasil.append({
                        "no": row_num,
                        "nama": nama,
                        "id": userid,
                        "filename": filename,
                        "size": f"{file_size_kb:.2f} KB",
                        "resolution": f"{width} x {height} px",
                        "modules": f"{data['qr_modules']} x {data['qr_modules']}",
                        "version": data['qr_version'],
                        "signature_length": len(payload["signature"]),
                        "data_time": f"{data_time:.3f} detik",
                        "sign_time": f"{sign_time:.3f} detik",
                        "qr_time": f"{qr_time:.3f} detik",
                        "save_time": f"{save_time:.3f} detik",
                        "total_time": f"{total_qr_time:.3f} detik",
                        "qr_url": qr_url  # Tambahkan URL ke hasil
                    })
                    
                    generated_files.append(filename)
                    
                    app.logger.info(f"Generated QR untuk {nama} ({userid}) dari CSV dalam {total_qr_time:.3f} detik")
                    
                except Exception as e:
                    app.logger.error(f"Error pada baris {row_num}: {e}")
                    massal_stats["error_count"] += 1
                    hasil.append({
                        "no": row_num,
                        "nama": row.get('nama', 'ERROR'),
                        "id": row.get('id', 'ERROR'),
                        "filename": f"error_{row_num}",
                        "size": "ERROR",
                        "resolution": "ERROR",
                        "modules": "ERROR",
                        "version": "ERROR",
                        "signature_length": "ERROR",
                        "data_time": "ERROR",
                        "sign_time": "ERROR",
                        "qr_time": "ERROR",
                        "save_time": "ERROR",
                        "total_time": "ERROR"
                    })
            
            total_massal_time = total_massal_timer.stop()
            
            # Hitung statistik massal
            if massal_stats["individual_times"]:
                massal_stats["avg_time_per_qr"] = sum(massal_stats["individual_times"]) / len(massal_stats["individual_times"])
                massal_stats["min_time"] = min(massal_stats["individual_times"])
                massal_stats["max_time"] = max(massal_stats["individual_times"])
            else:
                massal_stats["avg_time_per_qr"] = 0
                massal_stats["min_time"] = 0
                massal_stats["max_time"] = 0
            
            massal_stats["total_time"] = total_massal_time
            massal_stats["success_rate"] = (massal_stats["success_count"] / massal_stats["total_qr"]) * 100 if massal_stats["total_qr"] > 0 else 0
            
            # Hitung dimensi rata-rata
            if massal_stats["dimensions"]:
                avg_width = sum(d[0] for d in massal_stats["dimensions"]) / len(massal_stats["dimensions"])
                avg_height = sum(d[1] for d in massal_stats["dimensions"]) / len(massal_stats["dimensions"])
                massal_stats["avg_dimension"] = f"{int(avg_width)}x{int(avg_height)}"
            else:
                massal_stats["avg_dimension"] = "N/A"
            
            # Simpan hasil ke task
            with task_lock:
                task['results'] = hasil
                task['massal_stats'] = massal_stats
                task['generated_files'] = generated_files
                task['generated_file_count'] = len(generated_files)
                task['is_processing'] = False
                task['is_complete'] = True
                if task.get('is_stopped'):
                    task['status'] = f'Proses dihentikan! {len(hasil)} QR Code berhasil digenerate dari total {total_rows}.'
                else:
                    task['status'] = f'Proses selesai! {len(hasil)} QR Code berhasil digenerate.'
                task_snapshot = dict(task)

            save_generate_task_snapshot(task_id, task_snapshot)
            
            # Update grafik evaluasi
            # Update chart di background thread
            chart_thread = threading.Thread(target=_update_evaluation_chart)
            chart_thread.daemon = True
            chart_thread.start()
            
            # Hapus file CSV sementara setelah 30 detik
            def cleanup_temp_file():
                time.sleep(30)  # Tunggu 30 detik untuk memastikan tidak ada yang masih mengakses
                try:
                    if os.path.exists(csv_path):
                        os.remove(csv_path)
                        app.logger.info(f"File sementara dihapus: {csv_path}")
                except Exception as e:
                    app.logger.warning(f"Gagal menghapus file sementara {csv_path}: {e}")
            
            # Jalankan cleanup di thread terpisah
            cleanup_thread = threading.Thread(target=cleanup_temp_file)
            cleanup_thread.daemon = True
            cleanup_thread.start()
            
            app.logger.info(f"Background process selesai untuk task {task_id}")
            
    except Exception as e:
        app.logger.error(f"Error dalam background_generate_process: {e}", exc_info=True)
        with task_lock:
            task = background_tasks.get(task_id)
            if task:
                task['error'] = str(e)
                task['is_processing'] = False
                task['is_complete'] = True
                task['status'] = f'Error: {str(e)[:100]}'

@app.route('/api/get_generate_results')
@limiter.exempt  # PENTING: Kecualikan dari rate limiting
@login_required
def get_generate_results():
    """API untuk mendapatkan hasil generate"""
    task_id = request.args.get('task_id') or session.get('current_task_id')
    
    if not task_id:
        return jsonify({'error': 'Tidak ada task ID'})
    
    with task_lock:
        progress = background_tasks.get(task_id, {})

    if not progress:
        progress = load_generate_task_snapshot(task_id) or {}

    if not progress:
        return jsonify({'error': 'Task tidak ditemukan'})
    
    if not progress.get('is_complete', False):
        return jsonify({'error': 'Proses belum selesai'})
    
    if progress.get('error'):
        return jsonify({'error': progress['error']})
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'results': progress.get('results', []),
        'massal_stats': progress.get('massal_stats', {}),
        'total_processed': progress.get('processed', 0),
        'total_rows': progress.get('total', 0)
    })


def _generate_result_seconds(value):
    try:
        return float(str(value).split()[0])
    except (TypeError, ValueError, IndexError):
        return 0.0


def _generate_result_size_kb(value):
    try:
        return float(str(value).split()[0])
    except (TypeError, ValueError, IndexError):
        return 0.0


def _generate_result_int(value):
    try:
        return int(str(value).split()[0])
    except (TypeError, ValueError, IndexError):
        return 0


def _generate_result_text(item):
    if not isinstance(item, dict):
        return ''
    fields = [
        item.get('no', ''),
        item.get('nama', ''),
        item.get('id', ''),
        item.get('filename', ''),
        item.get('size', ''),
        item.get('resolution', ''),
        item.get('version', ''),
        item.get('modules', ''),
        item.get('signature_length', ''),
        item.get('total_time', ''),
    ]
    return ' '.join(str(field or '') for field in fields).lower()


@app.route('/api/get_generate_results_page')
@limiter.exempt
@login_required
def get_generate_results_page():
    """API paginated untuk tabel hasil generate massal DataTables."""
    draw = _datatables_int_arg('draw', 1, minimum=0)
    task_id = request.args.get('task_id') or session.get('current_task_id')

    def empty_response(error_message=None, status_code=200):
        payload = {
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': []
        }
        if error_message:
            payload['error'] = error_message
        return jsonify(payload), status_code

    if not task_id:
        return empty_response('Tidak ada task ID', 400)

    progress = ensure_generate_task_loaded(task_id) or {}
    if not progress:
        return empty_response('Task tidak ditemukan', 404)

    if not progress.get('is_complete', False):
        return empty_response('Proses belum selesai', 409)

    if progress.get('error'):
        return empty_response(progress['error'], 500)

    results = progress.get('results') or []
    indexed_results = [
        (index, item if isinstance(item, dict) else {})
        for index, item in enumerate(results)
    ]

    search_value = (request.args.get('search[value]') or '').strip().lower()
    if search_value:
        filtered_results = [
            indexed_item
            for indexed_item in indexed_results
            if search_value in _generate_result_text(indexed_item[1])
        ]
    else:
        filtered_results = indexed_results

    order_column = _datatables_int_arg('order[0][column]', 0, minimum=0, maximum=9)
    order_dir = (request.args.get('order[0][dir]') or 'asc').lower()
    reverse_order = order_dir == 'desc'

    def sort_key(indexed_item):
        _, item = indexed_item
        if order_column == 0:
            return _generate_result_int(item.get('no'))
        if order_column == 1:
            return str(item.get('nama') or '').lower()
        if order_column == 2:
            return str(item.get('id') or '').lower()
        if order_column == 3:
            return str(item.get('filename') or '').lower()
        if order_column == 4:
            return _generate_result_size_kb(item.get('size'))
        if order_column == 5:
            return str(item.get('resolution') or '').lower()
        if order_column == 6:
            return _generate_result_int(item.get('version'))
        if order_column == 7:
            return _generate_result_int(item.get('modules'))
        if order_column == 8:
            return _generate_result_int(item.get('signature_length'))
        if order_column == 9:
            return _generate_result_seconds(item.get('total_time'))
        return 0

    if order_column != 0 or reverse_order:
        filtered_results = sorted(filtered_results, key=sort_key, reverse=reverse_order)

    max_page_length = 500
    start = _datatables_int_arg('start', 0, minimum=0)
    length = _datatables_int_arg('length', 10)
    if length < 0:
        length = max_page_length
    length = min(max(length, 1), max_page_length)

    page_results = []
    for original_index, item in filtered_results[start:start + length]:
        row = dict(item)
        row['result_index'] = original_index
        row.setdefault('no', original_index + 1)
        row.setdefault('nama', '-')
        row.setdefault('id', '-')
        row.setdefault('filename', '-')
        row.setdefault('size', '-')
        row.setdefault('resolution', '-')
        row.setdefault('version', '-')
        row.setdefault('modules', '-')
        row.setdefault('signature_length', '-')
        row.setdefault('data_time', '-')
        row.setdefault('sign_time', '-')
        row.setdefault('qr_time', '-')
        row.setdefault('save_time', '-')
        row.setdefault('total_time', '-')
        page_results.append(row)

    return jsonify({
        'draw': draw,
        'recordsTotal': len(results),
        'recordsFiltered': len(filtered_results),
        'data': page_results,
        'success': True,
        'task_id': task_id,
        'total_rows': progress.get('total', len(results))
    })


@app.route('/view_generate_results')
@login_required
def view_generate_results():
    """Halaman untuk melihat hasil generate"""
    task_id = request.args.get('task_id') or session.get('current_task_id')
    
    if not task_id:
        flash('Tidak ada proses generate yang aktif', 'warning')
        return redirect(url_for('generate_progress'))
    
    progress = load_generate_task_summary(task_id) or {}

    if not progress:
        flash('Proses generate tidak ditemukan', 'danger')
        return redirect(url_for('index'))
    
    if not progress.get('is_complete', False):
        flash('Proses generate belum selesai', 'warning')
        return redirect(url_for('generate_progress', task_id=task_id))
    
    if progress.get('error'):
        flash(f'Error dalam proses generate: {progress["error"]}', 'danger')
        return redirect(url_for('index'))
    
    massal_stats = progress.get('massal_stats', {})
    task_display_stats = build_generate_task_display_stats(massal_stats, [])
    generated_file_count = (
        progress.get('generated_file_count')
        or massal_stats.get('success_count')
        or massal_stats.get('total_qr')
        or progress.get('total')
        or progress.get('total_files')
        or 0
    )

    session.pop('last_generated_files', None)
    session['last_generated_task_id'] = task_id
    session['last_generated_count'] = generated_file_count
    session['last_generated_time'] = datetime.now().isoformat()

    return render_template("hasil_massal.html",
        hasil=[],
        massal_stats=massal_stats,
        task_display_stats=task_display_stats,
        task_id=task_id,
        generated_file_count=generated_file_count)

@app.route('/download_qr_massal')
@login_required
def download_qr_massal():
    try:
        task_id = (
            request.args.get('task_id')
            or session.get('last_generated_task_id')
            or session.get('current_task_id')
        )
        filenames = get_generated_filenames_for_task(task_id)

        if not filenames:
            filenames = session.get('last_generated_files', [])

        if not filenames:
            flash('Tidak ada file untuk diunduh', 'warning')
            return redirect(url_for('index'))
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filename in filenames:
                filepath = os.path.join(app.config['QR_MASSAL_FOLDER'], filename)
                if os.path.exists(filepath):
                    zipf.write(filepath, arcname=filename)
        
        zip_buffer.seek(0)
        
        session.pop('last_generated_files', None)
        session['last_generated_task_id'] = task_id
        session['last_generated_count'] = len(filenames)
        
        app.logger.info(f"Download ZIP dengan {len(filenames)} file untuk task {task_id}")
        log_audit_event('download_qr_massal', {
            'task_id': task_id,
            'file_count': len(filenames)
        })
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'qr_massal_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        )
        
    except Exception as e:
        app.logger.error(f"Error download_qr_massal: {e}")
        flash(f'Error saat download: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/verify_generated_task/<task_id>', methods=['POST'])
@login_required
def verify_generated_task(task_id):
    """Mulai verifikasi massal langsung dari QR hasil generate di server."""
    if not is_verification_feature_enabled():
        flash('Fitur verifikasi hasil generate sedang dinonaktifkan sementara.', 'warning')
        return redirect(url_for('index'))

    try:
        source_task = ensure_generate_task_loaded(task_id)
        if not source_task:
            flash('Task generate tidak ditemukan', 'warning')
            return redirect(url_for('index'))

        if not source_task.get('is_complete'):
            flash('Generate QR belum selesai. Tunggu proses selesai sebelum verifikasi.', 'warning')
            return redirect(url_for('generate_progress', task_id=task_id))

        if source_task.get('error'):
            flash(f'Task generate memiliki error: {source_task["error"]}', 'danger')
            return redirect(url_for('view_generate_results', task_id=task_id))

        filenames = get_generated_filenames_for_task(task_id)
        if not filenames:
            flash('Tidak ada file QR dari task generate ini untuk diverifikasi', 'warning')
            return redirect(url_for('view_generate_results', task_id=task_id))

        saved_files = []
        original_filenames = []
        missing_count = 0
        for filename in filenames:
            safe_filename = sanitize_filename(filename)
            file_path = os.path.join(app.config['QR_MASSAL_FOLDER'], safe_filename)
            if os.path.exists(file_path):
                saved_files.append(file_path)
                original_filenames.append(safe_filename)
            else:
                missing_count += 1

        if not saved_files:
            flash('File QR hasil generate tidak ditemukan di server', 'danger')
            return redirect(url_for('view_generate_results', task_id=task_id))

        verify_task_id = str(uuid.uuid4())
        with task_lock:
            prune_oldest_background_task_if_needed()
            background_tasks[verify_task_id] = {
                'type': 'verify_massal',
                'total': len(saved_files),
                'processed': 0,
                'current': 0,
                'status': f'Memulai verifikasi {len(saved_files)} QR hasil generate...',
                'is_processing': True,
                'is_complete': False,
                'start_time': datetime.now().isoformat(),
                'results': None,
                'massal_stats': None,
                'error': None,
                'is_stopped': False,
                'saved_files': saved_files,
                'original_filenames': original_filenames,
                'total_files': len(saved_files),
                'source_generate_task_id': task_id,
                'cleanup_saved_files': False
            }

        session['current_verify_task_id'] = verify_task_id
        if missing_count:
            flash(f'{missing_count} file QR dari hasil generate tidak ditemukan dan dilewati.', 'warning')

        thread = threading.Thread(target=background_verify_massal_process, args=(verify_task_id,))
        thread.daemon = True
        thread.start()

        app.logger.info(
            f"Verifikasi hasil generate dimulai: source_task={task_id}, "
            f"verify_task={verify_task_id}, file_count={len(saved_files)}"
        )
        return redirect(url_for('verify_massal_progress', task_id=verify_task_id))

    except Exception as e:
        app.logger.error(f"Error verify_generated_task: {e}", exc_info=True)
        flash(f'Error saat memulai verifikasi hasil generate: {str(e)}', 'danger')
        return redirect(url_for('view_generate_results', task_id=task_id))

@app.route('/download_all_qr_codes')
@login_required
def download_all_qr_codes():
    zip_path = None

    try:
        qr_files = list(iter_qr_png_files())
        if not qr_files:
            flash('Belum ada file QR Code untuk diunduh', 'warning')
            return redirect(url_for('view_log'))

        os.makedirs(app.config['QR_DOWNLOAD_FOLDER'], exist_ok=True)
        cleanup_old_qr_downloads()
        with tempfile.NamedTemporaryFile(
            prefix='semua_qrcode_',
            suffix='.zip',
            dir=app.config['QR_DOWNLOAD_FOLDER'],
            delete=False
        ) as tmp_file:
            zip_path = tmp_file.name

        counts = {'qr_tunggal': 0, 'qr_massal': 0, 'qr_modifikasi': 0}
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zipf:
            for category, filename, filepath in qr_files:
                safe_filename = sanitize_filename(filename)
                if not safe_filename:
                    continue

                arcname = f'{category}/{safe_filename}'
                zipf.write(filepath, arcname=arcname)
                counts[category] = counts.get(category, 0) + 1

            manifest = {
                'created_at': datetime.now(timezone.utc).isoformat(),
                'total_files': sum(counts.values()),
                'counts': counts,
                'folders': {
                    'qr_tunggal': app.config['QR_FOLDER'],
                    'qr_massal': app.config['QR_MASSAL_FOLDER'],
                    'qr_modifikasi': app.config['FAKE_QR_FOLDER']
                }
            }
            zipf.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))

        total_files = sum(counts.values())
        if total_files == 0:
            try:
                os.remove(zip_path)
            except OSError:
                pass
            flash('Belum ada file QR Code untuk diunduh', 'warning')
            return redirect(url_for('view_log'))

        download_name = f'semua_qrcode_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        app.logger.info(f"Download semua QR Code: {total_files} file -> {download_name}")
        log_audit_event('download_all_qr_codes', {
            'download_name': download_name,
            'total_files': total_files,
            'counts': counts
        })

        response = send_file(
            zip_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=download_name
        )

        def cleanup_zip(path=zip_path):
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception as cleanup_error:
                app.logger.warning(f'Gagal menghapus ZIP sementara {path}: {cleanup_error}')

        response.call_on_close(cleanup_zip)
        return response

    except Exception as e:
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except OSError:
                pass
        app.logger.error(f"Error download_all_qr_codes: {e}", exc_info=True)
        flash(f'Error saat download semua QR Code: {str(e)}', 'danger')
        return redirect(url_for('view_log'))

@app.route('/jobs')
@login_required
def jobs_page():
    jobs = list_job_summaries()
    return render_template('jobs.html', jobs=jobs)

@app.route('/security_profile')
@login_required
def security_profile():
    return render_template('security_profile.html', profile=get_security_profile_context())

@app.route('/cleanup_verify_payloads', methods=['POST'])
@login_required
def cleanup_verify_payloads():
    deleted = cleanup_old_verify_payloads()
    log_audit_event('cleanup_verify_payloads', {
        'deleted': deleted,
        'retention_days': app.config['VERIFY_PAYLOAD_RETENTION_DAYS']
    })
    flash(f'Cleanup payload selesai: {deleted} file lama dihapus.', 'success')
    return redirect(url_for('security_profile'))

@app.route('/audit_log')
@login_required
def view_audit_log():
    page = max(int(request.args.get('page', 1)), 1)
    per_page = min(max(int(request.args.get('per_page', 25)), 10), 250)
    headers = ["Waktu", "Aksi", "Actor", "IP", "User Agent", "Detail"]
    rows = []

    if os.path.exists(app.config['AUDIT_LOG']):
        try:
            with open(app.config['AUDIT_LOG'], 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as e:
            app.logger.warning(f"Gagal membaca audit log: {e}")
            rows = []

    rows.reverse()
    total_rows = len(rows)
    total_pages = math.ceil(total_rows / per_page) if total_rows else 1
    start = (page - 1) * per_page
    visible_rows = rows[start:start + per_page]

    return render_template(
        'audit_log.html',
        headers=headers,
        rows=visible_rows,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_rows=total_rows
    )

@app.route('/download_audit_log')
@login_required
def download_audit_log():
    if not os.path.exists(app.config['AUDIT_LOG']):
        flash('Audit log belum tersedia', 'warning')
        return redirect(url_for('view_audit_log'))

    log_audit_event('download_audit_log', {'path': app.config['AUDIT_LOG']})
    return send_file(
        app.config['AUDIT_LOG'],
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'audit_log_{datetime.now().strftime("%Y%m%d")}.csv'
    )

@app.route('/log')
@login_required
def view_log():
    try:
        # TINGKATKAN BATAS FIELD SIZE UNTUK CSV
        csv.field_size_limit(10 * 1024 * 1024)  # 10MB
        
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
        sumber_filter = request.args.get("sumber", "")
        date_filter = request.args.get("date", "")
        
        rows = []
        headers = []
        jumlah_data = 0
        statistik = {}
        qr_file_counts = get_qr_file_counts()
        
        if os.path.exists(app.config['CSV_LOG_GENERATE']):
            data = []
            with open(app.config['CSV_LOG_GENERATE'], 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    header = []
                
                if len(header) == 10:
                    new_header = [
                        "Sumber", "Waktu", "Nama", "ID", "Versi QR", "Modul", 
                        "Resolusi", "Ukuran File (KB)", "Panjang Signature",
                        "Waktu Data (detik)", "Waktu Sign (detik)", 
                        "Waktu QR (detik)", "Waktu Save (detik)", "Total Waktu (detik)"
                    ]
                else:
                    new_header = header
                
                # Baca baris dengan error handling lebih baik
                for i, row in enumerate(reader, start=1):
                    try:
                        if len(row) == 10:
                            new_row = row[:9] + ['0', '0', '0', '0'] + [row[9]]
                        elif len(row) == 14:
                            new_row = row
                        else:
                            app.logger.warning(f"Baris {i}: Jumlah kolom tidak sesuai: {len(row)}")
                            continue
                        data.append(new_row)
                    except Exception as e:
                        app.logger.warning(f"Error pada baris {i}: {e}")
                        continue
            
            if new_header and data:
                try:
                    df = pd.DataFrame(data, columns=new_header)
                    
                    # Konversi kolom ke tipe yang sesuai
                    numeric_cols = ["Versi QR", "Modul", "Ukuran File (KB)", "Panjang Signature", 
                                   "Waktu Data (detik)", "Waktu Sign (detik)", "Waktu QR (detik)", 
                                   "Waktu Save (detik)", "Total Waktu (detik)"]
                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    # Konversi kolom waktu dan urutkan dari terbaru
                    if 'Waktu' in df.columns:
                        df['Waktu'] = pd.to_datetime(df['Waktu'], errors='coerce')
                        # Urutkan dari terbaru ke terlama
                        df = df.sort_values('Waktu', ascending=False)
                    
                except Exception as e:
                    app.logger.error(f"Error membuat DataFrame: {e}")
                    df = pd.DataFrame()
            else:
                df = pd.DataFrame()
            
            # Filter berdasarkan sumber jika ada
            if sumber_filter and 'Sumber' in df.columns:
                df = df[df['Sumber'] == sumber_filter]
            
            # Filter berdasarkan tanggal jika ada
            if date_filter and 'Waktu' in df.columns:
                try:
                    date_obj = pd.to_datetime(date_filter).date()
                    df = df[df['Waktu'].dt.date == date_obj]
                except Exception as e:
                    app.logger.warning(f"Error filter tanggal: {e}")
            
            jumlah_data = len(df)
            
            if jumlah_data > 0:
                # Statistik dengan error handling
                try:
                    # Hitung statistik dari data yang sudah difilter
                    statistik = {
                        'total': jumlah_data,
                        'tunggal': len(df[df['Sumber'] == 'Tunggal']) if 'Sumber' in df.columns else 0,
                        'massal': len(df[df['Sumber'] == 'Massal']) if 'Sumber' in df.columns else 0,
                        'rata_waktu': df['Total Waktu (detik)'].mean() if 'Total Waktu (detik)' in df.columns else 0,
                        'rata_ukuran': df['Ukuran File (KB)'].mean() if 'Ukuran File (KB)' in df.columns else 0,
                        'rata_data_time': df['Waktu Data (detik)'].mean() if 'Waktu Data (detik)' in df.columns else 0,
                        'rata_sign_time': df['Waktu Sign (detik)'].mean() if 'Waktu Sign (detik)' in df.columns else 0,
                        'rata_qr_time': df['Waktu QR (detik)'].mean() if 'Waktu QR (detik)' in df.columns else 0,
                        'rata_save_time': df['Waktu Save (detik)'].mean() if 'Waktu Save (detik)' in df.columns else 0
                    }
                except Exception as e:
                    app.logger.error(f"Error menghitung statistik: {e}")
                    statistik = {
                        'total': jumlah_data,
                        'tunggal': 0,
                        'massal': 0,
                        'rata_waktu': 0,
                        'rata_ukuran': 0,
                        'rata_data_time': 0,
                        'rata_sign_time': 0,
                        'rata_qr_time': 0,
                        'rata_save_time': 0
                    }
                
                # Pagination dengan data yang sudah difilter dan diurutkan
                start = (page - 1) * per_page
                end = start + per_page
                try:
                    rows = df.iloc[start:end].to_dict('records')
                    attach_qr_previews_to_log_rows(rows)
                    headers = df.columns.tolist()
                    if LOG_QR_PREVIEW_HEADER not in headers:
                        headers.append(LOG_QR_PREVIEW_HEADER)
                    total_pages = math.ceil(jumlah_data / per_page) if per_page else 1
                except Exception as e:
                    app.logger.error(f"Error memotong data: {e}")
                    rows = []
                    headers = []
                    total_pages = 1
            else:
                total_pages = 1
        else:
            total_pages = 1
        
        return render_template(
            "log.html",
            headers=headers,
            rows=rows,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            jumlah_data=jumlah_data,
            statistik=statistik,
            qr_file_counts=qr_file_counts
        )
        
    except Exception as e:
        app.logger.error(f"Error view_log: {e}")
        flash(f'Error saat melihat log: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/log_verifikasi')
@login_required
def view_log_verifikasi():
    try:
        # TINGKATKAN BATAS FIELD SIZE UNTUK CSV
        csv.field_size_limit(10 * 1024 * 1024)  # 10MB
        
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
        filter_status = request.args.get("status", "").strip().lower()
        sumber_filter = request.args.get("sumber", "").strip()
        date_filter = request.args.get("date", "")
        
        rows = []
        headers = []
        jumlah_data = 0
        
        # Inisialisasi statistik dengan nilai default
        statistik = {
            'total': 0,
            'valid': 0,  # Hanya ✅ Valid dan Authentik
            'palsu': 0,  # ❌ Data Telah Dimodifikasi, ⛔ Data Tidak Ditemukan
            'replay': 0,  # 🔁 Replay Attack
            'tidak_ditemukan': 0,  # ⛔ Data Tidak Ditemukan di Database
            'signature_invalid': 0,  # ⚠️ Data Valid tapi Signature Invalid
            'kedaluwarsa': 0,  # ⏰ QR Code Kedaluwarsa
            'lainnya': 0,  # Status yang belum dikenali kategori mana pun
            'tunggal': 0,
            'massal': 0,
            'direct': 0,  # Direct/Scanner
            'rata_load_time': 0,
            'rata_decode_time': 0,
            'rata_verify_time': 0,
            'rata_db_time': 0,
            'rata_total_time': 0
        }
        
        if os.path.exists(app.config['CSV_LOG_VERIFIKASI']):
            data = []
            # COBA BERBAGAI ENCODING JIKA UTF-8 GAGAL
            encodings_to_try = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            
            for encoding in encodings_to_try:
                try:
                    with open(app.config['CSV_LOG_VERIFIKASI'], 'r', encoding=encoding, errors='replace') as f:
                        reader = csv.reader(f)
                        try:
                            header = next(reader)
                        except StopIteration:
                            header = []
                        
                        # Normalisasi header untuk versi lama dan baru
                        if len(header) == 8:
                            new_header = [
                                "Sumber", "Waktu", "Nama File", "Status", "Nama", "ID", "Perubahan Data",
                                "Waktu Load (detik)", "Waktu Decode (detik)", "Waktu Verify (detik)",
                                "Waktu DB (detik)", "Total Waktu (detik)"
                            ]
                        else:
                            new_header = header
                        
                        # Baca baris dengan error handling lebih baik
                        for i, row in enumerate(reader, start=1):
                            try:
                                # Bersihkan setiap cell dari karakter non-UTF-8
                                cleaned_row = []
                                for cell in row:
                                    if isinstance(cell, str):
                                        # Bersihkan karakter non-UTF-8
                                        cell = cell.encode('utf-8', 'replace').decode('utf-8', 'replace')
                                        # Hapus karakter kontrol
                                        cell = ''.join(char for char in cell if ord(char) >= 32 or char in '\t\n\r')
                                    cleaned_row.append(cell)
                                
                                # Normalisasi jumlah kolom
                                if len(cleaned_row) == 8:
                                    # Versi lama: tambahkan kolom waktu yang hilang
                                    new_row = cleaned_row[:7] + ['0', '0', '0', '0'] + [cleaned_row[7]]
                                elif len(cleaned_row) == 12:
                                    new_row = cleaned_row
                                else:
                                    # Jika tidak sesuai, skip atau isi dengan nilai default
                                    continue
                                
                                data.append(new_row)
                            except Exception as e:
                                app.logger.warning(f"Error pada baris {i}: {e}")
                                continue
                    
                    # Jika berhasil membaca dengan encoding ini, keluar dari loop
                    app.logger.info(f"Berhasil membaca file log dengan encoding: {encoding}")
                    break
                    
                except UnicodeDecodeError:
                    app.logger.warning(f"Encoding {encoding} gagal, mencoba encoding berikutnya...")
                    continue
                except Exception as e:
                    app.logger.error(f"Error membaca file dengan encoding {encoding}: {e}")
                    continue
            
            if new_header and data:
                try:
                    df = pd.DataFrame(data, columns=new_header)
                    
                    # Konversi kolom waktu dengan error handling
                    if 'Waktu' in df.columns:
                        # Bersihkan data waktu
                        df['Waktu'] = df['Waktu'].apply(
                            lambda x: str(x).split('.')[0] if pd.notnull(x) else None
                        )
                        df['Waktu'] = pd.to_datetime(df['Waktu'], errors='coerce')
                    
                        # Urutkan dari terbaru ke terlama agar data terbaru tampil di halaman pertama
                        df = df.sort_values('Waktu', ascending=False)
                    
                    # Konversi kolom numerik dengan error handling
                    numeric_cols = [
                        "Waktu Load (detik)", "Waktu Decode (detik)", 
                        "Waktu Verify (detik)", "Waktu DB (detik)", "Total Waktu (detik)"
                    ]
                    
                    for col in numeric_cols:
                        if col in df.columns:
                            # Bersihkan data sebelum konversi
                            df[col] = df[col].apply(
                                lambda x: str(x).replace('�', '0').replace(',', '.').strip() 
                                if pd.notnull(x) else '0'
                            )
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    # Filter berdasarkan tanggal jika ada
                    if date_filter:
                        try:
                            date_obj = pd.to_datetime(date_filter).date()
                            df['Waktu_Date'] = df['Waktu'].dt.date
                            df = df[df['Waktu_Date'] == date_obj]
                        except Exception as e:
                            app.logger.warning(f"Error filter tanggal: {e}")
                    
                    # Filter berdasarkan sumber jika ada
                    if sumber_filter and 'Sumber' in df.columns:
                        df = df[df['Sumber'] == sumber_filter]
                    
                    # Filter berdasarkan status dengan LOGIKA YANG DIPERBAIKI
                    if filter_status and 'Status' in df.columns:
                        status_mapping = {
                            'valid': ['✅ Valid dan Authentik', '✅ Valid'],
                            'palsu': ['❌ Data Telah Dimodifikasi', '❌ Data Palsu'],
                            'replay': ['🔁', 'Replay Attack'],
                            'signature_invalid': ['⚠️ Data Valid tapi Signature Invalid'],
                            'tidak_ditemukan': ['⛔ Data Tidak Ditemukan', '⛔ Data Tidak Ditemukan di Database'],
                            'kedaluwarsa': ['⏰ QR Code Kedaluwarsa', 'Kedaluwarsa'],
                            'error': ['❌ Error', '❌ Format QR', '⛔ Tidak dapat membaca QR']
                        }
                        
                        if filter_status in status_mapping:
                            status_patterns = status_mapping[filter_status]
                            mask = df['Status'].astype(str).apply(
                                lambda x: any(pattern in x for pattern in status_patterns)
                            )
                            df = df[mask]
                    
                    jumlah_data = len(df)
                    
                    if jumlah_data > 0:
                        # Hitung statistik dengan LOGIKA YANG DIPERBAIKI
                        if 'Status' in df.columns and 'Sumber' in df.columns:
                            for status_val in df['Status'].astype(str):
                                # Logika statistik yang lebih akurat
                                if '✅ Valid dan Authentik' in status_val:
                                    statistik['valid'] += 1
                                elif '🔁' in status_val:
                                    statistik['replay'] += 1
                                elif '⚠️ Data Valid tapi Signature Invalid' in status_val:
                                    statistik['signature_invalid'] += 1
                                elif '⛔ Data Tidak Ditemukan' in status_val:
                                    statistik['tidak_ditemukan'] += 1
                                    statistik['palsu'] += 1
                                elif 'Kedaluwarsa' in status_val:
                                    # Kategori tersendiri: QR sah yang lewat batas umur
                                    # bukan pemalsuan, jadi tidak ditambahkan ke 'palsu'.
                                    statistik['kedaluwarsa'] += 1
                                elif '❌ Data Telah Dimodifikasi' in status_val or '❌ Data Palsu' in status_val:
                                    statistik['palsu'] += 1
                                else:
                                    # Penampung status yang belum dikenali, termasuk error.
                                    # Tanpa cabang ini status baru hilang dari seluruh
                                    # kategori sementara 'total' tetap menghitungnya.
                                    statistik['lainnya'] += 1
                            
                            # Hitung berdasarkan sumber
                            sumber_counts = df['Sumber'].value_counts()
                            for sumber, count in sumber_counts.items():
                                if sumber == 'Tunggal':
                                    statistik['tunggal'] = count
                                elif sumber in ['Massal', 'Massal_Async']:
                                    statistik['massal'] += count
                                elif sumber in ['Direct/Scanner', 'Kamera HP']:
                                    statistik['direct'] += count
                        
                        # Hitung total
                        statistik['total'] = jumlah_data
                        
                        # Hitung rata-rata waktu
                        time_columns = {
                            'Waktu Load (detik)': 'rata_load_time',
                            'Waktu Decode (detik)': 'rata_decode_time',
                            'Waktu Verify (detik)': 'rata_verify_time',
                            'Waktu DB (detik)': 'rata_db_time',
                            'Total Waktu (detik)': 'rata_total_time'
                        }
                        
                        for col, key in time_columns.items():
                            if col in df.columns:
                                valid_times = pd.to_numeric(df[col], errors='coerce')
                                valid_times = valid_times.dropna()
                                if not valid_times.empty:
                                    statistik[key] = valid_times.mean()
                        
                        # Pagination dengan error handling
                        try:
                            start = (page - 1) * per_page
                            end = start + per_page
                            rows = df.iloc[start:end].to_dict('records')
                            headers = df.columns.tolist()
                            total_pages = math.ceil(jumlah_data / per_page) if per_page and jumlah_data > 0 else 1
                        except Exception as e:
                            app.logger.error(f"Error memotong data: {e}")
                            rows = df.to_dict('records') if not df.empty else []
                            headers = df.columns.tolist() if not df.empty else []
                            total_pages = 1
                    else:
                        total_pages = 1
                        
                except Exception as e:
                    app.logger.error(f"Error memproses DataFrame: {e}", exc_info=True)
                    rows = []
                    headers = []
                    total_pages = 1
            else:
                total_pages = 1
        else:
            total_pages = 1
        
        # Debug info
        app.logger.info(f"Statistik log verifikasi: {statistik}")
        app.logger.info(f"Filter diterapkan: status={filter_status}, sumber={sumber_filter}, date={date_filter}")
        
        return render_template(
            "log_verifikasi.html",
            headers=headers,
            rows=rows,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            jumlah_data=jumlah_data,
            statistik=statistik,
            status_selected=filter_status,
            sumber_selected=sumber_filter,
            date_selected=date_filter
        )
        
    except Exception as e:
        app.logger.error(f"Error view_log_verifikasi: {e}", exc_info=True)
        flash(f'Error saat melihat log verifikasi: {str(e)}', 'danger')
        return redirect(url_for('index'))

# Tambahkan juga perbaikan untuk fungsi calculate_stats_from_logs()
def calculate_stats_from_logs():
    """Menghitung statistik dari log file yang sudah ada - DIPERBAIKI"""
    global qr_stats
    
    try:
        app.logger.info("Menghitung statistik dari log file...")
        
        # Reset statistik
        qr_stats._reset_to_defaults()
        
        # Hitung dari log generate
        if os.path.exists(app.config['CSV_LOG_GENERATE']):
            try:
                df = pd.read_csv(
                    app.config['CSV_LOG_GENERATE'], 
                    engine='python', 
                    on_bad_lines='skip',
                    encoding_errors='replace'
                )
                
                if not df.empty:
                    # Hitung statistik generate
                    qr_stats.qr_count = len(df)
                    
                    # Waktu generate
                    if 'Total Waktu (detik)' in df.columns:
                        valid_times = pd.to_numeric(df['Total Waktu (detik)'], errors='coerce').dropna()
                        if not valid_times.empty:
                            qr_stats.total_generate_time = valid_times.sum()
                    
                    # Ukuran file
                    if 'Ukuran File (KB)' in df.columns:
                        valid_sizes = pd.to_numeric(df['Ukuran File (KB)'], errors='coerce').dropna()
                        qr_stats.file_sizes = valid_sizes.tolist()
                    
                    # Dimensi
                    if 'Resolusi' in df.columns:
                        for resolusi in df['Resolusi'].astype(str):
                            try:
                                if 'x' in resolusi:
                                    parts = resolusi.split('x')
                                    if len(parts) >= 2:
                                        width = int(float(parts[0].strip()))
                                        height = int(float(parts[1].strip()))
                                        qr_stats.dimensions.append((width, height))
                            except:
                                continue
                    
                    app.logger.info(f"Ditemukan {qr_stats.qr_count} entri log generate")
            except Exception as e:
                app.logger.error(f"Error reading generate log: {e}")
        
        # Hitung dari log verifikasi
        if os.path.exists(app.config['CSV_LOG_VERIFIKASI']):
            try:
                df = pd.read_csv(
                    app.config['CSV_LOG_VERIFIKASI'],
                    engine='python',
                    on_bad_lines='skip',
                    encoding_errors='replace'
                )
                
                if not df.empty:
                    # Hitung total verifikasi
                    qr_stats.verify_count = len(df)
                    
                    # Hitung success count dari kolom Status
                    if 'Status' in df.columns:
                        qr_stats.success_verify_count = int(df['Status'].astype(str).str.contains('✅').sum())

                    # Waktu verifikasi
                    if 'Total Waktu (detik)' in df.columns:
                        valid_times = pd.to_numeric(df['Total Waktu (detik)'], errors='coerce').dropna()
                        if not valid_times.empty:
                            qr_stats.total_verify_time = float(valid_times.sum())
                    
                    app.logger.info(f"Ditemukan {qr_stats.verify_count} entri log verifikasi")
            except Exception as e:
                app.logger.error(f"Error reading verify log: {e}")
        
        # Simpan ke file
        save_stats_to_file(qr_stats)
        
        app.logger.info(f"Statistik dihitung ulang: {qr_stats.qr_count} QR, {qr_stats.verify_count} verify")
        
        return True
        
    except Exception as e:
        app.logger.error(f"Error calculating stats from logs: {e}")
        return False

@app.route('/download_log_verifikasi_excel')
@login_required
def download_log_verifikasi_excel():
    try:
        if not os.path.exists(app.config['CSV_LOG_VERIFIKASI']):
            flash('Log verifikasi belum tersedia', 'warning')
            return redirect(url_for('view_log_verifikasi'))
        
        # Baca dengan encoding alternatif
        encodings_to_try = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        df = None
        
        for encoding in encodings_to_try:
            try:
                df = pd.read_csv(app.config['CSV_LOG_VERIFIKASI'], 
                                encoding=encoding,
                                engine='python',
                                on_bad_lines='skip',
                                encoding_errors='replace')
                
                # Bersihkan data
                for col in df.columns:
                    if df[col].dtype == 'object':
                        df[col] = df[col].astype(str).apply(
                            lambda x: x.encode('utf-8', 'replace').decode('utf-8', 'replace') 
                            if isinstance(x, str) else x
                        )
                
                app.logger.info(f"Berhasil membaca log dengan encoding: {encoding}")
                break
                
            except UnicodeDecodeError:
                app.logger.warning(f"Encoding {encoding} gagal, mencoba berikutnya...")
                continue
            except Exception as e:
                app.logger.error(f"Error membaca dengan encoding {encoding}: {e}")
                continue
        
        if df is None or df.empty:
            flash('Tidak dapat membaca file log verifikasi', 'danger')
            return redirect(url_for('view_log_verifikasi'))
        
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Log Verifikasi')
            
            # Buat sheet summary jika ada data
            if 'Status' in df.columns:
                status_counts = df['Status'].value_counts()
                summary_data = {
                    'Status': status_counts.index.tolist(),
                    'Jumlah': status_counts.values.tolist()
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, index=False, sheet_name='Summary')
            
            # Buat sheet waktu jika kolom waktu ada
            time_stats = {}
            time_columns = [
                'Waktu Load (detik)', 'Waktu Decode (detik)', 
                'Waktu Verify (detik)', 'Total Waktu (detik)'
            ]
            
            for col in time_columns:
                if col in df.columns:
                    # Konversi ke numerik dan hitung rata-rata
                    numeric_data = pd.to_numeric(df[col], errors='coerce')
                    if not numeric_data.empty:
                        time_stats[f'Rata-rata {col}'] = [numeric_data.mean()]
            
            if time_stats:
                time_df = pd.DataFrame(time_stats)
                time_df.to_excel(writer, index=False, sheet_name='Waktu')
        
        output.seek(0)
        
        app.logger.info("Log verifikasi di-download sebagai Excel")
        log_audit_event('download_log_verifikasi_excel', {'rows': len(df)})
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'log_verifikasi_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
        
    except Exception as e:
        app.logger.error(f"Error download_log_verifikasi_excel: {e}", exc_info=True)
        flash(f'Error saat download log verifikasi: {str(e)}', 'danger')
        return redirect(url_for('view_log_verifikasi'))

@app.route('/download_log_excel')
@login_required
def download_log_excel():
    try:
        if not os.path.exists(app.config['CSV_LOG_GENERATE']):
            flash('Log generate belum tersedia', 'warning')
            return redirect(url_for('view_log'))
        
        df = pd.read_csv(app.config['CSV_LOG_GENERATE'], engine='python', on_bad_lines='skip')
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Log Generate')
            
            summary_data = {}
            if 'Total Waktu (detik)' in df.columns:
                summary_data['Rata-rata Total Waktu (detik)'] = [df['Total Waktu (detik)'].mean()]
            if 'Ukuran File (KB)' in df.columns:
                summary_data['Rata-rata Ukuran File (KB)'] = [df['Ukuran File (KB)'].mean()]
            if 'Waktu Data (detik)' in df.columns:
                summary_data['Rata-rata Waktu Data (detik)'] = [df['Waktu Data (detik)'].mean()]
            if 'Waktu Sign (detik)' in df.columns:
                summary_data['Rata-rata Waktu Sign (detik)'] = [df['Waktu Sign (detik)'].mean()]
            if 'Waktu QR (detik)' in df.columns:
                summary_data['Rata-rata Waktu QR (detik)'] = [df['Waktu QR (detik)'].mean()]
            if 'Waktu Save (detik)' in df.columns:
                summary_data['Rata-rata Waktu Save (detik)'] = [df['Waktu Save (detik)'].mean()]
            
            summary_data['Total Records'] = [len(df)]
            if 'Sumber' in df.columns:
                summary_data['Tunggal'] = [len(df[df['Sumber'] == 'Tunggal'])]
                summary_data['Massal'] = [len(df[df['Sumber'] == 'Massal'])]
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, index=False, sheet_name='Summary')
        
        output.seek(0)
        
        app.logger.info("Log generate di-download sebagai Excel")
        log_audit_event('download_log_generate_excel', {'rows': len(df)})
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'log_generate_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
        
    except Exception as e:
        app.logger.error(f"Error download_log_excel: {e}")
        flash(f'Error saat download log: {str(e)}', 'danger')
        return redirect(url_for('view_log'))

@app.route('/filter_log_by_date')
def filter_log_by_date():
    try:
        date_str = request.args.get('date')
        if not date_str:
            return redirect(url_for('view_log'))
        
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        if os.path.exists(app.config['CSV_LOG_GENERATE']):
            df = pd.read_csv(app.config['CSV_LOG_GENERATE'], engine='python', on_bad_lines='skip')
            df['Waktu'] = pd.to_datetime(df['Waktu']).dt.date
            filtered_df = df[df['Waktu'] == date_obj]
            
            rows = filtered_df.to_dict('records')
            headers = filtered_df.columns.tolist() if not filtered_df.empty else []
            
            return render_template('log.html',
                headers=headers,
                rows=rows,
                page=1,
                per_page=len(rows),
                total_pages=1,
                jumlah_data=len(rows),
                filtered_date=date_str
            )
        else:
            flash('Log belum tersedia', 'warning')
            return redirect(url_for('view_log'))
            
    except ValueError:
        flash('Format tanggal salah. Gunakan YYYY-MM-DD.', 'warning')
        return redirect(url_for('view_log'))
    except Exception as e:
        app.logger.error(f"Error filter_log_by_date: {e}")
        flash(f'Error saat filter log: {str(e)}', 'danger')
        return redirect(url_for('view_log'))

@app.route('/filter_log_verifikasi_by_date')
def filter_log_verifikasi_by_date():
    try:
        date_str = request.args.get('date')
        if not date_str:
            return redirect(url_for('view_log_verifikasi'))
        
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        if os.path.exists(app.config['CSV_LOG_VERIFIKASI']):
            df = pd.read_csv(app.config['CSV_LOG_VERIFIKASI'], engine='python', on_bad_lines='skip')
            df['Waktu'] = pd.to_datetime(df['Waktu']).dt.date
            filtered_df = df[df['Waktu'] == date_obj]
            
            rows = filtered_df.to_dict('records')
            headers = filtered_df.columns.tolist() if not filtered_df.empty else []
            
            return render_template('log_verifikasi.html',
                headers=headers,
                rows=rows,
                page=1,
                per_page=len(rows),
                total_pages=1,
                jumlah_data=len(rows),
                filtered_date=date_str
            )
        else:
            flash('Log verifikasi belum tersedia', 'warning')
            return redirect(url_for('view_log_verifikasi'))
            
    except ValueError:
        flash('Format tanggal salah. Gunakan YYYY-MM-DD.', 'warning')
        return redirect(url_for('view_log_verifikasi'))
    except Exception as e:
        app.logger.error(f"Error filter_log_verifikasi_by_date: {e}")
        flash(f'Error saat filter log: {str(e)}', 'danger')
        return redirect(url_for('view_log_verifikasi'))

@app.route('/hapus_log/<jenis>', methods=['GET', 'POST'])
@login_required
def hapus_log(jenis):
    try:
        if jenis == "generate":
            log_path = app.config['CSV_LOG_GENERATE']
            redirect_url = 'view_log'
        elif jenis == "verifikasi":
            log_path = app.config['CSV_LOG_VERIFIKASI']
            redirect_url = 'view_log_verifikasi'
        else:
            flash("Jenis log tidak dikenal", "warning")
            return redirect(url_for('index'))
        
        if os.path.exists(log_path):
            backup_path = f"{log_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(log_path, backup_path)
            
            if jenis == "generate" and os.path.exists(app.config['NONCE_LOG']):
                nonce_backup = f"{app.config['NONCE_LOG']}.backup"
                os.rename(app.config['NONCE_LOG'], nonce_backup)
            
            app.logger.warning(f"Log {jenis} dihapus, backup dibuat: {backup_path}")
            log_audit_event('hapus_log', {
                'jenis': jenis,
                'backup_path': backup_path
            })
            flash(f"Log {jenis} berhasil dihapus (backup dibuat)", "success")
        else:
            flash(f"Log {jenis} tidak ditemukan", "warning")
        
        return redirect(url_for(redirect_url))
        
    except Exception as e:
        app.logger.error(f"Error hapus_log: {e}")
        flash(f'Error saat menghapus log: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/testing_dashboard')
@login_required
def redirect_to_testing():
    """Redirect ke testing dashboard"""
    return redirect(url_for('testing.testing_dashboard'))

# Jendela pengukuran latensi dashboard.
#
# Tanpa jendela, P95 dihitung atas seluruh riwayat CSV sehingga satu sesi lambat
# mengunci grade selamanya: P95 adalah persentil, jadi K baris lambat baru turun
# di bawahnya setelah ada 19K baris cepat. Akibatnya grade hanya bisa dipulihkan
# lewat Reset Statistik — yang ikut menghapus seluruh data QR.
#
# 28 hari dipilih mengikuti praktik lazim, bukan standar yang mengikat: Core Web
# Vitals (CrUX) memakai jendela bergulir 28 hari, dan error budget SRE umumnya
# 28 hari. Empat minggu penuh membuat komposisi hari kerja dan akhir pekan
# seimbang; jendela 30 hari menggeser komposisi itu dan menyuntikkan musiman
# mingguan ke dalam angka.
DASHBOARD_GRADE_WINDOW_DAYS = 28
DASHBOARD_TREND_WINDOW_DAYS = 7

# Di bawah ambang ini P95 tidak bermakna. Dengan index = round((n-1)*0.95),
# untuk n <= 11 nilai P95 persis sama dengan permintaan terlambat, sehingga satu
# permintaan lambat langsung menetapkan grade.
DASHBOARD_GRADE_MIN_SAMPLES = 20


def _is_batch_source(source):
    """Item batch bukan permintaan interaktif dan tidak layak masuk grade.

    Satu scan kamera adalah satu permintaan HTTP yang ditunggu pengguna,
    sedangkan satu baris Massal hanyalah satu berkas di dalam satu unggahan.
    Mencampurnya membuat grade dapat dinaikkan sekadar dengan menjalankan batch
    besar: 20.000 item cepat mengencerkan scan kamera yang lambat tanpa ada yang
    membaik. Grade karenanya dihitung dari sumber interaktif saja.
    """
    return str(source or '').strip().lower().startswith('massal')


def _parse_log_timestamp(value):
    try:
        return datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None


def _empty_timing_summary():
    return {
        'count': 0,
        'total_s': 0.0,
        'mean_s': 0.0,
        'median_s': 0.0,
        'p90_s': 0.0,
        'p95_s': 0.0,
        'p99_s': 0.0,
        'max_s': 0.0,
        'outliers_over_1s': 0,
        'file_size_mean_kb': 0.0,
        'file_size_median_kb': 0.0,
        'by_source': {},
        'interactive_count': 0,
        'interactive_p95_s': 0.0,
        'interactive_median_s': 0.0,
        'batch_count': 0,
        'batch_p95_s': 0.0,
        'batch_median_s': 0.0,
        'window_days': None,
        'skipped_no_timestamp': 0,
    }

def _percentile(sorted_values, percentile):
    if not sorted_values:
        return 0.0
    index = round((len(sorted_values) - 1) * percentile / 100)
    index = max(0, min(len(sorted_values) - 1, index))
    return sorted_values[index]

# Ambang grade bersandar pada batas persepsi respons Miller (1968) yang
# dipopulerkan Nielsen (1993, Usability Engineering bab 5):
#
#   0,1 detik — pengguna merasa sistem bereaksi seketika
#   1,0 detik — alur pikir pengguna tidak terputus meski jeda terasa
#
# Grade A dan C memetakan langsung ke kedua batas itu. Grade B pada 300 ms adalah
# interpolasi internal tanpa rujukan kanonik, dan dinyatakan demikian.
#
# Catatan: versi sebelumnya mengutip RAIL untuk ambang 100 ms. Rujukan itu keliru.
# RAIL adalah model performa antarmuka web, dan 100 ms di sana adalah anggaran
# persepsi untuk umpan balik visual atas input pengguna, bukan target latensi API
# sisi server. RAIL juga sama sekali tidak mengenal sistem grade A-D.
RESPONSE_GRADE_REFERENCE = 'Miller (1968) & Nielsen (1993): batas 0,1 s dan 1,0 s'


def _response_grade(seconds, sample_count=None):
    """Grade latensi. sample_count di bawah ambang minimum menghasilkan N/A."""
    if sample_count is not None and sample_count < DASHBOARD_GRADE_MIN_SAMPLES:
        return {
            'grade': 'N/A',
            'label': f'Data belum cukup ({sample_count}/{DASHBOARD_GRADE_MIN_SAMPLES})',
            'class': 'text-muted',
            'progress': 0,
            'insufficient': True,
        }

    ms = seconds * 1000
    if seconds <= 0:
        return {'grade': 'N/A', 'label': 'N/A', 'class': 'text-muted', 'progress': 0}
    if ms <= 100:
        return {'grade': 'A', 'label': 'Grade A', 'class': 'text-success', 'progress': 100}
    if ms <= 300:
        return {'grade': 'B', 'label': 'Grade B', 'class': 'text-info', 'progress': 80}
    if ms <= 1000:
        return {'grade': 'C', 'label': 'Grade C', 'class': 'text-warning', 'progress': 60}
    return {'grade': 'D', 'label': 'Grade D', 'class': 'text-danger', 'progress': 40}

def _summarize_timing_csv(path, window_days=None):
    """Ringkas kolom waktu dari CSV log, opsional dibatasi jendela bergulir."""
    summary = _empty_timing_summary()
    summary['window_days'] = window_days
    if not os.path.exists(path):
        return summary

    batas = None
    if window_days:
        batas = datetime.now(timezone.utc) - timedelta(days=window_days)

    values = []
    file_size_values = []
    interactive_values = []
    batch_values = []
    by_source_values = defaultdict(list)
    skipped_no_timestamp = 0
    try:
        with open(path, newline='', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    value = float(str(row.get('Total Waktu (detik)', '')).strip())
                except (TypeError, ValueError):
                    continue
                if value < 0:
                    continue

                if batas is not None:
                    waktu = _parse_log_timestamp(row.get('Waktu'))
                    if waktu is None:
                        # Baris tanpa timestamp yang terbaca tidak dapat ditempatkan
                        # dalam jendela; dikeluarkan agar tidak menyelundup sebagai
                        # data terkini, dan jumlahnya dilaporkan.
                        skipped_no_timestamp += 1
                        continue
                    if waktu.tzinfo is None:
                        waktu = waktu.replace(tzinfo=timezone.utc)
                    if waktu < batas:
                        continue

                values.append(value)
                source = row.get('Sumber') or row.get('Jenis') or '-'
                by_source_values[source].append(value)
                if _is_batch_source(source):
                    batch_values.append(value)
                else:
                    interactive_values.append(value)

                try:
                    file_size = float(str(row.get('Ukuran File (KB)', '')).strip())
                except (TypeError, ValueError):
                    file_size = None
                if file_size is not None and file_size >= 0:
                    file_size_values.append(file_size)
    except Exception as e:
        app.logger.error(f'Error summarizing timing log {path}: {e}')
        return summary

    if not values:
        return summary

    sorted_values = sorted(values)
    summary.update({
        'count': len(values),
        'total_s': sum(values),
        'mean_s': statistics.mean(values),
        'median_s': statistics.median(values),
        'p90_s': _percentile(sorted_values, 90),
        'p95_s': _percentile(sorted_values, 95),
        'p99_s': _percentile(sorted_values, 99),
        'max_s': sorted_values[-1],
        'outliers_over_1s': sum(1 for value in values if value > 1),
    })

    if file_size_values:
        summary.update({
            'file_size_mean_kb': statistics.mean(file_size_values),
            'file_size_median_kb': statistics.median(file_size_values),
        })

    for source, source_values in by_source_values.items():
        source_sorted = sorted(source_values)
        summary['by_source'][source] = {
            'count': len(source_values),
            'mean_s': statistics.mean(source_values),
            'median_s': statistics.median(source_values),
            'p95_s': _percentile(source_sorted, 95),
            'max_s': source_sorted[-1],
            'is_batch': _is_batch_source(source),
        }

    if interactive_values:
        interactive_sorted = sorted(interactive_values)
        summary.update({
            'interactive_count': len(interactive_values),
            'interactive_p95_s': _percentile(interactive_sorted, 95),
            'interactive_median_s': statistics.median(interactive_values),
        })

    # Angka batch tidak pernah masuk grade, tetapi tetap dilaporkan. Tanpa ini
    # dashboard tampak kosong pada instalasi yang beban kerjanya murni verifikasi
    # massal, padahal ratusan ribu berkas baru saja diproses.
    if batch_values:
        batch_sorted = sorted(batch_values)
        summary.update({
            'batch_count': len(batch_values),
            'batch_p95_s': _percentile(batch_sorted, 95),
            'batch_median_s': statistics.median(batch_values),
        })

    summary['skipped_no_timestamp'] = skipped_no_timestamp
    return summary

def _build_dashboard_performance_summary(cache):
    generate_path = app.config['CSV_LOG_GENERATE']
    verify_path = app.config['CSV_LOG_VERIFIKASI']
    signature = (
        os.path.getmtime(generate_path) if os.path.exists(generate_path) else 0,
        os.path.getsize(generate_path) if os.path.exists(generate_path) else 0,
        os.path.getmtime(verify_path) if os.path.exists(verify_path) else 0,
        os.path.getsize(verify_path) if os.path.exists(verify_path) else 0,
    )

    # Cache ikut memuat tanggal: jendela bergulir bergeser tiap hari meskipun
    # berkas log tidak berubah sama sekali.
    signature = signature + (datetime.now(timezone.utc).strftime('%Y-%m-%d'),)

    if cache.get('performance_signature') == signature and cache.get('performance_summary'):
        return cache['performance_summary']

    generate_summary = _summarize_timing_csv(generate_path, DASHBOARD_GRADE_WINDOW_DAYS)
    verify_summary = _summarize_timing_csv(verify_path, DASHBOARD_GRADE_WINDOW_DAYS)
    verify_trend = _summarize_timing_csv(verify_path, DASHBOARD_TREND_WINDOW_DAYS)
    generate_target_s = 0.2
    generate_median_s = generate_summary['median_s']
    throughput_ops = (1 / generate_median_s) if generate_median_s > 0 else 0
    generate_p95_s = generate_summary['p95_s']
    target_attainment = min(100, (generate_target_s / generate_p95_s) * 100) if generate_p95_s > 0 else 0

    # Grade dihitung dari permintaan interaktif saja. Bila belum ada satu pun
    # dalam jendela, jangan diam-diam jatuh ke agregat gabungan — laporkan
    # sebagai data belum cukup, karena angka gabungan didominasi item batch.
    grade_p95_s = verify_summary['interactive_p95_s']
    grade_count = verify_summary['interactive_count']

    performance_summary = {
        'generate': {
            **generate_summary,
            'throughput_ops_s': throughput_ops,
            'target_s': generate_target_s,
            'target_ops_s': 1 / generate_target_s,
            'throughput_efficiency': max(0, target_attainment),
        },
        'verify': {
            **verify_summary,
            'grade_metric': 'p95 interaktif',
            'grade': _response_grade(grade_p95_s, grade_count),
            'grade_p95_s': grade_p95_s,
            'grade_sample_count': grade_count,
            'median_grade': _response_grade(verify_summary['interactive_median_s'], grade_count),
            'mean_grade': _response_grade(verify_summary['mean_s']),
            'trend': {
                'window_days': DASHBOARD_TREND_WINDOW_DAYS,
                'p95_s': verify_trend['interactive_p95_s'],
                'count': verify_trend['interactive_count'],
                'grade': _response_grade(
                    verify_trend['interactive_p95_s'], verify_trend['interactive_count']
                ),
            },
        },
        'meta': {
            'grade_window_days': DASHBOARD_GRADE_WINDOW_DAYS,
            'trend_window_days': DASHBOARD_TREND_WINDOW_DAYS,
            'min_samples': DASHBOARD_GRADE_MIN_SAMPLES,
            'grade_reference': RESPONSE_GRADE_REFERENCE,
        },
    }

    cache['performance_signature'] = signature
    cache['performance_summary'] = performance_summary
    return performance_summary

@app.route('/dashboard')
@limiter.limit(app.config['RATELIMIT_DASHBOARD'])
@login_required
def dashboard():
    # Inisialisasi cache jika belum ada
    if not hasattr(app, 'dashboard_cache'):
        app.dashboard_cache = {
            'stats': {
                'generate': {'total': 0, 'tunggal': 0, 'massal': 0},
                'verifikasi': {'total': 0, 'valid': 0, 'invalid': 0, 'replay': 0}
            },
            'file_counts': {
                'qr_tunggal': 0, 'qr_massal': 0, 'qr_fake': 0, 'data_json': 0, 'uploads': 0
            },
            'mtimes': {},
            'last_count_time': 0
        }
    
    # Gunakan cache
    cache = app.dashboard_cache
    statistik = cache['stats']
    file_counts = cache['file_counts']
    
    try:
        # PERBAIKAN: Jangan otomatis hitung ulang statistik dari log file
        # Biarkan dashboard membaca data dari file statistik saja
        # Jika file statistik tidak ada, gunakan nilai default
        
        stats_file = app.config['STATS_FILE']
        if not os.path.exists(stats_file):
            # Jika file statistik tidak ada, reset statistik ke default
            qr_stats._reset_to_defaults()
        else:
            # Muat statistik dari file
            load_stats_from_file(qr_stats)
        
        # Cek apakah file log berubah untuk update statistik
        if os.path.exists(app.config['CSV_LOG_GENERATE']):
            try:
                mtime = os.path.getmtime(app.config['CSV_LOG_GENERATE'])
                if mtime != cache['mtimes'].get('generate'):
                    # File berubah, baca ulang
                    with open(app.config['CSV_LOG_GENERATE'], 'r', encoding='utf-8', errors='ignore') as f:
                        # Gunakan iterator untuk hemat memori
                        next(f, None) # Skip header
                        
                        total_count = 0
                        tunggal_count = 0
                        massal_count = 0
                        
                        for line in f:
                            if line.strip():
                                total_count += 1
                                if 'Tunggal' in line:
                                    tunggal_count += 1
                                elif 'Massal' in line:
                                    massal_count += 1
                        
                        statistik['generate']['total'] = total_count
                        statistik['generate']['tunggal'] = tunggal_count
                        statistik['generate']['massal'] = massal_count
                        cache['mtimes']['generate'] = mtime
            except Exception as e:
                app.logger.error(f"Error reading generate log: {e}")
        
        if os.path.exists(app.config['CSV_LOG_VERIFIKASI']):
            try:
                mtime = os.path.getmtime(app.config['CSV_LOG_VERIFIKASI'])
                if mtime != cache['mtimes'].get('verifikasi'):
                    # File berubah, baca ulang
                    with open(app.config['CSV_LOG_VERIFIKASI'], 'r', encoding='utf-8', errors='ignore') as f:
                        next(f, None) # Skip header
                        
                        total_count = 0
                        valid_count = 0
                        invalid_count = 0
                        replay_count = 0
                        
                        for line in f:
                            if line.strip():
                                total_count += 1
                                if '✅' in line:
                                    valid_count += 1
                                if '❌' in line or '⛔' in line:
                                    invalid_count += 1
                                if '🔁' in line:
                                    replay_count += 1
                        
                        statistik['verifikasi']['total'] = total_count
                        statistik['verifikasi']['valid'] = valid_count
                        statistik['verifikasi']['invalid'] = invalid_count
                        statistik['verifikasi']['replay'] = replay_count
                        cache['mtimes']['verifikasi'] = mtime
            except Exception as e:
                app.logger.error(f"Error reading verification log: {e}")
        
        # Update file counts setiap 5 detik saja
        if time.time() - cache['last_count_time'] > 5:
            try:
                file_counts['qr_tunggal'] = count_files_fast(app.config['QR_FOLDER'], '.png')
                file_counts['qr_massal'] = count_files_fast(app.config['QR_MASSAL_FOLDER'], '.png')
                file_counts['qr_fake'] = count_files_fast(app.config['FAKE_QR_FOLDER'], '.png')
                file_counts['data_json'] = count_files_fast(app.config['DATA_FOLDER'], '.json')
                file_counts['uploads'] = count_files_fast(app.config['UPLOAD_FOLDER'], ('.png', '.jpg', '.jpeg', '.gif'))
                
                cache['last_count_time'] = time.time()
            except Exception as e:
                app.logger.error(f"Error counting files: {e}")

        performance_summary = _build_dashboard_performance_summary(cache)
        
        # Debug logging untuk memastikan statistik terisi
        app.logger.info(f"Dashboard stats - Generate: {statistik['generate']}, Verify: {statistik['verifikasi']}")
        app.logger.info(f"QR Stats - QR Count: {qr_stats.qr_count}, Verify Count: {qr_stats.verify_count}")
        app.logger.info(f"QR Stats - Avg Generate Time: {qr_stats.get_average_generate_time()}")
        app.logger.info(f"QR Stats - Avg Verify Time: {qr_stats.get_average_verify_time()}")
        app.logger.info(f"QR Stats - Avg File Size: {qr_stats.get_average_file_size()}")
        app.logger.info(f"QR Stats - Dimension Stats: {qr_stats.get_dimension_stats()}")
        app.logger.info(f"QR Stats - File Sizes: {len(qr_stats.file_sizes)} entries")
        app.logger.info(f"QR Stats - Dimensions: {len(qr_stats.dimensions)} entries")
        
        response = make_response(render_template('dashboard.html', 
                             statistik=statistik, 
                             file_counts=file_counts,
                             qr_stats=qr_stats,
                             performance_summary=performance_summary))
        
        # Set cache control untuk 30 detik
        response.headers['Cache-Control'] = 'public, max-age=30'
        response.headers['X-Accel-Buffering'] = 'no'  # Untuk nginx
        
        return response
                             
    except Exception as e:
        app.logger.error(f"Error in dashboard route: {str(e)}", exc_info=True)
        
        # Fallback: buat instance baru dan muat dari file
        default_stats = QRCodeStats()
        load_stats_from_file(default_stats)
        
        flash(f'Error saat memuat dashboard: {str(e)}', 'danger')
        response = make_response(render_template('dashboard.html',
                             statistik=statistik,  # sudah default
                             file_counts=file_counts,  # sudah default
                             qr_stats=default_stats,
	                             performance_summary={
	                                 'generate': {
	                                     **_empty_timing_summary(),
	                                     'throughput_ops_s': 0,
	                                     'target_s': 0.2,
	                                     'target_ops_s': 5,
	                                     'throughput_efficiency': 0,
	                                 },
	                                 'verify': {
	                                     **_empty_timing_summary(),
                                     'grade_metric': 'p95',
                                     'grade': _response_grade(0),
                                     'median_grade': _response_grade(0),
                                     'mean_grade': _response_grade(0),
                                 }
                             }))
        response.headers['Cache-Control'] = 'public, max-age=30'
        return response

@app.route('/reset_stats', methods=['POST'])
@login_required
def reset_stats():
    """Reset statistik global dan hapus semua file yang dihasilkan"""
    try:
        # Reset statistik global
        global qr_stats
        qr_stats.reset_stats()
        
        # Hapus file statistik
        stats_file = app.config['STATS_FILE']
        if os.path.exists(stats_file):
            os.remove(stats_file)
            app.logger.info(f"File statistik dihapus: {stats_file}")
        
        # HAPUS FILE LOG CSV juga
        log_files_to_delete = [
            app.config['CSV_LOG_GENERATE'],
            app.config['CSV_LOG_VERIFIKASI']
        ]
        
        for log_file in log_files_to_delete:
            if os.path.exists(log_file):
                # Buat backup dulu
                backup_file = f"{log_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(log_file, backup_file)
                os.remove(log_file)
                app.logger.info(f"File log dihapus: {log_file}")
        
        # Hapus semua file yang dihasilkan
        deleted_files, deleted_folders = cleanup_all_generated_files()
        
        # Reset background tasks
        with task_lock:
            background_tasks.clear()
        
        # Clear session data
        session_keys_to_clear = [
            'current_task_id',
            'last_generated_files',
            'last_generated_task_id',
            'last_generated_count',
            'last_generated_time',
            'batch_fake_files',
            'modify_original_data',
            'modify_original_signature',
            'modify_filename'
        ]
        for key in session_keys_to_clear:
            session.pop(key, None)
        
        # BUAT ULANG LOG FILE DENGAN HEADER SAJA
        ensure_log_files_exist()
        
        flash(f'✅ Statistik berhasil direset! {deleted_files} file dan {deleted_folders} folder telah dihapus.', 'success')
        app.logger.info(f"Statistics reset: {deleted_files} files and {deleted_folders} folders deleted")
        log_audit_event('reset_stats', {
            'deleted_files': deleted_files,
            'deleted_folders': deleted_folders
        })
        
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        app.logger.error(f"Error reset_stats: {e}")
        flash(f'❌ Error saat reset statistik: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/recalculate_stats')
@login_required
def recalculate_stats():
    """Endpoint untuk menghitung ulang statistik dari log file"""
    try:
        result = calculate_stats_from_logs()
        if result:
            flash('✅ Statistik berhasil dihitung ulang dari log file!', 'success')
        else:
            flash('⚠️ Statistik dihitung ulang dengan beberapa error, cek log untuk detail', 'warning')
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f'❌ Error menghitung ulang statistik: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/reset_log_format', methods=['GET'])
@login_required
def reset_log_format():
    """Reset log format ke versi terbaru"""
    try:
        log_files = [
            app.config['CSV_LOG_GENERATE'],
            app.config['CSV_LOG_VERIFIKASI']
        ]
        
        backup_dir = 'logs/backup'
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for log_file in log_files:
            if os.path.exists(log_file):
                backup_file = f"{backup_dir}/{os.path.basename(log_file)}.backup_{timestamp}"
                shutil.copy2(log_file, backup_file)
                
                os.remove(log_file)
                
                app.logger.info(f"Backup dan reset log: {log_file} -> {backup_file}")
        
        generate_headers = [
            "Sumber", "Waktu", "Nama", "ID", "Versi QR", "Modul", 
            "Resolusi", "Ukuran File (KB)", "Panjang Signature",
            "Waktu Data (detik)", "Waktu Sign (detik)", 
            "Waktu QR (detik)", "Waktu Save (detik)", "Total Waktu (detik)"
        ]
        
        verifikasi_headers = [
            "Sumber", "Waktu", "Nama File", "Status", "Nama", "ID", "Perubahan Data",
            "Waktu Load (detik)", "Waktu Decode (detik)", "Waktu Verify (detik)",
            "Waktu DB (detik)", "Total Waktu (detik)"
        ]
        
        with open(app.config['CSV_LOG_GENERATE'], 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(generate_headers)
        
        with open(app.config['CSV_LOG_VERIFIKASI'], 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(verifikasi_headers)
        
        flash('Format log berhasil direset ke versi terbaru!', 'success')
        log_audit_event('reset_log_format', {'backup_timestamp': timestamp})
        return redirect(url_for('view_log'))
        
    except Exception as e:
        app.logger.error(f"Error reset_log_format: {e}")
        flash(f'Error reset log: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/reset_nonce_log_manual', methods=['POST'])
@login_required
def reset_nonce_log_manual():
    """Manual reset nonce log untuk testing"""
    try:
        reset_nonce_log()
        flash('Nonce log berhasil direset!', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f'Error reset nonce log: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# ==================== BENCHMARKING ROUTES ====================
@app.route('/benchmark')
def benchmark_page():
    """Halaman untuk benchmarking algoritma"""
    return render_template('benchmark.html')

@app.route('/api/run_benchmark', methods=['POST'])
def run_benchmark_api():
    """API untuk menjalankan benchmark RSA vs ECDSA"""
    try:
        payload_json = request.get_json(silent=True) or {}
        iterations = max(30, min(int(payload_json.get('iterations', 100)), 5000))
        benchmark_started = time.perf_counter()
        
        # Payload simulasi yang sesuai dengan fitur keamanan (JSON + Timestamp + Nonce)
        def get_benchmark_payload():
            data = {
                "nama": "Benchmark User",
                "id": "bench_001",
                "timestamp": datetime.now().isoformat(),
                "nonce": secrets.token_hex(8),
                "padding": "x" * 100 # Simulasi data tambahan
            }
            return json.dumps(data, sort_keys=True).encode('utf-8')
        
        results = {
            'rsa': {'sign': [], 'verify': [], 'size': [], 'memory': 0},
            'ecdsa': {'sign': [], 'verify': [], 'size': [], 'memory': 0}
        }
        
        # --- SETUP KEYS ---
        # RSA 2048-bit
        # ECDSA P-256
        app.logger.info("Generating benchmark keys (RSA-2048 vs P-256)...")
        
        # Generate temporary keys for benchmark to ensure fairness
        rsa_key_bench = RSA.generate(2048)
        rsa_pub_bench = rsa_key_bench.public_key()
        
        ecdsa_key_bench = ECC.generate(curve='P-256')
        ecdsa_pub_bench = ecdsa_key_bench.public_key()

        def measure_peak_memory(operation):
            """Measure Python allocation overhead without distorting benchmark timing."""
            tracemalloc.start()
            try:
                operation()
                _, peak = tracemalloc.get_traced_memory()
                return peak / 1024
            finally:
                tracemalloc.stop()
        
        # --- RSA Benchmark ---
        for _ in range(iterations):
            payload = get_benchmark_payload()
            
            # Sign
            t0 = time.perf_counter()
            h = SHA256.new(payload)
            signer = pss.new(rsa_key_bench, salt_bytes=8) # FIX: Sesuaikan dengan Adapted RSA-PSS (8-byte salt)
            sig = signer.sign(h)
            t1 = time.perf_counter()
            results['rsa']['sign'].append((t1-t0)*1000) # ms
            results['rsa']['size'].append(len(base64.b64encode(sig)))
            
            # Verify
            t0 = time.perf_counter()
            h = SHA256.new(payload)
            verifier = pss.new(rsa_pub_bench, salt_bytes=8) # FIX: Sesuaikan verifikasi benchmark
            verifier.verify(h, sig)
            t1 = time.perf_counter()
            results['rsa']['verify'].append((t1-t0)*1000) # ms

        def run_rsa_memory_sample():
            payload = get_benchmark_payload()
            signature = pss.new(rsa_key_bench, salt_bytes=8).sign(SHA256.new(payload))
            pss.new(rsa_pub_bench, salt_bytes=8).verify(SHA256.new(payload), signature)

        results['rsa']['memory'] = measure_peak_memory(run_rsa_memory_sample)

        # --- ECDSA Benchmark ---
        for _ in range(iterations):
            payload = get_benchmark_payload()
            
            # Sign
            t0 = time.perf_counter()
            h = SHA256.new(payload)
            signer = DSS.new(ecdsa_key_bench, 'fips-186-3')
            sig = signer.sign(h)
            t1 = time.perf_counter()
            results['ecdsa']['sign'].append((t1-t0)*1000) # ms
            results['ecdsa']['size'].append(len(base64.b64encode(sig)))
            
            # Verify
            t0 = time.perf_counter()
            h = SHA256.new(payload)
            verifier = DSS.new(ecdsa_pub_bench, 'fips-186-3')
            verifier.verify(h, sig)
            t1 = time.perf_counter()
            results['ecdsa']['verify'].append((t1-t0)*1000) # ms

        def run_ecdsa_memory_sample():
            payload = get_benchmark_payload()
            signature = DSS.new(ecdsa_key_bench, 'fips-186-3').sign(SHA256.new(payload))
            DSS.new(ecdsa_pub_bench, 'fips-186-3').verify(SHA256.new(payload), signature)

        results['ecdsa']['memory'] = measure_peak_memory(run_ecdsa_memory_sample)
            
        # Calculate Averages
        summary = {}
        for algo in ['rsa', 'ecdsa']:
            if results[algo]['sign']:
                sign_data = results[algo]['sign']
                verify_data = results[algo]['verify']
                
                summary[algo] = {
                'avg_sign': statistics.mean(sign_data),
                'avg_verify': statistics.mean(verify_data),
                'avg_size': statistics.mean(results[algo]['size']),
                'min_sign': min(sign_data),
                'max_sign': max(sign_data),
                'min_verify': min(verify_data),
                'max_verify': max(verify_data),
                'stdev_sign': statistics.stdev(sign_data) if len(sign_data) > 1 else 0,
                'stdev_verify': statistics.stdev(verify_data) if len(verify_data) > 1 else 0,
                'peak_memory': results[algo]['memory']
                }
            
        return jsonify({
            'success': True, 
            'data': summary, 
            'iterations': iterations,
            'duration_seconds': time.perf_counter() - benchmark_started,
            'parameters': {
                'rsa_bits': 2048,
                'ecdsa_curve': 'P-256',
                'hash_algo': 'SHA-256',
                'security_level': 'Standard'
            }
        })
        
    except Exception as e:
        app.logger.error(f"Benchmark error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', 
                         error_code=404, 
                         error_message="Halaman tidak ditemukan"), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'Server Error: {error}')
    return render_template('error.html',
                         error_code=500,
                         error_message="Terjadi kesalahan internal server"), 500

@app.errorhandler(413)
def too_large(error):
    return render_template('error.html',
                         error_code=413,
                         error_message=get_upload_limit_message()), 413
                         
@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template('error.html',
                         error_code=429,
                         error_message="Terlalu banyak permintaan. Coba lagi nanti."), 429

@app.context_processor
def utility_processor():
    """Add utility functions to template context"""
    def safe_float(value, default=0.0):
        """Safely convert to float"""
        try:
            return float(value)
        except (ValueError, TypeError):
            return float(default)
    
    def safe_divide(a, b, default=0.0):
        """Safely divide two numbers"""
        try:
            a_float = safe_float(a)
            b_float = safe_float(b)
            if b_float != 0:
                return a_float / b_float
            return safe_float(default)
        except Exception:
            return safe_float(default)
    
    def safe_min(value, limit):
        """Safely get minimum of value and limit"""
        try:
            val = safe_float(value)
            lim = safe_float(limit)
            return min(val, lim)
        except Exception:
            return safe_float(value)
    
    def now():
        """Return current datetime"""
        from datetime import datetime
        return datetime.now()    
    
    return dict(
        safe_float=safe_float,
        safe_divide=safe_divide,
        safe_min=safe_min,
        now=now
    )

# ==================== CLEANUP TASK ====================
def cleanup_old_files():
    """Cleanup file-file lama secara berkala"""
    try:
        now = time.time()
        max_age = 7 * 24 * 3600  # 7 hari

        folders_to_clean = [
            app.config['UPLOAD_FOLDER'],
            app.config['QR_FOLDER'],
            app.config['QR_MASSAL_FOLDER'],
            app.config['FAKE_QR_FOLDER']
        ]

        for folder in folders_to_clean:
            if not os.path.exists(folder):
                continue

            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath):
                    try:
                        file_age = now - os.path.getmtime(filepath)
                        if file_age > max_age:
                            os.remove(filepath)
                            app.logger.info(f"Cleaned up old file: {filepath}")
                    except OSError as e:
                        app.logger.warning(f"Cannot clean up file {filepath}: {e}")

        cleanup_old_verify_payloads()
        
    except Exception as e:
        app.logger.error(f"Error in cleanup: {e}")
        
# ==================== ROUTES UNTUK VERIFIKASI MASSA DENGAN PROGRESS ====================

@app.route('/verify_massal_async')
@login_required
def verify_massal_async_page():
    """Halaman untuk memulai verifikasi massal dengan progress tracking"""
    return render_template('verify_massal_progress.html', stats=qr_stats)

@app.route('/verify_massal_async_start', methods=['POST'])
@login_required
def verify_massal_async_start():
    """Memulai proses verifikasi massal dengan progress tracking"""
    try:
        if 'qrfiles' not in request.files:
            flash('Tidak ada file yang diunggah', 'warning')
            return redirect(url_for('verify_massal_async_page'))
        
        uploaded_files = request.files.getlist('qrfiles')
        valid_files = [f for f in uploaded_files if f.filename != '']
        
        if not valid_files:
            flash('Tidak ada file yang dipilih', 'warning')
            return redirect(url_for('verify_massal_async_page'))
        
        # Validasi per file
        for file in valid_files:
            is_valid, error_msg = validate_single_upload(file)
            if not is_valid:
                flash(error_msg, 'danger')
                return redirect(url_for('verify_massal_async_page'))
        
        # Buat task ID
        task_id = str(uuid.uuid4())
        
        # Simpan file sementara
        tasks_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'verify_tasks')
        os.makedirs(tasks_dir, exist_ok=True)
        
        saved_files = []
        for file in valid_files:
            filename = sanitize_filename(f"verify_{task_id}_{file.filename}")
            file_path = os.path.join(tasks_dir, filename)
            file.save(file_path)
            saved_files.append(file_path)
        
        # Inisialisasi task progress
        with task_lock:
            # Hapus task lama jika sudah melebihi batas
            prune_oldest_background_task_if_needed()
            
            background_tasks[task_id] = {
                'type': 'verify_massal',
                'total': len(saved_files),
                'processed': 0,
                'current': 0,
                'status': 'Memulai proses verifikasi...',
                'is_processing': False,
                'is_complete': False,
                'start_time': datetime.now().isoformat(),
                'results': None,
                'massal_stats': None,
                'error': None,
                'is_stopped': False,
                'saved_files': saved_files,
                'original_filenames': [f.filename for f in valid_files],
                'total_files': len(saved_files),
                'cleanup_saved_files': True
            }
        
        # Simpan task_id di session
        session['current_verify_task_id'] = task_id
        
        return redirect(url_for('verify_massal_progress', task_id=task_id))
        
    except RequestEntityTooLarge:
        app.logger.warning("Upload verifikasi massal async melebihi batas request", exc_info=True)
        flash(get_upload_limit_message(), 'danger')
        return redirect(url_for('verify_massal_async_page'))
    except Exception as e:
        app.logger.error(f"Error verify_massal_async_start: {e}", exc_info=True)
        flash(f'Error saat memulai verifikasi massal: {str(e)}', 'danger')
        return redirect(url_for('verify_massal_async_page'))

@app.route('/api/verify_massal_progress_status')
@limiter.exempt
@login_required
def check_verify_massal_progress_status():
    """API untuk mendapatkan status progress verifikasi massal"""
    task_id = request.args.get('task_id') or session.get('current_verify_task_id')
    
    if not task_id:
        return jsonify({
            'total': 0,
            'processed': 0,
            'current': 0,
            'status': 'Tidak ada proses',
            'is_processing': False,
            'is_complete': False,
            'is_stopped': False,
            'start_time': None,
            'results': None,
            'massal_stats': None,
            'error': 'Task ID tidak ditemukan'
        })
    
    progress = load_task_from_memory_or_snapshot(task_id) or {}
    if not progress:
        return jsonify({
            'total': 0,
            'processed': 0,
            'current': 0,
            'status': 'Task tidak ditemukan',
            'is_processing': False,
            'is_complete': False,
            'is_stopped': False,
            'start_time': None,
            'results': None,
            'massal_stats': None,
            'error': 'Task tidak ditemukan'
        })
    
    # Hitung persentase
    total = progress.get('total', 0)
    processed = progress.get('processed', 0)
    if total > 0:
        percentage = (processed / total) * 100
    else:
        percentage = 0

    progress_stats = progress.get('massal_stats')
    if isinstance(progress_stats, dict):
        progress_stats = dict(progress_stats)
        progress_stats.pop('individual_times', None)
    
    # Hitung waktu yang telah berlalu
    elapsed_time = '0:00:00'
    estimated_remaining = 'Menghitung...'
    
    if progress.get('start_time'):
        try:
            start = datetime.fromisoformat(progress['start_time'])
            elapsed = datetime.now() - start
            elapsed_time = str(elapsed).split('.')[0]
            
            # Estimasi waktu tersisa
            if percentage > 0:
                total_seconds = elapsed.total_seconds()
                estimated_total = (total_seconds / percentage) * 100
                remaining_seconds = estimated_total - total_seconds
                if remaining_seconds > 0:
                    estimated_remaining = str(timedelta(seconds=int(remaining_seconds))).split('.')[0]
                else:
                    estimated_remaining = 'Hampir selesai'
        except Exception as e:
            app.logger.warning(f"Error menghitung waktu: {e}")
    
    response = {
        'task_id': task_id,
        'total': total,
        'processed': processed,
        'current': progress.get('current', 0),
        'status': progress.get('status', 'Tidak diketahui'),
        'is_processing': progress.get('is_processing', False),
        'is_complete': progress.get('is_complete', False),
        'is_stopped': progress.get('is_stopped', False),
        'start_time': progress.get('start_time'),
        'results': None,
        'results_count': len(progress.get('results') or []),
        'massal_stats': progress_stats,
        'error': progress.get('error'),
        'percentage': percentage,
        'elapsed_time': elapsed_time,
        'estimated_remaining': estimated_remaining,
        'type': progress.get('type', 'verify_massal')
    }
    
    return jsonify(response)

@app.route('/api/stop_verify_massal_process', methods=['POST'])
@limiter.exempt
@login_required
def stop_verify_massal_process():
    """API untuk menghentikan proses verifikasi massal di background."""
    task_id = request.args.get('task_id') or session.get('current_verify_task_id')

    if not task_id:
        return jsonify({'success': False, 'error': 'Tidak ada task ID'}), 400

    with task_lock:
        task = background_tasks.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Task tidak ditemukan'}), 404

        if task.get('is_complete'):
            return jsonify({
                'success': True,
                'status': 'Task sudah selesai',
                'task_id': task_id,
                'already_complete': True
            })

        if task.get('is_stopped'):
            return jsonify({
                'success': True,
                'status': 'Proses sedang dihentikan',
                'task_id': task_id,
                'already_stopping': True
            })

        task['is_stopped'] = True
        task['status'] = 'Menghentikan proses setelah file saat ini selesai...'
        task['stop_requested_at'] = datetime.now().isoformat()

    return jsonify({'success': True, 'status': 'Permintaan stop dikirim', 'task_id': task_id})

@app.route('/api/start_verify_massal_process')
@limiter.exempt
@login_required
def initiate_verify_massal_process():
    """API untuk memulai proses verifikasi di background"""
    task_id = request.args.get('task_id') or session.get('current_verify_task_id')
    
    if not task_id:
        return jsonify({'error': 'Tidak ada task ID'})
    
    with task_lock:
        task = background_tasks.get(task_id)
        if not task:
            return jsonify({'error': 'Task tidak ditemukan'})
        
        if task.get('is_processing') or task.get('is_complete'):
            return jsonify({'error': 'Task sudah diproses atau selesai'})
        
        # Tandai sedang diproses
        task['is_processing'] = True
        task['is_stopped'] = False
        task['start_time'] = datetime.now().isoformat()
    
    # Jalankan proses verifikasi di thread terpisah
    thread = threading.Thread(target=background_verify_massal_process, args=(task_id,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'Proses verifikasi dimulai', 'task_id': task_id})

def background_verify_massal_process(task_id):
    """Proses verifikasi massal di background"""
    try:
        # Dapatkan task data
        with task_lock:
            task = background_tasks.get(task_id)
            if not task:
                return
            
            saved_files = task.get('saved_files', [])
            source_generate_task_id = task.get('source_generate_task_id')
            if not saved_files:
                task['error'] = 'File tidak ditemukan'
                task['is_processing'] = False
                task['is_complete'] = True
                return
        
        # Buka aplikasi context untuk akses app.config dan logger
        with app.app_context():
            app.logger.info(f"Memulai background process verifikasi untuk task {task_id}")
            
            # Update status awal
            with task_lock:
                task['status'] = 'Memuat file untuk verifikasi...'
                task['processed'] = 0
            
            total_files = len(saved_files)
            
            with task_lock:
                task['total'] = total_files
                task['status'] = f'Memulai verifikasi {total_files} file QR Code...'
            
            # Timer untuk seluruh proses verifikasi massal
            total_massal_timer = Timer().start()
            
            hasil_verifikasi = []
            processed_files = set()
            stopped = False
            global_verify_time_total = 0.0
            global_verify_success_count = 0
            global_verify_count = 0
            log_buffer = []
            verify_log_flush_every = 500

            def flush_verify_log_buffer():
                nonlocal log_buffer
                if not log_buffer:
                    return
                for buffered_row in log_buffer:
                    _log_to_csv_extended(app.config['CSV_LOG_VERIFIKASI'], buffered_row)
                log_buffer = []

            def queue_verify_log(log_row):
                log_buffer.append(log_row)
                if len(log_buffer) >= verify_log_flush_every:
                    flush_verify_log_buffer()

            def get_generated_original_data(filename):
                if not source_generate_task_id:
                    return None

                data_filename = os.path.splitext(filename)[0] + '.json'
                data_path = os.path.join(app.config['DATA_FOLDER'], data_filename)
                if not os.path.exists(data_path):
                    return None

                try:
                    with open(data_path, 'r', encoding='utf-8') as data_file:
                        return json.load(data_file)
                except Exception as e:
                    app.logger.warning(f"Gagal membaca data asli {data_filename}: {e}")
                    return None
            
            # Statistik untuk verifikasi massal
            massal_stats = {
                "total_files": total_files,
                "success_count": 0,
                "error_count": 0,
                "replay_attack_count": 0,
                "expired_count": 0,
                "valid_signature_count": 0,
                "total_load_time": 0,
                "total_decode_time": 0,
                "total_verify_time": 0,
                "total_db_time": 0,
                "individual_times": []
            }
            
            for idx, file_path in enumerate(saved_files, start=1):
                with task_lock:
                    if task.get('is_stopped'):
                        stopped = True
                        processed_count = len(hasil_verifikasi)
                        task['processed'] = processed_count
                        task['current'] = processed_count
                        task['status'] = (
                            f'Proses dihentikan pada {processed_count} dari {total_files} file.'
                        )
                        break

                # Update progress setiap 10 file atau di akhir
                if idx % 10 == 0 or idx == total_files:
                    with task_lock:
                        task['current'] = idx
                        task['processed'] = idx
                        filename = os.path.basename(file_path)
                        task['status'] = f'Memproses file {idx} dari {total_files}: {filename[:20]}...'
                
                file_timer = Timer().start()
                filename = os.path.basename(file_path)
                
                try:
                    # Load file
                    load_timer = Timer().start()
                    image = cv2.imread(file_path)
                    if image is None:
                        load_time = load_timer.stop()
                        total_file_time = file_timer.stop()
                        
                        # LOG ERROR untuk kasus gambar tidak valid
                        log_row = [
                            "Massal_Async", datetime.now(timezone.utc).isoformat(), filename, "❌ File gambar tidak valid",
                            "-", "-", "-",
                            f"{load_time:.6f}", "0.000000", "0.000000", "0.000000", f"{total_file_time:.6f}"
                        ]
                        queue_verify_log(log_row)
                        
                        hasil_verifikasi.append({
                            "no": idx,
                            "filename": filename,
                            "status": "❌ File gambar tidak valid",
                            "data": None,
                            "perubahan": "-",
                            "load_time": f"{load_time:.3f}",
                            "decode_time": "-",
                            "verify_time": "-",
                            "db_time": "-",
                            "total_time": f"{total_file_time:.3f}"
                        })
                        massal_stats["error_count"] += 1
                        massal_stats["individual_times"].append(total_file_time)
                        continue
                    
                    load_time = load_timer.stop()
                    massal_stats["total_load_time"] += load_time
                    
                    # Decode QR
                    decode_timer = Timer().start()
                    qr_data = decode(image)
                    if not qr_data:
                        decode_time = decode_timer.stop()
                        total_file_time = file_timer.stop()
                        
                        # LOG ERROR untuk kasus QR tidak terbaca
                        log_row = [
                            "Massal_Async", datetime.now(timezone.utc).isoformat(), filename, "⛔ Tidak dapat membaca QR",
                            "-", "-", "-",
                            f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                        ]
                        queue_verify_log(log_row)
                        
                        hasil_verifikasi.append({
                            "no": idx,
                            "filename": filename,
                            "status": "⛔ Tidak dapat membaca QR",
                            "data": None,
                            "perubahan": "-",
                            "load_time": f"{load_time:.3f}",
                            "decode_time": f"{decode_time:.3f}",
                            "verify_time": "-",
                            "db_time": "-",
                            "total_time": f"{total_file_time:.3f}"
                        })
                        massal_stats["error_count"] += 1
                        massal_stats["individual_times"].append(total_file_time)
                        continue
                    
                    decode_time = decode_timer.stop()
                    massal_stats["total_decode_time"] += decode_time
                    
                    try:
                        raw = qr_data[0].data.decode('utf-8')
                        
                        payload = extract_payload_from_qr_string(raw)
                        if not payload:
                            raise ValueError("Format URL atau QR tidak sesuai")
                        
                        if "data" not in payload or "signature" not in payload:
                            raise ValueError("Format QR tidak lengkap")
                        
                        data = payload["data"]
                        signature_b64 = payload["signature"]
                        alg = payload.get("alg", "RSA")
                        
                        try:
                            signature = base64.b64decode(signature_b64)
                        except:
                            raise ValueError("Signature tidak valid")
                        
                        # Verifikasi signature
                        serialized = json.dumps(data, sort_keys=True) # Algoritma default diubah ke RSA
                        hash_obj = SHA256.new(serialized.encode('utf-8'))
                        
                        verify_timer = Timer().start()
                        if alg == 'RSA':
                            try:
                                verifier = pss.new(public_key, salt_bytes=8)
                                verifier.verify(hash_obj, signature)
                                signature_valid = True
                                sig_error = ""
                            except (ValueError, TypeError):
                                try:
                                    verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                                    verifier.verify(hash_obj, signature)
                                    signature_valid = True
                                    sig_error = "signature tidak valid (ECDSA)"
                                except (ValueError, TypeError):
                                    sig_error = "signature tidak valid (ECDSA)"
                                    signature_valid = False
                        elif alg == 'ECDSA':
                            try:
                                verifier = DSS.new(ecdsa_public_key, 'fips-186-3')
                                verifier.verify(hash_obj, signature)
                                signature_valid = True
                                sig_error = ""
                            except (ValueError, TypeError):
                                sig_error = "signature tidak valid (ECDSA)"
                                signature_valid = False
                        else:
                            sig_error = "signature tidak valid (algoritma tidak diketahui)"
                            signature_valid = False
                        
                        if signature_valid:
                            massal_stats["valid_signature_count"] += 1
                            
                        verify_time = verify_timer.stop()
                        massal_stats["total_verify_time"] += verify_time
                        
                        # Cek database dan replay attack
                        db_timer = Timer().start()
                        changed_fields = {}
                        message = ""
                        is_replay = False # Algoritma default diubah ke RSA
                        valid = False
                        
                        original_data_override = get_generated_original_data(filename)
                        verification_result = classify_qr_verification(
                            data,
                            signature_valid,
                            sig_error,
                            original_data_override=original_data_override
                        )
                        original_data = verification_result["original_data"]
                        changed_fields = verification_result["changed_fields"]
                        message = verification_result["message"]
                        valid = verification_result["valid"]
                        is_replay = verification_result["is_replay"]
                        is_expired = verification_result.get("is_expired", False)

                        if is_replay:
                            massal_stats["replay_attack_count"] += 1
                        if is_expired:
                            massal_stats["expired_count"] += 1
                        if valid:
                            massal_stats["success_count"] += 1
                        else:
                            massal_stats["error_count"] += 1
                        
                        db_time = db_timer.stop()
                        massal_stats["total_db_time"] += db_time
                        
                        total_file_time = file_timer.stop()
                        massal_stats["individual_times"].append(total_file_time)
                        
                        global_verify_time_total += total_file_time
                        global_verify_count += 1
                        if valid:
                            global_verify_success_count += 1
                        
                        # LOG HASIL VERIFIKASI
                        log_row = [
                            "Massal_Async", datetime.now(timezone.utc).isoformat(), filename, message,
                            data.get('nama', '-'), data.get('id', '-'),
                            json.dumps(changed_fields, ensure_ascii=False) if changed_fields else '-',
                            f"{load_time:.6f}", f"{decode_time:.6f}", f"{verify_time:.6f}",
                            f"{db_time:.6f}", f"{total_file_time:.6f}"
                        ]
                        queue_verify_log(log_row)
                        
                        hasil_verifikasi.append({
                            "no": idx,
                            "filename": filename,
                            "status": message,
                            "data": data,
                            "perubahan": changed_fields if changed_fields else "-",
                            "load_time": f"{load_time:.3f} detik",
                            "decode_time": f"{decode_time:.3f} detik",
                            "verify_time": f"{verify_time:.3f} detik",
                            "db_time": f"{db_time:.3f} detik",
                            "total_time": f"{total_file_time:.3f} detik",
                            "algorithm": alg,
                            "signature_valid": signature_valid,
                            "valid": valid,
                            "is_replay": is_replay,
                            "is_expired": is_expired
                        })
                        
                    except Exception as e:
                        app.logger.error(f"Error processing file {filename}: {e}")
                        total_file_time = file_timer.stop()
                        
                        # LOG ERROR untuk kasus umum
                        log_row = [
                            "Massal_Async", datetime.now(timezone.utc).isoformat(), filename, f"❌ Error: {str(e)[:50]}",
                            "-", "-", "-",
                            f"{load_time:.6f}", f"{decode_time:.6f}", "0.000000", "0.000000", f"{total_file_time:.6f}"
                        ]
                        queue_verify_log(log_row)
                        
                        hasil_verifikasi.append({
                            "no": idx,
                            "filename": filename,
                            "status": f"❌ Error: {str(e)[:50]}...",
                            "data": None,
                            "perubahan": "-",
                            "load_time": f"{load_time:.3f}",
                            "decode_time": f"{decode_time:.3f}",
                            "verify_time": "-",
                            "db_time": "-",
                            "total_time": f"{total_file_time:.3f} detik"
                        })
                        massal_stats["error_count"] += 1
                        massal_stats["individual_times"].append(total_file_time)
                        
                except Exception as e:
                    app.logger.error(f"Error processing file {filename}: {e}")
                    total_file_time = file_timer.stop()
                    
                    # LOG ERROR untuk kasus umum
                    log_row = [
                        "Massal_Async", datetime.now(timezone.utc).isoformat(), filename, f"❌ Error: {str(e)[:50]}",
                        "-", "-", "-",
                        "0.000000", "0.000000", "0.000000", "0.000000", f"{total_file_time:.6f}"
                    ]
                    queue_verify_log(log_row)
                    
                    hasil_verifikasi.append({
                        "no": idx,
                        "filename": filename,
                        "status": f"❌ Error: {str(e)[:50]}...",
                        "data": None,
                        "perubahan": "-",
                        "load_time": "-",
                        "decode_time": "-",
                        "verify_time": "-",
                        "db_time": "-",
                        "total_time": f"{total_file_time:.3f} detik"
                    })
                    massal_stats["error_count"] += 1
                    massal_stats["individual_times"].append(total_file_time)
            
            flush_verify_log_buffer()
            qr_stats.add_verify_batch_stats(
                global_verify_time_total,
                success_count=global_verify_success_count,
                verify_count=global_verify_count
            )

            total_massal_time = total_massal_timer.stop()
            
            # Hitung statistik massal
            processed_count = len(hasil_verifikasi)
            massal_stats["processed_files"] = processed_count
            massal_stats["total_time"] = total_massal_time
            if massal_stats["individual_times"]:
                massal_stats["avg_time_per_file"] = sum(massal_stats["individual_times"]) / len(massal_stats["individual_times"])
                massal_stats["min_time"] = min(massal_stats["individual_times"])
                massal_stats["max_time"] = max(massal_stats["individual_times"])
            else:
                massal_stats["avg_time_per_file"] = 0
                massal_stats["min_time"] = 0
                massal_stats["max_time"] = 0
            
            success_rate_denominator = processed_count if stopped else massal_stats["total_files"]
            massal_stats["success_rate"] = (
                (massal_stats["success_count"] / success_rate_denominator) * 100
                if success_rate_denominator > 0 else 0
            )
            massal_stats["time_breakdown"] = {
                "load": massal_stats["total_load_time"],
                "decode": massal_stats["total_decode_time"],
                "verify": massal_stats["total_verify_time"],
                "db": massal_stats["total_db_time"]
            }
            
            # Simpan hasil ke task
            with task_lock:
                stopped = stopped or task.get('is_stopped', False)
                task['results'] = hasil_verifikasi
                task['massal_stats'] = massal_stats
                task['is_processing'] = False
                task['is_complete'] = True
                task['is_stopped'] = stopped
                task['processed'] = processed_count
                task['current'] = processed_count
                task['end_time'] = datetime.now().isoformat()
                if stopped:
                    task['status'] = (
                        f'Proses dihentikan. {processed_count} dari {total_files} file diproses.'
                    )
                else:
                    task['status'] = f'Proses selesai! {processed_count} file berhasil diverifikasi.'
                task_snapshot = dict(task)

            save_generate_task_snapshot(task_id, task_snapshot)
            
            # Bersihkan file sementara setelah 30 detik
            def cleanup_temp_files():
                time.sleep(30)
                try:
                    with task_lock:
                        cleanup_task = background_tasks.get(task_id, task)
                    cleanup_task_saved_files(cleanup_task)
                    if cleanup_task.get('cleanup_saved_files', True):
                        with task_lock:
                            if task_id in background_tasks:
                                background_tasks[task_id]['saved_files'] = []
                        app.logger.info(f"File sementara verifikasi dihapus untuk task {task_id}")
                except Exception as e:
                    app.logger.warning(f"Gagal menghapus file sementara: {e}")
            
            cleanup_thread = threading.Thread(target=cleanup_temp_files)
            cleanup_thread.daemon = True
            cleanup_thread.start()
            
            app.logger.info(f"Background process verifikasi selesai untuk task {task_id}")
            
    except Exception as e:
        app.logger.error(f"Error dalam background_verify_massal_process: {e}", exc_info=True)
        try:
            if 'flush_verify_log_buffer' in locals():
                flush_verify_log_buffer()
        except Exception as flush_error:
            app.logger.warning(f"Gagal flush log verifikasi saat error: {flush_error}")
        with task_lock:
            task = background_tasks.get(task_id)
            if task:
                task['error'] = str(e)
                task['is_processing'] = False
                task['is_complete'] = True
                task['status'] = f'Error: {str(e)[:100]}'
                task['end_time'] = datetime.now().isoformat()
                task_snapshot = dict(task)
            else:
                task_snapshot = None
        if task_snapshot:
            save_generate_task_snapshot(task_id, task_snapshot)

def _datatables_int_arg(name, default=0, minimum=None, maximum=None):
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        value = default

    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _verify_result_qr_data(item):
    if not isinstance(item, dict):
        return {}
    data = item.get('data')
    return data if isinstance(data, dict) else {}


def _verify_result_seconds(value):
    try:
        return float(str(value).split()[0])
    except (TypeError, ValueError, IndexError):
        return 0.0


def _verify_result_text(item):
    data = _verify_result_qr_data(item)
    fields = [
        item.get('no') if isinstance(item, dict) else '',
        item.get('filename') if isinstance(item, dict) else '',
        item.get('status') if isinstance(item, dict) else '',
        item.get('total_time') if isinstance(item, dict) else '',
        data.get('nama', ''),
        data.get('id', ''),
        data.get('timestamp', ''),
        data.get('nonce', ''),
    ]
    return ' '.join(str(field or '') for field in fields).lower()


@app.route('/api/get_verify_massal_results_page')
@limiter.exempt
def fetch_verify_massal_results_page():
    """API paginated untuk tabel hasil verifikasi massal DataTables."""
    draw = _datatables_int_arg('draw', 1, minimum=0)
    task_id = request.args.get('task_id') or session.get('current_verify_task_id')

    def empty_response(error_message=None, status_code=200):
        payload = {
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': []
        }
        if error_message:
            payload['error'] = error_message
        return jsonify(payload), status_code

    if not task_id:
        return empty_response('Tidak ada task ID', 400)

    progress = load_task_from_memory_or_snapshot(task_id) or {}
    if not progress:
        return empty_response('Task tidak ditemukan', 404)

    if not progress.get('is_complete', False):
        return empty_response('Proses belum selesai', 409)

    if progress.get('error'):
        return empty_response(progress['error'], 500)

    results = progress.get('results') or []
    indexed_results = [
        (index, item if isinstance(item, dict) else {})
        for index, item in enumerate(results)
    ]

    search_value = (request.args.get('search[value]') or '').strip().lower()
    if search_value:
        filtered_results = [
            indexed_item
            for indexed_item in indexed_results
            if search_value in _verify_result_text(indexed_item[1])
        ]
    else:
        filtered_results = indexed_results

    order_column = _datatables_int_arg('order[0][column]', 0, minimum=0, maximum=7)
    order_dir = (request.args.get('order[0][dir]') or 'asc').lower()
    reverse_order = order_dir == 'desc'

    def sort_key(indexed_item):
        _, item = indexed_item
        data = _verify_result_qr_data(item)
        if order_column == 0:
            try:
                return int(item.get('no', 0))
            except (TypeError, ValueError):
                return 0
        if order_column == 1:
            return str(item.get('filename') or '').lower()
        if order_column == 2:
            return str(item.get('status') or '').lower()
        if order_column == 3:
            return str(data.get('nama') or '').lower()
        if order_column == 4:
            return str(data.get('id') or '').lower()
        if order_column == 5:
            return 1 if item.get('signature_valid') else 0
        if order_column == 6:
            return _verify_result_seconds(item.get('total_time'))
        return 0

    filtered_results = sorted(filtered_results, key=sort_key, reverse=reverse_order)

    max_page_length = 500
    start = _datatables_int_arg('start', 0, minimum=0)
    length = _datatables_int_arg('length', 25)
    if length < 0:
        length = max_page_length
    length = min(max(length, 1), max_page_length)

    page_results = []
    for original_index, item in filtered_results[start:start + length]:
        row = dict(item)
        row['result_index'] = original_index
        row.setdefault('no', original_index + 1)
        row.setdefault('filename', '-')
        row.setdefault('status', '-')
        row.setdefault('data', {})
        row.setdefault('perubahan', '-')
        row.setdefault('load_time', '-')
        row.setdefault('decode_time', '-')
        row.setdefault('verify_time', '-')
        row.setdefault('db_time', '-')
        row.setdefault('total_time', '-')
        row['signature_valid'] = bool(row.get('signature_valid'))
        row['is_replay'] = bool(row.get('is_replay'))
        page_results.append(row)

    return jsonify({
        'draw': draw,
        'recordsTotal': len(results),
        'recordsFiltered': len(filtered_results),
        'data': page_results,
        'success': True,
        'task_id': task_id,
        'total_files': progress.get('total_files', len(results))
    })


@app.route('/api/get_verify_massal_results')
@limiter.exempt
def fetch_verify_massal_results():
    """API untuk mendapatkan hasil verifikasi massal"""
    task_id = request.args.get('task_id') or session.get('current_verify_task_id')
    
    if not task_id:
        return jsonify({'error': 'Tidak ada task ID'})
    
    progress = load_task_from_memory_or_snapshot(task_id) or {}
    if not progress:
        return jsonify({'error': 'Task tidak ditemukan'})
    
    if not progress.get('is_complete', False):
        return jsonify({'error': 'Proses belum selesai'})
    
    if progress.get('error'):
        return jsonify({'error': progress['error']})
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'results': progress.get('results', []),
        'massal_stats': progress.get('massal_stats', {}),
        'total_processed': progress.get('processed', 0),
        'total_files': progress.get('total_files', 0)
    })

@app.route('/api/verify_massal_result_detail')
@limiter.exempt
def get_verify_massal_result_detail():
    """API ringan untuk mengambil detail satu hasil verifikasi massal."""
    task_id = request.args.get('task_id') or session.get('current_verify_task_id')
    result_index_raw = request.args.get('index')

    if not task_id:
        return jsonify({'success': False, 'error': 'Task ID tidak ditemukan'}), 400

    try:
        result_index = int(result_index_raw)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Index hasil tidak valid'}), 400

    progress = load_task_from_memory_or_snapshot(task_id) or {}
    if not progress:
        return jsonify({'success': False, 'error': 'Task tidak ditemukan'}), 404

    results = progress.get('results') or []
    if result_index < 0 or result_index >= len(results):
        return jsonify({'success': False, 'error': 'Detail hasil tidak ditemukan'}), 404

    result = results[result_index] or {}
    return jsonify({
        'success': True,
        'result': {
            'no': result.get('no', ''),
            'filename': result.get('filename', ''),
            'status': result.get('status', ''),
            'data': result.get('data') or {},
            'perubahan': result.get('perubahan', '-'),
            'load_time': result.get('load_time', '-'),
            'decode_time': result.get('decode_time', '-'),
            'verify_time': result.get('verify_time', '-'),
            'db_time': result.get('db_time', '-'),
            'total_time': result.get('total_time', '-'),
            'signature_valid': bool(result.get('signature_valid')),
            'is_replay': bool(result.get('is_replay')),
            'is_expired': bool(result.get('is_expired'))
        }
    })

@app.route('/view_verify_massal_results')
def render_verify_massal_results():
    """Halaman untuk melihat hasil verifikasi massal"""
    task_id = request.args.get('task_id') or session.get('current_verify_task_id')
    
    if not task_id:
        flash('Tidak ada proses verifikasi yang aktif', 'warning')
        return redirect(url_for('verify_massal_progress'))
    
    progress = load_task_from_memory_or_snapshot(task_id) or {}
    if not progress:
        flash('Proses verifikasi tidak ditemukan', 'danger')
        return redirect(url_for('verify_massal_async_page'))
    
    if not progress.get('is_complete', False):
        flash('Proses verifikasi belum selesai', 'warning')
        return redirect(url_for('verify_massal_progress', task_id=task_id))
    
    if progress.get('error'):
        flash(f'Error dalam proses verifikasi: {progress["error"]}', 'danger')
        return redirect(url_for('verify_massal_async_page'))
    
    hasil = progress.get('results', [])
    massal_stats = progress.get('massal_stats', {})
    
    return render_template("verify_massal_results.html",
        hasil=hasil,
        massal_stats=massal_stats,
        outcome=summarize_verification_outcomes(hasil),
        stats=qr_stats,
        task_id=task_id)

@app.route('/download_verify_massal_report')
@login_required
def export_verify_massal_report():
    """Download hasil verifikasi massal sebagai Excel"""
    try:
        task_id = request.args.get('task_id') or session.get('current_verify_task_id')
        
        if not task_id:
            flash('Tidak ada task ID', 'warning')
            return redirect(url_for('verify_massal_async_page'))
        
        progress = load_task_from_memory_or_snapshot(task_id) or {}
        if not progress or not progress.get('results'):
            flash('Data hasil verifikasi tidak ditemukan', 'warning')
            return redirect(url_for('verify_massal_async_page'))
        
        # Buat DataFrame dari hasil
        results = progress['results']
        massal_stats = progress.get('massal_stats', {})
        
        # Buat data untuk Excel
        import pandas as pd
        from io import BytesIO
        
        # Data utama
        main_data = []
        for result in results:
            main_data.append({
                'No': result.get('no', ''),
                'File Name': result.get('filename', ''),
                'Status': result.get('status', ''),
                'Nama': result.get('data', {}).get('nama', '') if result.get('data') else '',
                'ID': result.get('data', {}).get('id', '') if result.get('data') else '',
                'Signature Sah': 'Ya' if result.get('signature_valid') else 'Tidak',
                'Keberlakuan': OUTCOME_LABELS.get(classify_verification_outcome(result), '-'),
                'Is Replay': 'Ya' if result.get('is_replay') else 'Tidak',
                'Load Time': result.get('load_time', ''),
                'Decode Time': result.get('decode_time', ''),
                'Verify Time': result.get('verify_time', ''),
                'DB Time': result.get('db_time', ''),
                'Total Time': result.get('total_time', '')
            })
        
        df_main = pd.DataFrame(main_data)
        
        # Ringkasan dua sumbu: keabsahan signature dipisahkan dari keberlakuan QR,
        # sehingga dokumen otentik yang kedaluwarsa tidak terbaca setara dengan
        # pemalsuan. Angka diturunkan dari hasil per berkas, bukan dari penghitung
        # massal_stats yang menggabungkan penolakan kebijakan dengan error proses.
        outcome = summarize_verification_outcomes(results)
        summary_data = {
            'Metric': [
                'Total Berkas',
                'Berkas Dinilai',
                'Error Pemrosesan',
                '— Sumbu 1: Keabsahan Signature —',
                'Signature Sah',
                'Signature Tidak Sah',
                'Rasio Signature Sah',
                '— Sumbu 2: Keberlakuan QR —',
                'Berlaku',
                'Tidak Berlaku (total)',
                'Tidak Berlaku: Kedaluwarsa',
                'Tidak Berlaku: Replay',
                'Tidak Berlaku: Dimodifikasi/Palsu',
                'Tidak Berlaku: Tidak Ditemukan',
                'Tidak Berlaku: Signature Tidak Sah',
                'Rasio Berlaku',
                '— Kinerja —',
                'Average Time per File', 'Total Time', 'Min Time', 'Max Time'
            ],
            'Value': [
                outcome['total'],
                outcome['dinilai'],
                outcome[OUTCOME_ERROR],
                '',
                outcome['signature_sah'],
                outcome['signature_tidak_sah'],
                f"{outcome['pct_signature_sah']:.1f}%",
                '',
                outcome[OUTCOME_BERLAKU],
                outcome['tidak_berlaku'],
                outcome[OUTCOME_KEDALUWARSA],
                outcome[OUTCOME_REPLAY],
                outcome[OUTCOME_DIMODIFIKASI],
                outcome[OUTCOME_TIDAK_DITEMUKAN],
                outcome[OUTCOME_SIGNATURE_INVALID],
                f"{outcome['pct_berlaku']:.1f}%",
                '',
                f"{massal_stats.get('avg_time_per_file', 0):.3f} detik",
                f"{massal_stats.get('total_time', 0):.3f} detik",
                f"{massal_stats.get('min_time', 0):.3f} detik",
                f"{massal_stats.get('max_time', 0):.3f} detik"
            ]
        }
        df_summary = pd.DataFrame(summary_data)
        
        # Buat breakdown waktu
        time_breakdown = massal_stats.get('time_breakdown', {})
        time_data = {
            'Stage': ['Load File', 'Decode QR', 'Verify Signature', 'Database Check'],
            'Total Time (detik)': [
                time_breakdown.get('load', 0),
                time_breakdown.get('decode', 0),
                time_breakdown.get('verify', 0),
                time_breakdown.get('db', 0)
            ],
            'Percentage': [
                f"{(time_breakdown.get('load', 0) / massal_stats.get('total_time', 1) * 100):.1f}%" if massal_stats.get('total_time', 0) > 0 else "0%",
                f"{(time_breakdown.get('decode', 0) / massal_stats.get('total_time', 1) * 100):.1f}%" if massal_stats.get('total_time', 0) > 0 else "0%",
                f"{(time_breakdown.get('verify', 0) / massal_stats.get('total_time', 1) * 100):.1f}%" if massal_stats.get('total_time', 0) > 0 else "0%",
                f"{(time_breakdown.get('db', 0) / massal_stats.get('total_time', 1) * 100):.1f}%" if massal_stats.get('total_time', 0) > 0 else "0%"
            ]
        }
        df_time = pd.DataFrame(time_data)
        
        # Buat Excel di memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_main.to_excel(writer, sheet_name='Hasil Verifikasi', index=False)
            df_summary.to_excel(writer, sheet_name='Ringkasan', index=False)
            df_time.to_excel(writer, sheet_name='Breakdown Waktu', index=False)
            
            # Format lebar kolom
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for i, col in enumerate(df_main.columns if sheet_name == 'Hasil Verifikasi' else 
                                      df_summary.columns if sheet_name == 'Ringkasan' else 
                                      df_time.columns):
                    column_len = max(df_main[col].astype(str).str.len().max() if sheet_name == 'Hasil Verifikasi' else
                                   df_summary[col].astype(str).str.len().max() if sheet_name == 'Ringkasan' else
                                   df_time[col].astype(str).str.len().max(),
                                   len(col))
                    worksheet.set_column(i, i, min(column_len + 2, 50))
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'hasil_verifikasi_massal_{task_id[:8]}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
        
    except Exception as e:
        app.logger.error(f"Error download_verify_massal_report: {e}", exc_info=True)
        flash(f'Error saat download report: {str(e)}', 'danger')
        return redirect(url_for('verify_massal_async_page'))

# ==================== FUNGSI CLEANUP FILES ====================
def cleanup_all_generated_files():
    """Menghapus semua file yang dihasilkan sistem (QR, data, upload, fake)"""
    try:
        folders_to_clean = [
            app.config['UPLOAD_FOLDER'],
            app.config['QR_FOLDER'],
            app.config['QR_MASSAL_FOLDER'],
            app.config['FAKE_QR_FOLDER'],
            app.config['DATA_FOLDER'],
            app.config['TASK_RESULTS_FOLDER'],
            app.config.get('PAYLOAD_FOLDER', 'static/data/payloads'),
            app.config['QR_MASSAL_FOLDER']  # Tambahkan lagi untuk memastikan
        ]
        
        deleted_files_count = 0
        deleted_folders_count = 0
        
        for folder in folders_to_clean:
            if os.path.exists(folder):
                # Hapus semua file dalam folder
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            deleted_files_count += 1
                            app.logger.debug(f"Deleted file: {file_path}")
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                            deleted_folders_count += 1
                            app.logger.debug(f"Deleted folder: {file_path}")
                    except Exception as e:
                        app.logger.warning(f"Failed to delete {file_path}: {e}")
                        continue

        # Index pencarian harus ikut dikosongkan; entri yang menunjuk file
        # terhapus akan membuat record hilang dilaporkan sebagai data palsu.
        # Setelah itu index langsung dibangun ulang dari isi direktori yang
        # tersisa agar statusnya tetap otoritatif. Tanpa langkah ini pencarian
        # diam-diam kembali ke pemindaian direktori setiap kali reset dijalankan,
        # dan baru pulih bila seseorang ingat menjalankan backfill manual.
        reset_qr_record_index()
        try:
            backfill_qr_record_index()
        except Exception as e:
            app.logger.warning(f'Gagal membangun ulang index setelah cleanup: {e}')

        # Reset juga folder tasks
        tasks_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'tasks')
        if os.path.exists(tasks_folder):
            try:
                shutil.rmtree(tasks_folder)
                deleted_folders_count += 1
                app.logger.info(f"Deleted tasks folder: {tasks_folder}")
            except Exception as e:
                app.logger.warning(f"Failed to delete tasks folder: {e}")
        
        # Buat folder-folder kosong kembali
        for folder in folders_to_clean:
            os.makedirs(folder, exist_ok=True)
        
        # Buat folder tasks kembali
        os.makedirs(tasks_folder, exist_ok=True)
        
        app.logger.info(f"Cleanup completed: {deleted_files_count} files and {deleted_folders_count} folders deleted")
        return deleted_files_count, deleted_folders_count
        
    except Exception as e:
        app.logger.error(f"Error in cleanup_all_generated_files: {e}")
        return 0, 0

def run_scheduler():
    """Menjalankan background scheduler untuk membersihkan file lama (cron job internal)"""
    while True:
        # Jalankan cleanup setiap 24 jam (86400 detik)
        time.sleep(86400)
        with app.app_context():
            app.logger.info("Menjalankan tugas pembersihan otomatis untuk file payload dan QR lama...")
            cleanup_old_files()

# ==================== JALANKAN APLIKASI ====================
if __name__ == '__main__':
    cleanup_old_files()
    
    # Memulai scheduler untuk pembersihan otomatis
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(
        host=os.environ.get('HOST', '0.0.0.0'),
        port=port,
        debug=os.environ.get('DEBUG', 'False').lower() == 'true'
    )
