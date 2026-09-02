"""Ambiente dos testes: um app real, com um banco SQLite descartável por sessão.

O app cria as tabelas e semeia os casos no import, então o `DATABASE_URL` precisa
apontar pro banco de teste ANTES de `app.main` entrar em cena — daí o env var ser
ajustado aqui em cima, antes de qualquer import do projeto.
"""
import os
import tempfile

import pytest

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db", prefix="fluxoc-test-")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app import models  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    os.unlink(_DB_PATH)


@pytest.fixture(autouse=True)
def base_limpa(client):
    """Cada teste começa sem técnico, fase ou relato — o que um teste cria não
    pode mudar o resultado do próximo.

    Os ajustes criados durante o teste vão junto: um relato virado em ajuste
    deixa um item no backlog, e dois testes que levam o mesmo ponto pro backlog
    passariam sozinhos e falhariam na suíte. Os ajustes semeados pelo app ficam,
    porque fazem parte do estado normal dele — daí a marca no maior id do seed.
    """
    db = SessionLocal()
    try:
        ultimo_do_seed = db.query(models.AtivoAjuste.id).order_by(
            models.AtivoAjuste.id.desc()
        ).first()
        marca = ultimo_do_seed[0] if ultimo_do_seed else 0
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        db.query(models.TecnicoObservacao).delete(synchronize_session=False)
        db.query(models.Tecnico).delete(synchronize_session=False)
        db.query(models.PilotoFase).delete(synchronize_session=False)
        db.query(models.AtivoAjuste).filter(models.AtivoAjuste.id > marca).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture
def tecnico(client):
    """Um técnico cadastrado, do jeito que a tela cadastra."""
    resp = client.post("/api/tecnicos", json={
        "nome": "Carlos Eduardo Lima", "telefone": "11988887777", "regional": "São Paulo",
    })
    assert resp.status_code == 201
    return resp.json()


def planilha(linhas, cabecalho=("Nome", "Telefone", "Endereço - Cidade")):
    """Gera um .xlsx em memória, como o que o usuário sobe na importação."""
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(list(cabecalho))
    for linha in linhas:
        ws.append(list(linha))
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
