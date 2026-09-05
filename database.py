"""
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
