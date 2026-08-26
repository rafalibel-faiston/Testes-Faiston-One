"""Pauta da reunião semanal servida como página pronta.

`GET /relatorio` devolve, com os dados vivos do banco, tudo que ainda não
está aprovado — pontos em aberto, testes reprovados/bloqueados/não
executados, estágios travados das situações e os ajustes da Gestão de Ativos
pendentes de validação. É a página pra abrir e projetar na reunião; o
`tools/relatorio_reuniao.py` gera o mesmo HTML como arquivo.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..relatorio import montar_html

router = APIRouter(tags=["relatorio"])


def _dump(schema, itens) -> List[dict]:
    return [schema.model_validate(i).model_dump(mode="json") for i in itens]


def _coletar(db: Session, fluxo: Optional[str]) -> dict:
    """Monta os dados da pauta.

    Sem `fluxo`, cobre os três fluxos de uma vez: um estágio reprovado no Fluxo B
    precisa da mesma conversa que um do Fluxo C, e filtrar por um fluxo só
    escondia metade da reunião. `?fluxo=C` continua funcionando pra quem quiser
    a pauta de um fluxo específico.
    """
    casos_q = (
        db.query(models.TestCase)
        .options(joinedload(models.TestCase.screenshots), joinedload(models.TestCase.observations))
        .filter(models.TestCase.active.is_(True))
    )
    notas_q = db.query(models.MeetingNote)
    situacoes_q = (
        db.query(models.Situacao)
        .options(
            joinedload(models.Situacao.estagios).joinedload(models.SituacaoEstagio.screenshots),
            joinedload(models.Situacao.estagios).joinedload(models.SituacaoEstagio.observations),
        )
        .filter(models.Situacao.active.is_(True))
    )
    if fluxo:
        casos_q = casos_q.filter(models.TestCase.fluxo == fluxo)
        notas_q = notas_q.filter(models.MeetingNote.fluxo == fluxo)
        situacoes_q = situacoes_q.filter(models.Situacao.fluxo == fluxo)

    casos = casos_q.order_by(
        models.TestCase.fluxo, models.TestCase.grupo,
        models.TestCase.estagio_num.nulls_last(), models.TestCase.code,
    ).all()
    notas = notas_q.order_by(
        models.MeetingNote.resolvido, models.MeetingNote.cobrado, models.MeetingNote.created_at,
    ).all()
    situacoes = situacoes_q.order_by(models.Situacao.fluxo, models.Situacao.id).all()

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
def relatorio(fluxo: Optional[str] = None, db: Session = Depends(get_db)):
    fonte = f"Console de Teste — Fluxo {fluxo}" if fluxo else "Console de Teste — todos os fluxos"
    # servida pelo app: os campos de retorno salvam direto na API
    html = montar_html(_coletar(db, fluxo), fonte, editavel=True)
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
