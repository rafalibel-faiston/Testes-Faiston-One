"""Formulário de feedback do técnico, servido como página própria.

`GET /formulario/{token}` é o link que o técnico abre no celular depois de usar
o Track One num atendimento real. Ele responde ali mesmo e o retorno cai direto
na base de QA (cada campo vira uma observação do tipo certo no card dele), sem
ninguém precisar entrevistar um a um por WhatsApp.

A página é autocontida — CSS e logo embutidos, nada de CDN — e pensada pro
celular primeiro, que é onde o técnico vai abrir.
"""

from __future__ import annotations

import html
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

# As etapas do fluxo que o piloto precisa ver exercitadas. O `value` é o que fica
# gravado em Tecnico.etapas_testadas (separado por "|") — mudar o texto aqui muda
# o que aparece no formulário e no card, então mantenha os dois iguais.
ETAPAS = [
    "Recebi o chamado no app",
    "Acompanhei o rastreio da peça",
    "Confirmei o recebimento do equipamento",
    "Fechei a RAT pelo app",
]

# Cada pergunta aberta vira uma observação no card do técnico com o tipo
# correspondente ("comentario" entra como nota geral, sem marcação).
PERGUNTAS = [
    ("positivo", "O que funcionou bem?", "o que você achou bom no app"),
    ("melhoria", "O que precisa melhorar?", "o que te atrapalhou ou faltou"),
    ("problema", "Teve algum erro ou travamento?", "tela que não atualiza, notificação que não chega…"),
    ("comentario", "Mais alguma coisa?", "qualquer outro comentário (opcional)"),
]

NOTAS = [
    (1, "Ruim"),
    (2, "Fraco"),
    (3, "Ok"),
    (4, "Bom"),
    (5, "Ótimo"),
]

CSS = """
*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0; background: #f6f7fb; color: #151720;
  font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 16px; line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 620px; margin: 0 auto; padding: 0 16px 48px; }
header.topo {
  background: linear-gradient(135deg,#2226c0 0%,#0054ec 45%,#00c7e6 100%);
  padding: 22px 16px 26px; color: #fff; margin-bottom: -14px;
}
header.topo .topo-inner { max-width: 620px; margin: 0 auto; }
/* o símbolo da marca é colorido e sumiria no gradiente do topo — a pílula
   branca devolve o contraste sem descaracterizar o logo */
header.topo .marca {
  display: inline-block; background: #fff; border-radius: 999px;
  padding: 8px 16px; margin-bottom: 16px; box-shadow: 0 4px 14px rgba(0,0,0,.12);
}
header.topo .marca svg { height: 22px; width: auto; color: #151720; display: block; }
header.topo h1 { font-size: 20px; font-weight: 700; margin: 0 0 4px; }
header.topo p { font-size: 13.5px; margin: 0; opacity: .9; }

.card {
  background: #fff; border: 1px solid #e6e9f4; border-radius: 16px;
  padding: 20px 18px; margin-top: 18px; box-shadow: 0 4px 18px rgba(21,23,32,.07);
}
.intro { font-size: 14.5px; color: #3f4661; margin: 0; }
.intro b { color: #151720; }
.aviso {
  margin-top: 12px; padding: 10px 12px; border-radius: 10px; font-size: 13px;
  background: rgba(0,84,236,.06); border: 1px solid rgba(0,84,236,.2); color: #2226c0;
}

.campo { margin-top: 22px; }
.campo:first-child { margin-top: 0; }
.campo > label.titulo, .campo > .titulo {
  display: block; font-size: 15px; font-weight: 600; color: #151720; margin-bottom: 4px;
}
.campo .ajuda { display: block; font-size: 13px; color: #7a839c; margin-bottom: 10px; }

textarea {
  width: 100%; min-height: 88px; padding: 12px; border-radius: 12px;
  border: 1px solid #d5dae9; background: #fbfcfe; color: #151720;
  font-family: inherit; font-size: 15px; line-height: 1.5; resize: vertical;
}
textarea:focus { outline: none; border-color: #0054ec; background: #fff; box-shadow: 0 0 0 3px rgba(0,84,236,.12); }

/* nota: botões grandes em vez de lista suspensa — dá pra responder com o polegar */
.notas { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
.nota-btn {
  display: flex; flex-direction: column; align-items: center; gap: 3px; cursor: pointer;
  padding: 12px 4px; border-radius: 12px; border: 1.5px solid #d5dae9; background: #fbfcfe;
  transition: all .15s ease;
}
.nota-btn input { position: absolute; opacity: 0; pointer-events: none; }
.nota-btn .n { font-size: 20px; font-weight: 700; color: #3f4661; line-height: 1; }
.nota-btn .l { font-size: 10.5px; color: #7a839c; text-align: center; }
.nota-btn.on { border-color: #0054ec; background: rgba(0,84,236,.08); }
.nota-btn.on .n { color: #0054ec; }
.nota-btn.on .l { color: #2226c0; font-weight: 600; }

.etapas { display: flex; flex-direction: column; gap: 8px; }
.etapa {
  display: flex; align-items: center; gap: 11px; cursor: pointer;
  padding: 13px 14px; border-radius: 12px; border: 1.5px solid #d5dae9; background: #fbfcfe;
  font-size: 14.5px; color: #3f4661; transition: all .15s ease;
}
.etapa input { width: 20px; height: 20px; accent-color: #0054ec; flex-shrink: 0; margin: 0; }
.etapa.on { border-color: #0054ec; background: rgba(0,84,236,.06); color: #151720; font-weight: 500; }

button.enviar {
  width: 100%; margin-top: 22px; padding: 16px; border: none; border-radius: 14px;
  background: linear-gradient(135deg,#2226c0 0%,#0054ec 45%,#00c7e6 100%);
  color: #fff; font-family: inherit; font-size: 16px; font-weight: 700; cursor: pointer;
  box-shadow: 0 10px 24px -12px rgba(0,84,236,.8);
}
button.enviar:active { transform: translateY(1px); }
button.enviar:disabled { opacity: .6; cursor: default; }

.erro { margin-top: 12px; font-size: 13.5px; color: #e11d48; text-align: center; }
.rodape { margin-top: 18px; text-align: center; font-size: 12px; color: #7a839c; }

/* tela de obrigado */
.obrigado { text-align: center; padding: 34px 18px; }
.obrigado .check {
  width: 64px; height: 64px; margin: 0 auto 18px; border-radius: 50%;
  background: rgba(13,157,108,.1); border: 2px solid rgba(13,157,108,.35); color: #0d9d6c;
  display: flex; align-items: center; justify-content: center; font-size: 32px;
}
.obrigado h2 { font-size: 20px; margin: 0 0 8px; color: #151720; }
.obrigado p { font-size: 14.5px; color: #3f4661; margin: 0; }
[hidden] { display: none !important; }
"""


def _logo_svg() -> str:
    caminho = ASSETS_DIR / "logo-faiston-full.svg"
    if not caminho.exists():
        return ""
    return caminho.read_text(encoding="utf-8").replace("<svg", '<svg aria-label="Faiston"', 1)


def montar_html(nome: str, token: str, ja_respondeu: str = "") -> str:
    """Página do formulário para um técnico. `ja_respondeu` é a data formatada da
    resposta anterior (vazio se ainda não respondeu) — quem já respondeu pode
    mandar outro retorno depois de um novo atendimento, só é avisado disso."""
    primeiro_nome = html.escape((nome or "").strip().split(" ")[0] or "tudo bem")

    notas_html = "".join(
        f"""<label class="nota-btn" data-nota="{valor}">
          <input type="radio" name="nota" value="{valor}">
          <span class="n">{valor}</span><span class="l">{html.escape(rotulo)}</span>
        </label>"""
        for valor, rotulo in NOTAS
    )

    etapas_html = "".join(
        f"""<label class="etapa">
          <input type="checkbox" name="etapa" value="{html.escape(etapa)}">
          <span>{html.escape(etapa)}</span>
        </label>"""
        for etapa in ETAPAS
    )

    perguntas_html = "".join(
        f"""<div class="campo">
          <label class="titulo" for="q-{tipo}">{html.escape(titulo)}</label>
          <span class="ajuda">{html.escape(ajuda)}</span>
          <textarea id="q-{tipo}" name="{tipo}" placeholder="pode escrever do seu jeito"></textarea>
        </div>"""
        for tipo, titulo, ajuda in PERGUNTAS
    )

    aviso_html = (
        f'<div class="aviso">Você já mandou um retorno em {html.escape(ja_respondeu)}. '
        f"Se testou de novo e tem mais coisa pra contar, é só responder outra vez.</div>"
        if ja_respondeu
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Track One — como foi o seu teste?</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<header class="topo">
  <div class="topo-inner">
    <span class="marca">{_logo_svg()}</span>
    <h1>Track One — como foi o seu teste?</h1>
    <p>Leva 2 minutinhos. Seu retorno é o que ajusta o app antes de liberar pra todo mundo.</p>
  </div>
</header>

<div class="wrap">
  <form id="form" class="card">
    <p class="intro">Oi, <b>{primeiro_nome}</b>! Conta pra gente como foi usar o app no seu atendimento.</p>
    {aviso_html}

    <div class="campo" style="margin-top:22px">
      <span class="titulo">No geral, o que você achou do app?</span>
      <span class="ajuda">1 é ruim, 5 é ótimo</span>
      <div class="notas">{notas_html}</div>
    </div>

    <div class="campo">
      <span class="titulo">O que você conseguiu fazer pelo app?</span>
      <span class="ajuda">marque tudo que deu certo no atendimento</span>
      <div class="etapas">{etapas_html}</div>
    </div>

    {perguntas_html}

    <button type="submit" class="enviar" id="enviar">Enviar respostas</button>
    <p class="erro" id="erro" hidden></p>
  </form>

  <div class="card obrigado" id="obrigado" hidden>
    <div class="check">✓</div>
    <h2>Valeu, {primeiro_nome}!</h2>
    <p>Seu retorno já chegou pra gente. Qualquer coisa que aparecer depois, chama direto no WhatsApp.</p>
  </div>

  <p class="rodape">Faiston · Track One — teste piloto</p>
</div>

<script>
(function () {{
  var form = document.getElementById("form");
  var erro = document.getElementById("erro");
  var botao = document.getElementById("enviar");

  // realce visual de nota e etapa marcadas (o input real fica escondido/nativo)
  document.querySelectorAll(".nota-btn").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      document.querySelectorAll(".nota-btn").forEach(function (o) {{ o.classList.remove("on"); }});
      btn.classList.add("on");
    }});
  }});
  document.querySelectorAll(".etapa").forEach(function (item) {{
    var input = item.querySelector("input");
    input.addEventListener("change", function () {{ item.classList.toggle("on", input.checked); }});
  }});

  form.addEventListener("submit", async function (e) {{
    e.preventDefault();
    var fd = new FormData(form);
    var payload = {{
      nota: fd.get("nota") ? Number(fd.get("nota")) : null,
      etapas: fd.getAll("etapa"),
      positivo: (fd.get("positivo") || "").trim(),
      melhoria: (fd.get("melhoria") || "").trim(),
      problema: (fd.get("problema") || "").trim(),
      comentario: (fd.get("comentario") || "").trim(),
    }};
    var vazio = !payload.nota && !payload.etapas.length && !payload.positivo
      && !payload.melhoria && !payload.problema && !payload.comentario;
    if (vazio) {{
      erro.textContent = "Responde pelo menos uma coisa antes de enviar :)";
      erro.hidden = false;
      return;
    }}
    erro.hidden = true;
    botao.disabled = true;
    botao.textContent = "Enviando…";
    try {{
      var res = await fetch("/api/formulario/{token}", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload),
      }});
      if (!res.ok) throw new Error("falhou");
      form.hidden = true;
      document.getElementById("obrigado").hidden = false;
      window.scrollTo({{ top: 0, behavior: "smooth" }});
    }} catch (err) {{
      erro.textContent = "Não deu pra enviar agora. Confere a internet e tenta de novo.";
      erro.hidden = false;
      botao.disabled = false;
      botao.textContent = "Enviar respostas";
    }}
  }});
}})();
</script>
</body>
</html>"""


def pagina_invalida() -> str:
    """Link errado/expirado — sem detalhe do porquê, é página pública."""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Track One</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="card obrigado" style="margin-top:40px">
    <h2>Link não encontrado</h2>
    <p>Esse link de formulário não vale mais. Chama quem te mandou pra pegar o link certo.</p>
  </div>
</div>
</body>
</html>"""
