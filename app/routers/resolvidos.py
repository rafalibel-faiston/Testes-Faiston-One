"""Resolvidos pra comunicar à operação (ver app/resolvidos.py)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from .. import models, resolvidos, schemas
from ..activity import log as log_activity
from ..database import get_db

router = APIRouter(tags=["resolvidos"])


@router.get("/resolvidos", response_model=List[schemas.ResolvidoComunicarOut])
def list_resolvidos(comunicado: Optional[bool] = None, db: Session = Depends(get_db)):
    """Sem filtro traz tudo; `?comunicado=false` é a lista de quem ainda falta avisar."""
    q = db.query(models.ResolvidoComunicar)
    if comunicado is not None:
        q = q.filter(models.ResolvidoComunicar.comunicado.is_(comunicado))
    return q.order_by(models.ResolvidoComunicar.created_at.desc(),
                      models.ResolvidoComunicar.id.desc()).all()


@router.post("/resolvidos/resgatar")
def resgatar_antigos(desde: Optional[str] = None, aplicar: bool = False,
                     db: Session = Depends(get_db)):
    """Puxa, pela trilha de Novidades, o que virou de Reprovado para Aprovado antes
    do lembrete automático existir. Sem `aplicar=true` é só simulação — devolve a
    lista do que seria criado, sem gravar nada. `desde=AAAA-MM-DD` limita a data."""
    try:
        return resolvidos.resgatar(db, desde=desde, aplicar=aplicar)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida — use o formato AAAA-MM-DD.")


@router.patch("/resolvidos/{item_id}", response_model=schemas.ResolvidoComunicarOut)
def update_resolvido(item_id: int, payload: schemas.ResolvidoComunicarUpdate,
                     db: Session = Depends(get_db)):
    """Marca como comunicado (ou desfaz, se clicou sem querer)."""
    item = db.query(models.ResolvidoComunicar).filter(models.ResolvidoComunicar.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    if payload.comunicado != item.comunicado:
        item.comunicado = payload.comunicado
        item.comunicado_em = func.now() if payload.comunicado else None
        item.comunicado_por = (payload.comunicado_por or None) if payload.comunicado else None
        if payload.comunicado:
            log_activity(db, item.fluxo, "status", f"{item.codigo} · operação avisada da resolução",
                         autor=payload.comunicado_por, case_code=item.codigo)
    db.commit()
    db.refresh(item)
    return item
