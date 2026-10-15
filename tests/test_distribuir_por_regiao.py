"""Distribuição da base pelas fases conforme a UF de cada técnico.

O que estes testes protegem: a base do Brasil inteiro sobe numa planilha só e
cada técnico cai na fase que tem a UF dele marcada — sem tirar ninguém de uma
fase em que já está, sem usar fase encerrada e sem dar a fase planejada como
começada.
"""
from tests.conftest import planilha

CAB = ["Técnico", "Tipo", "UF", "Agente", "Telefone"]
BASE = [
    ["ANA ES", "Direto", "ES", "ES PARC1", 27911111111],
    ["BIA MG", "Direto", "MG", "MG PARC2", 31922222222],
    ["CAIO SP", "Direto", "SP", "SP PARC3", 11933333333],
    ["DUDA RS", "Direto", "RS", "RS PARC4", 51944444444],
    ["EDU BA", "Direto", "BA", "BA PARC5", 71955555555],
]


def _fase(client, nome, ufs, **extra):
    return client.post("/api/piloto/fases", json={"nome": nome, "ufs": ufs, **extra}).json()


def _importa(client, linhas=BASE, **form):
    resp = client.post("/api/tecnicos/importar",
                       files={"file": ("base.xlsx", planilha(linhas, cabecalho=CAB))}, data=form)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fase_de(client):
    fases = {f["id"]: f["nome"] for f in client.get("/api/piloto/fases").json()}
    return {t["nome"]: fases.get(t["fase_id"]) for t in client.get("/api/tecnicos").json()}


def test_importar_com_distribuir_poe_cada_um_na_fase_da_uf(client):
    _fase(client, "Fase 1 — Sudeste", ["ES", "MG", "SP", "RJ"])
    _fase(client, "Fase 2 — Sul", ["RS", "SC", "PR"])
    dados = _importa(client, distribuir="true")

    dist = dados["distribuicao"]
    assert dist["distribuidos"] == 4
    assert {f["nome"]: f["tecnicos"] for f in dist["fases"]} == {"Fase 1 — Sudeste": 3, "Fase 2 — Sul": 1}
    assert dist["ufs_sem_fase"] == {"BA": 1}
    assert _fase_de(client) == {
        "ANA ES": "Fase 1 — Sudeste", "BIA MG": "Fase 1 — Sudeste", "CAIO SP": "Fase 1 — Sudeste",
        "DUDA RS": "Fase 2 — Sul", "EDU BA": None,
    }
    # fase planejada recebe o pessoal mas continua planejada
    assert {f["status"] for f in client.get("/api/piloto/fases").json()} == {"planejada"}


def test_importar_sem_distribuir_deixa_na_base(client):
    _fase(client, "Fase 1", ["ES"])
    dados = _importa(client)
    assert dados["distribuicao"] is None
    assert set(_fase_de(client).values()) == {None}


def test_distribuir_nao_tira_quem_ja_esta_em_fase_nem_usa_fase_concluida(client):
    _importa(client)
    antiga = _fase(client, "Antiga", ["SP"])
    caio = next(t for t in client.get("/api/tecnicos").json() if t["nome"] == "CAIO SP")
    client.post(f"/api/piloto/fases/{antiga['id']}/tecnicos", json={"tecnico_ids": [caio["id"]]})
    client.patch(f"/api/piloto/fases/{antiga['id']}", json={"status": "concluida"})
    encerrada = _fase(client, "Encerrada", ["BA"])
    client.patch(f"/api/piloto/fases/{encerrada['id']}", json={"status": "concluida"})
    _fase(client, "Sudeste", ["ES", "MG", "SP"])

    dist = client.post("/api/piloto/fases/distribuir").json()
    assert dist["distribuidos"] == 2           # ANA e BIA; o CAIO já tinha fase
    assert dist["ufs_sem_fase"] == {"BA": 1, "RS": 1}
    fases = _fase_de(client)
    assert fases["CAIO SP"] == "Antiga"
    assert fases["EDU BA"] is None


def test_uf_em_duas_fases_vai_pra_primeira_e_avisa(client):
    _fase(client, "Primeira", ["SP"])
    _fase(client, "Segunda", ["SP", "MG"])
    _importa(client, BASE[1:3])
    dist = client.post("/api/piloto/fases/distribuir").json()
    assert dist["ufs_em_mais_de_uma_fase"] == [{"uf": "SP", "fases": ["Primeira", "Segunda"]}]
    assert _fase_de(client) == {"BIA MG": "Segunda", "CAIO SP": "Primeira"}


def test_regional_que_nao_e_uf_conta_como_sem_uf(client):
    _fase(client, "Fase SP", ["SP"])
    client.post("/api/tecnicos", json={"nome": "Velho", "telefone": "11999990000", "regional": "SP capital"})
    dist = client.post("/api/piloto/fases/distribuir").json()
    assert dist["distribuidos"] == 0 and dist["sem_uf"] == 1
