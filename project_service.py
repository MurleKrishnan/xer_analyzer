"""
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
