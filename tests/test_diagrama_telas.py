"""Telinhas (protótipos) por etapa do fluxograma."""
import pytest

BLOCOS = [
    {"tipo": "topo", "texto": "Chamado aceito"},
    {"tipo": "status", "texto": "Agendado", "extra": "verde"},
    {"tipo": "botao", "texto": "Iniciar deslocamento"},
]


def _diagrama(client, fluxo="C", titulo="Fluxo de teste das telas"):
    resp = client.post("/api/diagramas", json={
        "fluxo": fluxo, "kind": "ideal", "titulo": titulo,
        "mermaid": "flowchart TD\n  A[Início] --> B[Fim]",
    })
    assert resp.status_code == 201
    return resp.json()


def _tela(**extra):
    return {"dispositivo": "celular", "titulo": "Chamado aceito", "legenda": "O técnico vê o agendamento",
            "blocos": BLOCOS, **extra}


@pytest.fixture
def diagrama(client):
    d = _diagrama(client)
    yield d
    client.delete(f"/api/diagramas/{d['id']}")


def test_cria_e_le_a_tela_de_uma_etapa(client, diagrama):
    resp = client.put(f"/api/diagramas/{diagrama['id']}/telas/A", json=_tela())
    assert resp.status_code == 200
    tela = resp.json()
    assert tela["no_id"] == "A" and tela["dispositivo"] == "celular"
    assert [b["tipo"] for b in tela["blocos"]] == ["topo", "status", "botao"]
    assert tela["blocos"][1]["extra"] == "verde"

    todas = client.get("/api/diagramas-telas", params={"fluxo": "C"}).json()
    assert [t["no_id"] for t in todas if t["diagrama_id"] == diagrama["id"]] == ["A"]


def test_salvar_de_novo_substitui_em_vez_de_duplicar(client, diagrama):
    client.put(f"/api/diagramas/{diagrama['id']}/telas/A", json=_tela())
    outra = _tela(titulo="Outro nome", dispositivo="web", blocos=[{"tipo": "topo", "texto": "Painel"}])
    assert client.put(f"/api/diagramas/{diagrama['id']}/telas/A", json=outra).status_code == 200
    mesmas = [t for t in client.get("/api/diagramas-telas", params={"fluxo": "C"}).json()
              if t["diagrama_id"] == diagrama["id"]]
    assert len(mesmas) == 1
    assert mesmas[0]["titulo"] == "Outro nome" and mesmas[0]["dispositivo"] == "web"
    assert len(mesmas[0]["blocos"]) == 1


@pytest.mark.parametrize("payload, motivo", [
    (_tela(blocos=[]), "sem blocos"),
    (_tela(blocos=[{"tipo": "inexistente", "texto": "x"}]), "tipo de bloco inválido"),
    (_tela(dispositivo="tablet"), "dispositivo inválido"),
    (_tela(blocos=[{"tipo": "texto", "texto": "x" * 801}]), "texto grande demais"),
    (_tela(blocos=[{"tipo": "texto", "texto": "x"}] * 41), "blocos demais"),
])
def test_recusa_tela_invalida(client, diagrama, payload, motivo):
    resp = client.put(f"/api/diagramas/{diagrama['id']}/telas/A", json=payload)
    assert resp.status_code in (400, 422), motivo


def test_recusa_id_de_etapa_invalido_e_diagrama_inexistente(client, diagrama):
    assert client.put(f"/api/diagramas/{diagrama['id']}/telas/a-b", json=_tela()).status_code == 400
    assert client.put("/api/diagramas/99999999/telas/A", json=_tela()).status_code == 404


def test_filtra_por_fluxo(client, diagrama):
    outro = _diagrama(client, fluxo="financeiro", titulo="Diagrama de outro módulo")
    try:
        client.put(f"/api/diagramas/{diagrama['id']}/telas/A", json=_tela())
        client.put(f"/api/diagramas/{outro['id']}/telas/B", json=_tela())
        so_c = {t["diagrama_id"] for t in client.get("/api/diagramas-telas", params={"fluxo": "C"}).json()}
        assert diagrama["id"] in so_c and outro["id"] not in so_c
    finally:
        client.delete(f"/api/diagramas/{outro['id']}")


def test_excluir_a_tela_e_excluir_o_diagrama_leva_as_telas(client):
    d = _diagrama(client, titulo="Diagrama que vai embora")
    client.put(f"/api/diagramas/{d['id']}/telas/A", json=_tela())
    client.put(f"/api/diagramas/{d['id']}/telas/B", json=_tela())
    assert client.delete(f"/api/diagramas/{d['id']}/telas/A").status_code == 200
    assert client.delete(f"/api/diagramas/{d['id']}/telas/A").status_code == 404
    assert client.delete(f"/api/diagramas/{d['id']}").status_code == 200
    restantes = [t for t in client.get("/api/diagramas-telas").json() if t["diagrama_id"] == d["id"]]
    assert restantes == []


def test_salvar_tela_entra_na_trilha_de_novidades(client, diagrama):
    client.put(f"/api/diagramas/{diagrama['id']}/telas/A", json=_tela(atualizado_por="Rafa"))
    atividades = client.get("/api/atividades", params={"fluxo": "C"}).json()
    assert any("Chamado aceito" in a["texto"] and a["autor"] == "Rafa" for a in atividades)
