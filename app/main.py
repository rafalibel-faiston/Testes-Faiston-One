import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
from .routers import cases as cases_router
from . import seed_data

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="Fluxo C — Console de Teste (Faiston)")

Base.metadata.create_all(bind=engine)

# semeia a base de casos na primeira subida (idempotente)
_db = SessionLocal()
try:
    seed_data.seed(_db)
finally:
    _db.close()

app.include_router(cases_router.router, prefix="/api")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}
