import os
import threading

from app import app, cleanup_old_files, run_scheduler


def start_internal_scheduler():
    if os.environ.get('ENABLE_INTERNAL_SCHEDULER', 'True').lower() != 'true':
        return

    with app.app_context():
        cleanup_old_files()

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()


start_internal_scheduler()
