"""Catálogo de módulos do backlog de ajustes (Gestão de Ativos e afins).

O backlog "como está hoje / como deve ser" é um só (modelo `AtivoAjuste`); cada
item pertence a um módulo (`modulo`). A ordem desta lista é a ordem das abas na
tela, e a tela inteira (abas, painéis, cabeçalho) é gerada a partir dela via
`GET /api/ativos/modulos`.

Pra acrescentar um módulo novo basta uma entrada em `MODULOS` — sem tela nova,
sem migração, sem tocar no JS.

Campos opcionais:
- `processo: True` — o processo ainda não está desenhado: a aba ganha, acima da lista
  de pendências, o editor de diagramas (os mesmos dos fluxos do Dispatcher, guardados
  com `fluxo` = a `key` do módulo).
- `dispatcher_fluxo` — o módulo não tem aba própria na barra: ele mora dentro do
  Dispatcher, na visão "Pendências" da aba de fluxo indicada ("A", "projetos"...).

`ALIASES` guarda as chaves de módulos que já existiram e foram incorporados a outro:
quem ainda manda a chave antiga (conector, script) cai no módulo novo.
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
        "label": "Geral",
        "titulo": "Geral — pendências",
        "descricao": "Pendências da LPD que valem pra ferramenta toda: SLA, perfis e permissões "
                     "do Dispatcher, Dashboard, relatórios com exportação e publicação do app "
                     "nas lojas.",
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
                     "O processo ainda não está desenhado: o desenho fica na visão Fluxos "
                     "e as dúvidas e decisões em aberto aqui, nas pendências.",
        "versao_padrao": "v1",
        "dispatcher_fluxo": "projetos",
    },
    {
        "key": "fluxo-a",
        "label": "Fluxo A — Finalização",
        "titulo": "Fluxo A — finalização",
        "descricao": "O que falta pra fechar o Fluxo A: ajustes estéticos e de funcionamento.",
        "versao_padrao": "v1",
        "dispatcher_fluxo": "A",
    },
]

for _m in MODULOS:
    _m.setdefault("processo", False)
    _m.setdefault("dispatcher_fluxo", None)

_POR_KEY = {m["key"]: m for m in MODULOS}

# módulos que deixaram de existir por terem sido incorporados a outro
ALIASES = {"dashboard": "plataforma"}


def norm_modulo(valor: Optional[str]) -> str:
    """Devolve a chave de um módulo do catálogo. Nunca levanta: vazio, None ou
    valor desconhecido caem em `ativos` (o módulo original do backlog). Chave de um
    módulo incorporado a outro (`ALIASES`) vai pro módulo que o absorveu."""
    try:
        chave = str(valor or "").strip().lower()
    except Exception:  # noqa: BLE001 — qualquer lixo vira o padrão
        return MODULO_PADRAO
    chave = ALIASES.get(chave, chave)
    return chave if chave in _POR_KEY else MODULO_PADRAO


def versao_padrao(modulo: Optional[str]) -> str:
    return _POR_KEY[norm_modulo(modulo)]["versao_padrao"]


def label(modulo: Optional[str]) -> str:
    return _POR_KEY[norm_modulo(modulo)]["label"]


def e_modulo(chave: Optional[str]) -> bool:
    """A chave é de um módulo do catálogo (e não, por exemplo, um fluxo A/B/C)?"""
    return isinstance(chave, str) and chave.strip().lower() in _POR_KEY


def desenha_processo(chave: Optional[str]) -> bool:
    """O módulo é daqueles cujo processo ainda se desenha na própria aba?"""
    return bool(isinstance(chave, str) and _POR_KEY.get(chave.strip().lower(), {}).get("processo"))
