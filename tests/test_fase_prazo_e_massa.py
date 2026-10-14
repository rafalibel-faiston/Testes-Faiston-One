"""Prazo das fases e montagem da fase em massa.

O que estes testes protegem: o prazo é o que a diretoria cobra por região, então
data salva errada (ou apagada sem querer) vira cobrança errada. E montar a fase
tem que funcionar de uma vez — pela planilha ou por "todos do filtro" —, sem
roubar técnico de outra fase quando ninguém pediu.
"""
from tests.conftest import planilha


# --------------------------------------------------------------- prazo


def test_fase_guarda_inicio_e_prazo(client):
    fase = client.post("/api/piloto/fases", json={
        "nome": "Fase 1", "data_inicio": "2026-10-01", "prazo": "31/10/2026",
    }).json()
    # DD/MM/AAAA digitado à mão vira o mesmo formato do <input type=date>
    assert fase["data_inicio"] == "2026-10-01"
    assert fase["prazo"] == "2026-10-31"
    assert client.get("/api/piloto/fases").json()[0]["prazo"] == "2026-10-31"


def test_editar_fase_sem_mandar_prazo_nao_apaga(client):
    fase = client.post("/api/piloto/fases", json={"nome": "Fase 1", "prazo": "2026-10-31"}).json()
    client.patch(f"/api/piloto/fases/{fase['id']}", json={"nome": "Fase 1 — SP"})
    assert client.get("/api/piloto/fases").json()[0]["prazo"] == "2026-10-31"

    # string vazia é o jeito explícito de limpar
    client.patch(f"/api/piloto/fases/{fase['id']}", json={"prazo": ""})
    assert client.get("/api/piloto/fases").json()[0]["prazo"] is None


def test_prazo_invalido_ou_antes_do_inicio_e_recusado(client):
    resp = client.post("/api/piloto/fases", json={"nome": "Fase 1", "prazo": "amanhã"})
    assert resp.status_code == 400

    resp = client.post("/api/piloto/fases", json={
        "nome": "Fase 1", "data_inicio": "2026-10-10", "prazo": "2026-10-01",
    })
    assert resp.status_code == 400


# --------------------------------------------------------------- em massa


def _cadastra(client, *nomes, regional="Campinas"):
    ids = []
    for i, nome in enumerate(nomes):
        ids.append(client.post("/api/tecnicos", json={
            "nome": nome, "telefone": f"1198888{i:04d}", "regional": regional,
        }).json()["id"])
    return ids


def test_adicionar_todos_sem_filtro_pega_a_base_sem_fase(client):
    _cadastra(client, "Ana", "Bruno", "Carla")
    fase = client.post("/api/piloto/fases", json={"nome": "Fase 1"}).json()

    resp = client.post(f"/api/piloto/fases/{fase['id']}/tecnicos", json={"todos": True})
    assert resp.json() == {"adicionados": 3, "na_fase": 3}


def test_payload_vazio_nao_joga_a_base_inteira_na_fase(client):
    _cadastra(client, "Ana")
    fase = client.post("/api/piloto/fases", json={"nome": "Fase 1"}).json()
    resp = client.post(f"/api/piloto/fases/{fase['id']}/tecnicos", json={})
    assert resp.status_code == 400


def test_todos_nao_rouba_de_outra_fase(client):
    ana, _ = _cadastra(client, "Ana", "Bruno")
    fase1 = client.post("/api/piloto/fases", json={"nome": "Fase 1"}).json()
    fase2 = client.post("/api/piloto/fases", json={"nome": "Fase 2"}).json()
    client.post(f"/api/piloto/fases/{fase1['id']}/tecnicos", json={"tecnico_ids": [ana]})

    resp = client.post(f"/api/piloto/fases/{fase2['id']}/tecnicos", json={"todos": True})
    assert resp.json() == {"adicionados": 1, "na_fase": 1}


def test_importar_planilha_direto_na_fase(client):
    fase = client.post("/api/piloto/fases", json={"nome": "Fase 2"}).json()
    arquivo = planilha([
        ["Ana Souza", "11988880001", "Campinas"],
        ["Bruno Dias", "11988880002", "Campinas"],
        ["Carla Nunes", "", "Campinas"],          # rejeitada: não entra em fase nenhuma
    ])
    dados = client.post(
        "/api/tecnicos/importar",
        files={"file": ("fase2.xlsx", arquivo)}, data={"fase_id": str(fase["id"])},
    ).json()

    assert dados["criados"] == 2
    assert dados["fases"] == [{"id": fase["id"], "nome": "Fase 2", "tecnicos": 2}]
    assert len(client.get(f"/api/tecnicos?fase_id={fase['id']}").json()) == 2
    assert client.get("/api/piloto/fases").json()[0]["status"] == "em_andamento"


def test_importar_na_fase_move_quem_ja_estava_na_base(client):
    """Quem já foi importado antes (sem fase ou em outra) entra na fase pela
    planilha nova — subir a lista da fase é escolha explícita."""
    ana, = _cadastra(client, "Ana Souza")
    fase1 = client.post("/api/piloto/fases", json={"nome": "Fase 1"}).json()
    fase2 = client.post("/api/piloto/fases", json={"nome": "Fase 2"}).json()
    client.post(f"/api/piloto/fases/{fase1['id']}/tecnicos", json={"tecnico_ids": [ana]})
    token_antigo = client.get(f"/api/tecnicos?fase_id={fase1['id']}").json()[0]["token"]

    arquivo = planilha([["Ana Souza", "11988880000", "Campinas"]])
    dados = client.post(
        "/api/tecnicos/importar",
        files={"file": ("f.xlsx", arquivo)}, data={"fase_id": str(fase2["id"])},
    ).json()
    assert dados["atualizados"] == 1

    na_fase2 = client.get(f"/api/tecnicos?fase_id={fase2['id']}").json()
    assert [t["id"] for t in na_fase2] == [ana]
    # teste novo na fase nova: link do formulário trocado
    assert na_fase2[0]["token"] != token_antigo


def test_importar_em_fase_inexistente_da_404(client):
    arquivo = planilha([["Ana Souza", "11988880001", "Campinas"]])
    resp = client.post(
        "/api/tecnicos/importar", files={"file": ("f.xlsx", arquivo)}, data={"fase_id": "999999"},
    )
    assert resp.status_code == 404
    assert client.get("/api/tecnicos").json() == []


def test_coluna_fase_distribui_a_planilha_e_cria_fase_nova(client):
    client.post("/api/piloto/fases", json={"nome": "Fase 1 — SP"})
    arquivo = planilha(
        [
            ["Ana Souza", "11988880001", "fase 1 — sp"],    # casa sem diferenciar maiúscula
            ["Bruno Dias", "11988880002", "Fase 2 — RJ"],   # não existe: é criada
            ["Carla Nunes", "11988880003", ""],             # sem fase: fica na base
        ],
        cabecalho=["Nome", "Telefone", "Fase"],
    )
    dados = client.post("/api/tecnicos/importar", files={"file": ("f.xlsx", arquivo)}).json()

    assert dados["criados"] == 3
    assert dados["fases_criadas"] == ["Fase 2 — RJ"]
    por_nome = {f["nome"]: f for f in client.get("/api/piloto/fases").json()}
    assert por_nome["Fase 1 — SP"]["total_tecnicos"] == 1
    assert por_nome["Fase 2 — RJ"]["total_tecnicos"] == 1
    assert client.get("/api/tecnicos/base?sem_fase=1").json()["total"] == 1


def test_coluna_parecida_com_fase_nao_cria_fase(client):
    """Base exportada de outro sistema pode ter "Fase do contrato" — não é o piloto."""
    arquivo = planilha(
        [["Ana Souza", "11988880001", "Renovação"]],
        cabecalho=["Nome", "Telefone", "Fase do contrato"],
    )
    dados = client.post("/api/tecnicos/importar", files={"file": ("f.xlsx", arquivo)}).json()
    assert dados["criados"] == 1
    assert dados["fases_criadas"] == []
    assert client.get("/api/piloto/fases").json() == []
