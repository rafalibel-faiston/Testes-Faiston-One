"""Importação da base de técnicos.

O que estes testes protegem: numa planilha real de milhares de linhas, boa parte
não entra (telefone repetido, vazio, inválido) e a pessoa precisa saber quais e
por quê. E reimportar a base corrigida tem que atualizar quem já existe, nunca
duplicar.
"""
from tests.conftest import planilha


def test_importa_planilha_com_colunas_de_outro_sistema(client):
    """A base vem exportada de outro sistema, com colunas que o módulo não usa:
    o que importa é achar Nome e Telefone no meio delas."""
    arquivo = planilha(
        [["1001", "Carlos Lima", "12.345.678-9", "Rua X", "São Paulo", "(11) 98888-7777", "c@x.com"]],
        cabecalho=["Código", "Nome", "RG", "Endereço", "Endereço - Cidade", "Telefone", "Email"],
    )
    resp = client.post("/api/tecnicos/importar", files={"file": ("base.xlsx", arquivo)})
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["criados"] == 1
    assert dados["rejeitados"] == 0

    tecnico = client.get("/api/tecnicos").json()[0]
    assert tecnico["nome"] == "Carlos Lima"
    # telefone brasileiro sem DDI ganha o 55 sozinho
    assert tecnico["telefone"] == "5511988887777"
    # "Endereço - Cidade" vira a regional, mesmo sem se chamar "regional"
    assert tecnico["regional"] == "São Paulo"


def test_relatorio_diz_por_que_cada_linha_ficou_de_fora(client):
    arquivo = planilha([
        ["Ana Souza", "11988887777", "São Paulo"],
        ["Bruno Dias", "11988887777", "São Paulo"],   # mesmo telefone da Ana
        ["Carla Nunes", "", "Campinas"],              # sem telefone
        ["Diego Reis", "3333", "Campinas"],           # telefone inválido
        ["", "", ""],                                 # linha em branco: não é erro
    ])
    dados = client.post("/api/tecnicos/importar", files={"file": ("base.xlsx", arquivo)}).json()

    assert dados["criados"] == 1
    assert dados["rejeitados"] == 3
    assert dados["linhas_em_branco"] == 1
    assert dados["resumo"] == {
        "telefone repetido na planilha": 1, "sem telefone": 1, "telefone inválido": 1,
    }
    # o relatório aponta a linha da planilha, pra pessoa corrigir no arquivo dela
    linhas_com_erro = {e["linha"] for e in dados["erros"]}
    assert linhas_com_erro == {3, 4, 5}


def test_reimportar_atualiza_em_vez_de_duplicar(client):
    arquivo = planilha([["Carlos Lima", "11988887777", "São Paulo"]])
    client.post("/api/tecnicos/importar", files={"file": ("base.xlsx", arquivo)})

    # a planilha volta corrigida: nome completo e outra cidade, mesmo telefone
    corrigida = planilha([["Carlos Eduardo Lima", "11988887777", "Campinas"]])
    dados = client.post("/api/tecnicos/importar", files={"file": ("base.xlsx", corrigida)}).json()

    assert dados["criados"] == 0
    assert dados["atualizados"] == 1
    tecnicos = client.get("/api/tecnicos").json()
    assert len(tecnicos) == 1                      # não duplicou
    assert tecnicos[0]["nome"] == "Carlos Eduardo Lima"
    assert tecnicos[0]["regional"] == "Campinas"


def test_reimportar_nao_apaga_o_progresso_de_qa(client):
    """Cadastro vem da planilha; andamento do teste, não. Reimportar não pode
    zerar status, nota nem feedback de quem já testou."""
    arquivo = planilha([["Carlos Lima", "11988887777", "São Paulo"]])
    client.post("/api/tecnicos/importar", files={"file": ("base.xlsx", arquivo)})
    tecnico = client.get("/api/tecnicos").json()[0]
    client.post(f"/api/formulario/{tecnico['token']}", json={"nota": 5, "positivo": "muito bom"})

    client.post("/api/tecnicos/importar", files={"file": ("base.xlsx", planilha(
        [["Carlos Lima", "11988887777", "São Paulo"]]))})

    depois = client.get("/api/tecnicos").json()[0]
    assert depois["nota"] == 5
    assert depois["status"] == "concluido"
    assert len(depois["observacoes"]) == 1


def test_planilha_sem_as_colunas_obrigatorias_e_recusada(client):
    arquivo = planilha([["algum dado"]], cabecalho=["Coluna estranha"])
    resp = client.post("/api/tecnicos/importar", files={"file": ("base.xlsx", arquivo)})
    assert resp.status_code == 400
    assert "nome" in resp.json()["detail"]


def test_arquivo_que_nao_e_planilha_e_recusado(client):
    resp = client.post("/api/tecnicos/importar", files={"file": ("base.csv", b"nome;telefone")})
    assert resp.status_code == 400
