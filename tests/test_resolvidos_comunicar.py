"""Reprovado que virou Aprovado deixa um lembrete pra avisar a operação.

O que motivou isso: o bug é corrigido, o teste passa e ninguém conta pra
operação — que continua achando que o problema existe. Estes testes seguram a
promessa: toda virada de Reprovado para Aprovado (em qualquer nível, em qualquer
lugar onde o status muda) gera um item com a mensagem já rascunhada, e só some
da lista quando alguém marca que comunicou.
"""
import pytest

from app import mcp_server, resolvidos


@pytest.fixture(autouse=True)
def lista_limpa(client):
    """Cada teste começa sem lembretes — o que um cria não pode vazar pro outro."""
    from app import models
    from app.database import SessionLocal

    def limpa():
        db = SessionLocal()
        try:
            db.query(models.ResolvidoComunicar).delete(synchronize_session=False)
            # o SQLite de teste reaproveita códigos/ids depois de apagar (FC-MAN-01,
            # AJT-8): sem limpar a trilha, o histórico de um teste anterior vazaria
            # pro resgate do seguinte. No Postgres os ids não se repetem.
            db.query(models.ActivityLog).filter(
                models.ActivityLog.tipo.in_(("status", "ajuste"))
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    limpa()
    yield
    limpa()


def pendentes(client):
    return client.get("/api/resolvidos", params={"comunicado": "false"}).json()


@pytest.fixture
def caso(client):
    resp = client.post("/api/cases", json={
        "estagio": "03 · Aceite do chamado", "frente": "App do técnico",
        "resultado_esperado": "O técnico aceita o chamado e a OS muda de estágio",
    })
    assert resp.status_code == 201
    yield resp.json()
    client.delete(f"/api/cases/{resp.json()['code']}")


@pytest.fixture
def estagio(client):
    sit = client.post("/api/situacoes", json={
        "titulo": "Chamado sem aceite", "descricao": "O técnico não aceita o chamado",
    }).json()
    sit = client.post(f"/api/situacoes/{sit['code']}/estagios", json={
        "nome": "01 · Criar chamado", "resultado_esperado": "Chamado criado",
    }).json()
    yield sit["code"], sit["estagios"][0]["id"]
    client.delete(f"/api/situacoes/{sit['code']}")


@pytest.fixture
def ajuste(client):
    resp = client.post("/api/ativos/ajustes", json={
        "titulo": "Entrada não calcula o total", "tipo": "Bug", "versao": "v9",
        "atual": "Soma errado quando tem desconto", "esperado": "Somar certo",
    })
    assert resp.status_code == 201
    yield resp.json()
    client.delete(f"/api/ativos/ajustes/{resp.json()['id']}")


# --------------------------------------------------------------- a regra

@pytest.mark.parametrize("antes,depois,gera", [
    ("Reprovado", "Aprovado", True),
    # só o que estava quebrado e foi consertado conta
    ("Bloqueado", "Aprovado", False),
    ("Não testado", "Aprovado", False),
    ("Aprovado", "Aprovado", False),
    ("Reprovado", "Reprovado", False),
    ("Aprovado", "Reprovado", False),
    ("Reprovado", "N/A", False),
])
def test_so_reprovado_para_aprovado_gera_lembrete(antes, depois, gera):
    assert resolvidos.virou_aprovado(antes, depois) is gera


# --------------------------------------------------------------- caso de teste

def test_caso_reprovado_que_a_tecnica_aprova_vira_lembrete(client, caso):
    code = caso["code"]
    client.post(f"/api/cases/{code}/observacoes", json={
        "autor": "Rafael", "cor": "vermelho", "texto": "Botão Aceitar não responde",
    })
    client.patch(f"/api/cases/{code}", json={"status": "Reprovado", "testado_por": "Rafael"})
    assert pendentes(client) == []          # reprovar sozinho não gera nada

    client.patch(f"/api/cases/{code}", json={
        "status": "Aprovado", "testado_por": "Rafael", "chamado": "221207",
    })
    itens = pendentes(client)
    assert len(itens) == 1
    item = itens[0]
    assert (item["origem"], item["codigo"], item["nivel"]) == ("caso", code, "interno")
    assert item["resolvido_por"] == "Rafael"
    assert item["comunicado"] is False
    # a mensagem já sai pronta: o problema, o esperado, quem aprovou e o chamado
    msg = item["mensagem"]
    assert code in msg
    assert "Botão Aceitar não responde" in msg
    assert "O técnico aceita o chamado e a OS muda de estágio" in msg
    assert "Validação técnica" in msg and "Rafael" in msg
    assert "221207" in msg
    assert "operação confira" in msg        # técnica aprovou: pede a validação da operação


def test_aprovar_sem_ter_reprovado_nao_gera_lembrete(client, caso):
    client.patch(f"/api/cases/{caso['code']}", json={"status": "Aprovado"})
    assert pendentes(client) == []


def test_aprovacao_da_operacao_tambem_gera_e_muda_o_pedido(client, caso):
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status_operacao": "Reprovado"})
    client.patch(f"/api/cases/{code}", json={
        "status_operacao": "Aprovado", "testado_por_operacao": "Estoque",
    })
    (item,) = pendentes(client)
    assert item["nivel"] == "operacao"
    assert "Validação na operação" in item["mensagem"]
    assert "operação confira" not in item["mensagem"]   # ela mesma já validou


def test_reprovar_e_aprovar_de_novo_nao_duplica_o_lembrete_em_aberto(client, caso):
    code = caso["code"]
    for _ in range(2):
        client.patch(f"/api/cases/{code}", json={"status": "Reprovado"})
        client.patch(f"/api/cases/{code}", json={"status": "Aprovado", "testado_por": "Rafael"})
    assert len(pendentes(client)) == 1


def test_depois_de_comunicado_uma_nova_virada_abre_outro_lembrete(client, caso):
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status": "Reprovado"})
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado"})
    (item,) = pendentes(client)
    client.patch(f"/api/resolvidos/{item['id']}", json={"comunicado": True})

    client.patch(f"/api/cases/{code}", json={"status": "Reprovado"})
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado"})
    assert len(pendentes(client)) == 1
    assert len(client.get("/api/resolvidos").json()) == 2   # o histórico fica


# --------------------------------------------------------------- marcar como comunicado

def test_marcar_comunicado_tira_da_lista_e_registra_quem_e_quando(client, caso):
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status": "Reprovado"})
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado"})
    (item,) = pendentes(client)

    dados = client.patch(f"/api/resolvidos/{item['id']}", json={
        "comunicado": True, "comunicado_por": "Rafael",
    }).json()
    assert dados["comunicado"] is True
    assert dados["comunicado_por"] == "Rafael"
    assert dados["comunicado_em"] is not None
    assert pendentes(client) == []

    # clicou sem querer: desfazer devolve pra lista, sem lixo de quem/quando
    dados = client.patch(f"/api/resolvidos/{item['id']}", json={"comunicado": False}).json()
    assert dados["comunicado_em"] is None and dados["comunicado_por"] is None
    assert len(pendentes(client)) == 1


def test_item_inexistente_da_404(client):
    assert client.patch("/api/resolvidos/999999", json={"comunicado": True}).status_code == 404


# --------------------------------------------------------------- situações

def test_estagio_de_situacao_reprovado_que_aprova_vira_lembrete(client, estagio):
    code, estagio_id = estagio
    url = f"/api/situacoes/{code}/estagios/{estagio_id}"
    client.post(f"{url}/observacoes", json={
        "autor": "Rafael", "cor": "vermelho", "texto": "Chamado não aparece na fila",
    })
    client.patch(url, json={"status": "Reprovado"})
    assert pendentes(client) == []
    client.patch(url, json={"status": "Aprovado", "testado_por": "Rafael"})

    (item,) = pendentes(client)
    assert (item["origem"], item["codigo"]) == ("situacao", code)
    assert "Chamado não aparece na fila" in item["mensagem"]
    assert "Chamado criado" in item["mensagem"]


# --------------------------------------------------------------- gestão de ativos

def test_ajuste_reprovado_que_valida_diz_que_e_correcao_de_bug(client, ajuste):
    aid = ajuste["id"]
    client.patch(f"/api/ativos/ajustes/{aid}", json={"status": "entregue", "validacao": "Reprovado"})
    assert pendentes(client) == []
    client.patch(f"/api/ativos/ajustes/{aid}", json={
        "validacao": "Aprovado", "validado_por": "Rafael",
    })

    (item,) = pendentes(client)
    assert (item["origem"], item["codigo"], item["fluxo"]) == ("ajuste", f"AJT-{aid}", "ATIVOS")
    assert "correção de bug" in item["mensagem"]
    assert "Soma errado quando tem desconto" in item["mensagem"]


def test_melhoria_aprovada_diz_que_e_melhoria(client):
    a = client.post("/api/ativos/ajustes", json={
        "titulo": "Filtro por fornecedor", "tipo": "Melhoria", "versao": "v9",
    }).json()
    try:
        client.patch(f"/api/ativos/ajustes/{a['id']}", json={"validacao": "Reprovado"})
        client.patch(f"/api/ativos/ajustes/{a['id']}", json={"validacao": "Aprovado"})
        (item,) = pendentes(client)
        assert "melhoria" in item["mensagem"]
        assert "correção de bug" not in item["mensagem"]
    finally:
        client.delete(f"/api/ativos/ajustes/{a['id']}")


# --------------------------------------------------------------- MCP

def test_mcp_atualizar_status_gera_o_lembrete_e_da_pra_marcar(client, caso):
    code = caso["code"]
    mcp_server.atualizar_status_caso(code, "Reprovado")
    mcp_server.atualizar_status_caso(code, "Aprovado", testado_por="Rafael")

    (item,) = mcp_server.listar_resolvidos_para_comunicar()
    assert item["codigo"] == code and "Rafael" in item["mensagem"]

    feito = mcp_server.marcar_resolvido_comunicado(item["id"], comunicado_por="Rafael")
    assert feito["comunicado"] is True
    assert mcp_server.listar_resolvidos_para_comunicar() == []
    assert len(mcp_server.listar_resolvidos_para_comunicar(incluir_comunicados=True)) == 1
    assert "erro" in mcp_server.marcar_resolvido_comunicado(999999)


def test_mcp_validar_ajuste_gera_o_lembrete(client, ajuste):
    aid = ajuste["id"]
    mcp_server.validar_ajuste_ativos(aid, "Reprovado")
    mcp_server.validar_ajuste_ativos(aid, "Aprovado", validado_por="Rafael")
    (item,) = mcp_server.listar_resolvidos_para_comunicar()
    assert item["codigo"] == f"AJT-{aid}"


# --------------------------------------------------------------- tela e pauta

def test_api_devolve_o_nome_do_nivel_pra_tela(client, caso):
    client.patch(f"/api/cases/{caso['code']}", json={"status": "Reprovado"})
    client.patch(f"/api/cases/{caso['code']}", json={"status": "Aprovado"})
    (item,) = pendentes(client)
    assert item["nivel_label"] == "Validação técnica"


def test_pauta_lista_o_que_falta_avisar_e_esconde_o_ja_avisado(client, caso):
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status": "Reprovado"})
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado", "testado_por": "Rafael"})

    html = client.get("/relatorio").text
    assert 'id="resolvidos"' in html
    assert "Resolvidos — avisar a operação" in html
    assert code in html

    (item,) = pendentes(client)
    client.patch(f"/api/resolvidos/{item['id']}", json={"comunicado": True})
    html = client.get("/relatorio").text
    assert 'id="resolvidos"' not in html     # nada a comunicar: a seção some


# --------------------------------------------------------------- resgate do histórico

def apaga_lembretes():
    """Simula o banco de antes do recurso: a trilha de Novidades existe, o lembrete não."""
    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        db.query(models.ResolvidoComunicar).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def resgatar(client, **params):
    resp = client.post("/api/resolvidos/resgatar", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_resgate_acha_a_virada_antiga_pela_trilha_e_so_simula_por_padrao(client, caso):
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status": "Reprovado", "testado_por": "Rafael"})
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado", "testado_por": "Rafael"})
    apaga_lembretes()

    simulacao = resgatar(client)
    meus = [i for i in simulacao["itens"] if i["codigo"] == code]
    assert len(meus) == 1 and meus[0]["novo"] is True and meus[0]["resolvido_por"] == "Rafael"
    assert simulacao["aplicado"] is False
    assert pendentes(client) == []          # simular não grava nada


def test_resgate_aplicado_cria_o_lembrete_e_rodar_de_novo_nao_duplica(client, caso):
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status": "Reprovado"})
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado", "testado_por": "Rafael"})
    apaga_lembretes()

    resgatar(client, aplicar="true")
    (item,) = [i for i in pendentes(client) if i["codigo"] == code]
    assert "Rafael" in item["mensagem"]
    assert item["created_at"] is not None

    segunda = resgatar(client, aplicar="true")
    assert [i for i in segunda["itens"] if i["codigo"] == code][0]["novo"] is False
    assert len([i for i in pendentes(client) if i["codigo"] == code]) == 1


def test_resgate_nao_duplica_o_que_ja_nasceu_ao_vivo(client, caso):
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status": "Reprovado"})
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado"})    # lembrete já criado
    resgatar(client, aplicar="true")
    assert len([i for i in pendentes(client) if i["codigo"] == code]) == 1


def test_resgate_respeita_a_regra_de_passar_por_nao_testado(client, caso):
    code = caso["code"]
    for status in ("Reprovado", "Não testado", "Aprovado"):
        client.patch(f"/api/cases/{code}", json={"status": status})
    apaga_lembretes()
    assert [i for i in resgatar(client)["itens"] if i["codigo"] == code] == []


def test_resgate_separa_os_niveis_e_os_estagios_da_situacao(client, estagio):
    code, estagio_id = estagio
    extra = client.post(f"/api/situacoes/{code}/estagios", json={
        "nome": "02 · Técnico aceita", "resultado_esperado": "Aceito",
    }).json()["estagios"][-1]["id"]
    for eid in (estagio_id, extra):
        url = f"/api/situacoes/{code}/estagios/{eid}"
        client.patch(url, json={"status": "Reprovado"})
        client.patch(url, json={"status": "Aprovado"})
    # ao vivo também: dois estágios da mesma situação não se fundem num item só
    assert len([i for i in pendentes(client) if i["codigo"] == code]) == 2
    apaga_lembretes()

    resgatar(client, aplicar="true")
    meus = [i for i in pendentes(client) if i["codigo"] == code]
    assert len(meus) == 2                    # um por estágio, sem se fundirem
    assert {"01 · Criar chamado" in m["titulo"] for m in meus} == {True, False}


def test_resgate_ignora_teste_excluido_e_filtra_por_data(client, caso):
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status": "Reprovado"})
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado"})
    apaga_lembretes()

    assert [i for i in resgatar(client, desde="2999-01-01")["itens"] if i["codigo"] == code] == []
    assert client.post("/api/resolvidos/resgatar", params={"desde": "ontem"}).status_code == 400

    client.delete(f"/api/cases/{code}")
    assert [i for i in resgatar(client)["itens"] if i["codigo"] == code] == []


def test_resgate_acha_a_virada_antiga_de_ajuste(client, ajuste):
    aid = ajuste["id"]
    client.patch(f"/api/ativos/ajustes/{aid}", json={"validacao": "Reprovado"})
    client.patch(f"/api/ativos/ajustes/{aid}", json={"validacao": "Aprovado", "validado_por": "Rafael"})
    apaga_lembretes()
    resgatar(client, aplicar="true")
    (item,) = [i for i in pendentes(client) if i["codigo"] == f"AJT-{aid}"]
    assert "correção de bug" in item["mensagem"]


def test_mcp_resgatar_simula_e_aplica(client, caso):
    code = caso["code"]
    mcp_server.atualizar_status_caso(code, "Reprovado")
    mcp_server.atualizar_status_caso(code, "Aprovado")
    apaga_lembretes()
    assert mcp_server.resgatar_resolvidos_antigos()["aplicado"] is False
    assert mcp_server.listar_resolvidos_para_comunicar() == []
    mcp_server.resgatar_resolvidos_antigos(aplicar=True)
    assert any(i["codigo"] == code for i in mcp_server.listar_resolvidos_para_comunicar())
