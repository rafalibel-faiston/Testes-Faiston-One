import os
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
from .routers import cases as cases_router
from .routers import notes as notes_router
from .routers import export as export_router
from . import seed_data

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# versao usada pra "quebrar" o cache do navegador em /static/app.js e /static/style.css
# a cada deploy. O Railway injeta RAILWAY_GIT_COMMIT_SHA automaticamente; localmente
# (sem essa env var) cai pro horario de start do processo, que muda a cada reload.
APP_VERSION = os.getenv("RAILWAY_GIT_COMMIT_SHA", str(int(time.time())))[:12]

app = FastAPI(title="Fluxo C — Console de Teste (Faiston)")

Base.metadata.create_all(bind=engine)
# adiciona colunas novas em bancos que já existem (antes de qualquer query ORM)
seed_data.migrate_schema(engine)

# semeia a base de casos na primeira subida (idempotente)
_db = SessionLocal()
try:
    seed_data.seed(_db)
    seed_data.migrate_observations(_db)
finally:
    _db.close()

app.include_router(cases_router.router, prefix="/api")
app.include_router(notes_router.router, prefix="/api")
app.include_router(export_router.router, prefix="/api")

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
