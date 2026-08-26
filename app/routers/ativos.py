"""Ajustes do módulo Gestão de Ativos (Faiston One).

Cada ajuste é um item "como está hoje / como deve ser", classificado como Bug ou
Melhoria e agrupado por versão da leva (v2, v3...). A tela lê tudo daqui — não há
nada de v2 chumbado no código: para abrir a próxima rodada de ajustes basta
cadastrar itens com a versão nova.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["ativos"])

TIPOS = {"Bug", "Melhoria"}
PRIORIDADES = {"Alta", "Média", "Baixa", "A definir"}
# ciclo de vida do ajuste, do levantamento até a validação na tela do Faiston One
STATUSES = {"levantado", "analise", "desenvolvimento", "entregue", "validado", "descartado"}


def _norm_versao(valor: Optional[str], padrao: str = "v2") -> str:
    v = (valor or "").strip().lower()
    if not v:
        return padrao
    # aceita "2", "V2", "v2 " e grava sempre no formato "v2"
    if v.isdigit():
        v = "v" + v
    return v


def _next_numero(db: Session, versao: str) -> int:
    maior = (
        db.query(sa_func.max(models.AtivoAjuste.numero))
        .filter(models.AtivoAjuste.versao == versao)
        .scalar()
    )
    return (maior or 0) + 1


@router.get("/ativos/ajustes", response_model=List[schemas.AtivoAjusteOut])
def list_ajustes(
    versao: Optional[str] = None,
    tipo: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.AtivoAjuste)
    if versao:
        q = q.filter(models.AtivoAjuste.versao == _norm_versao(versao))
    if tipo:
        q = q.filter(models.AtivoAjuste.tipo == tipo)
    if status:
        q = q.filter(models.AtivoAjuste.status == status)
    return q.order_by(models.AtivoAjuste.versao, models.AtivoAjuste.numero, models.AtivoAjuste.id).all()


@router.post("/ativos/ajustes", response_model=schemas.AtivoAjusteOut, status_code=201)
def create_ajuste(payload: schemas.AtivoAjusteCreate, db: Session = Depends(get_db)):
    titulo = (payload.titulo or "").strip()
    if not titulo:
        raise HTTPException(status_code=400, detail="Título vazio.")
    versao = _norm_versao(payload.versao)
    tipo = (payload.tipo or "Melhoria").strip()
    if tipo not in TIPOS:
        raise HTTPException(status_code=400, detail="Tipo inválido — use Bug ou Melhoria.")
    prioridade = (payload.prioridade or "Média").strip()
    if prioridade not in PRIORIDADES:
        prioridade = "Média"
    status = (payload.status or "levantado").strip()
    if status not in STATUSES:
        status = "levantado"
    ajuste = models.AtivoAjuste(
        versao=versao,
        numero=payload.numero if payload.numero else _next_numero(db, versao),
        titulo=titulo,
        tipo=tipo,
        area=(payload.area or "").strip() or None,
        prioridade=prioridade,
        atual=payload.atual or "",
        esperado=payload.esperado or "",
        observacao=payload.observacao or "",
        status=status,
        responsavel=(payload.responsavel or "").strip() or None,
        autor=(payload.autor or "").strip() or None,
    )
    db.add(ajuste)
    db.commit()
    db.refresh(ajuste)
    return ajuste


@router.patch("/ativos/ajustes/{ajuste_id}", response_model=schemas.AtivoAjusteOut)
def update_ajuste(ajuste_id: int, payload: schemas.AtivoAjusteUpdate, db: Session = Depends(get_db)):
    ajuste = db.query(models.AtivoAjuste).filter(models.AtivoAjuste.id == ajuste_id).first()
    if not ajuste:
        raise HTTPException(status_code=404, detail="Ajuste não encontrado")
    if payload.titulo is not None:
        titulo = payload.titulo.strip()
        if not titulo:
            raise HTTPException(status_code=400, detail="Título vazio.")
        ajuste.titulo = titulo
    if payload.versao is not None:
        nova = _norm_versao(payload.versao, ajuste.versao)
        if nova != ajuste.versao:
            ajuste.versao = nova
            # ao mudar de versão o número antigo pode já existir lá — renumera pro fim
            if payload.numero is None:
                ajuste.numero = _next_numero(db, nova)
    if payload.numero is not None:
        ajuste.numero = payload.numero
    if payload.tipo is not None:
        if payload.tipo not in TIPOS:
            raise HTTPException(status_code=400, detail="Tipo inválido — use Bug ou Melhoria.")
        ajuste.tipo = payload.tipo
    if payload.area is not None:
        ajuste.area = payload.area.strip() or None
    if payload.prioridade is not None and payload.prioridade in PRIORIDADES:
        ajuste.prioridade = payload.prioridade
    if payload.atual is not None:
        ajuste.atual = payload.atual
    if payload.esperado is not None:
        ajuste.esperado = payload.esperado
    if payload.observacao is not None:
        ajuste.observacao = payload.observacao
    if payload.status is not None:
        if payload.status not in STATUSES:
            raise HTTPException(status_code=400, detail="Status inválido.")
        ajuste.status = payload.status
    if payload.responsavel is not None:
        ajuste.responsavel = payload.responsavel.strip() or None
    db.commit()
    db.refresh(ajuste)
    return ajuste


@router.delete("/ativos/ajustes/{ajuste_id}")
def delete_ajuste(ajuste_id: int, db: Session = Depends(get_db)):
    ajuste = db.query(models.AtivoAjuste).filter(models.AtivoAjuste.id == ajuste_id).first()
    if not ajuste:
        raise HTTPException(status_code=404, detail="Ajuste não encontrado")
    db.delete(ajuste)
    db.commit()
    return {"deleted": ajuste_id}
