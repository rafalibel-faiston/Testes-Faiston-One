from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["agenda"])


@router.get("/agenda", response_model=List[schemas.AgendaEventoOut])
def list_eventos(inicio: Optional[str] = None, fim: Optional[str] = None, db: Session = Depends(get_db)):
    """Eventos da agenda, opcionalmente filtrados por um intervalo de datas (AAAA-MM-DD)."""
    q = db.query(models.AgendaEvento)
    if inicio:
        q = q.filter(models.AgendaEvento.data >= inicio)
    if fim:
        q = q.filter(models.AgendaEvento.data <= fim)
    return q.order_by(models.AgendaEvento.data, models.AgendaEvento.hora_inicio).all()


@router.post("/agenda", response_model=schemas.AgendaEventoOut, status_code=201)
def create_evento(payload: schemas.AgendaEventoCreate, db: Session = Depends(get_db)):
    titulo = (payload.titulo or "").strip()
    if not titulo:
        raise HTTPException(status_code=400, detail="Título vazio.")
    if not (payload.data or "").strip():
        raise HTTPException(status_code=400, detail="Data obrigatória.")
    evento = models.AgendaEvento(
        titulo=titulo,
        descricao=payload.descricao or "",
        data=payload.data.strip(),
        hora_inicio=(payload.hora_inicio or "").strip() or None,
        hora_fim=(payload.hora_fim or "").strip() or None,
        autor=payload.autor,
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return evento


@router.patch("/agenda/{evento_id}", response_model=schemas.AgendaEventoOut)
def update_evento(evento_id: int, payload: schemas.AgendaEventoUpdate, db: Session = Depends(get_db)):
    evento = db.query(models.AgendaEvento).filter(models.AgendaEvento.id == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    if payload.titulo is not None:
        titulo = payload.titulo.strip()
        if not titulo:
            raise HTTPException(status_code=400, detail="Título vazio.")
        evento.titulo = titulo
    if payload.descricao is not None:
        evento.descricao = payload.descricao
    if payload.data is not None:
        if not payload.data.strip():
            raise HTTPException(status_code=400, detail="Data obrigatória.")
        evento.data = payload.data.strip()
    if payload.hora_inicio is not None:
        evento.hora_inicio = payload.hora_inicio.strip() or None
    if payload.hora_fim is not None:
        evento.hora_fim = payload.hora_fim.strip() or None
    db.commit()
    db.refresh(evento)
    return evento


@router.delete("/agenda/{evento_id}")
def delete_evento(evento_id: int, db: Session = Depends(get_db)):
    evento = db.query(models.AgendaEvento).filter(models.AgendaEvento.id == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    db.delete(evento)
    db.commit()
    return {"deleted": evento_id}
