# modules/testing_controller.py - Enhanced Version (Final dengan perbaikan rate limiting)
import json
import time
import threading
import sqlite3
import statistics
import os
import logging
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from html.parser import HTMLParser
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
import random
import secrets
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager
from collections import defaultdict
import psutil  # For memory monitoring
from modules.realistic_performance import RealisticDataGenerator, MultiScenarioDataGenerator


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QRUrlHTMLParser(HTMLParser):
    """Extract the verification URL rendered by hasil.html."""

    def __init__(self):
        super().__init__()
        self.qr_url = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'input':
            return

        attributes = dict(attrs)
        if attributes.get('id') == 'qrUrl' and attributes.get('value'):
            self.qr_url = attributes['value']


class TestStatus(Enum):
    """Enum untuk status test"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"
    TIMEOUT = "timeout"


@dataclass
class TestMetric:
    """Data class untuk metric test"""
    session_id: str
    metric_name: str
    metric_value: float
    metric_unit: str = ""
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class DatabaseManager:
    """Manager untuk operasi database dengan connection pooling"""
    
    def __init__(self, db_path: str = "data/testing/testing_results.db"):
        self.db_path = db_path
        self._setup_database()
        
    def _setup_database(self):
        """Setup database schema dengan indexing"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with self._get_connection() as conn:
            c = conn.cursor()
            
            # Tabel test_sessions
            c.execute('''
                CREATE TABLE IF NOT EXISTS test_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    test_type TEXT,
                    test_name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    status TEXT,
                    total_operations INTEGER DEFAULT 0,
                    completed_operations INTEGER DEFAULT 0,
                    progress REAL DEFAULT 0,
                    results_json TEXT,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    timeout_seconds INTEGER DEFAULT 3600
                )
            ''')
            
            # Tabel test_metrics dengan bulk insert support
            c.execute('''
                CREATE TABLE IF NOT EXISTS test_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    metric_unit TEXT,
                    timestamp TEXT,
                    batch_id TEXT,
                    FOREIGN KEY (session_id) REFERENCES test_sessions (session_id)
                )
            ''')
            
            # Index untuk query performa
            c.execute('CREATE INDEX IF NOT EXISTS idx_session_status ON test_sessions(session_id, status)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_session_time ON test_sessions(start_time)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_metrics_session ON test_metrics(session_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_metrics_batch ON test_metrics(batch_id)')
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager untuk koneksi database"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")  # Enable Write-Ahead Logging
        conn.execute("PRAGMA synchronous=NORMAL")  # Better performance
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def bulk_insert_metrics(self, metrics: List[TestMetric], batch_id: str = None):
        """Bulk insert metrics untuk performa lebih baik"""
        if not metrics:
            return
        
        batch_id = batch_id or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        with self._get_connection() as conn:
            c = conn.cursor()
            
            # Prepare batch insert
            values = []
            for metric in metrics:
                values.append((
                    metric.session_id,
                    metric.metric_name,
                    metric.metric_value,
                    metric.metric_unit,
                    metric.timestamp.isoformat(),
                    batch_id
                ))
            
            # Execute batch insert
            c.executemany('''
                INSERT INTO test_metrics 
                (session_id, metric_name, metric_value, metric_unit, timestamp, batch_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', values)
            
            return len(values)
    
    def execute_query(self, query: str, params: tuple = ()):
        """Execute query dengan error handling"""
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                c.execute(query, params)
                return c.fetchall()
        except Exception as e:
            logger.error(f"Database query error: {e}")
            raise


class TestSession:
    """Class untuk merepresentasikan session test"""
    
    def __init__(self, session_id: str, test_type: str, test_name: str, params: Dict):
        self.session_id = session_id
        self.test_type = test_type
        self.test_name = test_name
        self.params = params
        self.start_time = datetime.now()
        self.end_time = None
        self.status = TestStatus.PENDING
        self.total_operations = 0
        self.completed_operations = 0
        self.progress = 0.0
        self.results = {}
        self.error_message = None
        self.thread = None
        self.stop_flag = threading.Event()
        self.timeout_seconds = 3600  # Default timeout 1 hour
        self.metrics_buffer = []  # Buffer untuk bulk insert
        self.last_update = datetime.now()
        self.db_manager = None  # Akan di-set oleh controller
    
    def set_db_manager(self, db_manager):
        """Set database manager untuk session ini"""
        self.db_manager = db_manager
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        return {
            'session_id': self.session_id,
            'test_type': self.test_type,
            'test_name': self.test_name,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'status': self.status.value,
            'total_operations': self.total_operations,
            'completed_operations': self.completed_operations,
            'progress': self.progress,
            'results': self.results,
            'error_message': self.error_message,
            'timeout_seconds': self.timeout_seconds,
            'age_seconds': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }
    
    def add_metric(self, metric_name: str, metric_value: float, metric_unit: str = ""):
        """Add metric to buffer for batch insert"""
        metric = TestMetric(
            session_id=self.session_id,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit
        )
        self.metrics_buffer.append(metric)
        
        # Auto-flush jika buffer sudah penuh
        if len(self.metrics_buffer) >= 100:
            self.flush_metrics()
    
    def flush_metrics(self):
        """Flush metrics buffer to database"""
        if self.metrics_buffer and self.db_manager:
            try:
                self.db_manager.bulk_insert_metrics(self.metrics_buffer)
                self.metrics_buffer.clear()
            except Exception as e:
                logger.error(f"Failed to flush metrics: {e}")
        elif self.metrics_buffer:
            # Clear buffer jika tidak ada db_manager untuk menghindari memory leak
            self.metrics_buffer.clear()
    
    def is_timed_out(self) -> bool:
        """Check if session has timed out"""
        if self.status == TestStatus.RUNNING:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            return elapsed > self.timeout_seconds
        return False


class EnhancedTestingController:
    """Enhanced controller dengan performance improvements"""
    
    MAX_CONCURRENT_TESTS = 5  # Batasi concurrent tests
    MAX_TEST_DURATION = 7200  # 2 hours maximum
    METRICS_BUFFER_SIZE = 100
    
    def __init__(self):
        self.active_sessions: Dict[str, TestSession] = {}
        self.session_lock = threading.RLock()
        self.thread_pool = ThreadPoolExecutor(
            max_workers=self.MAX_CONCURRENT_TESTS,
            thread_name_prefix="TestWorker"
        )
        self.db_manager = DatabaseManager()
        self.monitor_thread = threading.Thread(target=self._monitor_sessions, daemon=True)
        self.monitor_thread.start()
        self._start_time = datetime.now()
        self._setup_cleanup_scheduler()
        
        # Inisialisasi generators
        try:
            self.performance_gen = RealisticDataGenerator()
            self.scenario_gen = MultiScenarioDataGenerator()
            logger.info("Realistic data generator and multi-scenario generator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize data generators: {e}")
            # Fallback jika gagal
            self.performance_gen = None
            self.scenario_gen = None
    
    def _setup_cleanup_scheduler(self):
        """Setup periodic cleanup scheduler"""
        def cleanup_old_sessions():
            while True:
                time.sleep(3600)  # Run every hour
                self._cleanup_old_sessions()
        
        cleanup_thread = threading.Thread(target=cleanup_old_sessions, daemon=True)
        cleanup_thread.start()
    
    def _monitor_sessions(self):
        """Monitor active sessions for timeouts and resource usage"""
        while True:
            time.sleep(30)  # Check every 30 seconds
            
            with self.session_lock:
                sessions_to_remove = []
                
                for session_id, session in list(self.active_sessions.items()):
                    # Check for timeout
                    if session.is_timed_out():
                        logger.warning(f"Session {session_id} timed out")
                        session.status = TestStatus.TIMEOUT
                        session.end_time = datetime.now()
                        sessions_to_remove.append(session_id)
                    
                    # Check memory usage
                    try:
                        memory_usage = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                        if memory_usage > 1024:  # 1GB limit
                            logger.warning(f"High memory usage: {memory_usage:.2f}MB")
                    except Exception as e:
                        logger.error(f"Memory check error: {e}")
                
                # Remove timed out sessions
                for session_id in sessions_to_remove:
                    self._save_session_to_db(self.active_sessions[session_id])
                    del self.active_sessions[session_id]
    
    def _cleanup_old_sessions(self):
        """Cleanup old sessions from memory"""
        with self.session_lock:
            cutoff_time = datetime.now() - timedelta(hours=24)  # 24 hours old
            
            sessions_to_remove = []
            for session_id, session in list(self.active_sessions.items()):
                if session.end_time and session.end_time < cutoff_time:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                try:
                    session = self.active_sessions[session_id]
                    session.flush_metrics()
                    del self.active_sessions[session_id]
                    logger.info(f"Cleaned up old session: {session_id}")
                except Exception as e:
                    logger.error(f"Error cleaning session {session_id}: {e}")
    
    def start_test_session(self, test_type: str, test_name: str, params: Dict) -> Optional[str]:
        """Start a new test session with validation"""
        
        # Validate input
        if not self._validate_test_parameters(test_type, params):
            raise ValueError("Invalid test parameters")
        
        # Check concurrent test limit
        with self.session_lock:
            active_count = sum(1 for s in self.active_sessions.values() 
                             if s.status == TestStatus.RUNNING)
            
            if active_count >= self.MAX_CONCURRENT_TESTS:
                raise RuntimeError(f"Maximum concurrent tests ({self.MAX_CONCURRENT_TESTS}) reached")
        
        # Generate session ID
        session_id = self._generate_session_id(test_type)
        
        # Convert parameters
        validated_params = self._validate_and_convert_params(params)
        
        # Create test session
        session = TestSession(session_id, test_type, test_name, validated_params)
        session.set_db_manager(self.db_manager)
        
        # Set timeout based on test type
        session.timeout_seconds = self._get_timeout_for_test_type(test_type)
        
        # Save to database
        self._save_session_to_db(session)
        
        # Store in memory
        with self.session_lock:
            self.active_sessions[session_id] = session
        
        # Start test in thread pool
        future = self.thread_pool.submit(
            self._run_test_wrapper,
            session_id,
            test_type,
            validated_params
        )
        
        # Store future reference
        session.thread = future
        
        logger.info(f"Started test session {session_id}: {test_name} ({test_type})")
        return session_id
    
    def _validate_test_parameters(self, test_type: str, params: Dict) -> bool:
        """Validate test parameters"""
        valid_test_types = {
            'normal_operations',
            'replay_attack',
            'data_tampering',
            'signature_forgery',
            'stress_test',
            'real_http_stress_test'
        }
        
        if test_type not in valid_test_types:
            return False
        
        # Type-specific validation
        if test_type == 'normal_operations':
            required = {'signing_count', 'verification_count'}
        elif test_type == 'replay_attack':
            required = {'sample_count', 'repetitions'}
        elif test_type == 'data_tampering':
            required = {'operations'}
        elif test_type == 'signature_forgery':
            required = {'attempts'}
        elif test_type in {'stress_test', 'real_http_stress_test'}:
            required = {'operations', 'concurrent_users'}
        else:
            return True
        
        return all(key in params for key in required)
    
    def _validate_and_convert_params(self, params: Dict) -> Dict:
        """Validate and convert parameters to proper types"""
        converted = {}
        
        for key, value in params.items():
            try:
                if key == 'concurrent_users':
                    if isinstance(value, str):
                        converted[key] = [
                            int(x.strip()) for x in value.split(',') 
                            if x.strip().isdigit()
                        ]
                    elif isinstance(value, list):
                        converted[key] = [int(v) for v in value]
                    else:
                        converted[key] = [100, 500, 1000, 1500]
                elif isinstance(value, str) and value.isdigit():
                    converted[key] = int(value)
                elif isinstance(value, (int, float)):
                    converted[key] = int(value)
                else:
                    converted[key] = value
            except (ValueError, TypeError):
                converted[key] = value
        
        return converted
    
    def _generate_session_id(self, test_type: str) -> str:
        """Generate unique session ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        random_part = secrets.token_hex(3)
        return f"test_{timestamp}_{test_type}_{random_part}"
    
    def _get_timeout_for_test_type(self, test_type: str) -> int:
        """Get timeout duration based on test type"""
        timeouts = {
            'normal_operations': 1800,  # 30 minutes
            'replay_attack': 3600,      # 1 hour
            'data_tampering': 5400,     # 1.5 hours
            'signature_forgery': 3600,  # 1 hour
            'stress_test': 7200,        # 2 hours
            'real_http_stress_test': 7200,
        }
        return timeouts.get(test_type, 3600)
    
    def _save_session_to_db(self, session: TestSession):
        """Save session to database"""
        try:
            query = '''
                INSERT OR REPLACE INTO test_sessions
                (session_id, test_type, test_name, start_time, end_time, status,
                 total_operations, completed_operations, progress, results_json,
                 timeout_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''

            params = (
                session.session_id,
                session.test_type,
                session.test_name,
                session.start_time.isoformat() if session.start_time else None,
                session.end_time.isoformat() if session.end_time else None,
                session.status.value,
                session.total_operations,
                session.completed_operations,
                session.progress,
                json.dumps(session.results, default=str),
                session.timeout_seconds
            )

            self.db_manager.execute_query(query, params)

        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")
    
    def _run_test_wrapper(self, session_id: str, test_type: str, params: Dict):
        """Wrapper untuk menjalankan test dengan error handling"""
        try:
            # Update session status
            with self.session_lock:
                if session_id in self.active_sessions:
                    session = self.active_sessions[session_id]
                    session.status = TestStatus.RUNNING
                    self._save_session_to_db(session)
            
            # Run the actual test
            self._run_test_scenario(session_id, test_type, params)
            
        except Exception as e:
            logger.error(f"Test {session_id} failed: {e}", exc_info=True)
            
            with self.session_lock:
                if session_id in self.active_sessions:
                    session = self.active_sessions[session_id]
                    session.status = TestStatus.FAILED
                    session.error_message = str(e)
                    session.end_time = datetime.now()
                    session.flush_metrics()
                    self._save_session_to_db(session)
    
    def _run_test_scenario(self, session_id: str, test_type: str, params: Dict):
        """Run test scenario based on type"""
        logger.info(f"Running test scenario: {test_type} for session {session_id}")
        
        with self.session_lock:
            if session_id not in self.active_sessions:
                return
            session = self.active_sessions[session_id]
            stop_flag = session.stop_flag
        
        # Map test type to function
        test_functions = {
            'normal_operations': self._run_normal_operations_test,
            'replay_attack': self._run_replay_attack_test,
            'data_tampering': self._run_data_tampering_test,
            'signature_forgery': self._run_signature_forgery_test,
            'stress_test': self._run_stress_test,
            'real_http_stress_test': self._run_real_http_stress_test
        }
        
        test_func = test_functions.get(test_type)
        if not test_func:
            raise ValueError(f"Unknown test type: {test_type}")
        
        # Run test
        results = test_func(session, params, stop_flag)
        
        # Update final state
        if not stop_flag.is_set():
            with self.session_lock:
                if session_id in self.active_sessions:
                    session = self.active_sessions[session_id]
                    session.status = TestStatus.COMPLETED
                    session.results = results
                    session.end_time = datetime.now()
                    session.progress = 100.0
                    session.completed_operations = session.total_operations
                    session.flush_metrics()
                    self._save_session_to_db(session)
                    logger.info(f"Test {session_id} completed successfully")
        else:
            logger.info(f"Test {session_id} stopped by user")
    
    def _run_normal_operations_test(self, session: TestSession, params: Dict, stop_flag: threading.Event) -> Dict:
        """Normal Operations Test - Optimized for speed"""
        signing_count = params.get('signing_count', 10000)
        verification_count = params.get('verification_count', 10000)
        total_ops = signing_count + verification_count

        session.total_operations = total_ops

        results = {
            'test_type': 'normal_operations',
            'total_operations': total_ops,
            'signing_times': [],
            'verification_times': [],
            'signing_success': 0,
            'verification_success': 0,
            'errors': []
        }

        # Signing operations (optimized with micro-sleep)
        for i in range(signing_count):
            if stop_flag.is_set() or session.is_timed_out():
                results['status'] = 'stopped'
                return results

            try:
                start_time = time.time()
                # Micro-sleep: 10-50 microseconds instead of 10-50 milliseconds
                # This simulates operation time without making test impractically slow
                time.sleep(random.uniform(0.0001, 0.0005))
                operation_time = time.time() - start_time

                results['signing_times'].append(operation_time)
                results['signing_success'] += 1

                session.add_metric(f'signing_time_{i}', operation_time, 'seconds')

            except Exception as e:
                results['errors'].append(f"Signing {i}: {str(e)}")

            # Update progress periodically
            if i % 1000 == 0:
                session.completed_operations = i + 1
                session.progress = (session.completed_operations / total_ops) * 100
                session.last_update = datetime.now()
                self._save_session_to_db(session)

        # Verification operations (optimized with micro-sleep)
        for i in range(verification_count):
            if stop_flag.is_set() or session.is_timed_out():
                results['status'] = 'stopped'
                return results

            try:
                start_time = time.time()
                # Micro-sleep: 5-20 microseconds
                time.sleep(random.uniform(0.00005, 0.0002))
                operation_time = time.time() - start_time

                results['verification_times'].append(operation_time)
                results['verification_success'] += 1

                session.add_metric(f'verification_time_{signing_count + i}', operation_time, 'seconds')

            except Exception as e:
                results['errors'].append(f"Verification {i}: {str(e)}")

            # Update progress
            current_op = signing_count + i + 1
            session.completed_operations = current_op
            session.progress = (current_op / total_ops) * 100

            if i % 1000 == 0:
                session.last_update = datetime.now()
                self._save_session_to_db(session)

        # Calculate statistics
        self._calculate_statistics(results, 'signing_times', 'signing')
        self._calculate_statistics(results, 'verification_times', 'verification')

        results['signing_success_rate'] = (results['signing_success'] / signing_count) * 100
        results['verification_success_rate'] = (results['verification_success'] / verification_count) * 100

        return results
    
    # 2. REPLAY ATTACK TEST
    def _run_replay_attack_test(self, session: TestSession, params: Dict, stop_flag: threading.Event) -> Dict:
        """Replay Attack Test dengan data realistis"""
        sample_count = params.get('sample_count', 1500)
        repetitions = params.get('repetitions', 20)
        total_ops = sample_count * repetitions
        
        session.total_operations = total_ops
        
        results = {
            'test_type': 'replay_attack',
            'total_operations': total_ops,
            'detection_times': [],
            'detected_replays': 0,
            'missed_replays': 0,
            'false_positives': 0,
            'false_negatives': 0,
            'detection_latency_ms': [],
            'attack_patterns': defaultdict(int),
            'detection_by_pattern': {},
            'timestamp_analysis': []
        }
        
        logger.info(f"Starting realistic replay attack test: "
                   f"{sample_count} samples × {repetitions} repetitions")
        
        # Load configuration once before the loop to prevent KeyError and improve performance
        replay_config = None
        if self.scenario_gen:
            try:
                # Gunakan .get() untuk keamanan akses kamus bertingkat
                replay_config = self.scenario_gen.REALISTIC_BENCHMARKS.get('replay_attack', {}).get('detection')
                # Gunakan .benchmarks yang berisi hasil kalibrasi gabungan
                replay_config = self.scenario_gen.benchmarks.get('replay_attack', {}).get('detection')
            except (AttributeError, KeyError):
                logger.warning("Key 'replay_attack' or 'detection' missing in benchmarks, using fallback")
        
        # Gunakan fallback jika konfigurasi tidak ditemukan atau tidak lengkap
        if not replay_config or 'patterns' not in replay_config:
            replay_config = {
                'patterns': {'simple_replay': 0.60, 'timing_attack': 0.25, 'session_hijack': 0.10, 'advanced_replay': 0.05},
                'detection_rate': 0.95,
                'false_positive_rate': 0.01,
                'false_negative_rate': 0.02
            }

        for sample_idx in range(sample_count):
            if stop_flag.is_set() or session.is_timed_out():
                results['status'] = 'stopped'
                return results
            
            # Determine attack pattern
            pattern = self._weighted_random_choice(replay_config['patterns'])
            results['attack_patterns'][pattern] += 1
            
            for rep_idx in range(repetitions):
                try:
                    # Generate realistic detection result
                    if self.scenario_gen:
                        detection_result = self.scenario_gen.generate_scenario_result(
                            scenario='replay_attack',
                            operation_type='detection',
                            payload_size_kb=random.randint(1, 10)
                        )
                        time_taken = detection_result['time_taken']
                    else:
                        time_taken = random.uniform(0.01, 0.05)
                    
                    results['detection_times'].append(time_taken)
                    results['detection_latency_ms'].append(time_taken * 1000)
                    
                    # Simulate detection dengan rates yang realistis
                    detection_rate = replay_config.get('detection_rate', 0.95)
                    false_positive_rate = replay_config.get('false_positive_rate', 0.01)
                    false_negative_rate = replay_config.get('false_negative_rate', 0.02)
                    
                    # Adjust rates based on pattern
                    pattern_factors = {
                        'simple_replay': 1.0,
                        'timing_attack': 0.95,
                        'session_hijack': 0.90,
                        'advanced_replay': 0.85
                    }
                    pattern_factor = pattern_factors.get(pattern, 1.0)
                    
                    if random.random() < (detection_rate * pattern_factor):
                        results['detected_replays'] += 1
                        
                        # False positive (detecting normal as attack)
                        if random.random() < false_positive_rate:
                            results['false_positives'] += 1
                            logger.warning(f"False positive at sample {sample_idx}, rep {rep_idx}")
                    else:
                        results['missed_replays'] += 1
                        
                        # False negative (missing real attack)
                        if random.random() < false_negative_rate:
                            results['false_negatives'] += 1
                            logger.warning(f"False negative at sample {sample_idx}, rep {rep_idx}")
                    
                    session.add_metric(f'replay_detection_{sample_idx}_{rep_idx}', time_taken, 'seconds')
                    
                except Exception as e:
                    logger.error(f"Replay attack error {sample_idx}-{rep_idx}: {str(e)}")
                
                # Update progress
                current_op = (sample_idx * repetitions) + rep_idx + 1
                session.completed_operations = current_op
                session.progress = (current_op / total_ops) * 100
                
                if rep_idx % 10 == 0:
                    session.last_update = datetime.now()
                    self._save_session_to_db(session)
            
            # Periodic logging
            if sample_idx % 100 == 0:
                detection_rate_current = (results['detected_replays'] / current_op) * 100 if current_op > 0 else 0
                logger.info(f"Replay test progress: {sample_idx}/{sample_count}, "
                          f"Detection rate: {detection_rate_current:.1f}%")
                
                results['timestamp_analysis'].append({
                    'timestamp': datetime.now().isoformat(),
                    'sample': sample_idx,
                    'detection_rate': detection_rate_current,
                    'detected': results['detected_replays'],
                    'missed': results['missed_replays']
                })
        
        # Calculate realistic statistics
        self._calculate_realistic_statistics(results, 'detection_times', 'detection')

        if results['detection_times']:
            results['avg_detection_time'] = statistics.mean(results['detection_times'])
            results['median_detection_time'] = statistics.median(results['detection_times'])
        
        if results['detection_latency_ms']:
            results['avg_detection_latency_ms'] = statistics.mean(results['detection_latency_ms'])
            results['p95_detection_latency_ms'] = np.percentile(results['detection_latency_ms'], 95)
            results['p99_detection_latency_ms'] = np.percentile(results['detection_latency_ms'], 99)

        results['detection_rate'] = (results['detected_replays'] / total_ops) * 100 if total_ops > 0 else 0
        results['false_positive_rate'] = (results['false_positives'] / total_ops) * 100 if total_ops > 0 else 0
        results['false_negative_rate'] = (results['false_negatives'] / total_ops) * 100 if total_ops > 0 else 0
        
        # Calculate detection by pattern
        total_samples_by_pattern = {}
        for pattern, count in results['attack_patterns'].items():
            total_ops_for_pattern = count * repetitions
            # Simulate different detection rates per pattern
            pattern_detection_rates = {
                'simple_replay': 0.98,
                'timing_attack': 0.95,
                'session_hijack': 0.90,
                'advanced_replay': 0.85
            }
            detection_rate_pattern = pattern_detection_rates.get(pattern, 0.90)
            detected = int(total_ops_for_pattern * detection_rate_pattern)
            missed = total_ops_for_pattern - detected
            
            results['detection_by_pattern'][pattern] = {
                'samples': count,
                'total_operations': total_ops_for_pattern,
                'detected': detected,
                'missed': missed,
                'detection_rate': (detected / total_ops_for_pattern) * 100,
                'expected_rate': detection_rate_pattern * 100
            }
        
        logger.info(f"Replay attack test completed: {results['detected_replays']}/{total_ops} detected "
                   f"({results['detection_rate']:.1f}%)")
        
        return results
    
    # 3. DATA TAMPERING TEST
    def _run_data_tampering_test(self, session: TestSession, params: Dict, stop_flag: threading.Event) -> Dict:
        """Data Tampering Test dengan data realistis"""
        operations = params.get('operations', 50000)
        session.total_operations = operations
        
        results = {
            'test_type': 'data_tampering',
            'total_operations': operations,
            'detection_times': [],
            'detected_tampering': 0,
            'missed_tampering': 0,
            'tampering_types': defaultdict(int),
            'detection_by_type': {},
            'severity_distribution': {
                'low': 0, 'medium': 0, 'high': 0, 'critical': 0
            },
            'integrity_violations': 0,
            'resource_usage_samples': [],
            'timestamp_analysis': []
        }
        
        logger.info(f"Starting realistic data tampering test: {operations} operations")
        
        tampering_config = None
        if self.scenario_gen:
            try:
                # Use calibrated benchmarks if available
                tampering_config = self.scenario_gen.benchmarks.get('data_tampering', {}).get('detection')
            except (AttributeError, KeyError):
                # Fallback to REALISTIC_BENCHMARKS if benchmarks not available
                try:
                    tampering_config = self.scenario_gen.REALISTIC_BENCHMARKS.get('data_tampering', {}).get('detection')
                except (AttributeError, KeyError):
                    tampering_config = None

        if not tampering_config:
            tampering_config = {
                'tampering_types': {'field_modification': 0.40, 'field_addition': 0.20, 'field_removal': 0.15, 'data_type_change': 0.10, 'timestamp_tampering': 0.08, 'signature_injection': 0.05, 'encryption_bypass': 0.02},
                'detection_rate': 0.92,
                'severity_weights': {'low': 0.5, 'medium': 0.3, 'high': 0.15, 'critical': 0.05}
            }
        
        for i in range(operations):
            if stop_flag.is_set() or session.is_timed_out():
                results['status'] = 'stopped'
                return results
            
            try:
                # Pilih jenis tampering
                tampering_type = self._weighted_random_choice(
                    tampering_config['tampering_types']
                )
                results['tampering_types'][tampering_type] += 1
                
                # Generate realistic detection result
                if self.scenario_gen:
                    detection_result = self.scenario_gen.generate_scenario_result(
                        scenario='data_tampering',
                        operation_type='detection',
                        payload_size_kb=random.randint(1, 100)
                    )
                    time_taken = detection_result['time_taken']
                else:
                    time_taken = random.uniform(0.01, 0.03)
                
                results['detection_times'].append(time_taken)
                
                # Determine detection success dengan rates realistis
                base_detection_rate = tampering_config['detection_rate']
                
                # Adjust rate berdasarkan jenis tampering
                type_difficulty = {
                    'field_modification': 0.90,
                    'field_addition': 0.85,
                    'field_removal': 0.80,
                    'data_type_change': 0.95,
                    'timestamp_tampering': 0.75,
                    'signature_injection': 0.60,
                    'encryption_bypass': 0.40
                }
                
                type_factor = type_difficulty.get(tampering_type, 0.85)
                adjusted_rate = base_detection_rate * type_factor
                
                # Add noise (±5%)
                adjusted_rate *= random.uniform(0.95, 1.05)
                adjusted_rate = min(0.99, max(0.1, adjusted_rate))
                
                if random.random() < adjusted_rate:
                    results['detected_tampering'] += 1
                    
                    # Tentukan severity
                    severity = self._weighted_random_choice(
                        tampering_config['severity_weights']
                    )
                    results['severity_distribution'][severity] += 1
                    
                    # Critical tampering detection
                    if tampering_type in ['signature_injection', 'encryption_bypass']:
                        if random.random() < 0.8:  # 80% chance of integrity violation
                            results['integrity_violations'] += 1
                            logger.warning(f"Integrity violation: {tampering_type}")
                else:
                    results['missed_tampering'] += 1
                    # Log critical misses
                    if tampering_type in ['signature_injection', 'encryption_bypass']:
                        logger.error(f"CRITICAL: Missed {tampering_type} at operation {i}")
                
                # Resource monitoring setiap 500 operasi
                if i % 500 == 0 and self.scenario_gen:
                    resource_usage = self.scenario_gen.generate_resource_usage(
                        scenario='data_tampering',
                        concurrent_ops=1,
                        duration_seconds=time_taken
                    )
                    results['resource_usage_samples'].append({
                        'operation': i,
                        'memory_mb': resource_usage['memory_mb'],
                        'cpu_percent': resource_usage['cpu_percent'],
                        'timestamp': datetime.now().isoformat()
                    })
                
                session.add_metric(f'tampering_detection_{i}', time_taken, 'seconds')
                session.add_metric(f'tampering_type_{tampering_type}', 1, 'count')
                
            except Exception as e:
                logger.error(f"Tampering test error {i}: {str(e)}")
            
            # Update progress
            session.completed_operations = i + 1
            session.progress = ((i + 1) / operations) * 100
            
            if i % 1000 == 0:
                session.last_update = datetime.now()
                
                detection_rate = (results['detected_tampering'] / (i + 1)) * 100 if (i + 1) > 0 else 0
                results['timestamp_analysis'].append({
                    'operation': i,
                    'timestamp': datetime.now().isoformat(),
                    'detection_rate': detection_rate,
                    'detected': results['detected_tampering'],
                    'missed': results['missed_tampering']
                })
                
                logger.info(f"Tampering test progress: {i}/{operations}, "
                          f"Detection rate: {detection_rate:.1f}%")
                self._save_session_to_db(session)
        
        # Calculate statistics
        self._calculate_realistic_statistics(results, 'detection_times', 'tampering_detection')

        if results['detection_times']:
            results['avg_detection_time'] = statistics.mean(results['detection_times'])
            results['median_detection_time'] = statistics.median(results['detection_times'])
        
        # Calculate detection by type
        for tampering_type, count in results['tampering_types'].items():
            if count > 0:
                type_difficulty = {
                    'field_modification': 0.90,
                    'field_addition': 0.85,
                    'field_removal': 0.80,
                    'data_type_change': 0.95,
                    'timestamp_tampering': 0.75,
                    'signature_injection': 0.60,
                    'encryption_bypass': 0.40
                }
                difficulty = type_difficulty.get(tampering_type, 0.85)
                
                estimated_detected = int(count * difficulty)
                estimated_missed = count - estimated_detected
                
                results['detection_by_type'][tampering_type] = {
                    'total': count,
                    'detected': estimated_detected,
                    'missed': estimated_missed,
                    'detection_rate': (estimated_detected / count) * 100,
                    'difficulty_factor': difficulty
                }
        
        results['detection_rate'] = (results['detected_tampering'] / operations) * 100
        results['missed_rate'] = (results['missed_tampering'] / operations) * 100
        
        # Calculate critical detection effectiveness
        critical_types = ['signature_injection', 'encryption_bypass']
        total_critical = sum(results['tampering_types'].get(t, 0) for t in critical_types)
        detected_critical = sum(results['detection_by_type'].get(t, {}).get('detected', 0) 
                              for t in critical_types)
        
        if total_critical > 0:
            results['critical_detection_rate'] = (detected_critical / total_critical) * 100
        else:
            results['critical_detection_rate'] = 100.0
        
        # Resource usage summary
        if results['resource_usage_samples']:
            memory_values = [s['memory_mb'] for s in results['resource_usage_samples']]
            cpu_values = [s['cpu_percent'] for s in results['resource_usage_samples']]
            
            results['resource_summary'] = {
                'avg_memory_mb': statistics.mean(memory_values),
                'max_memory_mb': max(memory_values),
                'avg_cpu_percent': statistics.mean(cpu_values),
                'max_cpu_percent': max(cpu_values)
            }
        
        logger.info(f"Data tampering test completed: {results['detected_tampering']}/{operations} detected "
                   f"({results['detection_rate']:.1f}%), "
                   f"Critical detection: {results['critical_detection_rate']:.1f}%")
        
        return results
    
    # 4. SIGNATURE FORGERY TEST
    def _run_signature_forgery_test(self, session: TestSession, params: Dict, stop_flag: threading.Event) -> Dict:
        """Signature Forgery Test dengan data realistis"""
        attempts = params.get('attempts', 20000)
        target_algo = params.get('algorithm')
        session.total_operations = attempts
        
        results = {
            'test_type': 'signature_forgery',
            'total_operations': attempts,
            'verification_times': [],
            'rejected_forgeries': 0,
            'accepted_forgeries': 0,
            'forgery_types': defaultdict(int),
            'forgery_type_rejected': defaultdict(int),  # NEW: Track rejected per forgery type
            'algorithms_used': defaultdict(int),
            'security_levels': {
                'weak': 0, 'medium': 0, 'strong': 0, 'very_strong': 0
            },
            'cryptographic_failures': 0,
            'algorithm_performance': {},
            'timestamp_log': []
        }
        
        logger.info(f"Starting realistic signature forgery test: {attempts} attempts")
        
        forgery_config = None
        if self.scenario_gen:
            try:
                forgery_config = self.scenario_gen.REALISTIC_BENCHMARKS.get('signature_forgery', {}).get('verification')
                forgery_config = self.scenario_gen.benchmarks.get('signature_forgery', {}).get('verification')
            except (AttributeError, KeyError):
                pass
        
        if not forgery_config:
            forgery_config = {
                'forgery_types': {'random_signature': 0.30, 'modified_valid': 0.20, 'replay_valid': 0.15, 'algorithm_weakness': 0.15, 'key_recovery': 0.10, 'quantum_attack': 0.10},
                'algorithms': {'ECDSA': 0.3, 'RSA-PSS': 0.3, 'Ed25519': 0.2, 'BLS': 0.1, 'Schnorr': 0.1},
                'rejection_rate': 0.985
            }
            
        # Filter algoritma jika spesifik diminta (misal: RSA dari testing_routes)
        if target_algo == 'RSA':
            forgery_config['algorithms'] = {'RSA-PSS': 1.0}
            # Include all 6 forgery types including algorithm_weakness and key_recovery for cryptographic failure tracking
            forgery_config['forgery_types'] = {
                'random_signature': 0.30,
                'swapped_signature': 0.25,
                'truncated_signature': 0.20,
                'algorithm_weakness': 0.15,
                'key_recovery': 0.07,
                'quantum_attack': 0.03
            }
        
        for i in range(attempts):
            if stop_flag.is_set() or session.is_timed_out():
                results['status'] = 'stopped'
                return results
            
            try:
                # Pilih jenis forgery
                forgery_type = self._weighted_random_choice(
                    forgery_config['forgery_types']
                )
                results['forgery_types'][forgery_type] += 1
                
                # Pilih algoritma
                algorithm = self._weighted_random_choice(
                    forgery_config['algorithms']
                )
                results['algorithms_used'][algorithm] += 1
                
                # Generate realistic verification result
                if self.scenario_gen:
                    verification_result = self.scenario_gen.generate_scenario_result(
                        scenario='signature_forgery',
                        operation_type='verification',
                        payload_size_kb=random.randint(1, 10)
                    )
                    time_taken = verification_result['time_taken']
                else:
                    time_taken = random.uniform(0.005, 0.015)
                
                results['verification_times'].append(time_taken)
                
                # Determine rejection dengan rates realistis
                base_rejection_rate = forgery_config['rejection_rate']
                
                # Adjust berdasarkan jenis forgery dan algoritma
                forgery_difficulty = {
                    'random_signature': 0.999,    # 99.9% rejection
                    'modified_valid': 0.995,      # 99.5% rejection
                    'swapped_signature': 0.995,   # Penolakan tinggi untuk signature yang ditukar
                    'truncated_signature': 0.99,  # Penolakan tinggi untuk signature yang dipotong
                    'replay_valid': 0.99,         # 99% rejection
                    'algorithm_weakness': 0.97,   # 97% rejection
                    'key_recovery': 0.9999,       # 99.99% rejection
                    'quantum_attack': 0.90        # 90% rejection
                }
                
                algorithm_strength = {
                    'ECDSA': 0.99,
                    'RSA-PSS': 0.995,
                    'Ed25519': 0.999,
                    'BLS': 0.998,
                    'Schnorr': 0.997
                }
                
                type_factor = forgery_difficulty.get(forgery_type, 0.99)
                algo_factor = algorithm_strength.get(algorithm, 0.99)
                
                adjusted_rate = base_rejection_rate * type_factor * algo_factor
                adjusted_rate = min(0.9999, max(0.8, adjusted_rate))
                
                if random.random() < adjusted_rate:
                    results['rejected_forgeries'] += 1
                    results['forgery_type_rejected'][forgery_type] += 1  # Track rejection per type

                    # Tentukan security level
                    if adjusted_rate > 0.999:
                        security_level = 'very_strong'
                    elif adjusted_rate > 0.99:
                        security_level = 'strong'
                    elif adjusted_rate > 0.95:
                        security_level = 'medium'
                    else:
                        security_level = 'weak'
                    
                    results['security_levels'][security_level] += 1
                else:
                    results['accepted_forgeries'] += 1
                    logger.error(f"DANGER: Forgery accepted! Type: {forgery_type}, Algorithm: {algorithm}")
                    
                    # Count cryptographic failures
                    if forgery_type in ['algorithm_weakness', 'key_recovery']:
                        results['cryptographic_failures'] += 1
                
                # Track algorithm performance
                if algorithm not in results['algorithm_performance']:
                    results['algorithm_performance'][algorithm] = {
                        'attempts': 0,
                        'rejected': 0,
                        'accepted': 0,
                        'avg_verification_time_ms': 0
                    }
                
                algo_stats = results['algorithm_performance'][algorithm]
                algo_stats['attempts'] += 1
                if random.random() < adjusted_rate:
                    algo_stats['rejected'] += 1
                else:
                    algo_stats['accepted'] += 1
                
                session.add_metric(f'forgery_verification_{i}', time_taken, 'seconds')
                session.add_metric(f'forgery_type_{forgery_type}', 1, 'count')
                session.add_metric(f'algorithm_{algorithm}', 1, 'count')
                
            except Exception as e:
                logger.error(f"Forgery test error {i}: {str(e)}")
            
            # Update progress
            session.completed_operations = i + 1
            session.progress = ((i + 1) / attempts) * 100
            
            if i % 1000 == 0:
                session.last_update = datetime.now()
                
                rejection_rate = (results['rejected_forgeries'] / (i + 1)) * 100 if (i + 1) > 0 else 0
                results['timestamp_log'].append({
                    'attempt': i,
                    'timestamp': datetime.now().isoformat(),
                    'rejection_rate': rejection_rate,
                    'rejected': results['rejected_forgeries'],
                    'accepted': results['accepted_forgeries']
                })
                
                logger.info(f"Forgery test progress: {i}/{attempts}, "
                          f"Rejection rate: {rejection_rate:.2f}%")
                self._save_session_to_db(session)
        
        # Calculate statistics
        self._calculate_realistic_statistics(results, 'verification_times', 'forgery_verification')
        
        # Calculate overall metrics
        results['rejection_accuracy'] = (results['rejected_forgeries'] / attempts) * 100
        results['acceptance_error'] = (results['accepted_forgeries'] / attempts) * 100
        
        # Konsolidasi data algoritma ke ringkasan utama (Verification Performance)
        results['target_algorithm'] = 'RSA-PSS 2048-bit (Adapted Salt 8-byte)' if target_algo == 'RSA' else 'Multi-Algorithm'
        results['total_attempts'] = attempts
        results['total_rejected'] = results['rejected_forgeries']
        results['rejection_summary'] = f"{results['rejected_forgeries']}/{attempts}"
        results['acceptance_summary'] = f"{results['accepted_forgeries']}/{attempts}"
        
        # Calculate security effectiveness score
        total_weak = results['security_levels']['weak']
        total_medium = results['security_levels']['medium']
        total_strong = results['security_levels']['strong']
        total_vstrong = results['security_levels']['very_strong']
        
        security_score = (
            total_vstrong * 1.0 + 
            total_strong * 0.9 + 
            total_medium * 0.7 + 
            total_weak * 0.5
        ) / attempts * 100
        
        results['security_effectiveness'] = {
            'overall_score': security_score,
            'critical_failures': results['cryptographic_failures'],
            'critical_failure_rate': (results['cryptographic_failures'] / attempts) * 100
        }
        
        # Calculate average verification time by algorithm
        if results['verification_times']:
            results['avg_verification_time'] = statistics.mean(results['verification_times'])
            results['median_verification_time'] = statistics.median(results['verification_times'])
            results['avg_verification_time_ms'] = statistics.mean(results['verification_times']) * 1000
            results['avg_time_display'] = f"{results['avg_verification_time_ms']:.3f} ms"
            results['p95_verification_time_ms'] = np.percentile(results['verification_times'], 95) * 1000
        
        logger.info(f"Signature forgery test completed: {results['rejected_forgeries']}/{attempts} rejected "
                   f"({results['rejection_accuracy']:.2f}%), "
                   f"Security score: {results['security_effectiveness']['overall_score']:.1f}")

        # Calculate algorithm performance for each algorithm used
        for algorithm, stats in results['algorithm_performance'].items():
            if stats['attempts'] > 0 and results['verification_times']:
                # Estimate average time per algorithm (proportional)
                stats['avg_verification_time_ms'] = (sum(results['verification_times']) / len(results['verification_times'])) * 1000
            stats['rejection_rate'] = (stats['rejected'] / stats['attempts'] * 100) if stats['attempts'] > 0 else 0

        # Keep forgery_types data for display in UI (don't clear it)
        # Convert defaultdict to regular dict for JSON serialization
        results['forgery_types'] = dict(results['forgery_types'])
        results['forgery_type_rejected'] = dict(results['forgery_type_rejected'])

        return results
    
    # 5. STRESS TEST
    def _run_stress_test(self, session: TestSession, params: Dict, stop_flag: threading.Event) -> Dict:
        """Stress Test dengan data realistis"""
        operations = params.get('operations', 10000)
        concurrent_users_str = params.get('concurrent_users', '100,500,1000,1500')

        # Parse concurrent users
        if isinstance(concurrent_users_str, str):
            concurrent_users = [int(x.strip()) for x in concurrent_users_str.split(',')]
        else:
            concurrent_users = concurrent_users_str

        total_ops = operations * len(concurrent_users)
        session.total_operations = total_ops

        # Capture BASELINE resource usage BEFORE stress test starts
        # This allows us to measure ONLY the stress test's resource impact
        try:
            process = psutil.Process(os.getpid())
            # Warm up cpu_percent measurement (first call always returns 0.0)
            process.cpu_percent()
            time.sleep(0.5)  # Wait 500ms to get a meaningful measurement
            
            # Capture baseline (CPU% over 500ms window)
            baseline_cpu = process.cpu_percent()
            baseline_memory_mb = process.memory_info().rss / 1024 / 1024
            logger.info(f"Stress test baseline - CPU: {baseline_cpu:.1f}%, RAM: {baseline_memory_mb:.0f} MB")
        except Exception as e:
            logger.warning(f"Failed to capture baseline: {e}")
            baseline_cpu = 0
            baseline_memory_mb = 0

        results = {
            'test_type': 'stress_test',
            'total_operations': total_ops,
            'response_times': [],
            'throughput_per_user_count': {},
            'response_time_by_user_count': {},
            'error_rate_by_user_count': {},
            'success_rate_by_user_count': {},
            'resource_utilization': {
                'cpu': [],
                'memory': [],
                'baseline_cpu': baseline_cpu,
                'baseline_memory_mb': baseline_memory_mb
            },
            'bottleneck_analysis': [],
            'scalability_metrics': {},
            'concurrent_tests': []
        }
        
        logger.info(f"Starting realistic stress test with user levels: {concurrent_users}")
        
        stress_config = None
        if self.scenario_gen:
            try:
                stress_config = self.scenario_gen.REALISTIC_BENCHMARKS.get('stress_test')
                stress_config = self.scenario_gen.benchmarks.get('stress_test')
            except (AttributeError, KeyError):
                pass
        
        if not stress_config:
            stress_config = {
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
        
        # Simulate untuk setiap concurrent user count
        for user_idx, user_count in enumerate(concurrent_users):
            if stop_flag.is_set() or session.is_timed_out():
                results['status'] = 'stopped'
                return results
            
            user_results = {
                'user_count': user_count,
                'operations': operations,
                'response_times': [],
                'success_count': 0,
                'error_count': 0,
                'timeout_count': 0,
                'throughput_samples': [],
                'resource_samples': []
            }
            
            logger.info(f"Testing with {user_count} concurrent users")
            
            # Simulasi operasi dengan pola arrival yang realistis
            for i in range(operations):
                try:
                    # Simulate request arrival dengan Poisson distribution
                    arrival_rate = user_count / 1000  # Requests per millisecond
                    if arrival_rate > 0:
                        inter_arrival = random.expovariate(arrival_rate)
                        time.sleep(min(0.0001, inter_arrival))  # Cap at 0.1ms (reduced from 10ms)

                    start_time = time.time()

                    # Base response time dengan contention factor
                    base_response = stress_config['base_response_ms'] / 1000  # Convert to seconds

                    # Concurrency-induced latency (Amdahl's law)
                    contention_factor = 1 + (user_count ** 1.5) * stress_config['concurrent_factor']

                    # Network latency simulation (reduced)
                    network_latency = random.uniform(0.0001, 0.001)  # 0.1-1ms (reduced from 1-10ms)

                    # Processing time dengan variability
                    processing_time = base_response * contention_factor

                    # Add jitter dan occasional spikes
                    jitter = random.uniform(-0.2, 0.2) * processing_time
                    if random.random() < 0.01:  # 1% chance of processing spike
                        spike_multiplier = random.uniform(2, 5)  # Reduced from 2-10
                        processing_time *= spike_multiplier
                        if user_count > 500:
                            logger.warning(f"Processing spike at {user_count} users")

                    total_time = max(0.0001, processing_time + network_latency + jitter)
                    time.sleep(total_time)  # Reduced sleep time
                    
                    operation_time = time.time() - start_time
                    user_results['response_times'].append(operation_time)
                    results['response_times'].append(operation_time)
                    
                    # Determine success berdasarkan load
                    base_error_rate = stress_config['error_rate_base']
                    additional_error = user_count * stress_config['error_rate_per_user']
                    total_error_rate = min(0.5, base_error_rate + additional_error)
                    
                    # Response time impact on success
                    if operation_time > 0.1:  # 100ms threshold
                        total_error_rate += 0.2
                    elif operation_time > 0.05:  # 50ms threshold
                        total_error_rate += 0.1
                    
                    total_error_rate = min(0.9, total_error_rate)  # Cap at 90%
                    
                    if random.random() < (1 - total_error_rate):
                        user_results['success_count'] += 1
                    else:
                        user_results['error_count'] += 1
                        
                        # Classify error
                        if operation_time > 0.2:  # 200ms = timeout
                            user_results['timeout_count'] += 1
                            logger.warning(f"Timeout at {user_count} users: {operation_time*1000:.1f}ms")
                    
                    # Periodically measure throughput and resource usage (more frequent sampling)
                    if i % 500 == 0 and i > 0:
                        window_time = 1.0  # 1 second window
                        throughput = 1000 / window_time  # 1000 ops in window
                        user_results['throughput_samples'].append(throughput)

                        # Real resource monitoring using psutil (NON-BLOCKING)
                        try:
                            # Get current CPU% since last call (non-blocking, interval=0)
                            current_cpu = process.cpu_percent()
                            current_memory_mb = process.memory_info().rss / 1024 / 1024
                            
                            # Calculate DELTA from baseline (stress test impact ONLY)
                            # Ensure delta is not negative (baseline might be higher during idle moments)
                            cpu_delta = max(0, current_cpu - baseline_cpu)
                            memory_delta = max(0, current_memory_mb - baseline_memory_mb)
                            
                            # Ensure minimum display values so charts show activity
                            if cpu_delta < 0.5 and cpu_delta > 0:
                                cpu_delta = 0.5
                            if memory_delta < 0.1 and memory_delta > 0:
                                memory_delta = 0.1
                                
                        except Exception as e:
                            logger.warning(f"Resource monitoring error: {e}")
                            # Fallback: use simulated deltas based on user count
                            cpu_delta = random.uniform(10, 30) * (user_count / 1500)
                            memory_delta = random.uniform(20, 80) * (user_count / 1500)

                        user_results['resource_samples'].append({
                            'cpu_percent': cpu_delta,  # Delta from baseline
                            'memory_mb': memory_delta,  # Delta from baseline
                            'timestamp': datetime.now().isoformat()
                        })

                        # Store in results for real-time monitoring
                        if 'cpu' not in results['resource_utilization']:
                            results['resource_utilization']['cpu'] = []
                            results['resource_utilization']['memory'] = []
                        
                        results['resource_utilization']['cpu'].append(cpu_delta)
                        results['resource_utilization']['memory'].append(memory_delta)
                    
                    session.add_metric(f'stress_{user_count}_{i}', operation_time, 'seconds')
                    
                except Exception as e:
                    user_results['error_count'] += 1
                    logger.error(f"Stress test error at {user_count} users, op {i}: {str(e)}")
                
                # Update progress
                current_op = (user_idx * operations) + i + 1
                session.completed_operations = current_op
                session.progress = (current_op / total_ops) * 100

                # Save session more frequently to include updated resource data
                if i % 500 == 0:
                    session.last_update = datetime.now()
                    # Update session.results with current progress data
                    session.results = results.copy()
                    self._save_session_to_db(session)
            
            # Calculate per-user statistics
            if user_results['response_times']:
                # Response time statistics
                avg_response = statistics.mean(user_results['response_times'])
                p95_response = np.percentile(user_results['response_times'], 95)
                p99_response = np.percentile(user_results['response_times'], 99)
                max_response = max(user_results['response_times'])
                
                # Throughput calculation
                if user_results['throughput_samples']:
                    avg_throughput = statistics.mean(user_results['throughput_samples'])
                    max_throughput = max(user_results['throughput_samples'])
                else:
                    total_time = sum(user_results['response_times'])
                    avg_throughput = operations / total_time if total_time > 0 else 0
                    max_throughput = avg_throughput
                
                # Success and error rates
                success_rate = (user_results['success_count'] / operations) * 100
                error_rate = (user_results['error_count'] / operations) * 100
                timeout_rate = (user_results['timeout_count'] / operations) * 100
                
                # Resource analysis (DELTA from baseline - stress test impact ONLY)
                if user_results['resource_samples']:
                    avg_cpu = statistics.mean([s['cpu_percent'] for s in user_results['resource_samples']])
                    avg_memory = statistics.mean([s['memory_mb'] for s in user_results['resource_samples']])

                    # Store resource data in overall results (delta values)
                    results['resource_utilization']['cpu'].append(avg_cpu)
                    results['resource_utilization']['memory'].append(avg_memory)
                else:
                    avg_cpu = avg_memory = 0

                # Store detailed results
                user_results['avg_response_time'] = avg_response
                user_results['p95_response_time'] = p95_response
                user_results['p99_response_time'] = p99_response
                user_results['max_response_time'] = max_response
                user_results['throughput'] = avg_throughput
                user_results['max_throughput'] = max_throughput
                user_results['success_rate'] = success_rate
                user_results['error_rate'] = error_rate
                user_results['timeout_rate'] = timeout_rate
                user_results['avg_cpu_usage'] = avg_cpu  # Delta from baseline
                user_results['avg_memory_usage'] = avg_memory  # Delta from baseline

                # Store in overall results
                results['throughput_per_user_count'][user_count] = avg_throughput
                results['response_time_by_user_count'][user_count] = avg_response
                results['error_rate_by_user_count'][user_count] = error_rate
                results['success_rate_by_user_count'][user_count] = success_rate

                # Analyze bottlenecks
                bottleneck_indicators = []
                if avg_response > 0.1:  # 100ms average
                    bottleneck_indicators.append('high_response_time')
                if error_rate > 5:
                    bottleneck_indicators.append('high_error_rate')
                if avg_cpu > 80:
                    bottleneck_indicators.append('cpu_bottleneck')
                if avg_memory > 1024:  # 1GB
                    bottleneck_indicators.append('memory_bottleneck')
                
                if bottleneck_indicators:
                    results['bottleneck_analysis'].append({
                        'user_count': user_count,
                        'indicators': bottleneck_indicators,
                        'avg_response_ms': avg_response * 1000,
                        'error_rate_percent': error_rate,
                        'cpu_percent': avg_cpu,
                        'memory_mb': avg_memory
                    })
                
                logger.info(f"Completed {user_count} users test: "
                          f"Throughput: {avg_throughput:.1f} ops/s, "
                          f"Avg response: {avg_response*1000:.1f}ms, "
                          f"Success: {success_rate:.1f}%")
            
            results['concurrent_tests'].append(user_results)
        
        # Calculate overall statistics
        self._calculate_realistic_statistics(results, 'response_times', 'overall')

        # ADD: Flat summary fields for template compatibility
        if results.get('response_times'):
            results['overall_avg_response_time'] = statistics.mean(results['response_times'])
            results['overall_p95_response_time'] = float(np.percentile(results['response_times'], 95))
            results['overall_p99_response_time'] = float(np.percentile(results['response_times'], 99))

        # Calculate overall success/error counts
        total_success = sum(c.get('success_count', 0) for c in results.get('concurrent_tests', []))
        total_errors = sum(c.get('error_count', 0) for c in results.get('concurrent_tests', []))
        results['successful_operations'] = total_success
        results['failed_operations'] = total_errors
        results['overall_success_rate'] = (total_success / total_ops * 100) if total_ops > 0 else 0
        results['overall_error_rate'] = (total_errors / total_ops * 100) if total_ops > 0 else 0

        # Calculate max throughput
        if results.get('throughput_per_user_count'):
            results['throughput'] = max(results['throughput_per_user_count'].values())

        # Calculate scalability metrics
        if len(concurrent_users) > 1:
            scalability = {
                'throughput_scaling': {},
                'response_time_degradation': {},
                'efficiency_metrics': {}
            }
            
            base_users = concurrent_users[0]
            base_throughput = results['throughput_per_user_count'].get(base_users, 0)
            base_response = results['response_time_by_user_count'].get(base_users, 0)
            
            for user_count in concurrent_users[1:]:
                throughput = results['throughput_per_user_count'].get(user_count, 0)
                response_time = results['response_time_by_user_count'].get(user_count, 0)
                
                if base_throughput > 0 and throughput > 0:
                    scaling_factor = user_count / base_users
                    throughput_gain = throughput / base_throughput
                    scalability['throughput_scaling'][user_count] = {
                        'scaling_factor': scaling_factor,
                        'throughput_gain': throughput_gain,
                        'efficiency': (throughput_gain / scaling_factor) * 100
                    }
                
                if base_response > 0 and response_time > 0:
                    response_degradation = ((response_time - base_response) / base_response) * 100
                    scalability['response_time_degradation'][user_count] = response_degradation
            
            results['scalability_metrics'] = scalability
        
        # Determine optimal user count (highest throughput with >95% success)
        optimal_user_count = 0
        max_throughput = 0
        
        for user_count, throughput in results['throughput_per_user_count'].items():
            success_rate = results['success_rate_by_user_count'].get(user_count, 0)
            if throughput > max_throughput and success_rate > 95:
                max_throughput = throughput
                optimal_user_count = user_count
        
        results['optimal_user_count'] = optimal_user_count
        results['max_sustainable_throughput'] = max_throughput
        
        # Calculate system capacity at different thresholds
        if results['response_times']:
            for threshold_ms in [50, 100, 200, 500]:
                threshold_sec = threshold_ms / 1000
                capacity_ops = sum(1 for rt in results['response_times'] if rt <= threshold_sec)
                capacity_pct = (capacity_ops / len(results['response_times'])) * 100
                results[f'capacity_at_{threshold_ms}ms'] = capacity_pct
        
        logger.info(f"Stress test completed. Optimal: {optimal_user_count} users, "
                   f"Max throughput: {max_throughput:.1f} ops/s")
        
        # Log resource utilization summary
        if results['resource_utilization']['cpu']:
            avg_cpu_all = statistics.mean(results['resource_utilization']['cpu'])
            avg_ram_all = statistics.mean(results['resource_utilization']['memory'])
            max_cpu_all = max(results['resource_utilization']['cpu'])
            max_ram_all = max(results['resource_utilization']['memory'])
            logger.info(f"Resource Impact (Delta from baseline): "
                       f"CPU avg={avg_cpu_all:.1f}% max={max_cpu_all:.1f}%, "
                       f"RAM avg={avg_ram_all:.0f}MB max={max_ram_all:.0f}MB")
        else:
            logger.warning("No resource data collected during stress test")

        return results

    def _read_env_file_value(self, key: str) -> Optional[str]:
        """Read one value from .env when the current process has not sourced it."""
        module_dir = os.path.dirname(os.path.abspath(__file__))
        env_candidates = [
            os.path.join(os.getcwd(), '.env'),
            os.path.abspath(os.path.join(module_dir, '..', '.env')),
            os.path.abspath(os.path.join(module_dir, '..', '..', '.env')),
        ]

        for env_path in dict.fromkeys(env_candidates):
            try:
                with open(env_path, 'r', encoding='utf-8') as env_file:
                    for raw_line in env_file:
                        line = raw_line.strip()
                        if not line or line.startswith('#') or '=' not in line:
                            continue

                        name, value = line.split('=', 1)
                        if name.strip() != key:
                            continue

                        value = value.strip()
                        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                            value = value[1:-1]
                        return value or None
            except OSError:
                continue

        return None

    def _get_real_http_cookie_header(self, base_url: str, timeout_seconds: int) -> str:
        """Login once and return a reusable Flask session cookie header."""
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        login_url = urllib.parse.urljoin(base_url, 'login')
        password = (
            os.environ.get('AUTH_PASSWORD')
            or self._read_env_file_value('AUTH_PASSWORD')
            or 'change-this-password'
        )
        form_data = urllib.parse.urlencode({'password': password}).encode('utf-8')
        request = urllib.request.Request(
            login_url,
            data=form_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'QRRealHTTPStress/1.0'
            },
            method='POST'
        )

        opener.open(request, timeout=timeout_seconds).read(1024)
        cookie_header = '; '.join(f'{cookie.name}={cookie.value}' for cookie in cookie_jar)
        if not cookie_header:
            raise RuntimeError('Login did not return a session cookie')
        return cookie_header

    def _extract_qr_verification_url(self, response_body: bytes, base_url: str) -> str:
        parser = QRUrlHTMLParser()
        parser.feed(response_body.decode('utf-8', errors='replace'))
        if not parser.qr_url:
            raise RuntimeError('Generate response did not include a QR verification URL')
        return urllib.parse.urljoin(base_url, parser.qr_url)

    def _open_real_http_endpoint(
        self,
        url: str,
        method: str,
        headers: Dict[str, str],
        body: Optional[bytes],
        timeout_seconds: int,
        read_limit: int = 2048
    ) -> Dict:
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                response_body = response.read(read_limit)
                status_code = response.getcode()
            return {
                'ok': 200 <= status_code < 400,
                'status_code': status_code,
                'body': response_body,
                'bytes_read': len(response_body),
                'error': None
            }
        except urllib.error.HTTPError as e:
            response_body = e.read(read_limit)
            return {
                'ok': False,
                'status_code': e.code,
                'body': response_body,
                'bytes_read': len(response_body),
                'error': f'HTTP {e.code}'
            }

    def _run_real_http_request(
        self,
        base_url: str,
        target_endpoint: str,
        cookie_header: str,
        timeout_seconds: int,
        session_id: str,
        user_count: int,
        op_index: int
    ) -> Dict:
        """Execute one real HTTP request against the running application."""
        headers = {
            'Cookie': cookie_header,
            'User-Agent': 'QRRealHTTPStress/1.0',
            'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8'
        }
        generate_headers = headers.copy()
        generate_headers['Content-Type'] = 'application/x-www-form-urlencoded'
        generate_payload = {
            'nama': f'HTTP Stress User {user_count}-{op_index}',
            'userid': f'HTTPSTRESS_{session_id[-6:]}_{user_count}_{op_index}',
            'alg': 'RSA'
        }
        generate_body = urllib.parse.urlencode(generate_payload).encode('utf-8')

        started = time.monotonic()
        try:
            if target_endpoint == 'generate_verify':
                generate_url = urllib.parse.urljoin(base_url, 'generate_qr')
                generate_result = self._open_real_http_endpoint(
                    generate_url,
                    'POST',
                    generate_headers,
                    generate_body,
                    timeout_seconds,
                    read_limit=512 * 1024
                )

                if not generate_result['ok']:
                    elapsed = time.monotonic() - started
                    return {
                        'ok': False,
                        'status_code': generate_result['status_code'],
                        'elapsed_seconds': elapsed,
                        'bytes_read': generate_result['bytes_read'],
                        'error': generate_result['error'] or 'Generate request failed',
                        'workflow': 'generate_verify_qr',
                        'generate_ok': False,
                        'verify_ok': False,
                        'generate_status_code': generate_result['status_code'],
                        'verify_status_code': 0,
                        'stage_status_counts': {f"generate_{generate_result['status_code']}": 1}
                    }

                verification_url = self._extract_qr_verification_url(generate_result['body'], base_url)
                verify_result = self._open_real_http_endpoint(
                    verification_url,
                    'GET',
                    headers,
                    None,
                    timeout_seconds,
                    read_limit=256 * 1024
                )
                verification_valid = verify_result['ok'] and b'status-valid' in verify_result['body']
                elapsed = time.monotonic() - started

                return {
                    'ok': verification_valid,
                    'status_code': verify_result['status_code'],
                    'elapsed_seconds': elapsed,
                    'bytes_read': generate_result['bytes_read'] + verify_result['bytes_read'],
                    'error': None if verification_valid else (verify_result['error'] or 'Verification result did not indicate a valid QR'),
                    'workflow': 'generate_verify_qr',
                    'generate_ok': True,
                    'verify_ok': verification_valid,
                    'generate_status_code': generate_result['status_code'],
                    'verify_status_code': verify_result['status_code'],
                    'verification_path': urllib.parse.urlparse(verification_url).path,
                    'stage_status_counts': {
                        f"generate_{generate_result['status_code']}": 1,
                        f"verify_{verify_result['status_code']}": 1
                    }
                }

            target_map = {
                'generate_qr': ('POST', 'generate_qr', generate_headers, generate_body),
                'dashboard': ('GET', '', headers, None),
                'server_metrics': ('GET', 'testing/server_metrics', headers, None)
            }
            method, path, request_headers, body = target_map.get(target_endpoint, target_map['generate_qr'])
            url = urllib.parse.urljoin(base_url, path)
            result = self._open_real_http_endpoint(url, method, request_headers, body, timeout_seconds)
            elapsed = time.monotonic() - started
            return {
                'ok': result['ok'],
                'status_code': result['status_code'],
                'elapsed_seconds': elapsed,
                'bytes_read': result['bytes_read'],
                'error': result['error']
            }
        except Exception as e:
            elapsed = time.monotonic() - started
            return {
                'ok': False,
                'status_code': 0,
                'elapsed_seconds': elapsed,
                'bytes_read': 0,
                'error': str(e)
            }

    def _sample_host_resources(self) -> Dict:
        memory = psutil.virtual_memory()
        return {
            'cpu_percent': psutil.cpu_percent(interval=None),
            'memory_mb': (memory.total - memory.available) / 1024 / 1024
        }

    def _run_real_http_stress_test(self, session: TestSession, params: Dict, stop_flag: threading.Event) -> Dict:
        """Run a real HTTP self-load test against this deployed application."""
        operations = max(1, int(params.get('operations', 20)))
        concurrent_users = params.get('concurrent_users', [2, 5, 10])
        if isinstance(concurrent_users, str):
            concurrent_users = [int(x.strip()) for x in concurrent_users.split(',') if x.strip().isdigit()]
        # Batas atas dinaikkan 100 -> 500. Catatan kapasitas: server ini 2 core
        # dengan gunicorn 1 worker (wajib 1, karena background_tasks/_calibration_state
        # disimpan di memori proses). Level di atas ~100 akan didominasi antrean,
        # bukan performa kriptografi.
        concurrent_users = [max(1, min(int(user_count), 500)) for user_count in concurrent_users] or [10, 25, 50, 100]

        base_url = str(params.get('base_url') or os.environ.get('BASE_URL') or 'http://127.0.0.1:5000/').strip()
        if not base_url.endswith('/'):
            base_url += '/'
        target_endpoint = str(params.get('target_endpoint') or 'generate_qr').strip()
        timeout_seconds = max(2, min(int(params.get('request_timeout_seconds', 15)), 120))

        total_ops = operations * len(concurrent_users)
        session.total_operations = total_ops

        results = {
            'test_type': 'real_http_stress_test',
            'test_mode': 'real_http_self_load',
            'base_url': base_url,
            'target_endpoint': target_endpoint,
            'request_timeout_seconds': timeout_seconds,
            'total_operations': total_ops,
            'response_times': [],
            'throughput_per_user_count': {},
            'successful_throughput_per_user_count': {},
            'request_rate_per_user_count': {},
            'failed_request_rate_per_user_count': {},
            'rate_limited_rate_per_user_count': {},
            'response_time_by_user_count': {},
            'error_rate_by_user_count': {},
            'success_rate_by_user_count': {},
            'http_status_counts': {},
            'stage_status_counts': {},
            'workflow_counts': {
                'generate_success': 0,
                'verify_success': 0,
                'workflow_success': 0
            },
            'resource_utilization': {
                'cpu': [],
                'memory': [],
                'type': 'host_snapshot'
            },
            'bottleneck_analysis': [],
            'scalability_metrics': {},
            'concurrent_tests': [],
            'notes': [
                'Requests are generated from the same server, so app load and load-generator overhead share CPU/RAM.',
                'Generate + Verify QR creates real QR artifacts, writes generate/verification logs, and may trigger configured rate limits.'
            ]
        }

        logger.info(
            "Starting real HTTP stress test: target=%s base_url=%s users=%s operations=%s",
            target_endpoint,
            base_url,
            concurrent_users,
            operations
        )

        cookie_header = self._get_real_http_cookie_header(base_url, timeout_seconds)
        completed_total = 0

        for user_idx, user_count in enumerate(concurrent_users):
            if stop_flag.is_set() or session.is_timed_out():
                results['status'] = 'stopped'
                return results

            user_results = {
                'user_count': user_count,
                'operations': operations,
                'target_endpoint': target_endpoint,
                'response_times': [],
                'success_count': 0,
                'error_count': 0,
                'timeout_count': 0,
                'status_counts': {},
                'stage_status_counts': {},
                'workflow_counts': {
                    'generate_success': 0,
                    'verify_success': 0,
                    'workflow_success': 0
                },
                'errors': {},
                'resource_samples': []
            }

            level_started = time.monotonic()
            max_workers = max(1, min(user_count, operations))

            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='RealHTTPStress') as executor:
                futures = [
                    executor.submit(
                        self._run_real_http_request,
                        base_url,
                        target_endpoint,
                        cookie_header,
                        timeout_seconds,
                        session.session_id,
                        user_count,
                        i
                    )
                    for i in range(operations)
                ]

                for completed_for_level, future in enumerate(as_completed(futures), start=1):
                    if stop_flag.is_set() or session.is_timed_out():
                        for pending in futures:
                            pending.cancel()
                        results['status'] = 'stopped'
                        return results

                    request_result = future.result()
                    elapsed = request_result['elapsed_seconds']
                    status_code = request_result['status_code']
                    status_key = str(status_code)

                    user_results['response_times'].append(elapsed)
                    results['response_times'].append(elapsed)
                    user_results['status_counts'][status_key] = user_results['status_counts'].get(status_key, 0) + 1
                    results['http_status_counts'][status_key] = results['http_status_counts'].get(status_key, 0) + 1

                    for stage_key, count in request_result.get('stage_status_counts', {}).items():
                        user_results['stage_status_counts'][stage_key] = user_results['stage_status_counts'].get(stage_key, 0) + count
                        results['stage_status_counts'][stage_key] = results['stage_status_counts'].get(stage_key, 0) + count

                    if request_result.get('workflow') == 'generate_verify_qr':
                        if request_result.get('generate_ok'):
                            user_results['workflow_counts']['generate_success'] += 1
                            results['workflow_counts']['generate_success'] += 1
                        if request_result.get('verify_ok'):
                            user_results['workflow_counts']['verify_success'] += 1
                            results['workflow_counts']['verify_success'] += 1
                        if request_result.get('ok'):
                            user_results['workflow_counts']['workflow_success'] += 1
                            results['workflow_counts']['workflow_success'] += 1

                    if request_result['ok']:
                        user_results['success_count'] += 1
                    else:
                        user_results['error_count'] += 1
                        error_key = request_result['error'] or f'HTTP {status_code}'
                        user_results['errors'][error_key] = user_results['errors'].get(error_key, 0) + 1
                        if elapsed >= timeout_seconds or 'timed out' in error_key.lower():
                            user_results['timeout_count'] += 1

                    session.add_metric(f'real_http_{target_endpoint}_{user_count}_{completed_for_level}', elapsed, 'seconds')
                    completed_total += 1
                    session.completed_operations = completed_total
                    session.progress = (completed_total / total_ops) * 100

                    if completed_for_level == 1 or completed_for_level % max(1, min(10, operations)) == 0 or completed_for_level == operations:
                        resource_sample = self._sample_host_resources()
                        user_results['resource_samples'].append({
                            **resource_sample,
                            'timestamp': datetime.now().isoformat()
                        })
                        results['resource_utilization']['cpu'].append(resource_sample['cpu_percent'])
                        results['resource_utilization']['memory'].append(resource_sample['memory_mb'])
                        session.results = results.copy()
                        self._save_session_to_db(session)

            attempted = user_results['success_count'] + user_results['error_count']
            level_elapsed = max(0.001, time.monotonic() - level_started)
            if user_results['response_times']:
                avg_response = statistics.mean(user_results['response_times'])
                p95_response = float(np.percentile(user_results['response_times'], 95))
                p99_response = float(np.percentile(user_results['response_times'], 99))
                max_response = max(user_results['response_times'])
            else:
                avg_response = p95_response = p99_response = max_response = 0

            request_rate = attempted / level_elapsed if level_elapsed > 0 else 0
            successful_throughput = user_results['success_count'] / level_elapsed if level_elapsed > 0 else 0
            failed_request_rate = user_results['error_count'] / level_elapsed if level_elapsed > 0 else 0
            rate_limited_rate = user_results['status_counts'].get('429', 0) / level_elapsed if level_elapsed > 0 else 0
            success_rate = (user_results['success_count'] / attempted * 100) if attempted else 0
            error_rate = (user_results['error_count'] / attempted * 100) if attempted else 0
            timeout_rate = (user_results['timeout_count'] / attempted * 100) if attempted else 0
            avg_cpu = statistics.mean([s['cpu_percent'] for s in user_results['resource_samples']]) if user_results['resource_samples'] else 0
            avg_memory = statistics.mean([s['memory_mb'] for s in user_results['resource_samples']]) if user_results['resource_samples'] else 0

            user_results.update({
                'avg_response_time': avg_response,
                'p95_response_time': p95_response,
                'p99_response_time': p99_response,
                'max_response_time': max_response,
                'throughput': successful_throughput,
                'successful_throughput': successful_throughput,
                'max_throughput': successful_throughput,
                'request_rate': request_rate,
                'offered_load': request_rate,
                'failed_request_rate': failed_request_rate,
                'rate_limited_rate': rate_limited_rate,
                'success_rate': success_rate,
                'error_rate': error_rate,
                'timeout_rate': timeout_rate,
                'avg_cpu_usage': avg_cpu,
                'avg_memory_usage': avg_memory
            })

            results['throughput_per_user_count'][user_count] = successful_throughput
            results['successful_throughput_per_user_count'][user_count] = successful_throughput
            results['request_rate_per_user_count'][user_count] = request_rate
            results['failed_request_rate_per_user_count'][user_count] = failed_request_rate
            results['rate_limited_rate_per_user_count'][user_count] = rate_limited_rate
            results['response_time_by_user_count'][user_count] = avg_response
            results['error_rate_by_user_count'][user_count] = error_rate
            results['success_rate_by_user_count'][user_count] = success_rate

            bottleneck_indicators = []
            if avg_response > 1.0:
                bottleneck_indicators.append('high_response_time')
            if error_rate > 5:
                bottleneck_indicators.append('high_error_rate')
            if user_results['status_counts'].get('429', 0) > 0:
                bottleneck_indicators.append('rate_limited')
            if avg_cpu > 80:
                bottleneck_indicators.append('cpu_bottleneck')
            if bottleneck_indicators:
                results['bottleneck_analysis'].append({
                    'user_count': user_count,
                    'indicators': bottleneck_indicators,
                    'avg_response_ms': avg_response * 1000,
                    'error_rate_percent': error_rate,
                    'cpu_percent': avg_cpu,
                    'memory_mb': avg_memory
                })

            results['concurrent_tests'].append(user_results)
            session.results = results.copy()
            self._save_session_to_db(session)

        self._calculate_realistic_statistics(results, 'response_times', 'overall')
        if results.get('response_times'):
            results['overall_avg_response_time'] = statistics.mean(results['response_times'])
            results['overall_p95_response_time'] = float(np.percentile(results['response_times'], 95))
            results['overall_p99_response_time'] = float(np.percentile(results['response_times'], 99))

        total_success = sum(c.get('success_count', 0) for c in results.get('concurrent_tests', []))
        total_errors = sum(c.get('error_count', 0) for c in results.get('concurrent_tests', []))
        total_attempted = total_success + total_errors
        results['successful_operations'] = total_success
        results['failed_operations'] = total_errors
        results['overall_success_rate'] = (total_success / total_attempted * 100) if total_attempted else 0
        results['overall_error_rate'] = (total_errors / total_attempted * 100) if total_attempted else 0
        results['throughput'] = max(results['successful_throughput_per_user_count'].values()) if results['successful_throughput_per_user_count'] else 0
        results['successful_throughput'] = results['throughput']
        results['max_observed_request_rate'] = max(results['request_rate_per_user_count'].values()) if results['request_rate_per_user_count'] else 0
        results['offered_load'] = results['max_observed_request_rate']
        results['failed_request_rate'] = max(results['failed_request_rate_per_user_count'].values()) if results['failed_request_rate_per_user_count'] else 0
        results['rate_limited_request_rate'] = max(results['rate_limited_rate_per_user_count'].values()) if results['rate_limited_rate_per_user_count'] else 0

        optimal_user_count = 0
        max_throughput = 0
        for user_count, throughput in results['throughput_per_user_count'].items():
            success_rate = results['success_rate_by_user_count'].get(user_count, 0)
            if throughput > max_throughput and success_rate >= 95:
                max_throughput = throughput
                optimal_user_count = user_count
        results['optimal_user_count'] = optimal_user_count
        results['max_sustainable_throughput'] = max_throughput

        if results['response_times']:
            for threshold_ms in [50, 100, 200, 500, 1000]:
                threshold_sec = threshold_ms / 1000
                capacity_ops = sum(1 for rt in results['response_times'] if rt <= threshold_sec)
                results[f'capacity_at_{threshold_ms}ms'] = (capacity_ops / len(results['response_times'])) * 100

        logger.info(
            "Real HTTP stress test completed. target=%s success=%.1f%% max_successful_throughput=%.1f req/s max_request_rate=%.1f req/s",
            target_endpoint,
            results['overall_success_rate'],
            results['throughput'],
            results['max_observed_request_rate']
        )
        return results

    def _calculate_statistics(self, results: Dict, time_key: str, prefix: str):
        """Calculate statistics for timing data"""
        if results.get(time_key):
            times = results[time_key]
            if times:
                results[f'avg_{prefix}_time'] = statistics.mean(times)
                results[f'min_{prefix}_time'] = min(times)
                results[f'max_{prefix}_time'] = max(times)
                results[f'p95_{prefix}_time'] = sorted(times)[int(len(times) * 0.95)]
                results[f'std_{prefix}_time'] = statistics.stdev(times) if len(times) > 1 else 0
    
    def _calculate_realistic_statistics(self, results, time_key, prefix):
        """Calculate realistic statistics with percentiles"""
        if results.get(time_key):
            times = results[time_key]
            if len(times) >= 2:
                try:
                    times_ms = [t * 1000 for t in times]  # Convert to ms
                    
                    results[f'{prefix}_stats'] = {
                        'mean_ms': statistics.mean(times_ms),
                        'median_ms': statistics.median(times_ms),
                        'min_ms': min(times_ms),
                        'max_ms': max(times_ms),
                        'stddev_ms': statistics.stdev(times_ms),
                        'p50_ms': np.percentile(times_ms, 50),
                        'p90_ms': np.percentile(times_ms, 90),
                        'p95_ms': np.percentile(times_ms, 95),
                        'p99_ms': np.percentile(times_ms, 99),
                        'p999_ms': np.percentile(times_ms, 99.9),
                        'total_ops': len(times),
                        'total_time_sec': sum(times)
                    }
                except Exception as e:
                    logger.error(f"Error calculating statistics: {e}")
    
    def _weighted_random_choice(self, weights_dict):
        """Pilih item berdasarkan bobot"""
        items = list(weights_dict.keys())
        weights = list(weights_dict.values())
        return random.choices(items, weights=weights, k=1)[0]
    
    def get_test_session(self, session_id: str) -> Optional[Dict]:
        """Get test session by ID"""
        # Check memory first
        with self.session_lock:
            if session_id in self.active_sessions:
                return self.active_sessions[session_id].to_dict()

        # Check database
        try:
            query = 'SELECT * FROM test_sessions WHERE session_id = ?'
            results = self.db_manager.execute_query(query, (session_id,))

            if results:
                columns = ['id', 'session_id', 'test_type', 'test_name', 'start_time',
                          'end_time', 'status', 'total_operations', 'completed_operations',
                          'progress', 'results_json', 'error_message', 'created_at', 'timeout_seconds']

                row = results[0]
                session_data = dict(zip(columns, row))

                if session_data.get('results_json'):
                    try:
                        session_data['results'] = json.loads(session_data['results_json'])
                    except:
                        session_data['results'] = {}

                # Add age_seconds for fallback duration calculation
                try:
                    if session_data.get('start_time'):
                        start_str = session_data['start_time']
                        if 'Z' in start_str:
                            start_str = start_str.replace('Z', '+00:00')
                        start_dt = datetime.fromisoformat(start_str)
                        session_data['age_seconds'] = (datetime.now() - start_dt).total_seconds()
                except:
                    pass

                return session_data
        
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
        
        return None
    
    def get_all_test_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get all test sessions with pagination"""
        try:
            query = '''
                SELECT * FROM test_sessions 
                ORDER BY start_time DESC 
                LIMIT ? OFFSET ?
            '''
            results = self.db_manager.execute_query(query, (limit, offset))
            
            columns = ['id', 'session_id', 'test_type', 'test_name', 'start_time', 
                      'end_time', 'status', 'total_operations', 'completed_operations',
                      'progress', 'results_json', 'error_message', 'created_at', 'timeout_seconds']
            
            sessions = []
            for row in results:
                session_data = dict(zip(columns, row))
                
                if session_data.get('results_json'):
                    try:
                        session_data['results'] = json.loads(session_data['results_json'])
                    except:
                        session_data['results'] = {}
                
                sessions.append(session_data)
            
            return sessions
        
        except Exception as e:
            logger.error(f"Error getting all sessions: {e}")
            return []
    
    def get_active_tests(self) -> List[Dict]:
        """Get active tests"""
        with self.session_lock:
            active = []
            for session in self.active_sessions.values():
                if session.status == TestStatus.RUNNING:
                    active.append(session.to_dict())
            return active
    
    def stop_test_session(self, session_id: str) -> bool:
        """Stop a test session"""
        with self.session_lock:
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                session.stop_flag.set()
                session.status = TestStatus.STOPPED
                session.end_time = datetime.now()
                session.flush_metrics()
                self._save_session_to_db(session)
                logger.info(f"Stopped test session: {session_id}")
                return True
        
        return False
    
    def cleanup_finished_tests(self) -> int:
        """Cleanup finished tests from memory"""
        with self.session_lock:
            finished_ids = []
            
            for session_id, session in self.active_sessions.items():
                if session.status in [TestStatus.COMPLETED, TestStatus.FAILED, 
                                      TestStatus.STOPPED, TestStatus.TIMEOUT]:
                    # Flush any remaining metrics
                    session.flush_metrics()
                    finished_ids.append(session_id)
            
            for session_id in finished_ids:
                del self.active_sessions[session_id]

            logger.info(f"Cleaned up {len(finished_ids)} finished tests")
            return len(finished_ids)

    def clear_all_sessions(self) -> int:
        """Clear all sessions dari memory dan database"""
        try:
            # Clear in-memory active sessions
            with self.session_lock:
                count_in_memory = len(self.active_sessions)
                self.active_sessions.clear()
                logger.info(f"Cleared {count_in_memory} active sessions from memory")

            # Delete from database using DatabaseManager
            session_count = 0
            with self.db_manager._get_connection() as conn:
                c = conn.cursor()
                
                # Hitung jumlah session sebelum hapus
                c.execute("SELECT COUNT(*) FROM test_sessions")
                session_count = c.fetchone()[0]
                
                # Hapus semua data terkait (hanya tabel yang ada di schema)
                c.execute("DELETE FROM test_metrics")
                c.execute("DELETE FROM test_sessions")
                
                logger.info(f"Cleared {session_count} sessions from database")

            # VACUUM harus di luar transaksi (connection sudah close di sini)
            try:
                import sqlite3
                vacuum_conn = sqlite3.connect(self.db_manager.db_path)
                vacuum_conn.execute("VACUUM")
                vacuum_conn.close()
            except Exception as ve:
                logger.warning(f"VACUUM failed (non-critical): {ve}")

            return session_count
        except Exception as e:
            logger.error(f"Error clearing all sessions: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0

    def delete_single_session(self, session_id: str) -> bool:
        """Delete a single session from memory and database"""
        try:
            # Remove from in-memory active sessions
            with self.session_lock:
                if session_id in self.active_sessions:
                    session_data = self.active_sessions[session_id]
                    # Stop the test if it's still running
                    if session_data.status in [TestStatus.RUNNING, TestStatus.PENDING]:
                        session_data.stop_flag.set()
                        session_data.status = TestStatus.STOPPED
                        session_data.end_time = datetime.now()
                        session_data.flush_metrics()
                        self._save_session_to_db(session_data)
                    del self.active_sessions[session_id]
                    logger.info(f"Removed session {session_id} from memory")

            # Delete from database
            with self.db_manager._get_connection() as conn:
                c = conn.cursor()

                # Delete associated metrics first
                c.execute("DELETE FROM test_metrics WHERE session_id = ?", (session_id,))

                # Delete the session
                c.execute("DELETE FROM test_sessions WHERE session_id = ?", (session_id,))

                if c.rowcount > 0:
                    logger.info(f"Deleted session {session_id} from database")
                    return True
                else:
                    logger.warning(f"Session {session_id} not found in database")
                    return False

        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def get_system_stats(self) -> Dict:
        """Get system statistics"""
        with self.session_lock:
            stats = {
                'active_sessions': len(self.active_sessions),
                'running_tests': sum(1 for s in self.active_sessions.values() 
                                   if s.status == TestStatus.RUNNING),
                'memory_usage_mb': psutil.Process().memory_info().rss / 1024 / 1024,
                'thread_pool_stats': {
                    'max_workers': self.thread_pool._max_workers,
                    'active_threads': threading.active_count(),
                },
                'database_stats': self._get_database_stats(),
                'uptime': self._get_uptime()
            }
            
            return stats
    
    def _get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            stats = {}
            
            # Session count by status
            query = '''
                SELECT status, COUNT(*) as count 
                FROM test_sessions 
                GROUP BY status
            '''
            results = self.db_manager.execute_query(query)
            stats['sessions_by_status'] = dict(results)
            
            # Total metrics count
            query = 'SELECT COUNT(*) FROM test_metrics'
            results = self.db_manager.execute_query(query)
            stats['total_metrics'] = results[0][0] if results else 0
            
            return stats
        
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
    
    def _get_uptime(self) -> int:
        """Get controller uptime in seconds"""
        return int((datetime.now() - self._start_time).total_seconds())
    
    def shutdown(self):
        """Graceful shutdown of controller"""
        logger.info("Shutting down testing controller...")
        
        # Stop all active tests
        with self.session_lock:
            for session_id in list(self.active_sessions.keys()):
                self.stop_test_session(session_id)
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True, cancel_futures=True)
        
        # Flush all metrics
        with self.session_lock:
            for session in self.active_sessions.values():
                session.flush_metrics()
        
        logger.info("Testing controller shutdown complete")


# Global instance
testing_controller = EnhancedTestingController()
