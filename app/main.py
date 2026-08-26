import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
from .routers import cases as cases_router
from .routers import notes as notes_router
from .routers import export as export_router
from .routers import diagrams as diagrams_router
from .routers import activity as activity_router
from .routers import situacoes as situacoes_router
from . import seed_data
from .routers import auth as auth_router
from .routers import agenda as agenda_router
from .routers import todo as todo_router
from .routers import ativos as ativos_router
from .routers import relatorio as relatorio_router
from .mcp_server import mcp as mcp_server, oauth_provider, MCP_TOKEN

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# versao usada pra "quebrar" o cache do navegador em /static/app.js e /static/style.css
# a cada deploy. O Railway injeta RAILWAY_GIT_COMMIT_SHA automaticamente; localmente
# (sem essa env var) cai pro horario de start do processo, que muda a cada reload.
APP_VERSION = os.getenv("RAILWAY_GIT_COMMIT_SHA", str(int(time.time())))[:12]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(title="Fluxo C — Console de Teste (Faiston)", lifespan=lifespan)

Base.metadata.create_all(bind=engine)
# adiciona colunas novas em bancos que já existem (antes de qualquer query ORM)
seed_data.migrate_schema(engine)

# semeia a base de casos na primeira subida (idempotente)
_db = SessionLocal()
try:
    seed_data.seed(_db)
    seed_data.migrate_observations(_db)
    seed_data.seed_diagrams(_db)
    seed_data.seed_situacoes(_db)
    seed_data.seed_agenda_operacao_logistica(_db)
    seed_data.seed_todo_desmame_planilha(_db)
    seed_data.seed_ativos_ajustes(_db)
finally:
    _db.close()

app.include_router(cases_router.router, prefix="/api")
app.include_router(notes_router.router, prefix="/api")
app.include_router(export_router.router, prefix="/api")
app.include_router(diagrams_router.router, prefix="/api")
app.include_router(activity_router.router, prefix="/api")
app.include_router(situacoes_router.router, prefix="/api")
app.include_router(auth_router.router, prefix="/api")
app.include_router(agenda_router.router, prefix="/api")
app.include_router(todo_router.router, prefix="/api")
app.include_router(ativos_router.router, prefix="/api")
# página pronta da pauta da reunião — sem prefixo /api, é pra abrir no navegador
app.include_router(relatorio_router.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace('href="/static/style.css"', f'href="/static/style.css?v={APP_VERSION}"')
    html = html.replace('src="/static/app.js"', f'src="/static/app.js?v={APP_VERSION}"')
    # a pagina em si nunca deve ficar em cache — assim o navegador sempre pega
    # a versao (query string) mais nova do JS/CSS a cada deploy/reload.
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/health")
def health():
    return {"status": "ok"}


def _login_page(request_id: str, erro: str = "") -> str:
    erro_html = f'<p class="erro">{erro}</p>' if erro else ""
    return f"""<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8">
<title>Conectar — Fluxo C</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
          display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
  form {{ background: #1e293b; padding: 2rem; border-radius: 12px; width: 320px; }}
  h1 {{ font-size: 1.1rem; margin: 0 0 1rem; }}
  input {{ width: 100%; box-sizing: border-box; padding: .6rem; border-radius: 6px;
           border: 1px solid #334155; background: #0f172a; color: #e2e8f0; margin-bottom: 1rem; }}
  button {{ width: 100%; padding: .6rem; border-radius: 6px; border: none;
            background: #38bdf8; color: #0f172a; font-weight: 600; cursor: pointer; }}
  .erro {{ color: #f87171; font-size: .85rem; margin: -.5rem 0 1rem; }}
</style></head>
<body>
  <form method="post" action="/mcp-login">
    <h1>Autorizar conexão com o Fluxo C — Console de Teste</h1>
    <input type="hidden" name="request_id" value="{request_id}">
    <input type="password" name="token" placeholder="Token de acesso (MCP_TOKEN)" autofocus>
    {erro_html}
    <button type="submit">Autorizar</button>
  </form>
</body></html>"""


@app.get("/mcp-login")
def mcp_login_form(request_id: str):
    if not oauth_provider.peek_pending_request(request_id):
        return HTMLResponse("Pedido de autorização expirado ou inválido. Tente vincular o conector de novo.", status_code=400)
    return HTMLResponse(_login_page(request_id))


@app.post("/mcp-login")
def mcp_login_submit(request_id: str = Form(...), token: str = Form(...)):
    if not oauth_provider.peek_pending_request(request_id):
        return HTMLResponse("Pedido de autorização expirado ou inválido. Tente vincular o conector de novo.", status_code=400)
    if not MCP_TOKEN or not secrets.compare_digest(token.strip(), MCP_TOKEN):
        return HTMLResponse(_login_page(request_id, erro="Token incorreto."), status_code=401)
    redirect_uri = oauth_provider.complete_authorization(request_id)
    return RedirectResponse(redirect_uri, status_code=302)


# montado por último, na raiz: só recebe o que nenhuma rota acima já respondeu
# (endpoint MCP em /mcp, e as rotas OAuth /authorize, /token, /register, /.well-known/...)
app.mount("/", mcp_server.streamable_http_app())
