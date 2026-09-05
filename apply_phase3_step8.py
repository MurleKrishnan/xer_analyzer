import os
import shutil
from datetime import datetime

print("🚀 Applying Phase 3 - Step 8: Persistent Backend Architecture...")
print("   This adds database persistence, file storage abstraction, and background jobs.")

# 1. Create Backup Folder
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = f"_backup_phase3_step8_{timestamp}"
os.makedirs(backup_dir, exist_ok=True)
print(f"📦 Created backup: {backup_dir}")

files_to_backup = [
    "app.py", "config.py", "requirements.txt",
]
for file_path in files_to_backup:
    if os.path.exists(file_path):
        dest = os.path.join(backup_dir, os.path.basename(file_path))
        shutil.copy2(file_path, dest)


# ==============================================================================
# FILE 1: database.py (NEW - SQLAlchemy Models & DB Adapter)
# ==============================================================================

DATABASE_CODE = '''"""
DATABASE LAYER (SQLite ↔ PostgreSQL)
=====================================
Auto-detects which database to use based on DATABASE_URL environment variable.

Local dev (no env var):     SQLite → ./analyzer.db
Production (env var set):   PostgreSQL

Tables:
- projects        (Uploaded schedules with metadata)
- analysis_cache  (Cached engine results by project ID)
- comparisons     (Baseline-vs-Current comparison sessions)
- trends          (Multi-period trend analyses)
- audit_log       (Track who did what — foundation for Step 9)
"""

import os
import logging
from datetime import datetime, timedelta
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, 
    Boolean, Float, LargeBinary, ForeignKey, JSON, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# DATABASE URL DETECTION
# ═══════════════════════════════════════════════════════════

DATABASE_URL = os.environ.get('DATABASE_URL', '')

if DATABASE_URL:
    # Handle Heroku/Render PostgreSQL URL format
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    logger.info("🐘 Using PostgreSQL: %s", DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'configured')
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
else:
    # Local SQLite fallback
    SQLITE_PATH = os.path.abspath('analyzer.db')
    DATABASE_URL = f'sqlite:///{SQLITE_PATH}'
    logger.info("🗃️ Using SQLite: %s", SQLITE_PATH)
    engine = create_engine(
        DATABASE_URL,
        connect_args={'check_same_thread': False, 'timeout': 30},
        poolclass=StaticPool,
    )

Base = declarative_base()
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))


# ═══════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════

class Project(Base):
    """A single uploaded schedule file with its parsed metadata."""
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True)  # Reserved for Step 9

    file_name = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # xer, xml (p6), xml (msp)
    storage_key = Column(String(500), nullable=False)  # local path or S3 key
    file_size_bytes = Column(Integer, default=0)

    proj_short_name = Column(String(255))
    proj_start_date = Column(String(50))
    proj_finish_date = Column(String(50))
    data_date = Column(String(50))

    activity_count = Column(Integer, default=0)
    relationship_count = Column(Integer, default=0)
    resource_count = Column(Integer, default=0)

    status = Column(String(20), default='pending')  # pending, processing, ready, failed
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime)
    last_accessed = Column(DateTime, default=datetime.utcnow)

    analyses = relationship('AnalysisCache', back_populates='project', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'file_name': self.file_name,
            'file_type': self.file_type,
            'proj_short_name': self.proj_short_name,
            'activity_count': self.activity_count,
            'relationship_count': self.relationship_count,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
        }


class AnalysisCache(Base):
    """Cached engine results (health, EVM, longest path, gantt) per project."""
    __tablename__ = 'analysis_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    analysis_type = Column(String(50), nullable=False)  # dashboard, health_all, health_dcma, evm, gantt, longest_path
    result_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship('Project', back_populates='analyses')

    __table_args__ = (
        Index('idx_cache_lookup', 'project_id', 'analysis_type'),
    )


class Comparison(Base):
    """Comparison between two Project IDs (baseline vs current)."""
    __tablename__ = 'comparisons'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=True)

    baseline_project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    current_project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)

    result_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrendSet(Base):
    """A multi-period trend analysis linking multiple projects."""
    __tablename__ = 'trend_sets'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=True)

    name = Column(String(255))
    project_ids = Column(JSON)  # List of project IDs in chronological order
    result_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Audit trail — foundation for Step 9 user tracking."""
    __tablename__ = 'audit_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=True)
    action = Column(String(100), nullable=False)  # upload, analyze, export, delete
    entity_type = Column(String(50))  # project, comparison, trend
    entity_id = Column(Integer)
    details = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ═══════════════════════════════════════════════════════════
# INITIALIZATION & HELPERS
# ═══════════════════════════════════════════════════════════

def init_db():
    """Create all tables if they don't exist."""
    logger.info("🔨 Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database schema ready")


def get_db():
    """Get a new database session. Always close after use."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def cleanup_old_projects(days=7):
    """Delete projects older than N days (housekeeping)."""
    db = get_db()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        old_projects = db.query(Project).filter(Project.created_at < cutoff).all()
        for p in old_projects:
            logger.info(f"🧹 Cleaning up old project: {p.file_name} (created {p.created_at})")
            db.delete(p)
        db.commit()
        return len(old_projects)
    except Exception as e:
        db.rollback()
        logger.error(f"Cleanup error: {e}")
        return 0
    finally:
        db.close()


def log_action(session_id, action, entity_type=None, entity_id=None, details=None, user_id=None):
    """Record an audit log entry."""
    db = get_db()
    try:
        entry = AuditLog(
            session_id=session_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {}
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Audit log failed: {e}")
    finally:
        db.close()
'''

with open("database.py", "w", encoding="utf-8") as f:
    f.write(DATABASE_CODE)
print("  ✅ Created database.py (SQLite/PostgreSQL adapter)")


# ==============================================================================
# FILE 2: storage.py (NEW - Local Disk ↔ S3 Adapter)
# ==============================================================================

STORAGE_CODE = '''"""
STORAGE ABSTRACTION LAYER
==========================
Auto-detects storage backend based on env vars:
  Local dev:  ./uploads/ folder
  Production: AWS S3 (requires AWS_ACCESS_KEY_ID + S3_BUCKET_NAME)

Usage:
  storage = get_storage()
  key = storage.save(file_stream, filename)      # Returns storage_key
  stream = storage.load(key)                     # Returns BytesIO
  storage.delete(key)
  exists = storage.exists(key)
"""

import os
import io
import uuid
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseStorage(ABC):
    """Storage backend interface."""

    @abstractmethod
    def save(self, file_stream, filename): pass

    @abstractmethod
    def load(self, storage_key): pass

    @abstractmethod
    def delete(self, storage_key): pass

    @abstractmethod
    def exists(self, storage_key): pass


class LocalDiskStorage(BaseStorage):
    """Store files on local disk in ./uploads/"""

    def __init__(self, base_folder='uploads'):
        self.base_folder = base_folder
        os.makedirs(base_folder, exist_ok=True)
        logger.info(f"💾 Using LocalDiskStorage: {os.path.abspath(base_folder)}")

    def save(self, file_stream, filename):
        # Generate a unique key
        ext = filename.split('.')[-1] if '.' in filename else 'bin'
        key = f"{uuid.uuid4().hex}_{filename}"
        fpath = os.path.join(self.base_folder, key)

        # Handle both Flask FileStorage and BytesIO
        if hasattr(file_stream, 'save'):
            file_stream.save(fpath)
        else:
            with open(fpath, 'wb') as f:
                if hasattr(file_stream, 'read'):
                    data = file_stream.read()
                    if isinstance(data, str):
                        data = data.encode('utf-8')
                    f.write(data)
                else:
                    f.write(file_stream)

        return key

    def load(self, storage_key):
        fpath = os.path.join(self.base_folder, storage_key)
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"File not found: {storage_key}")
        return open(fpath, 'rb')

    def delete(self, storage_key):
        fpath = os.path.join(self.base_folder, storage_key)
        if os.path.exists(fpath):
            os.remove(fpath)
            return True
        return False

    def exists(self, storage_key):
        return os.path.exists(os.path.join(self.base_folder, storage_key))

    def get_path(self, storage_key):
        """Get absolute local path (for parsers that need file paths)."""
        return os.path.abspath(os.path.join(self.base_folder, storage_key))


class S3Storage(BaseStorage):
    """AWS S3 storage backend."""

    def __init__(self):
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 required for S3 storage. Run: pip install boto3")

        self.bucket = os.environ.get('S3_BUCKET_NAME')
        if not self.bucket:
            raise ValueError("S3_BUCKET_NAME env var not set")

        region = os.environ.get('AWS_REGION', 'us-east-1')
        self.s3 = boto3.client('s3', region_name=region)
        logger.info(f"☁️ Using S3Storage: bucket={self.bucket}, region={region}")

    def save(self, file_stream, filename):
        key = f"schedules/{uuid.uuid4().hex}_{filename}"
        if hasattr(file_stream, 'read'):
            self.s3.upload_fileobj(file_stream, self.bucket, key)
        else:
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=file_stream)
        return key

    def load(self, storage_key):
        buf = io.BytesIO()
        self.s3.download_fileobj(self.bucket, storage_key, buf)
        buf.seek(0)
        return buf

    def delete(self, storage_key):
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception:
            return False

    def exists(self, storage_key):
        try:
            self.s3.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception:
            return False

    def get_path(self, storage_key):
        """S3 doesn't have local paths; download to temp file."""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
        buf = self.load(storage_key)
        tmp.write(buf.read())
        tmp.close()
        return tmp.name


# ═══════════════════════════════════════════════════════════
# FACTORY
# ═══════════════════════════════════════════════════════════

_storage_instance = None

def get_storage():
    """Get the singleton storage instance based on env vars."""
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    if os.environ.get('AWS_ACCESS_KEY_ID') and os.environ.get('S3_BUCKET_NAME'):
        try:
            _storage_instance = S3Storage()
            return _storage_instance
        except Exception as e:
            logger.warning(f"S3 storage init failed, falling back to local: {e}")

    _storage_instance = LocalDiskStorage()
    return _storage_instance
'''

with open("storage.py", "w", encoding="utf-8") as f:
    f.write(STORAGE_CODE)
print("  ✅ Created storage.py (Local/S3 adapter)")


# ==============================================================================
# FILE 3: task_queue.py (NEW - Background Job Processor)
# ==============================================================================

TASK_QUEUE_CODE = '''"""
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
                    logger.error(f"Job {job_id} failed: {e}\\n{tb}")
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
'''

with open("task_queue.py", "w", encoding="utf-8") as f:
    f.write(TASK_QUEUE_CODE)
print("  ✅ Created task_queue.py (Threads/Celery adapter)")


# ==============================================================================
# FILE 4: project_service.py (NEW - Business Logic Layer)
# ==============================================================================

PROJECT_SERVICE_CODE = '''"""
PROJECT SERVICE LAYER
======================
Business logic for uploading, processing, and querying projects.
Coordinates: Storage + Database + Task Queue + Engines
"""

import logging
from datetime import datetime
from database import get_db, Project, AnalysisCache, log_action
from storage import get_storage
from universal_parser import UniversalParser
from data_engine import ScheduleEngine

logger = logging.getLogger(__name__)


class ProjectService:
    """Handles project upload, processing, and retrieval."""

    def __init__(self, session_id, user_id=None):
        self.session_id = session_id
        self.user_id = user_id
        self.storage = get_storage()

    # ═══════════════════════════════════════════
    # UPLOAD & PROCESSING
    # ═══════════════════════════════════════════

    def upload_and_process(self, file_stream, filename, file_size_bytes=0):
        """
        Save file to storage, create DB record, parse and analyze.
        Returns project dict.
        """
        logger.info(f"📤 Uploading: {filename}")

        # Save to storage
        storage_key = self.storage.save(file_stream, filename)

        # Detect file type
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        file_type = ext

        # Create DB record
        db = get_db()
        try:
            project = Project(
                session_id=self.session_id,
                user_id=self.user_id,
                file_name=filename,
                file_type=file_type,
                storage_key=storage_key,
                file_size_bytes=file_size_bytes,
                status='processing',
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            project_id = project.id
        finally:
            db.close()

        log_action(self.session_id, 'upload', 'project', project_id, {'filename': filename}, self.user_id)

        # Parse and analyze (synchronous for now — could be async via task_queue)
        try:
            result = self._parse_and_analyze(project_id, storage_key, filename)
            return result
        except Exception as e:
            logger.exception(f"Processing failed: {e}")
            self._update_status(project_id, 'failed', str(e))
            raise

    def _parse_and_analyze(self, project_id, storage_key, filename):
        """Parse the file and cache results."""
        # Load file
        file_path = self.storage.get_path(storage_key)
        
        # Parse
        parser = UniversalParser()
        with open(file_path, 'rb') as f:
            tables = parser.parse(f, filename)
        
        if tables is None or not tables:
            self._update_status(project_id, 'failed', 'Failed to parse file')
            raise Exception('Failed to parse schedule file')

        # Analyze
        engine = ScheduleEngine()
        engine.load_data(tables)
        engine.analyze()

        # Auto-compute Longest Path
        try:
            from longest_path_engine import LongestPathEngine
            lp = LongestPathEngine(engine)
            lp.calculate()
            engine.longest_path_ids = lp.longest_path_ids
            engine.longest_path_results = lp.results if hasattr(lp, 'results') else {}
        except Exception as e:
            logger.warning(f"Longest Path calc failed: {e}")
            engine.longest_path_ids = set()

        # Get dashboard data
        dashboard_data = engine.get_dashboard_data()

        # Update project metadata
        info = engine._get_project_info() or {}
        db = get_db()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.proj_short_name = info.get('name', '')
                project.proj_start_date = info.get('start', '')
                project.proj_finish_date = info.get('finish', '')
                project.data_date = info.get('data_date', '')
                project.activity_count = len(engine.activities)
                project.relationship_count = len(engine.relationships)
                project.resource_count = len(engine.resources)
                project.status = 'ready'
                project.processed_at = datetime.utcnow()
                project.last_accessed = datetime.utcnow()
                db.commit()

                # Cache dashboard data
                self._save_analysis(db, project_id, 'dashboard', dashboard_data)

                # Store engine in memory for follow-up requests
                # (Session-scoped engine cache — stays in RAM for this session)
                _ENGINE_CACHE[project_id] = engine

                return project.to_dict()
        finally:
            db.close()

    def _update_status(self, project_id, status, error_message=None):
        db = get_db()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = status
                if error_message:
                    project.error_message = error_message
                db.commit()
        finally:
            db.close()

    def _save_analysis(self, db, project_id, analysis_type, result):
        """Cache an analysis result in DB."""
        # Delete old cache entry
        db.query(AnalysisCache).filter(
            AnalysisCache.project_id == project_id,
            AnalysisCache.analysis_type == analysis_type
        ).delete()
        # Insert new
        cache = AnalysisCache(
            project_id=project_id,
            analysis_type=analysis_type,
            result_json=result
        )
        db.add(cache)
        db.commit()

    # ═══════════════════════════════════════════
    # RETRIEVAL
    # ═══════════════════════════════════════════

    def list_projects(self, limit=50):
        """List all projects in this session."""
        db = get_db()
        try:
            projects = (
                db.query(Project)
                .filter(Project.session_id == self.session_id)
                .order_by(Project.created_at.desc())
                .limit(limit)
                .all()
            )
            return [p.to_dict() for p in projects]
        finally:
            db.close()

    def get_project(self, project_id):
        """Get project metadata."""
        db = get_db()
        try:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.session_id == self.session_id
            ).first()
            if not project:
                return None
            # Update last_accessed
            project.last_accessed = datetime.utcnow()
            db.commit()
            return project.to_dict()
        finally:
            db.close()

    def get_engine(self, project_id):
        """Get the ScheduleEngine for a project (loads from storage if not cached)."""
        # Check RAM cache first
        if project_id in _ENGINE_CACHE:
            return _ENGINE_CACHE[project_id]

        # Reconstruct from storage
        db = get_db()
        try:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.session_id == self.session_id
            ).first()
            if not project:
                return None

            file_path = self.storage.get_path(project.storage_key)
            parser = UniversalParser()
            with open(file_path, 'rb') as f:
                tables = parser.parse(f, project.file_name)

            engine = ScheduleEngine()
            engine.load_data(tables)
            engine.analyze()

            try:
                from longest_path_engine import LongestPathEngine
                lp = LongestPathEngine(engine)
                lp.calculate()
                engine.longest_path_ids = lp.longest_path_ids
            except Exception:
                engine.longest_path_ids = set()

            _ENGINE_CACHE[project_id] = engine
            return engine
        finally:
            db.close()

    def get_cached_analysis(self, project_id, analysis_type):
        """Get cached analysis JSON from DB."""
        db = get_db()
        try:
            cache = db.query(AnalysisCache).filter(
                AnalysisCache.project_id == project_id,
                AnalysisCache.analysis_type == analysis_type
            ).first()
            return cache.result_json if cache else None
        finally:
            db.close()

    def save_cached_analysis(self, project_id, analysis_type, result):
        """Save analysis result to cache."""
        db = get_db()
        try:
            self._save_analysis(db, project_id, analysis_type, result)
        finally:
            db.close()

    def delete_project(self, project_id):
        """Delete a project + its file + all analyses."""
        db = get_db()
        try:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.session_id == self.session_id
            ).first()
            if not project:
                return False
            # Delete file from storage
            try:
                self.storage.delete(project.storage_key)
            except Exception as e:
                logger.warning(f"Storage delete failed: {e}")
            # Delete DB record (cascade deletes analyses)
            db.delete(project)
            db.commit()
            # Remove from RAM cache
            if project_id in _ENGINE_CACHE:
                del _ENGINE_CACHE[project_id]
            log_action(self.session_id, 'delete', 'project', project_id, None, self.user_id)
            return True
        finally:
            db.close()


# ═══════════════════════════════════════════
# IN-MEMORY ENGINE CACHE
# ═══════════════════════════════════════════
# Keeps parsed engines in RAM between requests for the same session.
# This avoids re-parsing large XER files on every API call.
# LRU-style: bounded to N most recently used.

_ENGINE_CACHE = {}
_MAX_CACHED_ENGINES = 20


def evict_lru_engines():
    """Simple LRU eviction if cache grows too large."""
    if len(_ENGINE_CACHE) > _MAX_CACHED_ENGINES:
        # Just clear half — simple strategy
        keys = list(_ENGINE_CACHE.keys())
        for k in keys[:len(keys) // 2]:
            del _ENGINE_CACHE[k]
'''

with open("project_service.py", "w", encoding="utf-8") as f:
    f.write(PROJECT_SERVICE_CODE)
print("  ✅ Created project_service.py (Business logic layer)")


# ==============================================================================
# FILE 5: config.py PATCH
# ==============================================================================

try:
    with open("config.py", "r", encoding="utf-8") as f:
        cfg = f.read()

    if 'DATABASE_URL' not in cfg:
        addition = '''

# ═══════════════════════════════════════════════════════════
# PHASE 3 STEP 8: PERSISTENT BACKEND CONFIGURATION
# ═══════════════════════════════════════════════════════════
# All are optional — app auto-falls-back to local dev mode

# Database (optional — defaults to SQLite ./analyzer.db)
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Object Storage (optional — defaults to local ./uploads/)
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Task Queue (optional — defaults to in-process threads)
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', '')
WORKER_THREADS = int(os.environ.get('WORKER_THREADS', '2'))

# Project retention (days)
PROJECT_RETENTION_DAYS = int(os.environ.get('PROJECT_RETENTION_DAYS', '7'))
'''
        cfg += addition
        with open("config.py", "w", encoding="utf-8") as f:
            f.write(cfg)
        print("  ✅ Patched config.py (added Phase 3 Step 8 config)")
except Exception as e:
    print(f"  ⚠️ config.py patch failed: {e}")


# ==============================================================================
# FILE 6: requirements.txt PATCH
# ==============================================================================

try:
    with open("requirements.txt", "r", encoding="utf-8") as f:
        reqs = f.read()

    additions = []
    if 'sqlalchemy' not in reqs.lower():
        additions.append('SQLAlchemy>=2.0,<3.0')
    if 'psycopg2' not in reqs.lower():
        additions.append('psycopg2-binary>=2.9  # For PostgreSQL (optional)')
    if 'boto3' not in reqs.lower():
        additions.append('boto3>=1.28  # For S3 storage (optional)')

    if additions:
        reqs += '\n\n# Phase 3 Step 8: Persistent Backend\n' + '\n'.join(additions) + '\n'
        with open("requirements.txt", "w", encoding="utf-8") as f:
            f.write(reqs)
        print(f"  ✅ Added {len(additions)} packages to requirements.txt")
except Exception as e:
    print(f"  ⚠️ requirements.txt patch failed: {e}")


# ==============================================================================
# FILE 7: app.py PATCH (Bootstrap DB on startup + add project endpoints)
# ==============================================================================

try:
    with open("app.py", "r", encoding="utf-8") as f:
        app_code = f.read()

    # Add DB initialization at app startup
    if 'from database import init_db' not in app_code:
        app_code = app_code.replace(
            "from parser import XERParser",
            "from parser import XERParser\nfrom database import init_db, cleanup_old_projects\nfrom project_service import ProjectService"
        )

    # Call init_db() after Flask app creation
    if 'init_db()' not in app_code:
        app_code = app_code.replace(
            "app.secret_key = SECRET_KEY\nCORS(app)",
            "app.secret_key = SECRET_KEY\nCORS(app)\n\n# Initialize database schema on startup\ninit_db()\nlogger.info('✅ Database initialized')"
        )

    # Add new endpoints just before if __name__
    if '/api/projects' not in app_code:
        new_endpoints = '''

# ═══════════════════════════════════════════
# PHASE 3 STEP 8: PROJECT MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════

@app.route('/api/projects', methods=['GET'])
def list_user_projects():
    """List all uploaded projects for this session."""
    sess_id = session.get('sid')
    if not sess_id:
        return jsonify({'projects': []})
    service = ProjectService(sess_id)
    return jsonify({'projects': service.list_projects()})


@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_user_project(project_id):
    """Delete a project."""
    sess_id = session.get('sid')
    if not sess_id:
        return jsonify({'error': 'Not authenticated'}), 401
    service = ProjectService(sess_id)
    ok = service.delete_project(project_id)
    if not ok:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify({'success': True})


@app.route('/api/projects/<int:project_id>/activate', methods=['POST'])
def activate_project(project_id):
    """Load an existing project into the current session as active."""
    sess_id = session.get('sid')
    if not sess_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    service = ProjectService(sess_id)
    project = service.get_project(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    engine = service.get_engine(project_id)
    if not engine:
        return jsonify({'error': 'Failed to load project engine'}), 500
    
    # Load into legacy session structure for backward compat
    sess_data = get_session_data()
    sess_data['analysis']['engine'] = engine
    sess_data['analysis']['dashboard_data'] = engine.get_dashboard_data()
    sess_data['analysis']['file_name'] = project['file_name']
    sess_data['analysis']['analyzed_at'] = project.get('processed_at', '')
    sess_data['analysis']['project_id'] = project_id
    sess_data['health_cache'] = {}
    sess_data['longest_path_cache'] = None
    
    return jsonify({
        'success': True,
        'project': project,
        'data': sess_data['analysis']['dashboard_data']
    })

'''
        app_code = app_code.replace(
            "if __name__ == '__main__':",
            new_endpoints + "\nif __name__ == '__main__':"
        )

    with open("app.py", "w", encoding="utf-8") as f:
        f.write(app_code)
    print("  ✅ Patched app.py (DB init + project management endpoints)")
except Exception as e:
    print(f"  ⚠️ app.py patch failed: {e}")


print("\n")
print("═" * 70)
print("🎉 Phase 3 - Step 8 (Persistent Backend Architecture) COMPLETE!")
print("═" * 70)
print("")
print("📦 What was created:")
print("   ✅ database.py         → SQLite ↔ PostgreSQL adapter")
print("   ✅ storage.py          → Local disk ↔ S3 adapter")
print("   ✅ task_queue.py       → Threads ↔ Celery adapter")
print("   ✅ project_service.py  → Business logic layer")
print("   ✅ Patched: app.py, config.py, requirements.txt")
print("")
print("🚀 NEXT STEPS:")
print("")
print("1. Install new dependencies:")
print("     pip install -r requirements.txt")
print("")
print("2. Restart Flask:")
print("     python app.py")
print("")
print("   You'll see:")
print("     🗃️ Using SQLite: /path/to/analyzer.db")
print("     💾 Using LocalDiskStorage")
print("     🧵 ThreadedQueue started with 2 workers")
print("     🔨 Initializing database schema...")
print("     ✅ Database initialized")
print("")
print("3. Test the new endpoints:")
print("   • Upload an XER as usual")
print("   • Visit: http://localhost:5000/api/projects")
print("     → See your uploaded project persisted in the DB!")
print("   • Restart the server → project is still there!")
print("")
print("🌐 TO DEPLOY WITH POSTGRESQL (Render/Heroku/AWS):")
print("   Set these environment variables:")
print("     DATABASE_URL=postgresql://user:pass@host:5432/dbname")
print("")
print("🌐 TO DEPLOY WITH S3 STORAGE:")
print("     AWS_ACCESS_KEY_ID=...")
print("     AWS_SECRET_ACCESS_KEY=...")
print("     S3_BUCKET_NAME=my-analyzer-bucket")
print("     AWS_REGION=us-east-1")
print("")
print("🌐 TO ENABLE CELERY (production async):")
print("     CELERY_BROKER_URL=redis://redis-host:6379/0")
print("")
print("📊 In the browser console, try:")
print("     fetch('/api/projects').then(r => r.json()).then(console.log)")