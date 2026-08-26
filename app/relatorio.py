"""Monta a pauta da reunião semanal em um HTML único.

Recebe os dados já serializados (os mesmos dicts que a API devolve em
`/api/cases`, `/api/notas`, `/api/ativos/ajustes`, `/api/situacoes` e
`/api/summary`) e devolve a página inteira — CSS e logo embutidos, sem
nenhuma dependência externa, pra abrir num navegador e apresentar.

Usado em dois lugares: pela rota `/relatorio` (dados vivos do banco) e pelo
script `tools/relatorio_reuniao.py` (a partir da API ou de JSONs salvos).
"""

from __future__ import annotations

import html
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Status de caso de teste que contam como resolvido — o resto entra na pauta.
STATUS_OK = {"Aprovado", "N/A"}
STATUS_PROBLEMA = {"Reprovado", "Bloqueado"}

# Ajuste da Gestão de Ativos: só sai da pauta quando validado (ou descartado).
AJUSTE_FECHADO = {"validado", "descartado"}
AJUSTE_LABEL = {
    "levantado": "Levantado",
    "analise": "Em análise",
    "desenvolvimento": "Em desenvolvimento",
    "entregue": "Entregue (aguardando validação)",
    "validado": "Validado",
    "descartado": "Descartado",
}
AJUSTE_BADGE = {
    "levantado": "b-neutral",
    "analise": "b-info",
    "desenvolvimento": "b-info",
    "entregue": "b-warn",
}
PRIORIDADE_ORDEM = {"Alta": 0, "Média": 1, "Media": 1, "Baixa": 2}
PRIORIDADE_BADGE = {"Alta": "b-alert", "Média": "b-warn", "Media": "b-warn", "Baixa": "b-neutral"}
STATUS_BADGE = {"Reprovado": "b-alert", "Bloqueado": "b-warn", "Não testado": "b-neutral"}

# Cores da barra de status. Verde/vermelho/roxo passam no separador de daltonismo
# (o magenta da marca ficava perto demais do vermelho pra distinguir); os dois
# últimos são neutros de propósito — "sem resultado ainda" não é uma cor de dado.
# Cada faixa vem com rótulo e contagem na legenda, nunca só a cor.
STATUS_ORDEM = ["Aprovado", "Reprovado", "Bloqueado", "N/A", "Não testado"]
STATUS_COR = {
    "Aprovado": "#04795c",
    "Reprovado": "#c02234",
    "Bloqueado": "#960a9c",
    "N/A": "#9aa2b8",
    "Não testado": "#d5dae9",
}
STATUS_COR_TEXTO = {"N/A": "#ffffff", "Não testado": "#3f4661"}

BRT = timezone(timedelta(hours=-3))
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


# --------------------------------------------------------------------------- helpers


def e(valor) -> str:
    """Escapa pro HTML, tratando None como vazio."""
    return html.escape(str(valor or "").strip())


def nl2br(valor) -> str:
    return e(valor).replace("\n", "<br>")


def data_br(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return e(iso)
    return dt.strftime("%d/%m/%Y")


def badge(texto: str, classe: str = "b-neutral") -> str:
    return f'<span class="badge {classe}">{e(texto)}</span>'


def ultima_obs(item: dict) -> str:
    obs = item.get("observations") or []
    if obs:
        o = obs[-1]
        autor = f" — {e(o.get('autor'))}" if o.get("autor") else ""
        return f"{e(o.get('texto'))}{autor}"
    return e(item.get("observacao"))


def ordena_prioridade(itens: list, chave="prioridade") -> list:
    return sorted(itens, key=lambda i: (PRIORIDADE_ORDEM.get(i.get(chave), 3), i.get("numero", 0) or 0))


# --------------------------------------------------------------------------- seções


def anel(pct: float, legenda: str, detalhe: str) -> str:
    """Medidor de um número só: o quanto do plano de testes já foi executado.
    O valor vai escrito no centro — o anel dá a leitura de relance, o número dá a
    precisão."""
    raio, traco = 52, 12
    volta = 2 * 3.141592653589793 * raio
    preenchido = volta * max(0.0, min(pct, 100.0)) / 100
    return f"""
      <div class="anel">
        <svg viewBox="0 0 140 140" role="img" aria-label="{e(legenda)}: {pct:.0f}%">
          <circle cx="70" cy="70" r="{raio}" fill="none" stroke="var(--border)" stroke-width="{traco}"/>
          <circle cx="70" cy="70" r="{raio}" fill="none" stroke="url(#g-anel)" stroke-width="{traco}"
                  stroke-linecap="round" stroke-dasharray="{preenchido:.2f} {volta:.2f}"
                  transform="rotate(-90 70 70)"/>
          <defs><linearGradient id="g-anel" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#2226c0"/><stop offset="52%" stop-color="#960a9c"/>
            <stop offset="100%" stop-color="#fd11a4"/></linearGradient></defs>
          <text x="70" y="70" class="anel-n">{pct:.0f}<tspan class="anel-pc">%</tspan></text>
        </svg>
        <div class="anel-legenda">{e(legenda)}</div>
        <div class="anel-detalhe">{e(detalhe)}</div>
      </div>"""


def barra_status(counts: dict, total: int) -> str:
    """Uma barra só com a distribuição dos casos por status — a foto da semana
    inteira antes de entrar em qualquer detalhe."""
    if not total:
        return ""
    faixas, legenda = "", ""
    for status in STATUS_ORDEM:
        n = counts.get(status, 0)
        if not n:
            continue
        pct = n / total * 100
        cor = STATUS_COR[status]
        texto = STATUS_COR_TEXTO.get(status, "#ffffff")
        rotulo = f'<span style="color:{texto}">{n}</span>' if pct >= 6 else ""
        faixas += (f'<div class="faixa" style="flex:{n};background:{cor}" '
                   f'title="{e(status)}: {n} ({pct:.0f}%)">{rotulo}</div>')
        legenda += (f'<span class="leg"><i style="background:{cor}"></i>'
                    f'{e(status)} <b>{n}</b> <span class="muted">({pct:.0f}%)</span></span>')
    return f'<div class="barra">{faixas}</div><div class="legenda">{legenda}</div>'


def barra_mini(feito: int, total: int, cor: str = "var(--f-blue)") -> str:
    """Régua de progresso curta — usada dentro dos cards de situação."""
    pct = (feito / total * 100) if total else 0
    return (f'<div class="mini"><div class="mini-fill" style="width:{pct:.1f}%;background:{cor}"></div></div>')


def barra_linha(n: int, maximo: int, cor: str = "var(--f-blue)") -> str:
    """Barra proporcional dentro de uma linha de tabela — dá a comparação entre
    estágios de relance, que a coluna de número sozinha não dá."""
    pct = (n / maximo * 100) if maximo else 0
    return (f'<div class="linha-barra"><div class="linha-fill" style="width:{max(pct, 3):.1f}%;'
            f'background:{cor}"></div></div>')


def barras_por_area(ajustes: list) -> str:
    """Onde os ajustes se concentram. Bug e melhoria empilhados na mesma barra:
    uma área com cinco melhorias é um assunto diferente de uma com cinco bugs.

    Com poucos itens por área a barra não diz nada que a contagem já não diga —
    aí vira uma linha de chips, que ocupa menos espaço e lê igual."""
    areas: dict = {}
    for a in ajustes:
        area = (a.get("area") or "Sem área").strip() or "Sem área"
        slot = areas.setdefault(area, {"Bug": 0, "Melhoria": 0})
        slot["Bug" if a.get("tipo") == "Bug" else "Melhoria"] += 1
    if len(areas) < 2:
        return ""
    ordenadas = sorted(areas.items(), key=lambda kv: -(kv[1]["Bug"] + kv[1]["Melhoria"]))
    maximo = max(v["Bug"] + v["Melhoria"] for v in areas.values())

    if maximo < 3:
        chips = " ".join(
            f'<span class="pill">{e(area)} · <b>{v["Bug"] + v["Melhoria"]}</b>'
            + (f' <span style="color:#c02234">({v["Bug"]} bug)</span>' if v["Bug"] else "")
            + "</span>"
            for area, v in ordenadas
        )
        return f'<div class="card" style="margin-bottom:16px"><div class="label-sec">Por área do módulo</div>{chips}</div>'

    linhas = ""
    for area, v in ordenadas:
        total = v["Bug"] + v["Melhoria"]
        partes = ""
        for tipo, cor in (("Bug", "#c02234"), ("Melhoria", "#0054ec")):
            if v[tipo]:
                partes += (f'<div class="faixa" style="flex:{v[tipo]};background:{cor}" '
                           f'title="{e(area)} — {tipo}: {v[tipo]}"></div>')
        linhas += f"""
        <div class="area-linha">
          <div class="area-nome">{e(area)}</div>
          <div class="area-track"><div class="area-barra" style="width:{total / maximo * 100:.1f}%">{partes}</div></div>
          <div class="area-n">{total}</div>
        </div>"""
    return f"""
      <div class="card" style="margin-bottom:16px">
        <div class="card-head"><h3>Onde os ajustes se concentram</h3>
          <span class="sub">por área do módulo</span></div>
        {linhas}
        <div class="legenda" style="margin-top:12px">
          <span class="leg"><i style="background:#c02234"></i>Bug</span>
          <span class="leg"><i style="background:#0054ec"></i>Melhoria</span>
        </div>
      </div>"""


def sec(numero: str, titulo: str, sub: str, corpo: str, anchor: str) -> str:
    if not corpo.strip():
        return ""
    return f"""
    <section class="sec" id="{anchor}">
      <div class="sec-head">
        <span class="n">{e(numero)}</span>
        <h2>{e(titulo)}</h2>
        <span class="lead">{e(sub)}</span>
      </div>
      {corpo}
    </section>"""


def vazio(msg: str) -> str:
    return f'<div class="card"><p class="muted">{e(msg)}</p></div>'


def secao_pontos(notas: list) -> str:
    abertos = [n for n in notas if not n.get("resolvido")]
    if not abertos:
        return vazio("Nenhum ponto em aberto — tudo que foi levantado já está resolvido.")
    cobrados = [n for n in abertos if n.get("cobrado")]
    novos = [n for n in abertos if not n.get("cobrado")]

    def bloco(titulo: str, itens: list, classe: str, nota: str) -> str:
        if not itens:
            return ""
        cards = ""
        for n in itens:
            meta = " · ".join(
                filter(None, [e(n.get("estagio")), e(n.get("autor")), data_br(n.get("created_at"))])
            )
            extra = ""
            if n.get("cobrado_em"):
                extra = f'<div class="muted" style="font-size:12.5px;margin-top:8px">Cobrado em {data_br(n["cobrado_em"])}</div>'
            cards += f"""
          <div class="card hover">
            <div class="row" style="margin-bottom:10px">{badge(titulo, classe)}
              <span class="muted" style="font-size:12.5px">{meta}</span></div>
            <div style="color:var(--text-2)">{nl2br(n.get("texto"))}</div>{extra}
          </div>"""
        return f"""
      <div class="callout {'info' if classe == 'b-info' else ''}" style="margin-bottom:14px"><b>{e(titulo)}</b> — {e(nota)}</div>
      <div class="grid g2" style="align-items:start;margin-bottom:26px">{cards}</div>"""

    return (
        bloco("Aguardando retorno", cobrados, "b-info",
              f"{len(cobrados)} ponto(s) já levado(s) para a outra ponta — falta a devolutiva.")
        + bloco("A levantar", novos, "b-warn",
                f"{len(novos)} ponto(s) ainda não cobrado(s) — precisam entrar nesta reunião.")
    )


def secao_casos_problema(casos: list) -> str:
    itens = [c for c in casos if c.get("status") in STATUS_PROBLEMA]
    if not itens:
        return vazio("Nenhum caso reprovado ou bloqueado no momento.")
    itens = sorted(itens, key=lambda c: (c.get("status") != "Reprovado",
                                         PRIORIDADE_ORDEM.get(c.get("prioridade"), 3),
                                         c.get("code", "")))
    linhas = ""
    for c in itens:
        obs = ultima_obs(c)
        problema = e(c.get("problema_encontrado"))
        detalhe = ""
        if problema:
            detalhe += f'<div style="margin-top:6px"><b>Problema:</b> {problema}</div>'
        if obs:
            detalhe += f'<div class="muted" style="margin-top:6px;font-size:13.5px">{obs}</div>'
        prints = len(c.get("screenshots") or [])
        anexo = f' {badge(f"{prints} print(s)", "b-info")}' if prints else ""
        linhas += f"""
        <tr>
          <td><b class="mono">{e(c.get("code"))}</b><br><span class="muted" style="font-size:12.5px">{e(c.get("estagio"))}</span></td>
          <td>{e(c.get("frente"))}<br>{badge(c.get("prioridade") or "—", PRIORIDADE_BADGE.get(c.get("prioridade"), "b-neutral"))}</td>
          <td><b>{e(c.get("resultado_esperado"))}</b>{detalhe}</td>
          <td>{badge(c.get("status"), STATUS_BADGE.get(c.get("status"), "b-neutral"))}{anexo}<br>
              <span class="muted" style="font-size:12.5px">{e(c.get("testado_por"))}</span></td>
        </tr>"""
    return f"""
      <div class="card" style="padding:0;overflow:hidden">
        <table>
          <thead><tr><th style="width:17%">Caso</th><th style="width:15%">Frente</th>
            <th>O que era esperado / o que aconteceu</th><th style="width:16%">Status</th></tr></thead>
          <tbody>{linhas}</tbody>
        </table>
      </div>"""


def secao_situacoes(situacoes: list) -> str:
    """Mostra só o que trava a situação: estágios reprovados/bloqueados primeiro e,
    quando não há nenhum, os próximos da fila — a lista inteira de pendentes vira
    parede de texto e ninguém lê numa reunião."""
    blocos = ""
    for s in situacoes:
        estagios = s.get("estagios") or []
        pendentes = [x for x in estagios if x.get("status") not in STATUS_OK]
        if not pendentes:
            continue
        problemas = [x for x in pendentes if x.get("status") in STATUS_PROBLEMA]
        total = len(estagios)
        ok = total - len(pendentes)
        destaque = problemas or pendentes[:3]
        resto = len(pendentes) - len(destaque)
        rotulo = "trava aqui" if problemas else "próximos da fila"
        linhas = ""
        for x in destaque:
            obs = ultima_obs(x)
            linhas += f"""
            <li class="{'no' if x.get('status') in STATUS_PROBLEMA else ''}">
              <b>{e(x.get("nome"))}</b> {badge(x.get("status"), STATUS_BADGE.get(x.get("status"), "b-neutral"))}
              <div class="muted" style="font-size:13.5px">{e(x.get("resultado_esperado"))}</div>
              {f'<div style="font-size:13.5px;margin-top:4px">{obs}</div>' if obs else ""}
            </li>"""
        rodape = ""
        if resto > 0:
            rodape = f'<div class="muted" style="font-size:13px;margin-top:10px">+ {resto} estágio(s) pendente(s) nesta situação</div>'
        blocos += f"""
        <div class="card hover">
          <div class="card-head"><h3>{e(s.get("code"))} · {e(s.get("titulo"))}</h3>
            <span class="spacer">{badge(f"{ok}/{total} estágios ok", "b-alert" if problemas else "b-neutral")}</span></div>
          {barra_mini(ok, total, "#c02234" if problemas else "var(--f-blue)")}
          <p class="muted" style="font-size:13.5px;margin:12px 0">{e(s.get("descricao"))}</p>
          <div class="label" style="font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);margin-bottom:4px">{e(rotulo)}</div>
          <ul class="list">{linhas}</ul>{rodape}
        </div>"""
    if not blocos:
        return vazio("Todas as situações estão com os estágios aprovados.")
    return f'<div class="grid g2" style="align-items:start">{blocos}</div>'


def secao_ajustes(ajustes: list) -> str:
    abertos = [a for a in ajustes if a.get("status") not in AJUSTE_FECHADO]
    if not abertos:
        return vazio("Nenhum ajuste em aberto na Gestão de Ativos.")
    versoes = {}
    for a in abertos:
        versoes.setdefault(a.get("versao") or "—", []).append(a)
    blocos = ""
    for versao in sorted(versoes, reverse=True):
        itens = ordena_prioridade(versoes[versao])
        bugs = sum(1 for a in itens if a.get("tipo") == "Bug")
        cards = ""
        for a in itens:
            status = a.get("status") or "levantado"
            obs = e(a.get("observacao"))
            prints = len(a.get("prints") or [])
            cards += f"""
          <div class="card hover">
            <div class="row" style="margin-bottom:12px">
              <span class="mono" style="color:var(--f-purple);font-weight:600">#{e(a.get("numero"))}</span>
              {badge(a.get("tipo"), "b-alert" if a.get("tipo") == "Bug" else "b-info")}
              {badge(a.get("prioridade"), PRIORIDADE_BADGE.get(a.get("prioridade"), "b-neutral"))}
              {badge(AJUSTE_LABEL.get(status, status), AJUSTE_BADGE.get(status, "b-neutral"))}
              <span class="spacer muted" style="font-size:12.5px">{e(a.get("area"))}</span>
            </div>
            <h3 style="margin-bottom:10px">{e(a.get("titulo"))}</h3>
            <div style="font-size:14px;color:var(--text-2)">
              <div style="margin-bottom:8px"><b style="color:#c02234">Hoje:</b> {nl2br(a.get("atual"))}</div>
              <div><b style="color:#04795c">Deveria ser:</b> {nl2br(a.get("esperado"))}</div>
              {f'<div class="muted" style="margin-top:8px;font-size:13.5px">{obs}</div>' if obs else ""}
            </div>
            {f'<div style="margin-top:10px">{badge(f"{prints} print(s)", "b-info")}</div>' if prints else ""}
          </div>"""
        blocos += f"""
        <div class="callout" style="margin-bottom:14px"><b>Leva {e(versao)}</b> — {len(itens)} ajuste(s) em aberto, sendo {bugs} bug(s).</div>
        {barras_por_area(itens)}
        <div class="grid g2" style="align-items:start;margin-bottom:26px">{cards}</div>"""
    return blocos


def secao_nao_executados(casos: list) -> str:
    pendentes = [c for c in casos if c.get("status") == "Não testado"]
    if not pendentes:
        return ""
    por_estagio = {}
    for c in pendentes:
        chave = (c.get("estagio_num") if c.get("estagio_num") is not None else 99, c.get("estagio") or "—")
        por_estagio.setdefault(chave, []).append(c)
    maximo = max(len(i) for i in por_estagio.values())
    linhas = ""
    for (_num, estagio), itens in sorted(por_estagio.items()):
        frentes = {}
        for c in itens:
            frentes[c.get("frente")] = frentes.get(c.get("frente"), 0) + 1
        chips = " ".join(f'<span class="pill">{e(f)} · {n}</span>' for f, n in sorted(frentes.items()))
        codigos = " ".join(f'<span class="mono" style="color:var(--muted)">{e(c.get("code"))}</span>' for c in itens)
        linhas += f"""
        <tr>
          <td><b>{e(estagio)}</b><br><span style="font-size:12px">{codigos}</span></td>
          <td style="width:26%">{chips}</td>
          <td style="width:22%">{barra_linha(len(itens), maximo)}</td>
          <td style="width:7%;text-align:right"><b style="font-size:18px">{len(itens)}</b></td>
        </tr>"""
    return f"""
      <div class="card" style="padding:0;overflow:hidden">
        <table>
          <thead><tr><th>Estágio · casos</th><th>Frente</th><th>Volume</th>
            <th style="text-align:right">Qtde</th></tr></thead>
          <tbody>{linhas}</tbody>
        </table>
      </div>"""


# --------------------------------------------------------------------------- página


def kpi(label: str, valor, ico: str, nota: str = "", classe: str = "") -> str:
    tag = f'<span class="badge {classe}">{e(nota)}</span>' if nota else ""
    return f"""
      <div class="kpi">
        <div class="top"><div class="ico">{ico}</div>{tag}</div>
        <div class="label">{e(label)}</div>
        <div class="value">{e(valor)}</div>
      </div>"""


def montar_html(dados: dict, fonte: str) -> str:
    casos = dados.get("cases") or []
    notas = dados.get("notas") or []
    ajustes = dados.get("ativos_ajustes") or []
    situacoes = dados.get("situacoes") or []
    summary = dados.get("summary") or {}

    pontos_abertos = [n for n in notas if not n.get("resolvido")]
    casos_problema = [c for c in casos if c.get("status") in STATUS_PROBLEMA]
    casos_pendentes = [c for c in casos if c.get("status") == "Não testado"]
    ajustes_abertos = [a for a in ajustes if a.get("status") not in AJUSTE_FECHADO]
    situacoes_pendentes = sum(
        1 for s in situacoes
        if any(x.get("status") not in STATUS_OK for x in (s.get("estagios") or []))
    )
    pct = summary.get("pct_executado", 0) or 0
    aprovados = (summary.get("counts") or {}).get("Aprovado", 0)

    css = (ASSETS_DIR / "faiston-light.css").read_text(encoding="utf-8") if (ASSETS_DIR / "faiston-light.css").exists() else ""
    logo = (ASSETS_DIR / "logo-faiston-full.svg").read_text(encoding="utf-8") if (ASSETS_DIR / "logo-faiston-full.svg").exists() else ""
    if logo:
        logo = logo.replace("<svg", '<svg class="logo" style="height:34px;width:auto"', 1)

    agora = datetime.now(BRT)
    total_pauta = len(pontos_abertos) + len(casos_problema) + len(ajustes_abertos)

    kpis = "".join([
        kpi("Pontos em aberto", len(pontos_abertos), "◆",
            f'{sum(1 for n in pontos_abertos if n.get("cobrado"))} já cobrados', "b-info" if pontos_abertos else ""),
        kpi("Testes com problema", len(casos_problema), "✕",
            f'{sum(1 for c in casos_problema if c.get("status") == "Reprovado")} reprovados',
            "b-alert" if casos_problema else "b-ok"),
        kpi("Ajustes em aberto", len(ajustes_abertos), "▤",
            f'{sum(1 for a in ajustes_abertos if a.get("tipo") == "Bug")} bugs',
            "b-warn" if ajustes_abertos else "b-ok"),
        kpi("Testes por executar", len(casos_pendentes), "○",
            f"{len(casos)} no total", "b-neutral"),
    ])

    nav = "".join(
        f'<a class="tab" href="#{a}">{e(t)}</a>'
        for a, t in [
            ("pontos", f"Pontos ({len(pontos_abertos)})"),
            ("problemas", f"Testes com problema ({len(casos_problema)})"),
            ("situacoes", f"Situações ({situacoes_pendentes})"),
            ("ajustes", f"Ajustes ({len(ajustes_abertos)})"),
            ("pendentes", f"Por executar ({len(casos_pendentes)})"),
        ]
    )

    corpo = "".join([
        sec("01", "Pontos para a reunião", "levantados durante os testes e ainda não resolvidos",
            secao_pontos(notas), "pontos"),
        sec("02", "Testes reprovados e bloqueados", "o que falhou e precisa de decisão do time",
            secao_casos_problema(casos), "problemas"),
        sec("03", "Situações com estágio pendente", "cenários ponta a ponta que ainda não fecham",
            secao_situacoes(situacoes), "situacoes"),
        sec("04", "Ajustes da Gestão de Ativos", "hoje é assim / deveria ser assim — pendentes de validação",
            secao_ajustes(ajustes), "ajustes"),
        sec("05", "Testes ainda não executados", "fila de execução, agrupada por estágio",
            secao_nao_executados(casos), "pendentes"),
    ])

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pauta da reunião semanal · Faiston</title>
<style>
{css}
.navbar{{position:sticky;top:70px;z-index:15;background:var(--bg);padding:14px 0 18px}}
.navbar .tabs{{flex-wrap:wrap}}
.navbar a.tab{{text-decoration:none}}
.navbar a.tab:hover{{background:var(--surface-2);color:var(--text)}}
/* o link do menu precisa parar abaixo da topbar + menu, não atrás deles */
.sec{{scroll-margin-top:158px}}
.hero{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);
  padding:26px 28px;box-shadow:var(--shadow-sm);margin-bottom:24px}}
.hero h2{{margin-bottom:6px}}
.hero-grid{{display:grid;grid-template-columns:180px 1fr;gap:28px;align-items:center}}

/* anel de execução */
.anel{{text-align:center}}
.anel svg{{width:150px;height:150px;display:block;margin:0 auto}}
.anel-n{{font-family:'Roboto Slab',serif;font-size:34px;font-weight:700;fill:var(--text);
  text-anchor:middle;dominant-baseline:central}}
.anel-pc{{font-size:18px;fill:var(--muted)}}
.anel-legenda{{font-size:11.5px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);
  font-weight:500;margin-top:6px}}
.anel-detalhe{{font-size:13px;color:var(--text-2)}}

/* barra de status empilhada — 2px de respiro entre as faixas */
.barra{{display:flex;gap:2px;height:34px;border-radius:var(--r-sm);overflow:hidden}}
.barra .faixa{{display:flex;align-items:center;justify-content:center;min-width:3px;
  font-size:12.5px;font-weight:600}}
.barra .faixa:first-child{{border-radius:6px 0 0 6px}}
.barra .faixa:last-child{{border-radius:0 6px 6px 0}}
.legenda{{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:12px;font-size:13px;color:var(--text-2)}}
.legenda .leg{{display:inline-flex;align-items:center;gap:7px}}
.legenda .leg i{{width:10px;height:10px;border-radius:3px;display:inline-block}}
.legenda .leg b{{color:var(--text);font-weight:600}}

/* réguas de progresso */
.mini{{height:6px;background:var(--surface-2);border-radius:999px;overflow:hidden}}
.mini-fill{{height:100%;border-radius:999px}}
.linha-barra{{height:10px;background:var(--surface-2);border-radius:999px;overflow:hidden}}
.linha-fill{{height:100%;border-radius:999px}}

/* ajustes por área */
.area-linha{{display:flex;align-items:center;gap:12px;margin-bottom:9px}}
.area-nome{{width:120px;flex-shrink:0;font-size:13.5px;color:var(--text-2);text-align:right}}
.area-track{{flex:1;min-width:0}}
.area-barra{{display:flex;gap:2px;height:14px;border-radius:5px;overflow:hidden;min-width:8px}}
.area-barra .faixa{{min-width:4px}}
.area-n{{width:24px;text-align:right;font-size:13.5px;font-weight:600;color:var(--text)}}
.label-sec{{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);
  font-weight:500;margin-bottom:10px}}

@media(max-width:720px){{.hero-grid{{grid-template-columns:1fr}}.area-nome{{width:80px}}}}
@media print{{.navbar{{display:none}}.topbar{{position:static}}}}
</style>
</head>
<body>
<header class="topbar">
  {logo}
  <div class="titles">
    <h1>Pauta da reunião semanal</h1>
    <div class="sub">Console de Teste · tudo que ainda não está aprovado</div>
  </div>
  <div class="spacer"></div>
  <span class="badge b-warn">{total_pauta} itens em pauta</span>
</header>

<main class="wrap">
  <div class="accent"></div>

  <div class="hero">
    <div class="hero-grid">
      {anel(pct, "executado", f"{len(casos) - len(casos_pendentes)} de {len(casos)} casos")}
      <div>
        <h2>O que precisa de decisão nesta reunião</h2>
        <p class="lead" style="margin-bottom:18px">{len(pontos_abertos)} ponto(s) em aberto ·
          {len(casos_problema)} teste(s) reprovado(s) ou bloqueado(s) ·
          {len(ajustes_abertos)} ajuste(s) da Gestão de Ativos pendente(s).</p>
        {barra_status(summary.get("counts") or {{}}, len(casos))}
      </div>
    </div>
  </div>

  <div class="grid g4" style="margin-bottom:8px">{kpis}</div>

  <div class="navbar"><div class="tabs">{nav}</div></div>

  {corpo}
</main>

<footer>
  Faiston · gerado em {agora.strftime("%d/%m/%Y às %H:%M")} (BRT) · fonte: {e(fonte)}
</footer>
</body>
</html>
"""
