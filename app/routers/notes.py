from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from .. import models, schemas
from ..activity import log as log_activity, normaliza_prazo, snippet
from ..database import get_db

router = APIRouter(tags=["notes"])


@router.get("/notas", response_model=List[schemas.MeetingNoteOut])
def list_notes(fluxo: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.MeetingNote)
    if fluxo:
        q = q.filter(models.MeetingNote.fluxo == fluxo)
    return q.order_by(
        models.MeetingNote.resolvido, models.MeetingNote.cobrado, models.MeetingNote.created_at
    ).all()


@router.post("/notas", response_model=schemas.MeetingNoteOut, status_code=201)
def create_note(payload: schemas.MeetingNoteCreate, db: Session = Depends(get_db)):
    texto = (payload.texto or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Ponto vazio.")
    note = models.MeetingNote(
        fluxo=payload.fluxo or "C", estagio=payload.estagio, texto=texto, autor=payload.autor
    )
    db.add(note)
    log_activity(db, note.fluxo, "ponto", f'Ponto pra reunião: "{snippet(texto)}"', autor=payload.autor)
    db.commit()
    db.refresh(note)
    return note


@router.patch("/notas/{note_id}", response_model=schemas.MeetingNoteOut)
def update_note(note_id: int, payload: schemas.MeetingNoteUpdate, db: Session = Depends(get_db)):
    note = db.query(models.MeetingNote).filter(models.MeetingNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Ponto não encontrado")
    if payload.texto is not None:
        texto = payload.texto.strip()
        if not texto:
            raise HTTPException(status_code=400, detail="Ponto vazio.")
        note.texto = texto
    if payload.estagio is not None:
        note.estagio = payload.estagio
    if payload.cobrado is not None:
        if payload.cobrado and not note.cobrado:
            log_activity(db, note.fluxo, "ponto", f'Ponto cobrado: "{snippet(note.texto, 60)}"')
            note.cobrado_em = func.now()
        elif not payload.cobrado and note.cobrado:
            note.cobrado_em = None
        note.cobrado = payload.cobrado
    if payload.resolvido is not None:
        if payload.resolvido and not note.resolvido:
            log_activity(db, note.fluxo, "ponto", f'Ponto resolvido: "{snippet(note.texto, 60)}"')
            note.resolvido_em = func.now()
        elif not payload.resolvido and note.resolvido:
            note.resolvido_em = None
        note.resolvido = payload.resolvido
    if payload.retorno is not None:
        retorno = payload.retorno.strip()
        if retorno and retorno != (note.retorno or ""):
            log_activity(db, note.fluxo, "ponto",
                         f'Retorno no ponto "{snippet(note.texto, 40)}": {snippet(retorno, 60)}')
        note.retorno = retorno
        note.retorno_em = func.now() if retorno else None
    if payload.prazo is not None:
        note.prazo = normaliza_prazo(payload.prazo)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/notas/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(models.MeetingNote).filter(models.MeetingNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Ponto não encontrado")
    db.delete(note)
    db.commit()
    return {"deleted": note_id}
