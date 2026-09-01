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

from fastapi import HTTPException

from . import models
from .activity import log as log_activity, snippet, normaliza_cor
from .database import SessionLocal
from .routers.tecnicos import PAPEIS as TECNICO_PAPEIS
from .routers.tecnicos import STATUSES as TECNICO_STATUSES
from .routers.tecnicos import TIPOS_OBS as TECNICO_TIPOS_OBS
from .routers.tecnicos import _mensagem_para as mensagem_para_tecnico
from .routers.tecnicos import _norm_telefone as norm_telefone_tecnico

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
        "(Despacho NEXO), o quadro de tarefas do time Faiston e o QA do Track "
        "One (app dos técnicos). Use listar_casos/obter_caso pra consultar, "
        "atualizar_status_caso e adicionar_observacao pra registrar o resultado "
        "de um teste. Pra técnicos: criar_tecnico cadastra, "
        "gerar_mensagem_tecnico monta o convite (texto + link do WhatsApp), "
        "atualizar_status_tecnico acompanha o funil de QA e "
        "adicionar_observacao_tecnico registra o feedback do teste."
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
                # marcação de cor: "verde", "vermelho" ou None (sem cor)
                "cor": o.cor,
                "data": o.created_at.isoformat() if o.created_at else None,
                "atualizada_por": o.editado_por,
                "atualizada_em": o.editado_em.isoformat() if o.editado_em else None,
                # trilha: o que a observação dizia antes de cada atualização
                "versoes_anteriores": [
                    {
                        "texto": r.texto,
                        "cor": r.cor,
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
def adicionar_observacao(
    code: str, texto: str, autor: Optional[str] = None, cor: Optional[str] = None
) -> dict:
    """Adiciona uma observação ao histórico de um caso de teste (não apaga as anteriores).

    `cor` marca a observação na tela: "verde" (deu certo, resolvido) ou
    "vermelho" (problema, pendência). Sem cor é a observação normal.
    """
    texto = (texto or "").strip()
    if not texto:
        return {"erro": "Observação vazia."}
    try:
        cor = normaliza_cor(cor)
    except HTTPException as err:
        return {"erro": err.detail}
    db = SessionLocal()
    try:
        case = (
            db.query(models.TestCase)
            .filter(models.TestCase.code == code, models.TestCase.active.is_(True))
            .first()
        )
        if not case:
            return {"erro": f"Caso {code} não encontrado"}
        db.add(models.Observation(test_case_id=case.id, autor=autor, texto=texto, cor=cor))
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
def atualizar_observacao(
    observacao_id: int, texto: str, autor: Optional[str] = None, cor: Optional[str] = None
) -> dict:
    """Atualiza o texto de uma observação já existente de um caso de teste.

    O texto anterior não é perdido: vira uma versão na trilha da observação
    (`versoes_anteriores`), então dá pra acompanhar como o ponto evoluiu.
    O `observacao_id` vem do campo `id` das observações em listar_casos/ver_caso.
    `cor` ("verde"/"vermelho"/"neutro") muda a marcação; omitida, a cor atual fica
    como está.
    """
    texto = (texto or "").strip()
    if not texto:
        return {"erro": "Observação vazia."}
    try:
        cor_pedida = normaliza_cor(cor) if cor is not None else None
    except HTTPException as err:
        return {"erro": err.detail}
    db = SessionLocal()
    try:
        obs = db.query(models.Observation).filter(models.Observation.id == observacao_id).first()
        if not obs:
            return {"erro": f"Observação {observacao_id} não encontrada"}
        case = db.query(models.TestCase).filter(models.TestCase.id == obs.test_case_id).first()
        if not case:
            return {"erro": "Caso da observação não encontrado"}
        # cor omitida = mantém a que já está lá; os dois "mudou" são calculados
        # antes de mexer no objeto, senão a comparação vira sempre falsa depois.
        cor_nova = cor_pedida if cor is not None else obs.cor
        mudou_texto = texto != obs.texto
        mudou_cor = cor_nova != obs.cor
        if not mudou_texto and not mudou_cor:
            return _case_to_dict(case)
        if mudou_texto:
            db.add(models.ObservationRevision(
                observation_id=obs.id, texto=obs.texto, cor=obs.cor,
                autor=obs.autor, editado_por=autor,
            ))
            obs.texto = texto
            obs.editado_por = autor
            obs.editado_em = func.now()
            log_activity(
                db, case.fluxo, "obs",
                f'Observação atualizada em {case.code}: "{snippet(texto)}"',
                autor=autor, case_code=case.code,
            )
        else:
            log_activity(
                db, case.fluxo, "obs",
                f'Observação de {case.code} marcada como {cor_nova or "sem cor"}: "{snippet(texto)}"',
                autor=autor, case_code=case.code,
            )
        obs.cor = cor_nova
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


def _tecnico_to_dict(tecnico: models.Tecnico) -> dict:
    return {
        "id": tecnico.id,
        "nome": tecnico.nome,
        "telefone": tecnico.telefone,
        "papel": tecnico.papel,
        "regional": tecnico.regional,
        "lider_nome": tecnico.lider_nome,
        "status": tecnico.status,
        "autor": tecnico.autor,
        "nota": tecnico.nota,
        "etapas_testadas": (tecnico.etapas_testadas or "").split("|") if tecnico.etapas_testadas else [],
        "respondido_em": tecnico.respondido_em.isoformat() if tecnico.respondido_em else None,
        "convidado_em": tecnico.convidado_em.isoformat() if tecnico.convidado_em else None,
        "instalado_em": tecnico.instalado_em.isoformat() if tecnico.instalado_em else None,
        "concluido_em": tecnico.concluido_em.isoformat() if tecnico.concluido_em else None,
        "observacoes": [
            {
                "id": o.id,
                "autor": o.autor,
                "texto": o.texto,
                "tipo": o.tipo,
                "data": o.created_at.isoformat() if o.created_at else None,
            }
            for o in tecnico.observacoes
        ],
    }


@mcp.tool()
def listar_tecnicos(status: Optional[str] = None, papel: Optional[str] = None) -> list[dict]:
    """Lista os técnicos (e líderes) cadastrados pra testar o Track One, com o
    funil de QA de cada um. status opcional: a_contatar, convidado, instalado,
    em_teste, concluido, sem_retorno. papel opcional: "tecnico" ou "lider"."""
    db = SessionLocal()
    try:
        query = db.query(models.Tecnico).options(joinedload(models.Tecnico.observacoes))
        if status:
            query = query.filter(models.Tecnico.status == status)
        if papel:
            query = query.filter(models.Tecnico.papel == papel)
        tecnicos = query.order_by(models.Tecnico.nome).all()
        return [_tecnico_to_dict(t) for t in tecnicos]
    finally:
        db.close()


@mcp.tool()
def criar_tecnico(
    nome: str,
    telefone: str,
    papel: str = "tecnico",
    regional: Optional[str] = None,
    lider_nome: Optional[str] = None,
    autor: Optional[str] = None,
) -> dict:
    """Cadastra um técnico (ou líder de equipe) na base de QA do Track One.
    telefone com DDD (e DDI, se não for Brasil) — números brasileiros de 10/11
    dígitos ganham o 55 na frente automaticamente. papel: "tecnico" (convite
    direto) ou "lider" (avisa o líder antes de chamar o time dele)."""
    nome = (nome or "").strip()
    if not nome:
        return {"erro": "Nome vazio."}
    papel = (papel or "tecnico").strip()
    if papel not in TECNICO_PAPEIS:
        return {"erro": 'Papel inválido — use "tecnico" ou "lider".'}
    db = SessionLocal()
    try:
        try:
            tel_norm = norm_telefone_tecnico(telefone)
        except HTTPException as err:
            return {"erro": err.detail}
        tecnico = models.Tecnico(
            nome=nome, telefone=tel_norm, papel=papel,
            regional=(regional or "").strip() or None,
            lider_nome=(lider_nome or "").strip() or None,
            autor=autor, status="a_contatar",
        )
        db.add(tecnico)
        db.commit()
        db.refresh(tecnico)
        return _tecnico_to_dict(tecnico)
    finally:
        db.close()


@mcp.tool()
def gerar_mensagem_tecnico(tecnico_id: int, tipo: str = "convite") -> dict:
    """Monta a mensagem do Track One pronta pra esse técnico, com o link do
    WhatsApp já preenchido. tipo="convite" (padrão) chama pra instalação
    conforme o papel dele; tipo="feedback" pede o retorno depois do atendimento
    e leva o link do formulário. O link do WhatsApp só leva o texto — o APK e o
    manual são enviados à parte na conversa."""
    from urllib.parse import quote

    db = SessionLocal()
    try:
        tecnico = db.query(models.Tecnico).filter(models.Tecnico.id == tecnico_id).first()
        if not tecnico:
            return {"erro": f"Técnico {tecnico_id} não encontrado"}
        mensagem = mensagem_para_tecnico(tecnico, tipo=tipo, base_url=PUBLIC_BASE_URL)
        return {
            "tecnico_id": tecnico.id,
            "telefone": tecnico.telefone,
            "mensagem": mensagem,
            "wa_link": f"https://wa.me/{tecnico.telefone}?text={quote(mensagem)}",
            "link_formulario": f"{PUBLIC_BASE_URL}/formulario/{tecnico.token}" if tecnico.token else None,
        }
    finally:
        db.close()


@mcp.tool()
def atualizar_status_tecnico(tecnico_id: int, status: str) -> dict:
    """Atualiza o status de QA de um técnico. Status válidos: a_contatar,
    convidado, instalado, em_teste, concluido, sem_retorno. A primeira vez que
    o status vira convidado/instalado/concluido, a data fica registrada."""
    if status not in TECNICO_STATUSES:
        return {"erro": f"Status inválido: {status}. Use um de {TECNICO_STATUSES}"}
    db = SessionLocal()
    try:
        tecnico = db.query(models.Tecnico).filter(models.Tecnico.id == tecnico_id).first()
        if not tecnico:
            return {"erro": f"Técnico {tecnico_id} não encontrado"}
        tecnico.status = status
        agora = func.now()
        if status == "convidado" and tecnico.convidado_em is None:
            tecnico.convidado_em = agora
        elif status == "instalado" and tecnico.instalado_em is None:
            tecnico.instalado_em = agora
        elif status == "concluido" and tecnico.concluido_em is None:
            tecnico.concluido_em = agora
        db.commit()
        db.refresh(tecnico)
        return _tecnico_to_dict(tecnico)
    finally:
        db.close()


@mcp.tool()
def adicionar_observacao_tecnico(
    tecnico_id: int, texto: str, autor: Optional[str] = None, tipo: Optional[str] = None
) -> dict:
    """Registra uma nota de QA sobre o teste de um técnico com o Track One.
    tipo opcional: "positivo" (o que ele achou bom), "melhoria" (sugestão) ou
    "problema" (bug/erro). Sem tipo é uma nota geral do que ele relatou."""
    texto = (texto or "").strip()
    if not texto:
        return {"erro": "Observação vazia."}
    tipo = (tipo or "").strip() or None
    if tipo is not None and tipo not in TECNICO_TIPOS_OBS:
        return {"erro": 'Tipo inválido — use "positivo", "melhoria" ou "problema".'}
    db = SessionLocal()
    try:
        tecnico = db.query(models.Tecnico).filter(models.Tecnico.id == tecnico_id).first()
        if not tecnico:
            return {"erro": f"Técnico {tecnico_id} não encontrado"}
        db.add(models.TecnicoObservacao(tecnico_id=tecnico.id, autor=autor, texto=texto, tipo=tipo))
        db.commit()
        db.refresh(tecnico)
        return _tecnico_to_dict(tecnico)
    finally:
        db.close()
