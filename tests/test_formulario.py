"""O formulário que o técnico responde no celular.

É a peça que dispensa entrevistar um a um: o que ele escreve tem que chegar na
base já classificado, sem ninguém digitar nada.
"""


def test_pagina_abre_pelo_link_do_tecnico(client, tecnico):
    resp = client.get(f"/formulario/{tecnico['token']}")
    assert resp.status_code == 200
    # o técnico é recebido pelo primeiro nome, não pelo nome completo do cadastro
    assert "Oi, <b>Carlos</b>" in resp.text


def test_link_invalido_mostra_pagina_e_nao_erro_tecnico(client):
    resp = client.get("/formulario/naoexiste")
    assert resp.status_code == 404
    assert "Link não encontrado" in resp.text      # quem abre isso não é dev


def test_resposta_vira_feedback_classificado_no_card(client, tecnico):
    resp = client.post(f"/api/formulario/{tecnico['token']}", json={
        "nota": 4,
        "etapas": ["Recebi o chamado no app", "Fechei a RAT pelo app"],
        "positivo": "O rastreio da peça ajudou muito",
        "melhoria": "A tela da RAT podia salvar sozinha",
        "problema": "A notificação não chegou",
        "comentario": "No geral gostei",
        "chamado": "221207",
    })
    assert resp.status_code == 200
    dados = resp.json()

    assert dados["nota"] == 4
    assert dados["etapas_testadas"] == "Recebi o chamado no app|Fechei a RAT pelo app"
    assert dados["respondido_em"] is not None
    # responder é ter testado: o funil anda sozinho
    assert dados["status"] == "concluido"

    por_tipo = {o["tipo"]: o["texto"] for o in dados["observacoes"]}
    assert por_tipo["positivo"] == "O rastreio da peça ajudou muito"
    assert por_tipo["melhoria"] == "A tela da RAT podia salvar sozinha"
    assert por_tipo["problema"] == "A notificação não chegou"
    assert por_tipo[None] == "No geral gostei"     # campo livre = nota geral
    # o chamado fica em cada relato: é por ele que se investiga o caso no NEXO
    assert all(o["chamado"] == "221207" for o in dados["observacoes"])


def test_campo_em_branco_nao_vira_relato_vazio(client, tecnico):
    dados = client.post(f"/api/formulario/{tecnico['token']}", json={
        "nota": 5, "positivo": "tudo certo", "melhoria": "", "problema": "   ",
    }).json()
    assert len(dados["observacoes"]) == 1


def test_formulario_vazio_e_recusado(client, tecnico):
    resp = client.post(f"/api/formulario/{tecnico['token']}", json={})
    assert resp.status_code == 400


def test_responder_de_novo_soma_em_vez_de_apagar(client, tecnico):
    """Ele testou de novo num segundo atendimento e tem mais a dizer."""
    client.post(f"/api/formulario/{tecnico['token']}", json={"nota": 3, "problema": "travou"})
    dados = client.post(f"/api/formulario/{tecnico['token']}", json={
        "nota": 5, "positivo": "melhorou muito",
    }).json()

    assert len(dados["observacoes"]) == 2          # o relato antigo continua lá
    assert dados["nota"] == 5                      # a nota é a do retorno mais novo


def test_relato_guarda_a_versao_que_a_fase_estava_testando(client, tecnico):
    """Se a LP subir build nova no meio do piloto, o que já foi relatado precisa
    continuar apontando pra versão em que aconteceu."""
    fase = client.post("/api/piloto/fases", json={"nome": "Fase 1", "versao_app": "1.0.0"}).json()
    client.post(f"/api/piloto/fases/{fase['id']}/tecnicos", json={"tecnico_ids": [tecnico["id"]]})

    client.post(f"/api/formulario/{tecnico['token']}", json={"problema": "notificação não chega"})
    client.patch(f"/api/piloto/fases/{fase['id']}", json={"versao_app": "1.1.0"})
    client.post(f"/api/formulario/{tecnico['token']}", json={"problema": "agora a tela some"})

    versoes = [o["versao_app"] for o in client.get("/api/tecnicos").json()[0]["observacoes"]]
    assert versoes == ["1.0.0", "1.1.0"]
