from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["todo"])

STATUSES = {"a_fazer", "fazendo", "feito"}


def _next_posicao(db: Session, status: str) -> int:
    maxpos = (
        db.query(sa_func.max(models.TodoTarefa.posicao))
        .filter(models.TodoTarefa.status == status)
        .scalar()
    )
    return (maxpos or 0) + 1


@router.get("/todo", response_model=List[schemas.TodoTarefaOut])
def list_tarefas(db: Session = Depends(get_db)):
    return db.query(models.TodoTarefa).order_by(models.TodoTarefa.status, models.TodoTarefa.posicao).all()


@router.post("/todo", response_model=schemas.TodoTarefaOut, status_code=201)
def create_tarefa(payload: schemas.TodoTarefaCreate, db: Session = Depends(get_db)):
    titulo = (payload.titulo or "").strip()
    if not titulo:
        raise HTTPException(status_code=400, detail="Título vazio.")
    status = payload.status if payload.status in STATUSES else "a_fazer"
    tarefa = models.TodoTarefa(
        titulo=titulo,
        descricao=payload.descricao or "",
        status=status,
        posicao=_next_posicao(db, status),
        responsavel=payload.responsavel,
        autor=payload.autor,
    )
    db.add(tarefa)
    db.commit()
    db.refresh(tarefa)
    return tarefa


@router.patch("/todo/{tarefa_id}", response_model=schemas.TodoTarefaOut)
def update_tarefa(tarefa_id: int, payload: schemas.TodoTarefaUpdate, db: Session = Depends(get_db)):
    tarefa = db.query(models.TodoTarefa).filter(models.TodoTarefa.id == tarefa_id).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    if payload.titulo is not None:
        titulo = payload.titulo.strip()
        if not titulo:
            raise HTTPException(status_code=400, detail="Título vazio.")
        tarefa.titulo = titulo
    if payload.descricao is not None:
        tarefa.descricao = payload.descricao
    if payload.responsavel is not None:
        tarefa.responsavel = payload.responsavel
    if payload.status is not None and payload.status != tarefa.status:
        if payload.status not in STATUSES:
            raise HTTPException(status_code=400, detail="Status inválido.")
        tarefa.status = payload.status
        tarefa.posicao = payload.posicao if payload.posicao is not None else _next_posicao(db, payload.status)
    elif payload.posicao is not None:
        tarefa.posicao = payload.posicao
    db.commit()
    db.refresh(tarefa)
    return tarefa


@router.delete("/todo/{tarefa_id}")
def delete_tarefa(tarefa_id: int, db: Session = Depends(get_db)):
    tarefa = db.query(models.TodoTarefa).filter(models.TodoTarefa.id == tarefa_id).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    db.delete(tarefa)
    db.commit()
    return {"deleted": tarefa_id}
