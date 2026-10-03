"""Atomic local filesystem storage for snapshots and diffs."""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from app.config import settings, BACKEND_DIR

logger = logging.getLogger(__name__)


class StorageSecurityError(ValueError):
    """Raised when a path traversal attempt is detected."""
    pass


class StorageManager:
    def __init__(self, storage_root: Optional[Path] = None):
        self.storage_root = (storage_root or (BACKEND_DIR / "storage")).resolve()
        self.snapshots_dir = (self.storage_root / "snapshots").resolve()
        self.diffs_dir = (self.storage_root / "diffs").resolve()
        self.logs_dir = (self.storage_root / "logs").resolve()

        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.diffs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _safe_resolve(self, relative_path: str) -> Path:
        """Resolve a relative path and verify it stays strictly within storage_root."""
        path_obj = Path(relative_path)
        if path_obj.is_absolute():
            raise StorageSecurityError(f"Absolute paths not permitted: {relative_path}")

        target = (self.storage_root / relative_path).resolve()
        try:
            target.relative_to(self.storage_root)
        except ValueError as exc:
            raise StorageSecurityError(f"Path traversal detected: {relative_path}") from exc
        return target

    def save_snapshot_text(
        self,
        company_id: int,
        page_id: int,
        snapshot_id: int,
        text_content: str,
    ) -> str:
        """Atomically write snapshot text using internal integer IDs.
        
        Never overwrites an earlier snapshot. Returns relative path from storage root.
        """
        # Ensure company/page subdirectories exist
        page_dir = (self.snapshots_dir / str(company_id) / str(page_id)).resolve()
        page_dir.mkdir(parents=True, exist_ok=True)

        final_filename = f"{snapshot_id}.txt"
        final_path = page_dir / final_filename

        if final_path.exists():
            raise FileExistsError(f"Snapshot file already exists: {final_path}")

        # Atomic write: write to temp file in same directory, flush & fsync, then atomic rename
        temp_fd, temp_path_str = tempfile.mkstemp(
            prefix=f".{snapshot_id}_",
            suffix=".tmp",
            dir=page_dir,
        )
        temp_path = Path(temp_path_str)
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(text_content)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace
            temp_path.replace(final_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

        rel_path = final_path.relative_to(self.storage_root).as_posix()
        return rel_path

    def read_snapshot_text(self, relative_path: str) -> str:
        """Safely read UTF-8 snapshot content from a relative path."""
        target_path = self._safe_resolve(relative_path)
        if not target_path.exists():
            raise FileNotFoundError(f"Snapshot file not found: {relative_path}")
        return target_path.read_text(encoding="utf-8", errors="replace")

    def save_diff_text(self, change_event_id: int, diff_content: str) -> str:
        """Atomically write text diff for a change event."""
        final_filename = f"{change_event_id}.txt"
        final_path = self.diffs_dir / final_filename

        temp_fd, temp_path_str = tempfile.mkstemp(
            prefix=f".{change_event_id}_",
            suffix=".tmp",
            dir=self.diffs_dir,
        )
        temp_path = Path(temp_path_str)
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(diff_content)
                f.flush()
                os.fsync(f.fileno())

            temp_path.replace(final_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

        rel_path = final_path.relative_to(self.storage_root).as_posix()
        return rel_path

    def read_diff_text(self, relative_path: str) -> str:
        """Safely read UTF-8 diff content from a relative path."""
        target_path = self._safe_resolve(relative_path)
        if not target_path.exists():
            raise FileNotFoundError(f"Diff file not found: {relative_path}")
        return target_path.read_text(encoding="utf-8", errors="replace")

    def delete_company_files(self, company_id: int) -> None:
        """Delete company snapshot directory upon hard delete per §5.
        
        Failures are logged and do not roll back the database transaction.
        """
        company_dir = self.snapshots_dir / str(company_id)
        if company_dir.exists() and company_dir.is_dir():
            try:
                shutil.rmtree(company_dir)
                logger.info(f"Deleted storage files for company {company_id}")
            except Exception as exc:
                logger.error(f"Failed to delete files for company {company_id}: {exc}")


storage_manager = StorageManager()
