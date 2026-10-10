import sqlite3
from pathlib import Path

import pytest

from backend.app.services import backup_service

OK_HEADERS = {"x-algo-backup": "restore", "content-type": "application/octet-stream"}


@pytest.fixture()
def data_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_service, "data_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture()
def lab(client, data_folder):
    """A client whose market has history, plus a trade and an alert on ALPHA."""
    client.post("/api/market/generate", json={"days": 80, "seed": 3})
    client.post("/api/orders/buy", json={"symbol": "ALPHA", "quantity": 5})
    price = next(s for s in client.get("/api/stocks").json() if s["symbol"] == "ALPHA")["current_price"]
    client.post("/api/alerts", json={"symbol": "ALPHA", "kind": "above", "level": round(price * 1.2, 2), "note": "keep me"})
    return client


def restore(client, data, **headers):
    return client.post("/api/backup/restore", content=data, headers={**OK_HEADERS, **headers})


def tables_in(data: bytes, tmp_path: Path) -> dict:
    path = tmp_path / "inspect.db"
    path.write_bytes(data)
    con = sqlite3.connect(path)
    try:
        return {name: con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        con.close()


# ---------- downloading ----------


def test_the_download_is_a_real_database_with_my_data_in_it(lab, tmp_path):
    response = lab.get("/api/backup/download")

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith('attachment; filename="algo-lab-backup-')
    assert response.content.startswith(b"SQLite format 3\x00")
    counts = tables_in(response.content, tmp_path)
    assert counts["trades"] == 1 and counts["price_alerts"] == 1 and counts["stocks"] >= 4 and counts["price_data"] > 0


def test_info_reports_the_size_and_safety_copies(lab):
    info = lab.get("/api/backup/info").json()
    assert info["database_bytes"] > 0 and info["safety_copies"] == 0 and info["newest_safety_copy"] is None


# ---------- restoring ----------


def test_a_restore_brings_everything_back_after_a_reset(lab):
    before = lab.get("/api/portfolio").json()
    backup = lab.get("/api/backup/download").content
    lab.post("/api/reset")
    assert lab.get("/api/trades").json() == [] and lab.get("/api/alerts").json() == []

    response = restore(lab, backup)

    assert response.status_code == 200, response.text
    assert response.json()["trades"] == 1
    assert [t["symbol"] for t in lab.get("/api/trades").json()] == ["ALPHA"]
    assert [a["note"] for a in lab.get("/api/alerts").json()] == ["keep me"]
    after = lab.get("/api/portfolio").json()
    assert (after["cash"], after["realized_pnl"]) == (before["cash"], before["realized_pnl"])
    assert lab.get("/api/market/status").json()["date"] is not None


def test_a_restore_first_saves_what_was_there(lab, data_folder):
    backup = lab.get("/api/backup/download").content
    lab.post("/api/reset")  # now there are no trades

    safety = restore(lab, backup).json()["safety_copy"]

    kept = Path(safety)
    assert kept.parent == data_folder / "backups" and kept.is_file()
    con = sqlite3.connect(kept)
    try:
        assert con.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0  # the data from before the restore
    finally:
        con.close()
    assert lab.get("/api/backup/info").json()["safety_copies"] == 1


def test_only_the_newest_safety_copies_are_kept(lab, data_folder):
    backup = lab.get("/api/backup/download").content
    for _ in range(backup_service.KEEP_SAFETY_COPIES + 2):
        assert restore(lab, backup).status_code == 200
    assert len(list((data_folder / "backups").glob("before-restore-*.db"))) == backup_service.KEEP_SAFETY_COPIES


def test_an_older_backup_is_upgraded_after_restoring(lab, tmp_path):
    backup = lab.get("/api/backup/download").content
    old = tmp_path / "old.db"
    old.write_bytes(backup)
    con = sqlite3.connect(old)
    con.execute("ALTER TABLE trades DROP COLUMN fees")  # a column added since
    con.execute("DROP TABLE price_alerts")  # a table added since
    con.commit()
    con.close()

    response = restore(lab, old.read_bytes())

    assert response.status_code == 200, response.text
    assert lab.get("/api/trades").json()[0]["fees"] is not None
    assert lab.get("/api/alerts").status_code == 200  # the table exists again


# ---------- refusing bad files and bad requests ----------


def test_a_file_that_is_not_a_database_is_refused_and_nothing_changes(lab):
    response = restore(lab, b"just some text pretending to be a backup")

    assert response.status_code == 400 and "isn't a backup" in response.json()["detail"]
    assert len(lab.get("/api/trades").json()) == 1


def test_a_damaged_database_is_refused(lab, tmp_path):
    backup = bytearray(lab.get("/api/backup/download").content)
    for i in range(4096 * 2, min(len(backup), 4096 * 6)):
        backup[i] = 0xFF  # scribble over some pages
    response = restore(lab, bytes(backup))
    assert response.status_code == 400
    assert len(lab.get("/api/trades").json()) == 1


def test_a_database_from_something_else_is_refused(lab, tmp_path):
    other = tmp_path / "other.db"
    con = sqlite3.connect(other)
    con.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
    con.commit()
    con.close()

    response = restore(lab, other.read_bytes())

    assert response.status_code == 400 and "missing" in response.json()["detail"]
    assert len(lab.get("/api/trades").json()) == 1


def test_an_empty_upload_is_refused(lab):
    assert restore(lab, b"").status_code == 400


def test_an_oversize_upload_is_refused(lab, monkeypatch):
    monkeypatch.setattr("backend.app.api.backup.MAX_BACKUP_BYTES", 100)
    assert restore(lab, b"x" * 500).status_code == 413


def test_a_restore_must_carry_the_apps_own_header_and_content_type(lab):
    backup = lab.get("/api/backup/download").content
    assert lab.post("/api/backup/restore", content=backup, headers={"content-type": "application/octet-stream"}).status_code == 400
    assert lab.post("/api/backup/restore", content=backup, headers={"x-algo-backup": "restore", "content-type": "text/plain"}).status_code == 415


def test_a_restore_from_another_website_is_refused(lab):
    backup = lab.get("/api/backup/download").content
    response = restore(lab, backup, origin="https://evil.example")
    assert response.status_code == 403
    assert len(lab.get("/api/trades").json()) == 1


def test_a_restore_from_the_apps_own_page_is_accepted(lab):
    backup = lab.get("/api/backup/download").content
    assert restore(lab, backup, origin="http://testserver").status_code == 200
