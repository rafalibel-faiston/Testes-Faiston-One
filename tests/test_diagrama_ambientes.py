"""Catálogo de ambientes ("onde a ação acontece") dos fluxogramas."""
import pytest

from app import models
from app.database import SessionLocal
from app.routers.diagrams import AMBIENTES_PADRAO


def _item(slug="faiston_one", nome="Faiston One", cor="#0054ec", estilo="pilula"):
    return {"slug": slug, "nome": nome, "cor": cor, "estilo": estilo}


@pytest.fixture(autouse=True)
def catalogo_limpo():
    """Cada teste começa (e termina) sem a linha do catálogo: a próxima leitura recria o padrão."""
    def apaga():
        db = SessionLocal()
        try:
            db.query(models.DiagramaAmbientes).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
    apaga()
    yield
    apaga()


def test_primeira_leitura_traz_as_sugestoes_iniciais(client):
    dados = client.get("/api/diagramas-ambientes").json()
    assert [i["slug"] for i in dados["itens"]] == [a["slug"] for a in AMBIENTES_PADRAO]
    assert any(i["nome"] == "Faiston One" for i in dados["itens"])


def test_salvar_substitui_o_catalogo_inteiro(client):
    novo = [_item(), _item(slug="tiflux", nome="Tiflux", cor="#EA580C", estilo="solido")]
    resp = client.put("/api/diagramas-ambientes", json={"itens": novo, "atualizado_por": "Rafa"})
    assert resp.status_code == 200
    dados = client.get("/api/diagramas-ambientes").json()
    assert [i["slug"] for i in dados["itens"]] == ["faiston_one", "tiflux"]
    assert dados["itens"][1]["cor"] == "#ea580c"          # cor normalizada pra minúscula
    assert dados["atualizado_por"] == "Rafa"


def test_o_que_o_time_apagou_nao_volta_a_cada_leitura(client):
    client.get("/api/diagramas-ambientes")                  # cria o padrão
    assert client.put("/api/diagramas-ambientes", json={"itens": [_item()]}).status_code == 200
    for _ in range(2):                                      # "subidas do app" seguintes
        assert [i["slug"] for i in client.get("/api/diagramas-ambientes").json()["itens"]] == ["faiston_one"]


def test_pode_esvaziar_o_catalogo(client):
    assert client.put("/api/diagramas-ambientes", json={"itens": []}).status_code == 200
    assert client.get("/api/diagramas-ambientes").json()["itens"] == []


@pytest.mark.parametrize("item, motivo", [
    (_item(cor="azul"), "cor que não é hexadecimal"),
    (_item(cor="#12345"), "cor curta demais"),
    (_item(estilo="neon"), "estilo inexistente"),
    (_item(slug="Faiston One"), "identificador com espaço e maiúscula"),
    (_item(slug=""), "identificador vazio"),
    (_item(nome="   "), "nome em branco"),
    (_item(nome="x" * 41), "nome grande demais"),
])
def test_recusa_ambiente_invalido(client, item, motivo):
    resp = client.put("/api/diagramas-ambientes", json={"itens": [item]})
    assert resp.status_code in (400, 422), motivo


def test_recusa_repetidos_e_excesso(client):
    dois_slugs = [_item(), _item(nome="Outro nome")]
    assert client.put("/api/diagramas-ambientes", json={"itens": dois_slugs}).status_code == 422
    dois_nomes = [_item(), _item(slug="outro", nome="FAISTON one")]
    assert client.put("/api/diagramas-ambientes", json={"itens": dois_nomes}).status_code == 422
    demais = [_item(slug=f"a{i}", nome=f"Ambiente {i}") for i in range(25)]
    assert client.put("/api/diagramas-ambientes", json={"itens": demais}).status_code == 422
    # nada disso alterou o catálogo
    assert len(client.get("/api/diagramas-ambientes").json()["itens"]) == len(AMBIENTES_PADRAO)
