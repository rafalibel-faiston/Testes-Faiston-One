"""O seed de diagramas roda a cada subida do app. O que o time exclui não pode voltar."""
from app import models, seed_data
from app.database import SessionLocal


def _limpa_removidos():
    db = SessionLocal()
    try:
        db.query(models.DiagramaSeedRemovido).delete(synchronize_session=False)
        db.commit()
        seed_data.seed_diagrams(db)   # devolve ao estado normal do app: tudo semeado
    finally:
        db.close()


def _roda_seed():
    db = SessionLocal()
    try:
        return seed_data.seed_diagrams(db)
    finally:
        db.close()


def _titulos(client, fluxo):
    return {d["titulo"]: d["id"] for d in client.get("/api/diagramas", params={"fluxo": fluxo}).json()}


def test_diagrama_do_seed_excluido_nao_volta_na_proxima_subida(client):
    try:
        titulos = _titulos(client, "financeiro")
        alvo = "Cenário 2 — Projetos (D1)"
        assert alvo in titulos, "o seed do Financeiro devia ter criado este diagrama"

        assert client.delete(f"/api/diagramas/{titulos[alvo]}").status_code == 200
        assert alvo not in _titulos(client, "financeiro")

        # a "subida do app" roda o seed de novo: não pode recriar o que foi excluído...
        assert _roda_seed() == 0
        depois = _titulos(client, "financeiro")
        assert alvo not in depois
        # ...e os outros continuam intactos
        assert set(depois) == set(titulos) - {alvo}
    finally:
        _limpa_removidos()


def test_excluir_de_novo_o_mesmo_titulo_nao_duplica_o_registro(client):
    try:
        alvo = "Cenário 3 — Atendimento CLT"
        ids = _titulos(client, "financeiro")
        assert alvo in ids
        assert client.delete(f"/api/diagramas/{ids[alvo]}").status_code == 200
        _roda_seed()
        # o seed não recriou; se alguém criar outro com o mesmo título e apagar, não estoura a unicidade
        novo = client.post("/api/diagramas", json={
            "fluxo": "financeiro", "kind": "ideal", "titulo": alvo, "mermaid": "flowchart TD\n  A-->B",
        })
        assert novo.status_code in (200, 201)
        assert client.delete(f"/api/diagramas/{novo.json()['id']}").status_code == 200
        db = SessionLocal()
        try:
            assert db.query(models.DiagramaSeedRemovido).filter_by(fluxo="financeiro", titulo=alvo).count() == 1
        finally:
            db.close()
    finally:
        _limpa_removidos()


def test_diagrama_criado_pelo_time_com_outro_titulo_nao_vira_removido(client):
    d = client.post("/api/diagramas", json={
        "fluxo": "financeiro", "kind": "ideal", "titulo": "Meu rascunho", "mermaid": "flowchart TD\n  A-->B",
    }).json()
    assert client.delete(f"/api/diagramas/{d['id']}").status_code == 200
    db = SessionLocal()
    try:
        assert db.query(models.DiagramaSeedRemovido).filter_by(titulo="Meu rascunho").count() == 0
    finally:
        db.close()
