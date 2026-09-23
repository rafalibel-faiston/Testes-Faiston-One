"""O nome padrão do chamado de teste no Tiflux.

A promessa: todo teste do console tem um nome no mesmo formato, e refazer o
teste gera um nome parecido mas nunca igual a um já usado.
"""
import pytest

from app import nomes_tiflux


# --------------------------------------------------------------- a regra

def test_formato_padrao():
    nome = nomes_tiflux.montar("fc-04-app-02", "interno", 1, 'Mostra "Aguardando início" (não "Em rota")')
    assert nome == "[TESTE IA] - FC-04-APP-02 - T01 - MOSTRA AGUARDANDO INÍCIO (NÃO EM ROTA)"


def test_operacao_tem_letra_propria():
    assert " - O03 - " in nomes_tiflux.montar("SIT-01", "operacao", 3, "Chamado sem aceite")


def test_resumo_longo_e_cortado_numa_palavra_inteira():
    texto = "O técnico registra Acesso Liberado e então toca Iniciar Atendimento — sem etapa de liberação pelo operador"
    nome = nomes_tiflux.montar("FC-06-APP-04", "interno", 12, texto)
    assert len(nome) <= nomes_tiflux.MAX_TITULO
    assert nome.startswith("[TESTE IA] - FC-06-APP-04 - T12 - O TÉCNICO REGISTRA")
    # termina numa palavra do texto original, não no meio dela
    assert texto.upper().replace("—", "").split().count(nome.split()[-1]) >= 1


def test_sem_descricao_fica_so_a_base():
    assert nomes_tiflux.montar("FC-MAN-01", "interno", 1, "") == "[TESTE IA] - FC-MAN-01 - T01"


# --------------------------------------------------------------- a API

@pytest.fixture
def caso(client):
    resp = client.post("/api/cases", json={
        "estagio": "03 · Téc. Aceitou",
        "resultado_esperado": "Ao aceitar, o chamado sai da lista e o passo avança",
    })
    assert resp.status_code == 201
    yield resp.json()
    client.delete(f"/api/cases/{resp.json()['code']}")


def _gerar(client, code, nivel="interno"):
    resp = client.post("/api/nomes-tiflux", json={"code": code, "nivel": nivel, "gerado_por": "Rafa"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_refazer_o_teste_gera_a_proxima_rodada(client, caso):
    code = caso["code"]
    primeiro = _gerar(client, code)
    segundo = _gerar(client, code)
    assert primeiro["nome"] == f"[TESTE IA] - {code} - T01 - AO ACEITAR, O CHAMADO SAI DA LISTA E O PASSO AVANÇA"
    assert segundo["seq"] == 2 and " - T02 - " in segundo["nome"]
    assert primeiro["nome"] != segundo["nome"]


def test_operacao_conta_separado_da_tecnica(client, caso):
    code = caso["code"]
    _gerar(client, code)
    _gerar(client, code)
    op = _gerar(client, code, "operação")
    assert op["nivel"] == "operacao" and op["seq"] == 1 and " - O01 - " in op["nome"]


def test_situacao_usa_o_titulo(client):
    sit = client.get("/api/situacoes").json()[0]
    nome = _gerar(client, sit["code"])
    assert nome["tipo"] == "situacao"
    assert nome["nome"].startswith(f"[TESTE IA] - {sit['code']} - T")


def test_historico_por_teste(client, caso):
    code = caso["code"]
    _gerar(client, code)
    _gerar(client, code)
    nomes = client.get("/api/nomes-tiflux", params={"code": code.lower()}).json()
    assert [n["seq"] for n in nomes] == [1, 2]
    assert all(n["gerado_por"] == "Rafa" for n in nomes)


def test_teste_inexistente_e_nivel_invalido(client, caso):
    assert client.post("/api/nomes-tiflux", json={"code": "FC-NAO-EXISTE"}).status_code == 404
    assert client.post("/api/nomes-tiflux", json={"code": caso["code"], "nivel": "xyz"}).status_code == 400
