"""Servidor MCP (Model Context Protocol) do console Fluxo C.

Expõe um subconjunto das operações da API (casos de teste, observações,
resumo de execução e quadro de tarefas) como *tools* MCP, pra poder pedir
essas coisas em linguagem natural direto do Claude/Cowork, sem precisar
abrir a tela. Fica montado em `/mcp` (ver app/main.py), atrás de
autenticação por token (MCP_TOKEN) — ver README para configurar.
"""

from typing import Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from . import models
from .activity import log as log_activity, snippet
from .database import SessionLocal

VALID_STATUSES = {"Não testado", "Aprovado", "Reprovado", "Bloqueado", "N/A"}
TODO_STATUSES = {"a_fazer", "fazendo", "feito"}

mcp = FastMCP(
    "Fluxo C — Console de Teste (Faiston)",
    instructions=(
        "Ferramentas para consultar e atualizar os casos de teste do Fluxo C "
        "(Despacho NEXO) e o quadro de tarefas do time Faiston. Use "
        "listar_casos/obter_caso pra consultar, atualizar_status_caso e "
        "adicionar_observacao pra registrar o resultado de um teste."
    ),
    stateless_http=True,
    streamable_http_path="/",
)


def _case_to_dict(case: models.TestCase) -> dict:
    return {
        "code": case.code,
        "fluxo": case.fluxo,
        "grupo": case.grupo,
        "estagio": case.estagio,
        "frente": case.frente,
        "status": case.status,
        "testado_por": case.testado_por,
        "chamado": case.chamado,
        "resultado_esperado": case.resultado_esperado,
        "observacoes": [
            {
                "autor": o.autor,
                "texto": o.texto,
                "data": o.created_at.isoformat() if o.created_at else None,
            }
            for o in case.observations
        ],
    }


@mcp.tool()
def listar_casos(
    status: Optional[str] = None,
    grupo: Optional[str] = None,
    frente: Optional[str] = None,
) -> list[dict]:
    """Lista os casos de teste do Fluxo C. Filtros opcionais por status
    (Não testado/Aprovado/Reprovado/Bloqueado/N/A), grupo (ex.: "Grupo A")
    ou frente (ex.: "Operador (web)", "App do técnico")."""
    db = SessionLocal()
    try:
        query = (
            db.query(models.TestCase)
            .options(joinedload(models.TestCase.observations))
            .filter(models.TestCase.active.is_(True))
        )
        if status:
            query = query.filter(models.TestCase.status == status)
        if grupo:
            query = query.filter(models.TestCase.grupo == grupo)
        if frente:
            query = query.filter(models.TestCase.frente == frente)
        cases = query.order_by(
            models.TestCase.grupo, models.TestCase.estagio_num.nulls_last(), models.TestCase.code
        ).all()
        return [_case_to_dict(c) for c in cases]
    finally:
        db.close()


@mcp.tool()
def obter_caso(code: str) -> dict:
    """Retorna os detalhes completos de um caso de teste pelo código (ex.: FC-01)."""
    db = SessionLocal()
    try:
        case = (
            db.query(models.TestCase)
            .options(joinedload(models.TestCase.observations))
            .filter(models.TestCase.code == code, models.TestCase.active.is_(True))
            .first()
        )
        if not case:
            return {"erro": f"Caso {code} não encontrado"}
        return _case_to_dict(case)
    finally:
        db.close()


@mcp.tool()
def atualizar_status_caso(code: str, status: str, testado_por: Optional[str] = None) -> dict:
    """Atualiza o status de um caso de teste. Status válidos: Não testado,
    Aprovado, Reprovado, Bloqueado, N/A."""
    if status not in VALID_STATUSES:
        return {"erro": f"Status inválido: {status}. Use um de {sorted(VALID_STATUSES)}"}
    db = SessionLocal()
    try:
        case = (
            db.query(models.TestCase)
            .filter(models.TestCase.code == code, models.TestCase.active.is_(True))
            .first()
        )
        if not case:
            return {"erro": f"Caso {code} não encontrado"}
        old_status = case.status
        case.status = status
        if testado_por is not None:
            case.testado_por = testado_por
        if status != old_status:
            log_activity(
                db, case.fluxo, "status", f"{case.code} mudou para {status}",
                autor=testado_por or case.testado_por, case_code=case.code,
            )
        db.commit()
        db.refresh(case)
        return _case_to_dict(case)
    finally:
        db.close()


@mcp.tool()
def adicionar_observacao(code: str, texto: str, autor: Optional[str] = None) -> dict:
    """Adiciona uma observação ao histórico de um caso de teste (não apaga as anteriores)."""
    texto = (texto or "").strip()
    if not texto:
        return {"erro": "Observação vazia."}
    db = SessionLocal()
    try:
        case = (
            db.query(models.TestCase)
            .filter(models.TestCase.code == code, models.TestCase.active.is_(True))
            .first()
        )
        if not case:
            return {"erro": f"Caso {code} não encontrado"}
        db.add(models.Observation(test_case_id=case.id, autor=autor, texto=texto))
        log_activity(
            db, case.fluxo, "obs", f'Observação em {case.code}: "{snippet(texto)}"',
            autor=autor, case_code=case.code,
        )
        db.commit()
        db.refresh(case)
        return _case_to_dict(case)
    finally:
        db.close()


@mcp.tool()
def resumo_execucao() -> dict:
    """Retorna a contagem de casos de teste por status e o percentual executado do Fluxo C."""
    db = SessionLocal()
    try:
        total = db.query(models.TestCase).filter(models.TestCase.active.is_(True)).count()
        rows = (
            db.query(models.TestCase.status, func.count(models.TestCase.id))
            .filter(models.TestCase.active.is_(True))
            .group_by(models.TestCase.status)
            .all()
        )
        counts = {status: qtd for status, qtd in rows}
        executado = total - counts.get("Não testado", 0)
        pct = round((executado / total) * 100, 1) if total else 0.0
        return {"total": total, "counts": counts, "pct_executado": pct}
    finally:
        db.close()


@mcp.tool()
def listar_tarefas(status: Optional[str] = None) -> list[dict]:
    """Lista as tarefas do quadro Kanban do time Faiston. Status opcional:
    a_fazer, fazendo ou feito."""
    db = SessionLocal()
    try:
        query = db.query(models.TodoTarefa)
        if status:
            query = query.filter(models.TodoTarefa.status == status)
        tarefas = query.order_by(models.TodoTarefa.status, models.TodoTarefa.posicao).all()
        return [
            {
                "id": t.id,
                "titulo": t.titulo,
                "descricao": t.descricao,
                "status": t.status,
                "responsavel": t.responsavel,
            }
            for t in tarefas
        ]
    finally:
        db.close()


@mcp.tool()
def criar_tarefa(
    titulo: str,
    descricao: str = "",
    responsavel: Optional[str] = None,
    autor: Optional[str] = None,
) -> dict:
    """Cria uma nova tarefa no quadro Kanban do time Faiston, na coluna 'A Fazer'."""
    titulo = (titulo or "").strip()
    if not titulo:
        return {"erro": "Título vazio."}
    db = SessionLocal()
    try:
        max_pos = (
            db.query(func.max(models.TodoTarefa.posicao))
            .filter(models.TodoTarefa.status == "a_fazer")
            .scalar()
        )
        tarefa = models.TodoTarefa(
            titulo=titulo,
            descricao=descricao or "",
            status="a_fazer",
            posicao=(max_pos or 0) + 1,
            responsavel=responsavel,
            autor=autor,
        )
        db.add(tarefa)
        db.commit()
        db.refresh(tarefa)
        return {"id": tarefa.id, "titulo": tarefa.titulo, "status": tarefa.status}
    finally:
        db.close()
