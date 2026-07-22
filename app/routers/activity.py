from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["activity"])

PERFIS = {"LP", "Faiston"}


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


@router.get("/atividades/visto", response_model=schemas.TeamViewOut)
def get_seen(perfil: str, fluxo: str = "C", db: Session = Depends(get_db)):
    """Até onde este perfil (time) já viu as Novidades deste fluxo."""
    if perfil not in PERFIS:
        raise HTTPException(status_code=400, detail="Perfil inválido.")
    tv = (
        db.query(models.TeamView)
        .filter(models.TeamView.perfil == perfil, models.TeamView.fluxo == fluxo)
        .first()
    )
    return schemas.TeamViewOut(perfil=perfil, fluxo=fluxo, last_seen_id=tv.last_seen_id if tv else 0)


@router.post("/atividades/visto", response_model=schemas.TeamViewOut)
def mark_seen(payload: schemas.TeamViewMark, db: Session = Depends(get_db)):
    """Marca as Novidades como vistas até certo evento, pro time todo (nunca
    volta atrás — usa o maior id entre o já salvo e o informado)."""
    if payload.perfil not in PERFIS:
        raise HTTPException(status_code=400, detail="Perfil inválido.")
    tv = (
        db.query(models.TeamView)
        .filter(models.TeamView.perfil == payload.perfil, models.TeamView.fluxo == payload.fluxo)
        .first()
    )
    new_id = max(0, payload.last_seen_id)
    if tv is None:
        tv = models.TeamView(perfil=payload.perfil, fluxo=payload.fluxo, last_seen_id=new_id)
        db.add(tv)
    elif new_id > tv.last_seen_id:
        tv.last_seen_id = new_id
    db.commit()
    return schemas.TeamViewOut(perfil=tv.perfil, fluxo=tv.fluxo, last_seen_id=tv.last_seen_id)
