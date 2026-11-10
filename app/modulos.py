"""Catálogo de módulos do backlog de ajustes (Gestão de Ativos e afins).

O backlog "como está hoje / como deve ser" é um só (modelo `AtivoAjuste`); cada
item pertence a um módulo (`modulo`). A ordem desta lista é a ordem das abas na
tela, e a tela inteira (abas, painéis, cabeçalho) é gerada a partir dela via
`GET /api/ativos/modulos`.

Pra acrescentar um módulo novo basta uma entrada em `MODULOS` — sem tela nova,
sem migração, sem tocar no JS.

`processo: True` marca o módulo cujo processo ainda não está desenhado: a aba ganha,
acima da lista de pendências, o editor de diagramas (os mesmos dos fluxos do
Dispatcher, guardados com `fluxo` = a `key` do módulo).
"""
from typing import Optional

MODULO_PADRAO = "ativos"

MODULOS = [
    {
        "key": "ativos",
        "label": "Gestão de Ativos",
        "titulo": "Gestão de Ativos — ajustes",
        "descricao": "Backlog de bugs e melhorias do módulo Gestão de Ativos do Faiston One, "
                     "por versão da leva.",
        "versao_padrao": "v2",
    },
    {
        "key": "plataforma",
        "label": "Plataforma",
        "titulo": "Plataforma — pendências",
        "descricao": "Pendências da LPD que valem pra ferramenta toda: SLA, perfis e permissões "
                     "do Dispatcher e publicação do app nas lojas.",
        "versao_padrao": "v1",
    },
    {
        "key": "financeiro",
        "label": "Financeiro",
        "titulo": "Módulo Financeiro — pendências",
        "descricao": "Acompanhamento da entrega do Módulo Financeiro do Dispatcher pela LPD. "
                     "O processo ainda não está desenhado: o desenho fica no editor de diagramas "
                     "e as dúvidas e decisões em aberto na lista de pendências.",
        "versao_padrao": "v1",
        "processo": True,
    },
    {
        "key": "projetos",
        "label": "Projetos",
        "titulo": "Fluxo de Projetos — pendências",
        "descricao": "Acompanhamento da entrega do Fluxo de Projetos do Dispatcher pela LPD. "
                     "O processo ainda não está desenhado: o desenho fica no editor de diagramas "
                     "e as dúvidas e decisões em aberto na lista de pendências.",
        "versao_padrao": "v1",
        "processo": True,
    },
    {
        "key": "dashboard",
        "label": "Dashboard e Relatórios",
        "titulo": "Dashboard e Relatórios — pendências",
        "descricao": "Finalização do Dashboard e dos relatórios com exportação do Dispatcher.",
        "versao_padrao": "v1",
    },
    {
        "key": "fluxo-a",
        "label": "Fluxo A — Finalização",
        "titulo": "Fluxo A — finalização",
        "descricao": "O que falta pra fechar o Fluxo A: ajustes estéticos e de funcionamento.",
        "versao_padrao": "v1",
    },
]

for _m in MODULOS:
    _m.setdefault("processo", False)

_POR_KEY = {m["key"]: m for m in MODULOS}


def norm_modulo(valor: Optional[str]) -> str:
    """Devolve a chave de um módulo do catálogo. Nunca levanta: vazio, None ou
    valor desconhecido caem em `ativos` (o módulo original do backlog)."""
    try:
        chave = str(valor or "").strip().lower()
    except Exception:  # noqa: BLE001 — qualquer lixo vira o padrão
        return MODULO_PADRAO
    return chave if chave in _POR_KEY else MODULO_PADRAO


def versao_padrao(modulo: Optional[str]) -> str:
    return _POR_KEY[norm_modulo(modulo)]["versao_padrao"]


def label(modulo: Optional[str]) -> str:
    return _POR_KEY[norm_modulo(modulo)]["label"]


def e_modulo(chave: Optional[str]) -> bool:
    """A chave é de um módulo do catálogo (e não, por exemplo, um fluxo A/B/C)?"""
    return isinstance(chave, str) and chave.strip().lower() in _POR_KEY
