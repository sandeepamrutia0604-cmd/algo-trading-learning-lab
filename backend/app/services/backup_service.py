"""Backing up and restoring everything the app knows: the whole database in one file.

The database holds the portfolio and market clock, trades, positions, strategies, signals, saved backtests,
alerts, the risk and cost settings and every stock's price history (history imported from a file can't be
regenerated, so it has to be kept). So a backup is simply a consistent copy of that one file, made with SQLite's
online backup API: it is safe while the app is running and works on the in-memory database the tests use.

A restore copies the uploaded file *into* the live database with the same API instead of swapping files, which
works on Windows with connections open. Before it overwrites anything it saves a safety copy of the current data
(`backups/before-restore-<time>.db` in the data folder, the newest few kept), and afterwards it runs the same
startup steps as a normal launch, so a backup made by an older version is upgraded to the current schema.
"""

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from .. import models  # noqa: F401  (registers every table for create_all)
from ..db import Base
from ..migrations import ensure_columns
from ..paths import data_dir
from .exceptions import TradingError
from .seed import ensure_seed_data

MAX_BACKUP_BYTES = 200 * 1024 * 1024
KEEP_SAFETY_COPIES = 5
CORE_TABLES = {"portfolio", "stocks", "price_data", "trades", "positions"}
SQLITE_HEADER = b"SQLite format 3\x00"
SAFETY_PREFIX = "before-restore-"


class BackupError(TradingError):
    """A file that can't be used as a backup, or a backup that can't be taken."""


class BackupBusyError(BackupError):
    """The database is in the middle of something else; try again in a moment."""


def _tmp_path(prefix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=".db", prefix=prefix)
    os.close(fd)
    return Path(name)


def snapshot(engine: Engine) -> Path:
    """A consistent copy of the live database in a new temporary file (the caller deletes it)."""
    target = _tmp_path("algo-backup-")
    raw = engine.raw_connection()
    try:
        copy = sqlite3.connect(target)
        try:
            raw.driver_connection.backup(copy)
        finally:
            copy.close()
    except sqlite3.OperationalError as err:
        target.unlink(missing_ok=True)
        raise BackupBusyError(f"The database is busy ({err}). Try again in a moment.") from None
    finally:
        raw.close()
    return target


def validate(path: Path) -> None:
    """Raise BackupError unless `path` is a healthy SQLite database that looks like one of ours."""
    size = path.stat().st_size
    if size > MAX_BACKUP_BYTES:
        raise BackupError(f"That file is too large to be a backup ({size // (1024 * 1024)} MB; the limit is {MAX_BACKUP_BYTES // (1024 * 1024)} MB).")
    with open(path, "rb") as handle:
        if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            raise BackupError("That isn't a backup made by this app (it is not a database file).")
    try:
        check = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise BackupError("That backup file is damaged (it failed the database integrity check).")
            tables = {row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            check.close()
    except sqlite3.DatabaseError:
        raise BackupError("That isn't a backup made by this app (the database can't be read).") from None
    missing = CORE_TABLES - tables
    if missing:
        raise BackupError(f"That database isn't one of this app's backups (missing: {', '.join(sorted(missing))}).")


def _prune(folder: Path) -> None:
    copies = sorted(folder.glob(f"{SAFETY_PREFIX}*.db"))
    for old in copies[:-KEEP_SAFETY_COPIES]:
        old.unlink(missing_ok=True)


def safety_copies() -> list[Path]:
    folder = data_dir() / "backups"
    return sorted(folder.glob(f"{SAFETY_PREFIX}*.db")) if folder.is_dir() else []


def save_safety_copy(engine: Engine) -> Path:
    """Keep a copy of the current data before a restore overwrites it."""
    folder = data_dir() / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    taken = snapshot(engine)
    target = folder / f"{SAFETY_PREFIX}{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.db"  # sorts oldest first
    shutil.move(str(taken), str(target))  # the temp folder may be on another drive
    _prune(folder)
    return target


def restore(engine: Engine, uploaded: Path, db: Session) -> Path:
    """Replace the live database's contents with the backup at `uploaded`. Returns the safety copy of what was
    there before. `db` is a session on the same engine, used for the post-restore upgrade."""
    validate(uploaded)
    safety = save_safety_copy(engine)

    source = sqlite3.connect(uploaded)
    raw = engine.raw_connection()
    try:
        source.backup(raw.driver_connection)
    except sqlite3.OperationalError as err:
        raise BackupBusyError(f"The database is busy ({err}). Nothing was changed; try again in a moment.") from None
    finally:
        source.close()
        raw.close()

    db.expire_all()
    Base.metadata.create_all(bind=engine)  # tables an older backup didn't have yet
    ensure_columns(engine)  # columns added since it was made
    ensure_seed_data(db)
    return safety


def database_file(engine: Engine) -> Path | None:
    name = make_url(str(engine.url)).database
    return Path(name).resolve() if name and name != ":memory:" else None


def database_bytes(engine: Engine) -> int:
    raw = engine.raw_connection()
    try:
        con = raw.driver_connection
        return con.execute("PRAGMA page_count").fetchone()[0] * con.execute("PRAGMA page_size").fetchone()[0]
    finally:
        raw.close()
