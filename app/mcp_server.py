"""Servidor MCP (Model Context Protocol) do console Fluxo C.

Expõe um subconjunto das operações da API (casos de teste, observações,
resumo de execução e quadro de tarefas) como *tools* MCP, pra poder pedir
essas coisas em linguagem natural direto do Claude/Cowork, sem precisar
abrir a tela. Fica montado na raiz do app (ver app/main.py), atrás de um
fluxo OAuth mínimo: o "Vincular" do Cowork abre /mcp-login, que pede o
MCP_TOKEN como senha antes de emitir o token de acesso — ver README.
"""

import os
import secrets
import time
from typing import Optional
from urllib.parse import urlparse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    TokenError,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from . import models
from .activity import log as log_activity, snippet
from .database import SessionLocal

VALID_STATUSES = {"Não testado", "Aprovado", "Reprovado", "Bloqueado", "N/A"}
TODO_STATUSES = {"a_fazer", "fazendo", "feito"}

# URL pública do app (sem barra no final) — usada como issuer/resource do OAuth.
# Em produção (Railway) defina PUBLIC_BASE_URL; localmente cai pro localhost.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
MCP_TOKEN = os.getenv("MCP_TOKEN", "").strip()
ACCESS_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 dias — sem refresh token, reconecta depois disso
AUTH_REQUEST_TTL_SECONDS = 60 * 10
AUTH_CODE_TTL_SECONDS = 60 * 5


class SimpleOAuthProvider:
    """Provider OAuth mínimo, em memória: o único "login" é digitar o MCP_TOKEN
    na telinha /mcp-login (ver app/main.py). Não tem múltiplos usuários nem
    refresh token — pensado pra um admin único conectando o Cowork/Claude.
    Client registration (DCR) é aceita de qualquer cliente, como o Claude exige."""

    def __init__(self):
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_requests: dict[str, tuple[OAuthClientInformationFull, AuthorizationParams, float]] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.access_tokens: dict[str, AccessToken] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.clients[client_info.client_id] = client_info

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        request_id = secrets.token_urlsafe(24)
        self.auth_requests[request_id] = (client, params, time.time() + AUTH_REQUEST_TTL_SECONDS)
        return f"{PUBLIC_BASE_URL}/mcp-login?request_id={request_id}"

    def peek_pending_request(self, request_id: str):
        """Usado por /mcp-login (main.py) pra checar se um pedido de autorização
        pendente existe/ainda é válido, sem consumi-lo (só complete_authorization
        remove — assim a página de login pode ser recarregada sem invalidar)."""
        entry = self.auth_requests.get(request_id)
        if not entry:
            return None
        client, params, expires_at = entry
        if expires_at < time.time():
            self.auth_requests.pop(request_id, None)
            return None
        return client, params

    def complete_authorization(self, request_id: str) -> str:
        """Gera o código de autorização e devolve a redirect_uri pro cliente (Claude)."""
        from mcp.server.auth.provider import construct_redirect_uri

        client, params, _ = self.auth_requests.pop(request_id)
        code = secrets.token_urlsafe(32)
        self.auth_codes[code] = AuthorizationCode(
            code=code,
            scopes=params.scopes or ["mcp"],
            expires_at=time.time() + AUTH_CODE_TTL_SECONDS,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self.auth_codes.get(authorization_code)
        if code is None or code.client_id != client.client_id:
            return None
        if code.expires_at < time.time():
            self.auth_codes.pop(authorization_code, None)
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self.auth_codes.pop(authorization_code.code, None)
        token = secrets.token_urlsafe(32)
        self.access_tokens[token] = AccessToken(
            token=token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + ACCESS_TOKEN_TTL_SECONDS,
        )
        return OAuthToken(
            access_token=token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_TTL_SECONDS,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str):
        return None

    async def exchange_refresh_token(self, client, refresh_token, scopes: list[str]) -> OAuthToken:
        raise TokenError(error="unsupported_grant_type", error_description="Refresh token não é suportado.")

    async def load_access_token(self, token: str) -> AccessToken | None:
        access = self.access_tokens.get(token)
        if access is None:
            return None
        if access.expires_at and access.expires_at < time.time():
            self.access_tokens.pop(token, None)
            return None
        return access

    async def revoke_token(self, token) -> None:
        self.access_tokens.pop(token.token, None)


oauth_provider = SimpleOAuthProvider()

# a proteção de DNS-rebinding do SDK, se deixada no padrão, só libera Host
# "localhost"/"127.0.0.1" — sem isso o domínio real do Railway toma 421
# Misdirected Request em toda chamada a /mcp. Libera explicitamente o host
# público configurado (+ localhost, pra continuar funcionando em dev local).
_public_netloc = urlparse(PUBLIC_BASE_URL).netloc

mcp = FastMCP(
    "Fluxo C — Console de Teste (Faiston)",
    instructions=(
        "Ferramentas para consultar e atualizar os casos de teste do Fluxo C "
        "(Despacho NEXO) e o quadro de tarefas do time Faiston. Use "
        "listar_casos/obter_caso pra consultar, atualizar_status_caso e "
        "adicionar_observacao pra registrar o resultado de um teste."
    ),
    stateless_http=True,
    auth_server_provider=oauth_provider,
    auth=AuthSettings(
        issuer_url=PUBLIC_BASE_URL,
        resource_server_url=f"{PUBLIC_BASE_URL}/mcp",
        required_scopes=["mcp"],
        client_registration_options=ClientRegistrationOptions(
            enabled=True, valid_scopes=["mcp"], default_scopes=["mcp"]
        ),
        revocation_options=RevocationOptions(enabled=True),
    ),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[_public_netloc, f"{_public_netloc}:*", "127.0.0.1:*", "localhost:*", "[::1]:*"],
        allowed_origins=[PUBLIC_BASE_URL, "http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
    ),
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
                "id": o.id,
                "autor": o.autor,
                "texto": o.texto,
                "data": o.created_at.isoformat() if o.created_at else None,
                "atualizada_por": o.editado_por,
                "atualizada_em": o.editado_em.isoformat() if o.editado_em else None,
                # trilha: o que a observação dizia antes de cada atualização
                "versoes_anteriores": [
                    {
                        "texto": r.texto,
                        "autor": r.autor,
                        "substituida_por": r.editado_por,
                        "data": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in o.revisions
                ],
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
def atualizar_observacao(observacao_id: int, texto: str, autor: Optional[str] = None) -> dict:
    """Atualiza o texto de uma observação já existente de um caso de teste.

    O texto anterior não é perdido: vira uma versão na trilha da observação
    (`versoes_anteriores`), então dá pra acompanhar como o ponto evoluiu.
    O `observacao_id` vem do campo `id` das observações em listar_casos/ver_caso.
    """
    texto = (texto or "").strip()
    if not texto:
        return {"erro": "Observação vazia."}
    db = SessionLocal()
    try:
        obs = db.query(models.Observation).filter(models.Observation.id == observacao_id).first()
        if not obs:
            return {"erro": f"Observação {observacao_id} não encontrada"}
        case = db.query(models.TestCase).filter(models.TestCase.id == obs.test_case_id).first()
        if not case:
            return {"erro": "Caso da observação não encontrado"}
        if texto != obs.texto:
            db.add(models.ObservationRevision(
                observation_id=obs.id, texto=obs.texto, autor=obs.autor, editado_por=autor,
            ))
            obs.texto = texto
            obs.editado_por = autor
            obs.editado_em = func.now()
            log_activity(
                db, case.fluxo, "obs",
                f'Observação atualizada em {case.code}: "{snippet(texto)}"',
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


@mcp.tool()
def listar_ajustes_ativos(versao: Optional[str] = None, tipo: Optional[str] = None) -> list[dict]:
    """Lista os ajustes pedidos no módulo Gestão de Ativos do Faiston One.
    versao opcional (ex.: "v2", "v3"); tipo opcional: "Bug" ou "Melhoria"."""
    db = SessionLocal()
    try:
        query = db.query(models.AtivoAjuste)
        if versao:
            query = query.filter(models.AtivoAjuste.versao == versao.strip().lower())
        if tipo:
            query = query.filter(models.AtivoAjuste.tipo == tipo)
        # mesma ordem da tela: prioridade primeiro, número do item como desempate
        ajustes = query.order_by(
            models.AtivoAjuste.versao, models.AJUSTE_PRIORIDADE_ORDEM,
            models.AtivoAjuste.numero, models.AtivoAjuste.id,
        ).all()
        return [
            {
                "id": a.id,
                "versao": a.versao,
                "numero": a.numero,
                "titulo": a.titulo,
                "tipo": a.tipo,
                "area": a.area,
                "prioridade": a.prioridade,
                "atual": a.atual,
                "esperado": a.esperado,
                "status": a.status,
                "responsavel": a.responsavel,
                "retorno": a.retorno,
                "prazo": a.prazo,
            }
            for a in ajustes
        ]
    finally:
        db.close()


@mcp.tool()
def criar_ajuste_ativos(
    titulo: str,
    atual: str,
    esperado: str,
    tipo: str = "Melhoria",
    versao: str = "v2",
    area: Optional[str] = None,
    prioridade: str = "Média",
    autor: Optional[str] = None,
) -> dict:
    """Cadastra um ajuste do módulo Gestão de Ativos: `atual` é como está hoje e
    `esperado` é como deve ser. tipo: "Bug" (está quebrado) ou "Melhoria".
    versao agrupa a leva de ajustes — usar uma versão nova (v3, v4...) abre a
    próxima rodada na tela automaticamente. O número do item é atribuído
    sozinho, na sequência da versão."""
    titulo = (titulo or "").strip()
    if not titulo:
        return {"erro": "Título vazio."}
    if tipo not in {"Bug", "Melhoria"}:
        return {"erro": 'Tipo inválido — use "Bug" ou "Melhoria".'}
    versao = (versao or "v2").strip().lower() or "v2"
    if versao.isdigit():
        versao = "v" + versao
    db = SessionLocal()
    try:
        maior = (
            db.query(func.max(models.AtivoAjuste.numero))
            .filter(models.AtivoAjuste.versao == versao)
            .scalar()
        )
        ajuste = models.AtivoAjuste(
            versao=versao,
            numero=(maior or 0) + 1,
            titulo=titulo,
            tipo=tipo,
            area=(area or "").strip() or None,
            prioridade=prioridade if prioridade in {"Alta", "Média", "Baixa", "A definir"} else "Média",
            atual=atual or "",
            esperado=esperado or "",
            status="levantado",
            autor=autor,
        )
        db.add(ajuste)
        db.commit()
        db.refresh(ajuste)
        return {"id": ajuste.id, "versao": ajuste.versao, "numero": ajuste.numero,
                "titulo": ajuste.titulo, "tipo": ajuste.tipo}
    finally:
        db.close()
