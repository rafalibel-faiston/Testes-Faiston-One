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
    """Só a última observação — pra onde cabe uma linha (cards de situação)."""
    obs = item.get("observations") or []
    if obs:
        o = obs[-1]
        autor = f" — {e(o.get('autor'))}" if o.get("autor") else ""
        return f"{e(o.get('texto'))}{autor}"
    return e(item.get("observacao"))


def todas_obs(item: dict) -> list:
    """Todas as observações do item, em ordem. Num estágio reprovado cada
    observação costuma ser um ajuste diferente sendo pedido — mostrar só a
    última perdia o resto da conversa."""
    linhas = []
    for o in (item.get("observations") or []):
        # observação atualizada mostra a data da atualização junto: na reunião o
        # que importa é quando o ponto mudou de figura, não quando nasceu.
        atualizada = f"atualizada {data_br(o.get('editado_em'))}" if o.get("editado_em") else ""
        assinatura = " · ".join(filter(None, [
            e(o.get("autor")), data_br(o.get("created_at")), atualizada,
        ]))
        # a cor com que a observação foi marcada na tela (verde/vermelho) vem
        # junto: na reunião ela já diz de cara o que ficou resolvido e o que não.
        cor = o.get("cor") if o.get("cor") in ("verde", "vermelho") else ""
        linhas.append((nl2br(o.get("texto")), assinatura, cor))
    solta = (item.get("observacao") or "").strip()
    if not linhas and solta:
        linhas.append((nl2br(solta), "", ""))
    return linhas


def ordena_prioridade(itens: list, chave="prioridade") -> list:
    return sorted(itens, key=lambda i: (PRIORIDADE_ORDEM.get(i.get(chave), 3), i.get("numero", 0) or 0))


# --------------------------------------------------------------------------- seções


def bloco_retorno(tipo: str, item_id, retorno: str, prazo: str, editavel: bool) -> str:
    """O que a outra ponta respondeu sobre este item, e pra quando prometeram.

    Servido pelo app (`/relatorio`), vira formulário: dá pra anotar durante a
    própria reunião, sem trocar de tela. Num arquivo .html gerado pelo script
    não há pra onde salvar, então aparece só como leitura."""
    prazo = (prazo or "").strip()
    retorno = (retorno or "").strip()

    if not editavel:
        if not retorno and not prazo:
            return ""
        partes = ""
        if prazo:
            partes += f'<div><b>Prazo:</b> {data_br(prazo)}</div>'
        if retorno:
            partes += f"<div>{nl2br(retorno)}</div>"
        return (f'<div class="retorno retorno-ro">'
                f'<div class="label-sec">Retorno do time</div>{partes}</div>')

    return f"""
      <div class="retorno" data-tipo="{e(tipo)}" data-id="{e(item_id)}">
        <div class="label-sec">Retorno do time</div>
        <div class="retorno-linha">
          <label class="retorno-prazo-wrap">Prazo
            <input type="date" class="retorno-prazo" value="{e(prazo)}">
          </label>
          <textarea class="retorno-texto" rows="2"
            placeholder="O que ficou combinado na reunião…">{e(retorno)}</textarea>
          <button type="button" class="retorno-salvar">Salvar</button>
        </div>
        <div class="retorno-aviso" aria-live="polite"></div>
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


def secao_pontos(notas: list, editavel: bool = False) -> str:
    """Os pontos em aberto, separados entre os que já foram cobrados da outra
    ponta (falta a devolutiva) e os que ainda nem foram levantados."""
    abertos = [n for n in notas if not n.get("resolvido")]
    if not abertos:
        return vazio("Nenhum ponto em aberto — tudo que foi levantado já está resolvido.")
    cobrados = [n for n in abertos if n.get("cobrado")]
    novos = [n for n in abertos if not n.get("cobrado")]

    def bloco(titulo: str, itens: list, classe: str, nota: str) -> str:
        if not itens:
            return ""
        linhas = ""
        for n in itens:
            meta = " · ".join(filter(None, [e(n.get("autor")), data_br(n.get("created_at"))]))
            if n.get("cobrado_em"):
                meta += f' · cobrado em {data_br(n["cobrado_em"])}'
            linhas += f"""
            <li>
              <div class="item-head">
                <span class="num">{e(n.get("estagio") or "—")}</span>
                <span class="titulo" style="font-family:'Roboto',sans-serif;font-weight:400;font-size:15px">{nl2br(n.get("texto"))}</span>
                {badge(titulo, classe)}
              </div>
              <div class="item-corpo">
                <div class="item-meta">{meta}</div>
                {bloco_retorno("nota", n.get("id"), n.get("retorno"), n.get("prazo"), editavel)}
              </div>
            </li>"""
        return f"""
      <div class="callout {'info' if classe == 'b-info' else ''}" style="margin-bottom:14px"><b>{e(titulo)}</b> — {e(nota)}</div>
      <div class="card" style="margin-bottom:26px"><ul class="itens">{linhas}</ul></div>"""

    return (
        bloco("Aguardando retorno", cobrados, "b-info",
              f"{len(cobrados)} ponto(s) já levado(s) para a outra ponta — falta a devolutiva.")
        + bloco("A levantar", novos, "b-warn",
                f"{len(novos)} ponto(s) ainda não cobrado(s) — precisam entrar nesta reunião.")
    )


def secao_reprovados(casos: list, situacoes: list, multi_fluxo: bool = False) -> str:
    """Tudo que está reprovado ou bloqueado numa lista só — caso de teste solto e
    estágio de situação lado a lado. Estavam em seções separadas, mas na reunião
    é a mesma conversa: o que falhou e o que vai ser feito.

    Cada observação vira uma linha própria: num estágio reprovado elas costumam
    ser ajustes diferentes sendo pedidos, não variações do mesmo comentário."""
    itens = []
    for c in casos:
        if c.get("status") in STATUS_PROBLEMA:
            itens.append({
                "chave": c.get("code"),
                "fluxo": c.get("fluxo"),
                "contexto": c.get("estagio"),
                "titulo": c.get("resultado_esperado"),
                "status": c.get("status"),
                "prioridade": c.get("prioridade"),
                "frente": c.get("frente"),
                "problema": c.get("problema_encontrado"),
                "obs": todas_obs(c),
                "prints": len(c.get("screenshots") or []),
                "quem": c.get("testado_por"),
                "chamado": c.get("chamado"),
                "origem": None,
            })
    for sit in situacoes:
        for x in (sit.get("estagios") or []):
            if x.get("status") in STATUS_PROBLEMA:
                itens.append({
                    "chave": sit.get("code"),
                    "fluxo": sit.get("fluxo"),
                    "contexto": x.get("nome"),
                    "titulo": x.get("resultado_esperado"),
                    "status": x.get("status"),
                    "prioridade": None,
                    "frente": x.get("frente"),
                    "problema": None,
                    "obs": todas_obs(x),
                    "prints": len(x.get("screenshots") or []),
                    "quem": x.get("testado_por"),
                    "chamado": sit.get("chamado"),
                    "origem": sit.get("titulo"),
                })
    if not itens:
        return vazio("Nada reprovado nem bloqueado no momento.")

    itens.sort(key=lambda i: (i["status"] != "Reprovado",
                              PRIORIDADE_ORDEM.get(i["prioridade"], 3),
                              i["fluxo"] or "", i["chave"] or ""))
    linhas = ""
    for i in itens:
        etiquetas = badge(i["status"], STATUS_BADGE.get(i["status"], "b-neutral"))
        if multi_fluxo and i["fluxo"]:
            etiquetas += " " + badge(f'Fluxo {i["fluxo"]}', "b-neutral")
        if i["prioridade"]:
            etiquetas += " " + badge(i["prioridade"], PRIORIDADE_BADGE.get(i["prioridade"], "b-neutral"))
        if i["frente"]:
            etiquetas += f' <span class="item-meta">{e(i["frente"])}</span>'
        if i["prints"]:
            etiquetas += " " + badge(f'{i["prints"]} print(s)', "b-info")

        corpo = ""
        if i["origem"]:
            corpo += f'<div class="item-meta">Situação: {e(i["origem"])}</div>'
        if i["problema"]:
            corpo += f'<div><b>Problema:</b> {nl2br(i["problema"])}</div>'
        if i["obs"]:
            anotacoes = ""
            for texto, assinatura, cor in i["obs"]:
                credito = f'<span class="item-meta"> \u2014 {assinatura}</span>' if assinatura else ""
                classe = f' class="obs-{cor}"' if cor else ""
                anotacoes += f"<li{classe}>{texto}{credito}</li>"
            corpo += ('<div class="label-sec" style="margin:12px 0 4px">O que foi anotado</div>'
                      f'<ul class="anotacoes">{anotacoes}</ul>')
        rodape = " · ".join(filter(None, [
            f'Testado por {e(i["quem"])}' if i["quem"] else "",
            f'Chamado {e(i["chamado"])}' if i["chamado"] else "",
        ]))
        if rodape:
            corpo += f'<div class="item-meta" style="margin-top:8px">{rodape}</div>'

        linhas += f"""
        <li>
          <div class="item-head">
            <span class="num mono">{e(i["chave"])}</span>
            <span class="titulo">{e(i["titulo"])}</span>
            {etiquetas}
          </div>
          <div class="item-corpo">
            <div class="item-meta">{e(i["contexto"])}</div>
            {corpo}
          </div>
        </li>"""
    return f'<div class="card"><ul class="itens">{linhas}</ul></div>'


def secao_situacoes(situacoes: list, multi_fluxo: bool = False) -> str:
    """Onde cada cenário ponta a ponta está parado. Os estágios reprovados já
    aparecem na lista acima; aqui fica o que vem a seguir, no máximo três por
    situação — a lista inteira de pendentes vira parede de texto."""
    blocos = ""
    for s in situacoes:
        estagios = s.get("estagios") or []
        pendentes = [x for x in estagios if x.get("status") not in STATUS_OK]
        if not pendentes:
            continue
        problemas = [x for x in pendentes if x.get("status") in STATUS_PROBLEMA]
        fila = [x for x in pendentes if x.get("status") not in STATUS_PROBLEMA]
        total = len(estagios)
        ok = total - len(pendentes)
        destaque = fila[:3]
        resto = len(fila) - len(destaque)
        linhas = ""
        for x in destaque:
            obs = ultima_obs(x)
            linhas += f"""
            <li>
              <b>{e(x.get("nome"))}</b> {badge(x.get("status"), STATUS_BADGE.get(x.get("status"), "b-neutral"))}
              <div class="muted" style="font-size:13.5px">{e(x.get("resultado_esperado"))}</div>
              {f'<div style="font-size:13.5px;margin-top:4px">{obs}</div>' if obs else ""}
            </li>"""
        rodape = ""
        if problemas:
            rodape += (f'<div style="font-size:13px;margin-top:10px;color:#c02234">'
                       f'{len(problemas)} estágio(s) reprovado(s) ou bloqueado(s) — na lista acima</div>')
        if resto > 0:
            rodape += f'<div class="muted" style="font-size:13px;margin-top:6px">+ {resto} estágio(s) na fila</div>'
        blocos += f"""
        <div class="card hover">
          <div class="card-head"><h3>{e(s.get("code"))} · {e(s.get("titulo"))}</h3>
            <span class="spacer">{badge(f'Fluxo {s.get("fluxo")}', "b-neutral") + " " if multi_fluxo and s.get("fluxo") else ""}{badge(f"{ok}/{total} estágios ok", "b-alert" if problemas else "b-neutral")}</span></div>
          <p class="muted" style="font-size:13.5px;margin:10px 0">{e(s.get("descricao"))}</p>
          {'<div class="label-sec">Próximos da fila</div>' if linhas else ""}
          <ul class="list">{linhas}</ul>{rodape}
        </div>"""
    if not blocos:
        return vazio("Todas as situações estão com os estágios aprovados.")
    return f'<div class="grid g2" style="align-items:start">{blocos}</div>'


def secao_ajustes(ajustes: list, editavel: bool = False) -> str:
    """Os ajustes pendentes em lista, na ordem em que o time ataca (prioridade e
    depois o número do item) — é por esse número que eles se referem ao ajuste na
    reunião."""
    abertos = [a for a in ajustes if a.get("status") not in AJUSTE_FECHADO]
    if not abertos:
        return vazio("Nenhum ajuste em aberto na Gestão de Ativos.")
    versoes: dict = {}
    for a in abertos:
        versoes.setdefault(a.get("versao") or "—", []).append(a)

    blocos = ""
    for versao in sorted(versoes, reverse=True):
        itens = ordena_prioridade(versoes[versao])
        bugs = sum(1 for a in itens if a.get("tipo") == "Bug")
        linhas = ""
        for a in itens:
            status = a.get("status") or "levantado"
            etiquetas = badge(a.get("tipo"), "b-alert" if a.get("tipo") == "Bug" else "b-info")
            etiquetas += " " + badge(a.get("prioridade"), PRIORIDADE_BADGE.get(a.get("prioridade"), "b-neutral"))
            etiquetas += " " + badge(AJUSTE_LABEL.get(status, status), AJUSTE_BADGE.get(status, "b-neutral"))
            if a.get("area"):
                etiquetas += f' <span class="item-meta">{e(a.get("area"))}</span>'
            if a.get("prints"):
                etiquetas += " " + badge(f'{len(a["prints"])} print(s)', "b-info")
            obs = e(a.get("observacao"))
            linhas += f"""
            <li>
              <div class="item-head">
                <span class="num">#{e(a.get("numero"))}</span>
                <span class="titulo">{e(a.get("titulo"))}</span>
                {etiquetas}
              </div>
              <div class="item-corpo">
                <div class="hoje"><b>Hoje:</b> {nl2br(a.get("atual"))}</div>
                <div class="deveria"><b>Deveria ser:</b> {nl2br(a.get("esperado"))}</div>
                {f'<div class="item-meta">{obs}</div>' if obs else ""}
                {bloco_retorno("ajuste", a.get("id"), a.get("retorno"), a.get("prazo"), editavel)}
              </div>
            </li>"""
        blocos += f"""
        <div class="callout" style="margin-bottom:14px"><b>Leva {e(versao)}</b> — {len(itens)} ajuste(s) em aberto, sendo {bugs} bug(s).</div>
        <div class="card" style="margin-bottom:26px"><ul class="itens">{linhas}</ul></div>"""
    return blocos


def secao_piloto(piloto: dict) -> str:
    """O andamento do piloto do Track One — o app dos técnicos.

    A reunião é uma só, então o que trava a liberação do app precisa estar na
    mesma pauta dos ajustes e dos casos de teste. Aqui vai o que a outra ponta
    precisa saber: em que pé está cada fase, o que os técnicos relataram e,
    principalmente, o que ainda não virou item de backlog — porque isso é o que
    ninguém está tratando ainda.
    """
    if not piloto:
        return ""
    fases = piloto.get("fases") or []
    soltos = piloto.get("relatos_sem_ajuste") or []
    if not fases and not soltos:
        return ""

    FASE_LABEL = {
        "planejada": ("Planejada", "b-neutral"),
        "em_andamento": ("Em andamento", "b-info"),
        "concluida": ("Concluída", "b-warn"),
        "liberada": ("Liberada", "b-ok"),
    }
    linhas = ""
    for f in fases:
        rotulo, cor = FASE_LABEL.get(f.get("status"), (f.get("status"), "b-neutral"))
        criterios = f.get("criterios") or []
        faltando = [c for c in criterios if not c.get("ok")]
        detalhe = (
            "critérios batidos — pronta pra liberar"
            if criterios and not faltando
            else "; ".join(f'{c["nome"]}: {c["atual"]}/{c["meta"]}' for c in faltando[:3])
        ) or "sem técnicos ainda"
        extras = badge(rotulo, cor)
        if f.get("versao_app"):
            extras += " " + badge(f'versão {f["versao_app"]}', "b-neutral")
        linhas += f"""
        <li>
          <div class="item-head">
            <span class="titulo">{e(f.get("nome"))}</span>
            {extras}
            <span class="item-meta">{e(f.get("total_tecnicos"))} técnico(s) · {e(f.get("responderam"))} responderam · nota {e(f.get("nota_media") or "—")}</span>
          </div>
          <div class="item-corpo">
            <div class="item-meta">{e(detalhe)}</div>
          </div>
        </li>"""

    blocos = ""
    if linhas:
        blocos += f'<div class="card" style="margin-bottom:20px"><ul class="itens">{linhas}</ul></div>'

    if soltos:
        itens = ""
        for r in soltos[:12]:
            marca = badge("Problema", "b-alert") if r.get("tipo") == "problema" else badge("Melhoria", "b-info")
            meta = " · ".join(x for x in [
                r.get("tecnico"),
                f'chamado {r["chamado"]}' if r.get("chamado") else "",
                f'versão {r["versao_app"]}' if r.get("versao_app") else "",
            ] if x)
            itens += f"""
            <li>
              <div class="item-head">{marca}<span class="titulo">{e(r.get("texto"))}</span></div>
              <div class="item-corpo"><div class="item-meta">{e(meta)}</div></div>
            </li>"""
        sobra = len(soltos) - len(soltos[:12])
        blocos += f"""
        <div class="callout" style="margin-bottom:14px"><b>Relatado pelos técnicos e ainda sem item no backlog</b> —
        {len(soltos)} ponto(s) que ninguém está tratando até virarem ajuste.</div>
        <div class="card"><ul class="itens">{itens}</ul>
        {f'<p class="muted" style="margin-top:10px">e mais {sobra} relato(s).</p>' if sobra > 0 else ""}</div>"""
    return blocos


def secao_nao_executados(casos: list) -> str:
    pendentes = [c for c in casos if c.get("status") == "Não testado"]
    if not pendentes:
        return ""
    por_estagio = {}
    for c in pendentes:
        chave = (c.get("estagio_num") if c.get("estagio_num") is not None else 99, c.get("estagio") or "—")
        por_estagio.setdefault(chave, []).append(c)
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
          <td style="width:34%">{chips}</td>
          <td style="width:8%;text-align:right"><b style="font-size:18px">{len(itens)}</b></td>
        </tr>"""
    return f"""
      <div class="card" style="padding:0;overflow:hidden">
        <table>
          <thead><tr><th>Estágio · casos</th><th>Frente</th>
            <th style="text-align:right">Qtde</th></tr></thead>
          <tbody>{linhas}</tbody>
        </table>
      </div>"""


# --------------------------------------------------------------------------- página


SCRIPT_RETORNO = """
<script>
(function () {
  var ROTA = { nota: "/api/notas/", ajuste: "/api/ativos/ajustes/" };

  function avisar(caixa, texto, classe) {
    var aviso = caixa.querySelector(".retorno-aviso");
    aviso.textContent = texto;
    aviso.className = "retorno-aviso" + (classe ? " " + classe : "");
  }

  async function salvar(caixa) {
    var botao = caixa.querySelector(".retorno-salvar");
    var rota = ROTA[caixa.dataset.tipo];
    if (!rota) return;
    botao.disabled = true;
    avisar(caixa, "Salvando...", "");
    try {
      var resposta = await fetch(rota + caixa.dataset.id, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          retorno: caixa.querySelector(".retorno-texto").value,
          prazo: caixa.querySelector(".retorno-prazo").value,
        }),
      });
      if (!resposta.ok) {
        var erro = await resposta.json().catch(function () { return {}; });
        throw new Error(erro.detail || ("HTTP " + resposta.status));
      }
      var agora = new Date();
      avisar(caixa, "Salvo às " + agora.toTimeString().slice(0, 5), "ok");
    } catch (e) {
      avisar(caixa, "Não salvou: " + e.message, "erro");
    } finally {
      botao.disabled = false;
    }
  }

  document.querySelectorAll(".retorno").forEach(function (caixa) {
    var botao = caixa.querySelector(".retorno-salvar");
    if (!botao) return;
    botao.addEventListener("click", function () { salvar(caixa); });
    // Ctrl+Enter salva sem tirar a mão do teclado — em reunião isso conta.
    caixa.querySelector(".retorno-texto").addEventListener("keydown", function (ev) {
      if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter") { ev.preventDefault(); salvar(caixa); }
    });
    caixa.querySelectorAll(".retorno-texto, .retorno-prazo").forEach(function (campo) {
      campo.addEventListener("input", function () { avisar(caixa, "", ""); });
    });
  });
})();
</script>
"""


def kpi(label: str, valor, ico: str, nota: str = "", classe: str = "") -> str:
    tag = f'<span class="badge {classe}">{e(nota)}</span>' if nota else ""
    return f"""
      <div class="kpi">
        <div class="top"><div class="ico">{ico}</div>{tag}</div>
        <div class="label">{e(label)}</div>
        <div class="value">{e(valor)}</div>
      </div>"""


def montar_html(dados: dict, fonte: str, editavel: bool = False) -> str:
    """`editavel` liga os campos de retorno — só faz sentido quando a página é
    servida pelo app, que tem pra onde salvar."""
    casos = dados.get("cases") or []
    notas = dados.get("notas") or []
    ajustes = dados.get("ativos_ajustes") or []
    situacoes = dados.get("situacoes") or []
    summary = dados.get("summary") or {}
    piloto = dados.get("piloto") or {}
    piloto_soltos = piloto.get("relatos_sem_ajuste") or []

    pontos_abertos = [n for n in notas if not n.get("resolvido")]
    fluxos = sorted({f for f in ({c.get("fluxo") for c in casos}
                                 | {s.get("fluxo") for s in situacoes}) if f})
    multi_fluxo = len(fluxos) > 1
    reprovados = [c for c in casos if c.get("status") in STATUS_PROBLEMA] + [
        x for sit in situacoes for x in (sit.get("estagios") or [])
        if x.get("status") in STATUS_PROBLEMA
    ]
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
    total_pauta = len(pontos_abertos) + len(reprovados) + len(ajustes_abertos)

    kpis = "".join([
        kpi("Pontos em aberto", len(pontos_abertos), "◆",
            f'{sum(1 for n in pontos_abertos if n.get("cobrado"))} já cobrados', "b-info" if pontos_abertos else ""),
        kpi("Reprovados / bloqueados", len(reprovados), "✕",
            f'{sum(1 for c in reprovados if c.get("status") == "Reprovado")} reprovados',
            "b-alert" if reprovados else "b-ok"),
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
            ("problemas", f"Reprovados / bloqueados ({len(reprovados)})"),
            ("situacoes", f"Situações ({situacoes_pendentes})"),
            ("ajustes", f"Ajustes ({len(ajustes_abertos)})"),
            ("piloto", f"Track One ({len(piloto_soltos)})"),
            ("pendentes", f"Por executar ({len(casos_pendentes)})"),
        ]
    )

    # O botão salva direto na API do app. Fora do app (arquivo .html gerado pelo
    # script) não há servidor pra receber, e o bloco de retorno já vem só-leitura.
    script = SCRIPT_RETORNO if editavel else ""

    corpo = "".join([
        sec("01", "Pontos para a reunião", "levantados durante os testes e ainda não resolvidos",
            secao_pontos(notas, editavel), "pontos"),
        sec("02", "Reprovados e bloqueados", "casos de teste e estágios de situação que falharam",
            secao_reprovados(casos, situacoes, multi_fluxo), "problemas"),
        sec("03", "Situações — onde cada cenário parou", "os próximos estágios da fila de cada situação",
            secao_situacoes(situacoes, multi_fluxo), "situacoes"),
        sec("04", "Ajustes da Gestão de Ativos", "hoje é assim / deveria ser assim — pendentes de validação",
            secao_ajustes(ajustes, editavel), "ajustes"),
        sec("05", "Track One — piloto com os técnicos", "como está cada fase e o que os técnicos relataram",
            secao_piloto(piloto), "piloto"),
        sec("06", "Testes ainda não executados", "fila de execução, agrupada por estágio",
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
/* lista de itens — uma linha por assunto, pra ler de cima pra baixo */
.itens{{list-style:none;counter-reset:item}}
.itens li{{padding:18px 0;border-bottom:1px solid var(--border)}}
.itens li:first-child{{padding-top:4px}}
.itens li:last-child{{border-bottom:none;padding-bottom:4px}}
.item-head{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:8px}}
.item-head .num{{font-family:'Roboto Slab',serif;font-size:13px;font-weight:700;color:var(--f-purple);
  min-width:38px;flex-shrink:0}}
.item-head .titulo{{font-family:'Roboto Slab',serif;font-size:16px;font-weight:700;color:var(--text);
  flex:1;min-width:240px}}
.item-corpo{{padding-left:48px;font-size:14.5px;color:var(--text-2)}}
.item-corpo .hoje b{{color:#c02234}}
.item-corpo .deveria b{{color:#04795c}}
.item-corpo>div{{margin-bottom:6px}}
.item-corpo>div:last-child{{margin-bottom:0}}
.item-meta{{color:var(--muted);font-size:13px}}
.anotacoes{{list-style:none;margin:0}}
.anotacoes li{{position:relative;padding:5px 0 5px 16px;font-size:14px}}
.anotacoes li::before{{content:"";position:absolute;left:0;top:13px;width:5px;height:5px;
  border-radius:50%;background:var(--f-magenta)}}
/* observação marcada em verde/vermelho na tela mantém a cor aqui */
.anotacoes li.obs-verde{{color:#04795c}}
.anotacoes li.obs-verde::before{{background:#04795c}}
.anotacoes li.obs-vermelho{{color:#c02234}}
.anotacoes li.obs-vermelho::before{{background:#c02234}}

/* retorno do time — o que responderam e pra quando prometeram */
.retorno{{margin-top:12px;padding:12px 14px;border-radius:var(--r-sm);
  background:var(--surface-2);border:1px solid var(--border)}}
.retorno .label-sec{{margin-bottom:8px}}
.retorno-linha{{display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap}}
.retorno-prazo-wrap{{display:flex;flex-direction:column;gap:4px;font-size:11px;
  text-transform:uppercase;letter-spacing:.7px;color:var(--muted);font-weight:500}}
.retorno-prazo{{font-family:'Roboto',sans-serif;font-size:14px;color:var(--text);
  padding:8px 10px;border:1px solid var(--border-strong);border-radius:var(--r-sm);
  background:var(--surface)}}
.retorno-texto{{flex:1;min-width:220px;font-family:'Roboto',sans-serif;font-size:14px;
  color:var(--text);padding:8px 10px;border:1px solid var(--border-strong);
  border-radius:var(--r-sm);background:var(--surface);resize:vertical}}
.retorno-prazo:focus,.retorno-texto:focus{{outline:none;border-color:var(--f-blue);
  box-shadow:0 0 0 3px rgba(0,84,236,.12)}}
.retorno-salvar{{align-self:stretch;background:var(--grad-brand);color:#fff;border:none;
  padding:9px 18px;border-radius:var(--r-sm);font-family:'Roboto',sans-serif;font-size:14px;
  font-weight:500;cursor:pointer}}
.retorno-salvar:hover{{filter:brightness(1.06)}}
.retorno-salvar:disabled{{opacity:.55;cursor:default;filter:none}}
.retorno-aviso{{font-size:13px;margin-top:8px;min-height:1px}}
.retorno-aviso.ok{{color:#04795c}}
.retorno-aviso.erro{{color:#c02234}}
.retorno-ro{{background:transparent;border-left:3px solid var(--f-blue);border-radius:0;
  border-top:none;border-right:none;border-bottom:none;padding:2px 0 2px 14px;font-size:14px}}
@media print{{.retorno-salvar{{display:none}}}}
@media(max-width:720px){{.item-corpo{{padding-left:0}}}}
</style>
</head>
<body>
<header class="topbar">
  {logo}
  <div class="spacer"></div>
  <span class="badge b-warn">{total_pauta} itens em pauta</span>
</header>

<main class="wrap">
  <div class="accent"></div>

  <div class="hero">
    <h2>O que precisa de decisão nesta reunião</h2>
    <p class="lead">{len(pontos_abertos)} ponto(s) em aberto · {len(reprovados)} item(ns) reprovado(s) ou bloqueado(s) ·
      {len(ajustes_abertos)} ajuste(s) da Gestão de Ativos pendente(s) · {len(casos_pendentes)} teste(s) na fila de execução
      ({pct:.0f}% do plano já executado).</p>
  </div>

  <div class="grid g4" style="margin-bottom:8px">{kpis}</div>

  <div class="navbar"><div class="tabs">{nav}</div></div>

  {corpo}
</main>

{script}

<footer>
  Faiston · gerado em {agora.strftime("%d/%m/%Y às %H:%M")} (BRT) · fonte: {e(fonte)}
</footer>
</body>
</html>
"""
