import sqlite3
import os
import sys
import logging

class ManifestManager:
    DB_NAME = "manifest.db"

    def __init__(self, db_path=None):
        self.db_path = db_path or self._get_default_db_path()
        self.logger = logging.getLogger(__name__)
        self._init_db()

    @staticmethod
    def _get_default_db_path():
        if getattr(sys, 'frozen', False):
            app_root = os.path.dirname(sys.executable)
        else:
            # src/manifest_manager.py → go up two levels to project root
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.abspath(os.path.join(app_root, "config", ManifestManager.DB_NAME))

    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS files (
                        job_name TEXT,
                        file_path TEXT,
                        rel_path TEXT,
                        size INTEGER,
                        mtime REAL,
                        PRIMARY KEY (job_name, file_path)
                    )
                """)
                conn.commit()
        except Exception as e:
            self.logger.error("Failed to initialize manifest DB: %s", e, exc_info=True)

    def get_file_state(self, job_name, file_path):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT size, mtime FROM files WHERE job_name=? AND file_path=?",
                    (job_name, file_path)
                )
                row = cursor.fetchone()
                return {'size': row[0], 'mtime': row[1]} if row else None
        except Exception as e:
            self.logger.error("Error getting file state for %s: %s", file_path, e, exc_info=True)
            return None

    def update_file_state(self, job_name, file_path, rel_path, size, mtime):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO files (job_name, file_path, rel_path, size, mtime) VALUES (?, ?, ?, ?, ?)",
                    (job_name, file_path, rel_path, size, mtime)
                )
                conn.commit()
        except Exception as e:
            self.logger.error("Error updating file state for %s: %s", file_path, e, exc_info=True)

    def batch_update_files(self, job_name, updates):
        """Bulk-insert or replace file states. updates: list of (file_path, rel_path, size, mtime)."""
        if not updates:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO files (job_name, file_path, rel_path, size, mtime) VALUES (?, ?, ?, ?, ?)",
                    [(job_name, fp, rp, sz, mt) for fp, rp, sz, mt in updates]
                )
                conn.commit()
            self.logger.info("Batch updated %d manifest entries for job '%s'.", len(updates), job_name)
        except Exception as e:
            self.logger.error("Error batch-updating manifest for job '%s': %s", job_name, e, exc_info=True)

    def batch_remove_files(self, job_name, file_paths):
        """Bulk-delete file states. file_paths: list of absolute file path strings."""
        if not file_paths:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    "DELETE FROM files WHERE job_name=? AND file_path=?",
                    [(job_name, fp) for fp in file_paths]
                )
                conn.commit()
            self.logger.info("Batch removed %d manifest entries for job '%s'.", len(file_paths), job_name)
        except Exception as e:
            self.logger.error("Error batch-removing manifest for job '%s': %s", job_name, e, exc_info=True)

    def remove_file_state(self, job_name, file_path):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM files WHERE job_name=? AND file_path=?",
                    (job_name, file_path)
                )
                conn.commit()
        except Exception as e:
            self.logger.error("Error removing file state for %s: %s", file_path, e, exc_info=True)

    def get_job_files(self, job_name):
        """Return all manifest entries for a job as {file_path: {rel_path, size, mtime}}."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT file_path, rel_path, size, mtime FROM files WHERE job_name=?",
                    (job_name,)
                ).fetchall()
                return {row['file_path']: {'rel_path': row['rel_path'], 'size': row['size'], 'mtime': row['mtime']} for row in rows}
        except Exception as e:
            self.logger.error("Error getting job files for '%s': %s", job_name, e, exc_info=True)
            return {}

    def clear_job_manifest(self, job_name):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM files WHERE job_name=?", (job_name,))
                conn.commit()
        except Exception as e:
            self.logger.error("Error clearing manifest for '%s': %s", job_name, e, exc_info=True)
