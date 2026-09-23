"""API do nome padrão dos chamados de teste no Tiflux (regra em app/nomes_tiflux.py)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from .. import models, niveis, nomes_tiflux, schemas
from ..activity import log as log_activity
from ..database import get_db

router = APIRouter(tags=["nomes-tiflux"])


def _alvo(db: Session, code: str):
    """Acha o teste pelo código: caso (FC-…) ou situação (SIT-…). Devolve
    (code, tipo, fluxo, texto que vira o assunto do nome)."""
    code = code.strip().upper()
    caso = (
        db.query(models.TestCase)
        .filter(models.TestCase.code == code, models.TestCase.active.is_(True))
        .first()
    )
    if caso:
        return code, "caso", caso.fluxo, caso.resultado_esperado
    sit = (
        db.query(models.Situacao)
        .filter(models.Situacao.code == code, models.Situacao.active.is_(True))
        .first()
    )
    if sit:
        return code, "situacao", sit.fluxo, sit.titulo
    raise HTTPException(status_code=404, detail=f"Teste {code} não encontrado")


def gerar(db: Session, code: Optional[str] = None, assunto: Optional[str] = None,
          nivel: Optional[str] = None, gerado_por: Optional[str] = None) -> models.NomeTiflux:
    """Reserva a próxima rodada do assunto e grava o nome. Usado pela API e pelo MCP."""
    try:
        nivel = niveis.normaliza_nivel(nivel)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    alvo, tipo, fluxo, texto = None, "avulso", None, None
    if code and code.strip():
        alvo, tipo, fluxo, texto = _alvo(db, code)
    if assunto and assunto.strip():
        texto = assunto
    texto = nomes_tiflux.assunto(texto)
    chave = nomes_tiflux.chave(texto)
    if not chave:
        raise HTTPException(status_code=400, detail="Diga o assunto do teste (ou o código do card).")
    autor = (gerado_por or "").strip() or None
    # o mesmo teste mantém o texto da primeira rodada — só o número muda
    primeiro = (
        db.query(models.NomeTiflux.nome)
        .filter(models.NomeTiflux.chave == chave)
        .order_by(models.NomeTiflux.id)
        .first()
    )
    if primeiro:
        texto = nomes_tiflux.assunto_do_nome(primeiro[0])

    # duas pessoas gerando ao mesmo tempo disputam o mesmo número; a trava
    # única do banco decide, e quem perdeu pega o seguinte
    for _ in range(3):
        ultimo = (
            db.query(func.max(models.NomeTiflux.seq))
            .filter(models.NomeTiflux.chave == chave, models.NomeTiflux.nivel == nivel)
            .scalar()
        ) or 0
        seq = ultimo + 1
        row = models.NomeTiflux(
            tipo=tipo, alvo=alvo, chave=chave, nivel=nivel, seq=seq, gerado_por=autor,
            nome=nomes_tiflux.montar(texto, nivel, seq),
        )
        db.add(row)
        log_activity(db, fluxo, "nome_tiflux",
                     f"Nome de chamado gerado: {row.nome}", autor=autor, case_code=alvo)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(row)
        return row
    raise HTTPException(status_code=409, detail="Não deu pra reservar o número da rodada, tente de novo")


@router.get("/nomes-tiflux", response_model=List[schemas.NomeTifluxOut])
def listar(code: Optional[str] = None, db: Session = Depends(get_db)):
    """Todos os nomes já gerados (ou só os de um card), do mais antigo pro mais novo."""
    q = db.query(models.NomeTiflux)
    if code:
        q = q.filter(models.NomeTiflux.alvo == code.strip().upper())
    return q.order_by(models.NomeTiflux.id).all()


@router.post("/nomes-tiflux", response_model=schemas.NomeTifluxOut, status_code=201)
def criar(payload: schemas.NomeTifluxIn, db: Session = Depends(get_db)):
    return gerar(db, payload.code, payload.assunto, payload.nivel, payload.gerado_por)
