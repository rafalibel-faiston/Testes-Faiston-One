from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["activity"])


@router.get("/atividades", response_model=List[schemas.ActivityOut])
def list_activities(fluxo: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    """Trilha de atividades do fluxo, da mais recente pra mais antiga."""
    q = db.query(models.ActivityLog)
    if fluxo:
        q = q.filter(models.ActivityLog.fluxo == fluxo)
    return (
        q.order_by(models.ActivityLog.created_at.desc(), models.ActivityLog.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
