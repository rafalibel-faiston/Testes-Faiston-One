"""Os dois níveis de teste: o meu e o da operação.

O que motivou isso: um caso passava na minha mão, virava "Aprovado" e sumia
da pauta — mas na operação o mesmo caso não funcionava. Agora cada caso é
testado duas vezes, em níveis separados, e só fica Aprovado de verdade quando
os dois passam. Estes testes seguram exatamente essa promessa.
"""
import pytest

from app import niveis


# --------------------------------------------------------------- a regra

@pytest.mark.parametrize("interno,operacao,esperado", [
    ("Aprovado", "Aprovado", "Aprovado"),
    # o ponto central: passar comigo não é passar na operação
    ("Aprovado", "Não testado", "Validação interna"),
    ("Não testado", "Aprovado", "Validação operação"),
    ("Não testado", "Não testado", "Não testado"),
    # problema em qualquer nível derruba o caso inteiro
    ("Aprovado", "Reprovado", "Reprovado"),
    ("Reprovado", "Aprovado", "Reprovado"),
    ("Aprovado", "Bloqueado", "Bloqueado"),
    ("Bloqueado", "Reprovado", "Reprovado"),
    # N/A num nível = aquele nível não se aplica; quem decide é o outro
    ("N/A", "Aprovado", "Aprovado"),
    ("Aprovado", "N/A", "Aprovado"),
    ("N/A", "Não testado", "Não testado"),
    ("N/A", "N/A", "N/A"),
])
def test_consolidado_dos_dois_niveis(interno, operacao, esperado):
    assert niveis.status_geral(interno, operacao) == esperado


def test_nivel_aceita_os_apelidos_do_dia_a_dia():
    assert niveis.normaliza_nivel(None) == "interno"
    assert niveis.normaliza_nivel("operação") == "operacao"
    with pytest.raises(ValueError):
        niveis.normaliza_nivel("qualquer coisa")


# --------------------------------------------------------------- casos de teste

@pytest.fixture
def caso(client):
    """Um caso novo, criado pela tela — zerado nos dois níveis."""
    resp = client.post("/api/cases", json={
        "estagio": "01 · Níveis de teste",
        "resultado_esperado": "O caso guarda meu teste e o da operação separados",
    })
    assert resp.status_code == 201
    yield resp.json()
    client.delete(f"/api/cases/{resp.json()['code']}")


def test_caso_nasce_zerado_nos_dois_niveis(caso):
    assert caso["status"] == "Não testado"
    assert caso["status_operacao"] == "Não testado"
    assert caso["status_geral"] == "Não testado"


def test_meu_aprovado_sozinho_nao_aprova_o_caso(client, caso):
    code = caso["code"]
    resp = client.patch(f"/api/cases/{code}", json={"status": "Aprovado", "testado_por": "Rafael"})
    dados = resp.json()
    assert dados["status"] == "Aprovado"
    assert dados["status_operacao"] == "Não testado"
    # é isso que antes virava "Aprovado" e enganava a reunião
    assert dados["status_geral"] == "Validação interna"
    assert dados["testado_em"] is not None

    dados = client.patch(f"/api/cases/{code}", json={
        "status_operacao": "Aprovado", "testado_por_operacao": "Operação",
    }).json()
    assert dados["status_geral"] == "Aprovado"
    # cada nível guarda quem testou; um não sobrescreve o outro
    assert dados["testado_por"] == "Rafael"
    assert dados["testado_por_operacao"] == "Operação"
    assert dados["testado_em_operacao"] is not None


def test_reprovado_na_operacao_derruba_o_caso_aprovado_por_mim(client, caso):
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado"})
    dados = client.patch(f"/api/cases/{code}", json={"status_operacao": "Reprovado"}).json()
    assert dados["status_geral"] == "Reprovado"
    # o meu teste continua registrado como estava — o que falhou foi a operação
    assert dados["status"] == "Aprovado"


def test_chamado_de_cada_nivel_vive_separado(client, caso):
    code = caso["code"]
    dados = client.patch(f"/api/cases/{code}", json={
        "chamado": "221193", "chamado_operacao": "221207",
    }).json()
    assert dados["chamado"] == "221193"
    assert dados["chamado_operacao"] == "221207"


def test_status_invalido_no_nivel_operacao_e_recusado(client, caso):
    resp = client.patch(f"/api/cases/{caso['code']}", json={"status_operacao": "Quase"})
    assert resp.status_code == 400


def test_observacao_sabe_de_qual_teste_veio(client, caso):
    code = caso["code"]
    client.post(f"/api/cases/{code}/observacoes", json={"texto": "Funcionou no meu ambiente"})
    dados = client.post(f"/api/cases/{code}/observacoes", json={
        "texto": "Na operação travou na hora de salvar", "nivel": "operacao",
    }).json()
    assert [o["nivel"] for o in dados["observations"]] == ["interno", "operacao"]


def test_resumo_separa_o_consolidado_de_cada_nivel(client, caso):
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado"})
    resumo = client.get("/api/summary").json()

    # o caso conta como "Validação interna" no consolidado, mas como aprovado
    # na leitura do meu nível — as duas coisas são verdade ao mesmo tempo
    assert resumo["counts"]["Validação interna"] >= 1
    assert resumo["counts_interno"]["Aprovado"] >= 1
    assert resumo["counts_operacao"]["Não testado"] >= 1
    assert resumo["total"] == sum(resumo["counts"].values())
    assert resumo["pct_executado_operacao"] <= resumo["pct_executado_interno"]


def test_exportacao_mostra_os_dois_niveis_e_o_consolidado(client, caso):
    from io import BytesIO

    from openpyxl import load_workbook

    client.patch(f"/api/cases/{caso['code']}", json={"status": "Aprovado"})
    resp = client.get("/api/export?fluxo=C")
    assert resp.status_code == 200
    ws = load_workbook(BytesIO(resp.content)).active
    cabecalho = [c.value for c in ws[3]]
    assert cabecalho[-3:] == ["Meu teste", "Operação", "Status"]
    # a linha do caso traz o consolidado na última coluna, não o meu status
    linha = next(r for r in ws.iter_rows(values_only=True) if r[3] == caso["resultado_esperado"])
    assert linha[-3:] == ("Aprovado", "Não testado", "Validação interna")


# --------------------------------------------------------------- situações

@pytest.fixture
def estagio(client):
    """Uma situação com um estágio — o mesmo modelo de dois níveis."""
    sit = client.post("/api/situacoes", json={
        "titulo": "Chamado sem aceite", "descricao": "O técnico não aceita o chamado",
    }).json()
    sit = client.post(f"/api/situacoes/{sit['code']}/estagios", json={
        "nome": "01 · Criar chamado", "resultado_esperado": "Chamado criado",
    }).json()
    yield sit["code"], sit["estagios"][0]["id"]
    client.delete(f"/api/situacoes/{sit['code']}")


def test_estagio_de_situacao_tambem_tem_os_dois_niveis(client, estagio):
    code, estagio_id = estagio
    sit = client.patch(f"/api/situacoes/{code}/estagios/{estagio_id}", json={
        "status": "Aprovado", "testado_por": "Rafael",
    }).json()
    est = sit["estagios"][0]
    assert est["status_geral"] == "Validação interna"

    sit = client.patch(f"/api/situacoes/{code}/estagios/{estagio_id}", json={
        "status_operacao": "Aprovado", "testado_por_operacao": "Operação",
    }).json()
    est = sit["estagios"][0]
    assert est["status_geral"] == "Aprovado"
    assert est["testado_por_operacao"] == "Operação"


def test_situacao_guarda_o_chamado_da_operacao(client, estagio):
    code, _ = estagio
    sit = client.patch(f"/api/situacoes/{code}", json={
        "chamado": "221193", "chamado_operacao": "221207",
    }).json()
    assert (sit["chamado"], sit["chamado_operacao"]) == ("221193", "221207")


def test_pauta_cobra_o_que_so_passou_no_meu_teste(client, caso):
    """O caso aprovado só por mim tem que continuar aparecendo na reunião."""
    code = caso["code"]
    client.patch(f"/api/cases/{code}", json={"status": "Aprovado"})
    html = client.get("/relatorio").text
    assert code in html
    assert "Falta a operação" in html or "esperando a operação" in html
