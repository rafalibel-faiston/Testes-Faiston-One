"""Fases do piloto, ponte com o backlog e a limpeza da base.

São as três coisas que, se quebrarem sem ninguém ver, custam caro: perder o
controle de quem está em qual leva, perder o vínculo entre o relato e o item que
a LP vai corrigir, ou apagar a base sem querer.
"""
import pytest


# --------------------------------------------------------------- fases


def test_fase_recebe_a_regional_inteira_de_uma_vez(client):
    for nome, regional in [("Ana", "Campinas"), ("Bruno", "Campinas"), ("Carla", "Santos")]:
        client.post("/api/tecnicos", json={
            "nome": nome, "telefone": f"1198888{abs(hash(nome)) % 10000:04d}", "regional": regional,
        })
    fase = client.post("/api/piloto/fases", json={"nome": "Fase 1 — Campinas"}).json()

    resp = client.post(f"/api/piloto/fases/{fase['id']}/tecnicos", json={"regional": "Campinas"})
    assert resp.json() == {"adicionados": 2, "na_fase": 2}

    # entrar gente na fase é o que a tira do papel
    assert client.get("/api/piloto/fases").json()[0]["status"] == "em_andamento"
    assert len(client.get(f"/api/tecnicos?fase_id={fase['id']}").json()) == 2


def test_fase_nao_rouba_tecnico_de_outra_fase(client):
    tecnico = client.post("/api/tecnicos", json={
        "nome": "Ana", "telefone": "11988887777", "regional": "Campinas",
    }).json()
    fase1 = client.post("/api/piloto/fases", json={"nome": "Fase 1"}).json()
    fase2 = client.post("/api/piloto/fases", json={"nome": "Fase 2"}).json()
    client.post(f"/api/piloto/fases/{fase1['id']}/tecnicos", json={"tecnico_ids": [tecnico["id"]]})

    # uma seleção ampla na fase 2 não pode esvaziar a fase 1
    resp = client.post(f"/api/piloto/fases/{fase2['id']}/tecnicos", json={"regional": "Campinas"})
    assert resp.json()["adicionados"] == 0

    # mover é decisão explícita
    resp = client.post(f"/api/piloto/fases/{fase2['id']}/tecnicos", json={
        "regional": "Campinas", "incluir_de_outras_fases": True,
    })
    assert resp.json()["adicionados"] == 1


def test_excluir_fase_devolve_os_tecnicos_pra_base(client, tecnico):
    fase = client.post("/api/piloto/fases", json={"nome": "Fase 1"}).json()
    client.post(f"/api/piloto/fases/{fase['id']}/tecnicos", json={"tecnico_ids": [tecnico["id"]]})

    resp = client.delete(f"/api/piloto/fases/{fase['id']}")
    assert resp.json()["tecnicos_soltos"] == 1
    assert len(client.get("/api/tecnicos").json()) == 1        # ninguém foi apagado
    assert client.get("/api/tecnicos").json()[0]["fase_id"] is None


def test_base_completa_vem_paginada_e_sem_observacoes(client):
    for i in range(12):
        client.post("/api/tecnicos", json={"nome": f"Tecnico {i:02d}", "telefone": f"11988880{i:03d}"})

    dados = client.get("/api/tecnicos/base?sem_fase=1&limite=5").json()
    assert dados["total"] == 12
    assert len(dados["itens"]) == 5
    # a lista leve não carrega observações — é o que segurava a tela com milhares
    assert "observacoes" not in dados["itens"][0]

    pagina2 = client.get("/api/tecnicos/base?sem_fase=1&limite=5&offset=5").json()
    assert dados["itens"][0]["id"] != pagina2["itens"][0]["id"]


def test_painel_usa_as_metas_da_fase(client, tecnico):
    """Cada leva tem a sua régua: uma fase pequena não pode ser cobrada pela meta
    de uma grande."""
    fase = client.post("/api/piloto/fases", json={
        "nome": "Fase 1", "meta_concluidos": 1, "meta_nota": 4, "meta_etapa": 1,
    }).json()
    client.post(f"/api/piloto/fases/{fase['id']}/tecnicos", json={"tecnico_ids": [tecnico["id"]]})
    client.post(f"/api/formulario/{tecnico['token']}", json={
        "nota": 5,
        "etapas": ["Recebi o chamado no app", "Acompanhei o rastreio da peça",
                   "Confirmei o recebimento do equipamento", "Fechei a RAT pelo app"],
        "positivo": "funcionou",
    })

    painel = client.get(f"/api/tecnicos/piloto?fase_id={fase['id']}").json()
    assert painel["fase"]["nome"] == "Fase 1"
    assert painel["liberado"] is True
    assert painel["notas"]["media"] == 5.0


# --------------------------------------------------------------- backlog


def test_relato_vira_item_do_backlog_e_fica_amarrado(client, tecnico):
    client.post(f"/api/formulario/{tecnico['token']}", json={"problema": "notificação não chega"})
    obs = client.get("/api/tecnicos").json()[0]["observacoes"][0]

    resp = client.post(f"/api/tecnicos/observacoes/{obs['id']}/virar-ajuste", json={
        "titulo": "Notificação de peça não dispara",
        "esperado": "Push assim que a peça chega na base",
    })
    assert resp.status_code == 200
    virada = resp.json()["observacoes"][0]
    assert virada["ajuste_ref"] is not None        # o card passa a mostrar "v2 #07"

    ajuste = [a for a in client.get("/api/ativos/ajustes").json() if a["id"] == virada["ajuste_id"]][0]
    assert ajuste["tipo"] == "Bug"                 # relato de problema vira bug
    assert ajuste["atual"] == "notificação não chega"
    assert tecnico["nome"] in ajuste["observacao"]  # a origem fica registrada


def test_melhoria_vira_melhoria_e_nao_bug(client, tecnico):
    client.post(f"/api/formulario/{tecnico['token']}", json={"melhoria": "podia salvar sozinho"})
    obs = client.get("/api/tecnicos").json()[0]["observacoes"][0]
    client.post(f"/api/tecnicos/observacoes/{obs['id']}/virar-ajuste", json={"titulo": "Salvar sozinho"})

    novo = client.get("/api/tecnicos").json()[0]["observacoes"][0]
    ajuste = [a for a in client.get("/api/ativos/ajustes").json() if a["id"] == novo["ajuste_id"]][0]
    assert ajuste["tipo"] == "Melhoria"


def test_mesmo_relato_nao_vira_dois_itens(client, tecnico):
    client.post(f"/api/formulario/{tecnico['token']}", json={"problema": "notificação não chega"})
    obs = client.get("/api/tecnicos").json()[0]["observacoes"][0]
    client.post(f"/api/tecnicos/observacoes/{obs['id']}/virar-ajuste", json={"titulo": "Primeiro"})

    resp = client.post(f"/api/tecnicos/observacoes/{obs['id']}/virar-ajuste", json={"titulo": "Segundo"})
    assert resp.status_code == 400


def test_varios_relatos_iguais_apontam_pro_mesmo_item(client):
    """Dez técnicos reclamando da mesma coisa têm que virar um item com dez
    relatos, não dez linhas duplicadas no backlog."""
    ids = []
    for i, nome in enumerate(["Ana", "Bruno", "Carla"]):
        t = client.post("/api/tecnicos", json={"nome": nome, "telefone": f"1198888000{i}"}).json()
        client.post(f"/api/formulario/{t['token']}", json={"problema": "notificação não chega"})
        ids.append(client.get(f"/api/tecnicos?busca={nome}").json()[0]["observacoes"][0]["id"])

    primeiro = client.post(f"/api/tecnicos/observacoes/{ids[0]}/virar-ajuste", json={
        "titulo": "Notificação não dispara"}).json()
    ajuste_id = primeiro["observacoes"][0]["ajuste_id"]
    for obs_id in ids[1:]:
        client.post(f"/api/tecnicos/observacoes/{obs_id}/vincular-ajuste", json={"ajuste_id": ajuste_id})

    ranking = client.get("/api/tecnicos/piloto").json()["ranking_ajustes"]
    assert ranking[0]["relatos"] == 3
    assert len([a for a in client.get("/api/ativos/ajustes").json()
                if a["titulo"] == "Notificação não dispara"]) == 1


# --------------------------------------------------------------- limpeza


@pytest.mark.parametrize("confirmacao", ["", "sim", "apagar tudo"])
def test_base_so_e_zerada_com_a_palavra_exata(client, tecnico, confirmacao):
    resp = client.post("/api/tecnicos/limpar", json={"confirmar": confirmacao})
    assert resp.status_code == 400
    assert len(client.get("/api/tecnicos").json()) == 1       # nada foi apagado


def test_limpar_leva_o_feedback_junto(client, tecnico):
    client.post(f"/api/formulario/{tecnico['token']}", json={"problema": "algo"})
    resp = client.post("/api/tecnicos/limpar", json={"confirmar": "APAGAR"})

    assert resp.json() == {"tecnicos_apagados": 1, "observacoes_apagadas": 1}
    assert client.get("/api/tecnicos").json() == []
    # o link do formulário dele para de funcionar junto
    assert client.get(f"/formulario/{tecnico['token']}").status_code == 404
