"""
BACKGROUND TASK QUEUE
======================
Auto-detects task backend:
  Local dev:      Python threads (in-process)
  Production:     Celery + Redis (when CELERY_BROKER_URL env var set)

Usage:
  queue = get_queue()
  job_id = queue.submit(func, arg1, arg2, kwarg1=val)
  status = queue.status(job_id)   # 'pending', 'running', 'done', 'failed'
  result = queue.result(job_id)   # Get result once done
"""

import os
import uuid
import threading
import traceback
import logging
from datetime import datetime
from queue import Queue

logger = logging.getLogger(__name__)


class ThreadedQueue:
    """Simple in-process threaded background worker (for local dev)."""

    def __init__(self, num_workers=2):
        self.num_workers = num_workers
        self.jobs = {}  # {job_id: {status, result, error, submitted_at, completed_at}}
        self.queue = Queue()
        self.lock = threading.Lock()
        
        for i in range(num_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f'TaskWorker-{i}')
            t.start()
        
        logger.info(f"🧵 ThreadedQueue started with {num_workers} workers")

    def _worker_loop(self):
        while True:
            try:
                job = self.queue.get()
                if job is None:
                    break
                job_id, func, args, kwargs = job
                
                with self.lock:
                    self.jobs[job_id]['status'] = 'running'
                
                try:
                    result = func(*args, **kwargs)
                    with self.lock:
                        self.jobs[job_id]['status'] = 'done'
                        self.jobs[job_id]['result'] = result
                        self.jobs[job_id]['completed_at'] = datetime.utcnow()
                except Exception as e:
                    tb = traceback.format_exc()
                    logger.error(f"Job {job_id} failed: {e}\n{tb}")
                    with self.lock:
                        self.jobs[job_id]['status'] = 'failed'
                        self.jobs[job_id]['error'] = str(e)
                        self.jobs[job_id]['traceback'] = tb
                        self.jobs[job_id]['completed_at'] = datetime.utcnow()
                
                self.queue.task_done()
            except Exception as e:
                logger.exception(f"Worker loop crash: {e}")

    def submit(self, func, *args, **kwargs):
        job_id = uuid.uuid4().hex
        with self.lock:
            self.jobs[job_id] = {
                'status': 'pending',
                'result': None,
                'error': None,
                'submitted_at': datetime.utcnow(),
                'completed_at': None,
            }
        self.queue.put((job_id, func, args, kwargs))
        return job_id

    def status(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return job['status'] if job else 'unknown'

    def result(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return {'status': 'unknown', 'error': 'Job ID not found'}
            return {
                'status': job['status'],
                'result': job['result'],
                'error': job['error'],
                'submitted_at': job['submitted_at'].isoformat() if job['submitted_at'] else None,
                'completed_at': job['completed_at'].isoformat() if job['completed_at'] else None,
            }

    def cleanup(self, max_age_hours=6):
        """Remove old completed jobs from memory."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        with self.lock:
            to_delete = [
                jid for jid, j in self.jobs.items()
                if j['completed_at'] and j['completed_at'] < cutoff
            ]
            for jid in to_delete:
                del self.jobs[jid]
        return len(to_delete)


class CeleryQueue:
    """Celery + Redis production queue."""

    def __init__(self):
        try:
            from celery import Celery
        except ImportError:
            raise ImportError("celery required. Run: pip install celery redis")

        broker = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        backend = os.environ.get('CELERY_RESULT_BACKEND', broker)
        
        self.app = Celery('analyzer', broker=broker, backend=backend)
        self.app.conf.update(
            task_serializer='json',
            result_serializer='json',
            accept_content=['json'],
            task_time_limit=600,  # 10 min max per job
        )
        logger.info(f"🚀 CeleryQueue started with broker: {broker}")

    def submit(self, func, *args, **kwargs):
        task = self.app.send_task('analyzer.run_task', args=[func.__name__, args, kwargs])
        return task.id

    def status(self, job_id):
        result = self.app.AsyncResult(job_id)
        return result.status.lower()

    def result(self, job_id):
        result = self.app.AsyncResult(job_id)
        return {
            'status': result.status.lower(),
            'result': result.result if result.ready() else None,
            'error': str(result.info) if result.failed() else None,
        }


# ═══════════════════════════════════════════════════════════
# FACTORY
# ═══════════════════════════════════════════════════════════

_queue_instance = None

def get_queue():
    """Get singleton task queue based on env vars."""
    global _queue_instance
    if _queue_instance is not None:
        return _queue_instance

    if os.environ.get('CELERY_BROKER_URL'):
        try:
            _queue_instance = CeleryQueue()
            return _queue_instance
        except Exception as e:
            logger.warning(f"Celery init failed, falling back to threaded: {e}")

    _queue_instance = ThreadedQueue(num_workers=int(os.environ.get('WORKER_THREADS', '2')))
    return _queue_instance
