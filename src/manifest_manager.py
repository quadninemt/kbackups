import sqlite3
import os
import logging

class ManifestManager:
    DB_NAME = "manifest.db"

    def __init__(self, config_dir="config"):
        self.db_path = os.path.join(config_dir, self.DB_NAME)
        self.logger = logging.getLogger(__name__)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
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
            self.logger.error(f"Failed to initialize manifest DB: {e}")

    def get_file_state(self, job_name, file_path):
        """Get the stored state of a file."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT size, mtime FROM files WHERE job_name=? AND file_path=?",
                    (job_name, file_path)
                )
                row = cursor.fetchone()
                if row:
                    return {'size': row[0], 'mtime': row[1]}
                return None
        except Exception as e:
            self.logger.error(f"Error getting file state for {file_path}: {e}")
            return None

    def update_file_state(self, job_name, file_path, rel_path, size, mtime):
        """Update or insert file state."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO files (job_name, file_path, rel_path, size, mtime)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (job_name, file_path, rel_path, size, mtime)
                )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error updating file state for {file_path}: {e}")

    def remove_file_state(self, job_name, file_path):
        """Remove a file from the manifest."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM files WHERE job_name=? AND file_path=?",
                    (job_name, file_path)
                )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error removing file state for {file_path}: {e}")

    def get_job_files(self, job_name):
        """Get all files associated with a job. Returns dict {path: {metadata}}."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT file_path, rel_path, size, mtime FROM files WHERE job_name=?",
                    (job_name,)
                )
                rows = cursor.fetchall()
                result = {}
                for row in rows:
                    result[row['file_path']] = {
                        'rel_path': row['rel_path'],
                        'size': row['size'],
                        'mtime': row['mtime']
                    }
                return result
        except Exception as e:
            self.logger.error(f"Error getting job files for {job_name}: {e}")
            return {}

    def clear_job_manifest(self, job_name):
        """Clear all entries for a specific job (e.g., for full re-scan)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM files WHERE job_name=?", (job_name,))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error clearing manifest for {job_name}: {e}")
