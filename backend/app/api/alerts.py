from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import AlertCreate, AlertOut
from ..services import alert_service
from ..services.alert_service import AlertNotFoundError

router = APIRouter()


def _not_found(err: AlertNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(err))


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(db: Session = Depends(get_db)):
    return alert_service.list_all(db)


@router.post("/alerts", response_model=AlertOut)
def create_alert(body: AlertCreate, db: Session = Depends(get_db)):
    return alert_service.create(db, body.symbol, body.kind, body.level, body.note)


@router.post("/alerts/{alert_id}/rearm", response_model=AlertOut)
def rearm_alert(alert_id: int, db: Session = Depends(get_db)):
    try:
        return alert_service.rearm(db, alert_id)
    except AlertNotFoundError as err:
        raise _not_found(err) from None


@router.delete("/alerts/{alert_id}")
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    try:
        alert_service.delete(db, alert_id)
    except AlertNotFoundError as err:
        raise _not_found(err) from None
    return {"deleted": alert_id}
