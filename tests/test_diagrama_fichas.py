"""Ficha técnica por etapa do fluxograma (de onde vem, o que faz, pra onde vai)."""
import pytest

FICHA = {
    "gatilho": "Chamado criado no Tiflux (webhook)",
    "entrada": "ticket_id, localidade, escopo, gastos",
    "origem": "API do Tiflux",
    "acao": "Confronta o escopo com o contrato do projeto",
    "regra": "Escopo fora do contrato -> reprova",
    "saida": "status aprovado/reprovado + motivo",
    "destino": "Fila do coordenador + WhatsApp do solicitante",
    "responsavel": "Faiston One",
    "execucao": "automatico",
    "sla": "15 min",
}


@pytest.fixture
def diagrama(client):
    resp = client.post("/api/diagramas", json={
        "fluxo": "C", "kind": "ideal", "titulo": "Fluxo de teste das fichas",
        "mermaid": "flowchart TD\n  A[Início] --> B[Fim]",
    })
    assert resp.status_code == 201
    d = resp.json()
    yield d
    client.delete(f"/api/diagramas/{d['id']}")


def _minhas(client, diag_id):
    return [f for f in client.get("/api/diagramas-fichas", params={"fluxo": "C"}).json()
            if f["diagrama_id"] == diag_id]


def test_cria_e_le_a_ficha_de_uma_etapa(client, diagrama):
    resp = client.put(f"/api/diagramas/{diagrama['id']}/fichas/A", json=FICHA)
    assert resp.status_code == 200
    f = resp.json()
    assert f["no_id"] == "A"
    assert f["campos"]["origem"] == "API do Tiflux"
    assert f["campos"]["execucao"] == "automatico"
    assert f["campos"]["observacoes"] == ""      # campo não enviado fica vazio (= a levantar)
    assert [x["no_id"] for x in _minhas(client, diagrama["id"])] == ["A"]


def test_salvar_de_novo_substitui(client, diagrama):
    client.put(f"/api/diagramas/{diagrama['id']}/fichas/A", json=FICHA)
    assert client.put(f"/api/diagramas/{diagrama['id']}/fichas/A",
                      json={"acao": "  Outra ação  "}).status_code == 200
    fichas = _minhas(client, diagrama["id"])
    assert len(fichas) == 1
    assert fichas[0]["campos"]["acao"] == "Outra ação" and fichas[0]["campos"]["origem"] == ""


@pytest.mark.parametrize("payload, motivo", [
    ({}, "ficha vazia"),
    ({"acao": "   "}, "só espaços"),
    ({"acao": "x", "execucao": "robo"}, "execução inválida"),
    ({"acao": "x" * 1501}, "texto grande demais"),
])
def test_rejeita_ficha_invalida(client, diagrama, payload, motivo):
    resp = client.put(f"/api/diagramas/{diagrama['id']}/fichas/A", json=payload)
    assert resp.status_code in (400, 422), motivo


def test_id_de_etapa_invalido_e_diagrama_inexistente(client, diagrama):
    assert client.put(f"/api/diagramas/{diagrama['id']}/fichas/a-b", json=FICHA).status_code == 400
    assert client.put("/api/diagramas/999999/fichas/A", json=FICHA).status_code == 404


def test_excluir_ficha_e_excluir_diagrama_leva_as_fichas(client, diagrama):
    client.put(f"/api/diagramas/{diagrama['id']}/fichas/A", json=FICHA)
    client.put(f"/api/diagramas/{diagrama['id']}/fichas/B", json=FICHA)
    assert client.delete(f"/api/diagramas/{diagrama['id']}/fichas/A").status_code == 200
    assert client.delete(f"/api/diagramas/{diagrama['id']}/fichas/A").status_code == 404
    assert [x["no_id"] for x in _minhas(client, diagrama["id"])] == ["B"]
    client.delete(f"/api/diagramas/{diagrama['id']}")
    assert _minhas(client, diagrama["id"]) == []
