import os
import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from ..db import get_db
from ..live import origin_allowed
from ..models import Stock, Trade
from ..schemas import BackupInfoOut, BackupRestoreOut
from ..services import backup_service, market_service
from ..services.backup_service import BackupBusyError, MAX_BACKUP_BYTES

router = APIRouter()

RESTORE_HEADER = "x-algo-backup"
RESTORE_CONTENT_TYPE = "application/octet-stream"


def _check_restore_request(request: Request) -> None:
    """A restore overwrites everything, so only this app's own page may ask for one. Another website can't
    send a custom header or this content type without a CORS preflight, which the app never allows, and a
    browser always says which site a POST came from."""
    if request.headers.get(RESTORE_HEADER) != "restore":
        raise HTTPException(status_code=400, detail="Restore requests must come from the app's own Backup tab.")
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != RESTORE_CONTENT_TYPE:
        raise HTTPException(status_code=415, detail="Send the backup file as application/octet-stream.")
    if not origin_allowed(request):
        raise HTTPException(status_code=403, detail="Restores are only accepted from the app's own page.")


@router.get("/backup/info", response_model=BackupInfoOut)
def backup_info(db: Session = Depends(get_db)):
    engine = db.get_bind()
    file = backup_service.database_file(engine)
    copies = backup_service.safety_copies()
    return BackupInfoOut(
        database_bytes=backup_service.database_bytes(engine),
        location=str(file) if file else None,
        safety_copies=len(copies),
        newest_safety_copy=str(copies[-1]) if copies else None,
    )


@router.get("/backup/download")
def download_backup(db: Session = Depends(get_db)):
    """The whole database as one file. Read-only: it changes nothing and is not announced to other tabs."""
    path = backup_service.snapshot(db.get_bind())
    return FileResponse(
        path,
        media_type=RESTORE_CONTENT_TYPE,
        filename=f"algo-lab-backup-{date.today().isoformat()}.db",
        background=BackgroundTask(os.remove, path),
    )


@router.post("/backup/restore", response_model=BackupRestoreOut)
async def restore_backup(request: Request, db: Session = Depends(get_db)):
    _check_restore_request(request)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BACKUP_BYTES:
        raise HTTPException(status_code=413, detail="That file is too large to be a backup.")

    fd, name = tempfile.mkstemp(suffix=".db", prefix="algo-restore-")
    path = os.fdopen(fd, "wb")
    received = 0
    try:
        with path:
            async for chunk in request.stream():
                received += len(chunk)
                if received > MAX_BACKUP_BYTES:
                    raise HTTPException(status_code=413, detail="That file is too large to be a backup.")
                path.write(chunk)
        if received == 0:
            raise HTTPException(status_code=400, detail="No file was sent.")
        try:
            safety = await run_in_threadpool(backup_service.restore, db.get_bind(), Path(name), db)
        except BackupBusyError as err:
            raise HTTPException(status_code=409, detail=str(err)) from None
    finally:
        os.remove(name)

    return BackupRestoreOut(
        stocks=db.query(Stock).count(),
        trades=db.query(Trade).count(),
        market_date=market_service.latest_market_date(db),
        safety_copy=str(safety),
    )

