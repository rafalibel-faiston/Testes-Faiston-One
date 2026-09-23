"""O nome padrão do chamado de teste no Tiflux.

A promessa: todo teste — de um card do console ou avulso — tem um nome no
mesmo formato, e refazer o teste gera um nome parecido mas nunca igual a um
já usado.
"""
import pytest

from app import nomes_tiflux


# --------------------------------------------------------------- a regra

def test_formato_padrao():
    nome = nomes_tiflux.montar('Mostra "Aguardando início" (não "Em rota")', "interno", 1)
    assert nome == "[TESTE IA] - T01 - MOSTRA AGUARDANDO INÍCIO (NÃO EM ROTA)"


def test_operacao_tem_marca_propria():
    assert nomes_tiflux.montar("Chamado sem aceite", "operacao", 3).startswith("[TESTE IA] - OP03 - ")


def test_assunto_longo_e_cortado_numa_palavra_inteira():
    texto = "O técnico registra Acesso Liberado e então toca Iniciar Atendimento — sem etapa de liberação pelo operador"
    tec = nomes_tiflux.montar(texto, "interno", 12)
    op = nomes_tiflux.montar(texto, "operacao", 12)
    assert len(op) <= nomes_tiflux.MAX_TITULO
    assert tec.startswith("[TESTE IA] - T12 - O TÉCNICO REGISTRA ACESSO LIBERADO")
    # o assunto sai igual nos dois níveis, só a rodada muda
    assunto = nomes_tiflux.assunto_do_nome(tec)
    assert assunto == nomes_tiflux.assunto_do_nome(op)
    assert (texto.upper() + " ").startswith(assunto + " ")


def test_assunto_com_hifen_se_mantem_inteiro():
    nome = nomes_tiflux.montar("Fluxo B - técnico retira", "interno", 1)
    assert nome == "[TESTE IA] - T01 - FLUXO B - TÉCNICO RETIRA"
    assert nomes_tiflux.assunto_do_nome(nome) == "FLUXO B - TÉCNICO RETIRA"


def test_nome_antigo_colado_nao_duplica_o_prefixo():
    assert nomes_tiflux.montar("[TESTE IA] - Teste distância", "interno", 1) == "[TESTE IA] - T01 - TESTE DISTÂNCIA"


def test_chave_ignora_acento_e_caixa():
    assert nomes_tiflux.chave("Teste distância") == nomes_tiflux.chave("TESTE DISTANCIA")


# --------------------------------------------------------------- a API

@pytest.fixture(autouse=True)
def sem_nomes_gerados():
    """A rodada conta pelo assunto e nunca volta — sem limpar, um teste
    continuaria a sequência do anterior."""
    from app import models
    from app.database import SessionLocal

    yield
    db = SessionLocal()
    try:
        db.query(models.NomeTiflux).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def caso(client):
    resp = client.post("/api/cases", json={
        "estagio": "03 · Téc. Aceitou",
        "resultado_esperado": "Ao aceitar, o chamado sai da lista e o passo avança",
    })
    assert resp.status_code == 201
    yield resp.json()
    client.delete(f"/api/cases/{resp.json()['code']}")


def _gerar(client, **body):
    body.setdefault("gerado_por", "Rafa")
    resp = client.post("/api/nomes-tiflux", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_card_gera_o_nome_sem_o_codigo(client, caso):
    nome = _gerar(client, code=caso["code"])
    assert nome["nome"] == "[TESTE IA] - T01 - AO ACEITAR, O CHAMADO SAI DA LISTA E O PASSO AVANÇA"
    assert caso["code"] not in nome["nome"]
    assert nome["alvo"] == caso["code"] and nome["tipo"] == "caso"


def test_refazer_o_teste_gera_a_proxima_rodada(client):
    primeiro = _gerar(client, assunto="Atribuir técnico manualmente")
    segundo = _gerar(client, assunto="atribuir tecnico manualmente")
    assert primeiro["nome"] == "[TESTE IA] - T01 - ATRIBUIR TÉCNICO MANUALMENTE"
    # digitado sem acento, mas sai com o texto da primeira rodada: só o número muda
    assert segundo["nome"] == "[TESTE IA] - T02 - ATRIBUIR TÉCNICO MANUALMENTE"
    assert primeiro["tipo"] == "avulso" and primeiro["alvo"] is None


def test_operacao_conta_separado_da_tecnica(client):
    _gerar(client, assunto="Chat com N2")
    _gerar(client, assunto="Chat com N2")
    op = _gerar(client, assunto="Chat com N2", nivel="operação")
    assert op["nivel"] == "operacao" and op["nome"] == "[TESTE IA] - OP01 - CHAT COM N2"


def test_dois_testes_com_o_mesmo_assunto_nunca_repetem_o_nome(client, caso):
    """O código saiu do nome, então a rodada conta pelo assunto: um teste
    avulso com o mesmo texto do card continua a sequência dele."""
    do_card = _gerar(client, code=caso["code"])
    avulso = _gerar(client, assunto=caso["resultado_esperado"])
    assert do_card["nome"] != avulso["nome"]
    assert avulso["nome"].startswith("[TESTE IA] - T02 - ")


def test_situacao_usa_o_titulo(client):
    sit = client.get("/api/situacoes").json()[0]
    nome = _gerar(client, code=sit["code"])
    assert nome["tipo"] == "situacao"
    assert nome["nome"] == "[TESTE IA] - T01 - " + nomes_tiflux.assunto(sit["titulo"])
    assert sit["code"] not in nome["nome"]


def test_historico_por_card(client, caso):
    code = caso["code"]
    _gerar(client, code=code)
    _gerar(client, code=code)
    nomes = client.get("/api/nomes-tiflux", params={"code": code.lower()}).json()
    assert [n["seq"] for n in nomes] == [1, 2]
    assert all(n["gerado_por"] == "Rafa" for n in nomes)


def test_pedidos_invalidos(client, caso):
    assert client.post("/api/nomes-tiflux", json={"code": "FC-NAO-EXISTE"}).status_code == 404
    assert client.post("/api/nomes-tiflux", json={"assunto": "x", "nivel": "xyz"}).status_code == 400
    assert client.post("/api/nomes-tiflux", json={"assunto": "  --  "}).status_code == 400
    assert client.post("/api/nomes-tiflux", json={}).status_code == 400
