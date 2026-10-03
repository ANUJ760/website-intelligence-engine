"""Tests for local atomic storage, safe filesystem paths, and snapshot retention."""

import pytest
from pathlib import Path

from app.storage.manager import StorageManager, StorageSecurityError


@pytest.fixture
def temp_storage(tmp_path: Path):
    return StorageManager(storage_root=tmp_path)


def test_atomic_snapshot_save_and_read(temp_storage: StorageManager):
    company_id = 1
    page_id = 10
    snapshot_id = 101
    content = "Hello, Acme Corp extracted text snapshot!"

    # 1. Save snapshot
    rel_path = temp_storage.save_snapshot_text(company_id, page_id, snapshot_id, content)
    assert rel_path == "snapshots/1/10/101.txt"

    # 2. Read snapshot
    read_back = temp_storage.read_snapshot_text(rel_path)
    assert read_back == content


def test_multiple_snapshots_retained_without_overwriting(temp_storage: StorageManager):
    """Acceptance test: multiple snapshots of one page are retained without overwriting earlier versions."""
    company_id = 1
    page_id = 10

    # Save snapshot 1
    path1 = temp_storage.save_snapshot_text(company_id, page_id, 1, "Snapshot Version 1")
    # Save snapshot 2
    path2 = temp_storage.save_snapshot_text(company_id, page_id, 2, "Snapshot Version 2")
    # Save snapshot 3
    path3 = temp_storage.save_snapshot_text(company_id, page_id, 3, "Snapshot Version 3")

    assert path1 != path2 != path3
    assert temp_storage.read_snapshot_text(path1) == "Snapshot Version 1"
    assert temp_storage.read_snapshot_text(path2) == "Snapshot Version 2"
    assert temp_storage.read_snapshot_text(path3) == "Snapshot Version 3"


def test_never_overwrite_existing_snapshot(temp_storage: StorageManager):
    company_id = 1
    page_id = 10
    snapshot_id = 5

    temp_storage.save_snapshot_text(company_id, page_id, snapshot_id, "Original")

    # Attempting to save snapshot with same snapshot_id must raise FileExistsError
    with pytest.raises(FileExistsError):
        temp_storage.save_snapshot_text(company_id, page_id, snapshot_id, "Attempted overwrite")


def test_missing_file_handling(temp_storage: StorageManager):
    with pytest.raises(FileNotFoundError):
        temp_storage.read_snapshot_text("snapshots/999/999/999.txt")


def test_path_traversal_prevention(temp_storage: StorageManager):
    traversal_paths = [
        "../../etc/passwd",
        "snapshots/../../../../etc/passwd",
        "/etc/shadow",
    ]
    for p in traversal_paths:
        with pytest.raises(StorageSecurityError):
            temp_storage.read_snapshot_text(p)


def test_delete_company_files(temp_storage: StorageManager):
    company_id = 42
    temp_storage.save_snapshot_text(company_id, 1, 100, "Company 42 Page 1")
    temp_storage.save_snapshot_text(company_id, 2, 200, "Company 42 Page 2")

    comp_dir = temp_storage.snapshots_dir / str(company_id)
    assert comp_dir.exists()

    temp_storage.delete_company_files(company_id)
    assert not comp_dir.exists()
