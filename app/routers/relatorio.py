"""Pauta da reunião semanal servida como página pronta.

`GET /relatorio` devolve, com os dados vivos do banco, tudo que ainda não
está aprovado — pontos em aberto, testes reprovados/bloqueados/não
executados, estágios travados das situações e os ajustes da Gestão de Ativos
pendentes de validação. É a página pra abrir e projetar na reunião; o
`tools/relatorio_reuniao.py` gera o mesmo HTML como arquivo.
"""

from typing import List

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..relatorio import montar_html

router = APIRouter(tags=["relatorio"])


def _dump(schema, itens) -> List[dict]:
    return [schema.model_validate(i).model_dump(mode="json") for i in itens]


def _coletar(db: Session, fluxo: str) -> dict:
    casos = (
        db.query(models.TestCase)
        .options(joinedload(models.TestCase.screenshots), joinedload(models.TestCase.observations))
        .filter(models.TestCase.active.is_(True), models.TestCase.fluxo == fluxo)
        .order_by(models.TestCase.grupo, models.TestCase.estagio_num.nulls_last(), models.TestCase.code)
        .all()
    )
    notas = (
        db.query(models.MeetingNote)
        .filter(models.MeetingNote.fluxo == fluxo)
        .order_by(models.MeetingNote.resolvido, models.MeetingNote.cobrado, models.MeetingNote.created_at)
        .all()
    )
    situacoes = (
        db.query(models.Situacao)
        .options(
            joinedload(models.Situacao.estagios).joinedload(models.SituacaoEstagio.screenshots),
            joinedload(models.Situacao.estagios).joinedload(models.SituacaoEstagio.observations),
        )
        .filter(models.Situacao.active.is_(True), models.Situacao.fluxo == fluxo)
        .order_by(models.Situacao.id)
        .all()
    )
    # os ajustes da Gestão de Ativos não pertencem a um fluxo — são do módulo
    # inteiro, então entram na pauta independente do fluxo pedido.
    ajustes = (
        db.query(models.AtivoAjuste)
        .options(joinedload(models.AtivoAjuste.prints))
        .order_by(
            models.AtivoAjuste.versao, models.AJUSTE_PRIORIDADE_ORDEM,
            models.AtivoAjuste.numero, models.AtivoAjuste.id,
        )
        .all()
    )

    counts: dict = {}
    for c in casos:
        counts[c.status] = counts.get(c.status, 0) + 1
    total = len(casos)
    executado = total - counts.get("Não testado", 0)

    return {
        "cases": _dump(schemas.TestCaseOut, casos),
        "notas": _dump(schemas.MeetingNoteOut, notas),
        "situacoes": _dump(schemas.SituacaoOut, situacoes),
        "ativos_ajustes": _dump(schemas.AtivoAjusteOut, ajustes),
        "summary": {
            "total": total,
            "counts": counts,
            "pct_executado": round((executado / total) * 100, 1) if total else 0.0,
        },
    }


@router.get("/relatorio", response_class=HTMLResponse)
def relatorio(fluxo: str = "C", db: Session = Depends(get_db)):
    html = montar_html(_coletar(db, fluxo), f"Console de Teste — Fluxo {fluxo}")
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
