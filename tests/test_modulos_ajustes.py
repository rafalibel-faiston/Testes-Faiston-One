"""Módulos do backlog de ajustes: catálogo, migração, seed das pendências da LPD,
numeração por módulo, e a presença do módulo na pauta e no export."""
import io
import re

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import modulos, models, seed_data
from app.database import Base, SessionLocal
from app.routers import ativos

NOVOS = ["plataforma", "financeiro", "projetos"]


def _ajustes(client, **filtros):
    return client.get("/api/ativos/ajustes", params=filtros).json()


def _novo(client, **campos):
    corpo = {"titulo": "Item de teste", "atual": "hoje", "esperado": "amanhã", **campos}
    resp = client.post("/api/ativos/ajustes", json=corpo)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ----------------------------------------------------------------- catálogo

def test_catalogo_tem_os_quatro_modulos_na_ordem_das_abas(client):
    cat = client.get("/api/ativos/modulos").json()
    assert [m["key"] for m in cat] == ["ativos", *NOVOS]
    assert {m["key"]: m["versao_padrao"] for m in cat} == {
        "ativos": "v2", "plataforma": "v1", "financeiro": "v1",
        "projetos": "v1",
    }
    assert all(m["label"] and m["titulo"] and m["descricao"] for m in cat)


def test_norm_modulo_nunca_levanta_e_cai_em_ativos():
    for lixo in (None, "", "   ", "nao-existe", 123, 0, [], {}, object()):
        assert modulos.norm_modulo(lixo) == "ativos"
    assert modulos.norm_modulo("  Financeiro ") == "financeiro"
    # o Fluxo A deixou de ser módulo (virou situações do Fluxo A): a chave cai no padrão
    assert modulos.norm_modulo("fluxo-a") == "ativos"
    assert modulos.versao_padrao("nao-existe") == "v2"
    assert modulos.versao_padrao("projetos") == "v1"
    assert modulos.label("plataforma") == "Geral"
    # o módulo Dashboard foi incorporado ao Geral: a chave antiga cai lá, não em "ativos"
    assert modulos.norm_modulo("dashboard") == "plataforma"
    assert modulos.norm_modulo(" Dashboard ") == "plataforma"
    assert modulos.label("dashboard") == "Geral"
    assert modulos.label(None) == "Gestão de Ativos"


# ----------------------------------------------------------------- migração

def test_migracao_adiciona_modulo_num_banco_antigo(tmp_path):
    """Um banco de antes desta mudança não tem a coluna: os itens que já existem
    precisam virar "ativos", e rodar de novo não pode quebrar nem alterar nada."""
    engine = create_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE ativo_ajustes (id INTEGER PRIMARY KEY, versao VARCHAR NOT NULL DEFAULT 'v2', "
            "numero INTEGER NOT NULL DEFAULT 0, titulo VARCHAR NOT NULL, "
            "status VARCHAR NOT NULL DEFAULT 'levantado')"))
        conn.execute(text("INSERT INTO ativo_ajustes (versao, numero, titulo) VALUES ('v2', 1, 'Antigo 1')"))
        conn.execute(text("INSERT INTO ativo_ajustes (versao, numero, titulo) VALUES ('v3', 1, 'Antigo 2')"))
    assert "modulo" not in {c["name"] for c in inspect(engine).get_columns("ativo_ajustes")}

    assert seed_data.migrate_schema(engine) > 0
    colunas = {c["name"]: c for c in inspect(engine).get_columns("ativo_ajustes")}
    assert "modulo" in colunas
    assert colunas["modulo"]["nullable"] is False
    with engine.connect() as conn:
        linhas = conn.execute(text("SELECT titulo, modulo FROM ativo_ajustes ORDER BY id")).all()
    assert [tuple(l) for l in linhas] == [("Antigo 1", "ativos"), ("Antigo 2", "ativos")]
    assert "ix_ativo_ajustes_modulo" in {i["name"] for i in inspect(engine).get_indexes("ativo_ajustes")}

    # segunda rodada: não tenta o ALTER de novo (senão estouraria "duplicate column")
    seed_data.migrate_schema(engine)
    assert [c["name"] for c in inspect(engine).get_columns("ativo_ajustes")].count("modulo") == 1
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM ativo_ajustes WHERE modulo='ativos'")).scalar() == 2


# --------------------------------------------------------------------- seed

def test_seed_das_pendencias_lpd_em_banco_limpo_e_idempotente():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        assert seed_data.seed_pendencias_lpd(db) == 8
        assert seed_data.seed_pendencias_lpd(db) == 0     # segunda rodada não duplica
        itens = db.query(models.AtivoAjuste).all()
        assert len(itens) == 8

        por_modulo = {}
        for a in itens:
            por_modulo.setdefault(a.modulo, []).append(a)
        assert {k: len(v) for k, v in por_modulo.items()} == {
            "plataforma": 6, "financeiro": 1, "projetos": 1}
        for a in itens:
            assert (a.versao, a.status, a.responsavel, a.autor) == ("v1", "levantado", "LPD", "Pendências LPD")
        # numeração começa em 1 em cada módulo, sem buraco
        for lista in por_modulo.values():
            assert sorted(a.numero for a in lista) == list(range(1, len(lista) + 1))

        # editar o que o time mexeu na tela não é desfeito pelo redeploy
        sla = next(a for a in itens if a.titulo.startswith("Cálculo do SLA"))
        sla.status, sla.numero = "analise", 9
        db.commit()
        assert seed_data.seed_pendencias_lpd(db) == 0
        db.refresh(sla)
        assert (sla.status, sla.numero) == ("analise", 9)
    finally:
        db.close()


def test_pendencias_lpd_conteudo_conforme_a_lista(client):
    por_titulo = {a["titulo"]: a for a in _ajustes(client, versao="v1")}
    assert len(por_titulo) == 8
    # os 7 itens da finalização do Fluxo A moraram aqui antes; agora são situações do Fluxo A
    assert not [t for t in por_titulo if "chamado" in t.lower() and "reaparece" in t.lower()]
    assert not [a for a in por_titulo.values() if a["tipo"] == "Bug"]

    def prio(trecho):
        return {a["prioridade"] for t, a in por_titulo.items() if trecho in t}

    assert prio("Cálculo do SLA") == {"Alta"}
    assert prio("Google Play") == {"Alta"} and prio("Apple App Store") == {"Alta"}
    assert prio("Relatórios") == {"Média"}

    # onde a lista da LPD só nomeia a entrega, o item diz que o escopo não foi detalhado
    for titulo in ("Cálculo do SLA dentro do sistema", "Módulo Financeiro", "Fluxo de Projetos"):
        assert "escopo ainda não foi detalhado" in por_titulo[titulo]["atual"]


def test_seed_do_ativos_original_fica_no_modulo_ativos(client):
    v2 = _ajustes(client, modulo="ativos", versao="v2")
    assert len(v2) == len(seed_data.AJUSTES_GESTAO_ATIVOS_V2)
    assert all(a["modulo"] == "ativos" for a in v2)
    db = SessionLocal()
    try:
        assert seed_data.seed_ativos_ajustes(db) == 0
        assert seed_data.seed_pendencias_lpd(db) == 0
    finally:
        db.close()


# ----------------------------------------------------------- numeração e API

def test_numeracao_e_independente_por_modulo(client):
    def proximo(modulo, versao):
        itens = _ajustes(client, modulo=modulo, versao=versao)
        return max(a["numero"] for a in itens) + 1

    esperado = {m: proximo(m, "v1") for m in ("financeiro", "plataforma", "projetos")}
    esperado_ativos = proximo("ativos", "v2")
    for modulo in ("financeiro", "plataforma", "projetos"):
        assert _novo(client, modulo=modulo)["numero"] == esperado[modulo]
    assert _novo(client, modulo="ativos", versao="v2")["numero"] == esperado_ativos
    # o segundo item do financeiro segue a sequência do financeiro, não a do resto
    assert _novo(client, modulo="financeiro")["numero"] == esperado["financeiro"] + 1


def test_versao_e_modulo_opcionais_na_criacao(client):
    padrao = _novo(client)
    assert (padrao["modulo"], padrao["versao"]) == ("ativos", "v2")
    fin = _novo(client, modulo="financeiro")
    assert (fin["modulo"], fin["versao"]) == ("financeiro", "v1")
    outra = _novo(client, modulo="financeiro", versao="3")
    assert outra["versao"] == "v3" and outra["numero"] == 1      # leva nova abre do 1


def test_modulo_invalido_cai_em_ativos(client):
    criado = _novo(client, modulo="modulo-que-nao-existe")
    assert (criado["modulo"], criado["versao"]) == ("ativos", "v2")
    # no filtro também: o desconhecido lista o que é de "ativos"
    assert {a["id"] for a in _ajustes(client, modulo="xpto")} == \
           {a["id"] for a in _ajustes(client, modulo="ativos")}
    # e no PATCH: não leva o item pra um módulo que não existe
    r = client.patch(f"/api/ativos/ajustes/{criado['id']}", json={"modulo": "xpto"})
    assert r.status_code == 200 and r.json()["modulo"] == "ativos"


def test_filtro_por_modulo(client):
    for modulo in NOVOS:
        itens = _ajustes(client, modulo=modulo)
        assert itens and {a["modulo"] for a in itens} == {modulo}
    assert len(_ajustes(client, modulo="projetos")) == 1
    assert len(_ajustes(client, modulo="plataforma")) == 6
    # a chave antiga do Dashboard filtra o Geral
    assert {a["id"] for a in _ajustes(client, modulo="dashboard")} == {a["id"] for a in _ajustes(client, modulo="plataforma")}
    assert {a["modulo"] for a in _ajustes(client)} >= {"ativos", *NOVOS}      # sem filtro: todos
    assert _ajustes(client, modulo="plataforma", tipo="Bug") == []


def test_mover_item_de_modulo_renumera_pro_fim_sem_pular_lugar(client):
    # o item nasce no fim de "ativos v2" (número alto) e vai pro financeiro
    item = _novo(client, modulo="ativos", versao="v2")
    assert item["numero"] >= 8
    maior_financeiro = max(a["numero"] for a in _ajustes(client, modulo="financeiro", versao="v1"))

    movido = client.patch(f"/api/ativos/ajustes/{item['id']}", json={"modulo": "financeiro"}).json()
    assert movido["modulo"] == "financeiro"
    assert movido["versao"] == "v1"                       # leva padrão do destino
    assert movido["numero"] == maior_financeiro + 1       # não herda o #8 de origem

    fin = sorted(a["numero"] for a in _ajustes(client, modulo="financeiro", versao="v1"))
    assert fin == list(range(1, len(fin) + 1))            # sem buraco no destino
    # e a origem não fica com o item
    assert item["id"] not in {a["id"] for a in _ajustes(client, modulo="ativos")}
    # o próximo item da origem reaproveita o lugar que o movido deixou
    assert _novo(client, modulo="ativos", versao="v2")["numero"] == item["numero"]


def test_mover_de_versao_dentro_do_modulo_ignora_o_proprio_item(client):
    item = _novo(client, modulo="projetos")               # projetos v1, #2 (o seed tem o #1)
    movido = client.patch(f"/api/ativos/ajustes/{item['id']}", json={"versao": "v2"}).json()
    assert (movido["modulo"], movido["versao"], movido["numero"]) == ("projetos", "v2", 1)

    db = SessionLocal()
    try:
        # ignorar_id: o número do próprio item não empurra o contador onde ele já está
        assert ativos._next_numero(db, "projetos", "v2") == 2
        assert ativos._next_numero(db, "projetos", "v2", ignorar_id=item["id"]) == 1
    finally:
        db.close()


def test_mover_com_modulo_e_versao_explicitos(client):
    item = _novo(client, modulo="ativos")
    movido = client.patch(f"/api/ativos/ajustes/{item['id']}",
                          json={"modulo": "plataforma", "versao": "v4"}).json()
    assert (movido["modulo"], movido["versao"], movido["numero"]) == ("plataforma", "v4", 1)


# ------------------------------------------------- técnico, Novidades, MCP

def _relato_do_tecnico(client, tecnico, texto="notificação não chega"):
    client.post(f"/api/formulario/{tecnico['token']}", json={"problema": texto})
    return client.get("/api/tecnicos").json()[0]["observacoes"][0]


def test_relato_do_tecnico_vira_ajuste_em_ativos_mesmo_com_outros_modulos_mais_novos(client, tecnico):
    # um módulo novo numa leva "mais alta" não pode puxar o relato pra lá
    _novo(client, modulo="financeiro", versao="v9")
    obs = _relato_do_tecnico(client, tecnico)

    resp = client.post(f"/api/tecnicos/observacoes/{obs['id']}/virar-ajuste", json={
        "titulo": "Notificação não dispara", "esperado": "push na entrega"})
    assert resp.status_code == 200
    virada = resp.json()["observacoes"][0]
    ajuste = next(a for a in _ajustes(client) if a["id"] == virada["ajuste_id"])
    assert ajuste["modulo"] == "ativos"
    assert ajuste["versao"] == "v2"                       # a leva ativa de "ativos"
    assert not virada["ajuste_ref"].startswith(("Financeiro", "Geral"))
    assert virada["ajuste_ref"] == f"v2 #{ajuste['numero']:02d}"   # em ativos a ref não leva o módulo


def test_ajuste_ref_leva_o_modulo_quando_nao_e_ativos(client, tecnico):
    obs = _relato_do_tecnico(client, tecnico)
    financeiro = _ajustes(client, modulo="financeiro")[0]
    resp = client.post(f"/api/tecnicos/observacoes/{obs['id']}/vincular-ajuste",
                       json={"ajuste_id": financeiro["id"]})
    assert resp.status_code == 200
    assert resp.json()["observacoes"][0]["ajuste_ref"] == "Financeiro v1 #01"


def test_novidades_citam_o_modulo(client):
    item = _novo(client, titulo="Aviso de SLA estourado", modulo="plataforma")
    client.patch(f"/api/ativos/ajustes/{item['id']}", json={"status": "analise"})
    textos = [a["texto"] for a in client.get("/api/atividades", params={"fluxo": "ATIVOS"}).json()]
    assert any("criado em Geral v1" in t for t in textos)
    assert any("Geral v1" in t and "Em análise" in t for t in textos)


def test_mcp_lista_e_cria_com_modulo(client):
    from app import mcp_server

    todos = mcp_server.listar_ajustes_ativos()
    assert {a["modulo"] for a in todos} >= {"ativos", *NOVOS}
    geral = mcp_server.listar_ajustes_ativos(modulo="plataforma")
    assert len(geral) == 6 and {a["modulo"] for a in geral} == {"plataforma"}
    assert mcp_server.listar_ajustes_ativos(modulo="plataforma", tipo="Bug") == []

    antes = max(a["numero"] for a in mcp_server.listar_ajustes_ativos(modulo="projetos"))
    criado = mcp_server.criar_ajuste_ativos(titulo="Via MCP", atual="a", esperado="b", modulo="projetos")
    assert (criado["modulo"], criado["versao"], criado["numero"]) == ("projetos", "v1", antes + 1)
    # sem modulo: continua sendo o backlog de Gestão de Ativos, v2 (compatível com o conector atual)
    legado = mcp_server.criar_ajuste_ativos(titulo="Via MCP legado", atual="a", esperado="b")
    assert (legado["modulo"], legado["versao"]) == ("ativos", "v2")
    assert mcp_server.criar_ajuste_ativos(titulo="x", atual="a", esperado="b", modulo="zzz")["modulo"] == "ativos"


# ------------------------------------------------------------- pauta e export

def test_pauta_agrupa_por_modulo_e_mostra_o_nome(client):
    pauta = client.get("/relatorio").text
    for rotulo in ("Geral · Leva v1", "Financeiro · Leva v1", "Projetos · Leva v1",
                   "Gestão de Ativos · Leva v2"):
        assert rotulo in pauta
    assert "Módulo Financeiro" in pauta and "Publicação do app na Apple App Store" in pauta
    # módulos na ordem do catálogo: ativos, Geral, Financeiro, Projetos
    assert pauta.index("Gestão de Ativos · Leva v2") < pauta.index("Geral · Leva v1") \
        < pauta.index("Financeiro · Leva v1") < pauta.index("Projetos · Leva v1")


def test_pauta_kpi_soma_todos_os_modulos_e_vazio_nao_diz_so_ativos(client):
    from app.relatorio import secao_ajustes

    todos = _ajustes(client)
    abertos = [a for a in todos if a["status"] not in ("validado", "descartado")]
    assert f"{len(abertos)} ajuste(s) pendente(s) nos módulos" in client.get("/relatorio").text
    vazio = secao_ajustes([])
    assert "Gestão de Ativos" not in vazio and "nenhum módulo" in vazio
    # dados antigos (de uma API sem `modulo`) continuam renderizando, como "ativos"
    sem_modulo = [{k: v for k, v in a.items() if k != "modulo"} for a in todos if a["modulo"] == "ativos"]
    assert "Gestão de Ativos · Leva v2" in secao_ajustes(sem_modulo)


def test_export_completo_traz_a_coluna_modulo(client):
    financeiro = _ajustes(client, modulo="financeiro")[0]
    client.post(f"/api/ativos/ajustes/{financeiro['id']}/observacoes",
                json={"texto": "alinhar escopo com a LPD", "autor": "Rafa"})

    resp = client.get("/api/export/completo")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))

    aba = wb["Ajustes de ativos"]
    cabecalho = [c.value for c in aba[1]]
    assert cabecalho[:3] == ["Módulo", "Versão", "Nº"]
    linhas = [[c.value for c in l] for l in aba.iter_rows(min_row=2)]
    modulos_na_planilha = {l[0] for l in linhas}
    assert modulos_na_planilha >= {"Gestão de Ativos", "Geral", "Financeiro", "Projetos"}
    assert "Fluxo A — Finalização" not in modulos_na_planilha
    assert "Dashboard e Relatórios" not in modulos_na_planilha
    assert any(l[0] == "Financeiro" and l[3] == "Módulo Financeiro" for l in linhas)

    obs = [[c.value for c in l] for l in wb["Observações (ajustes)"].iter_rows(min_row=2)]
    cab_obs = [c.value for c in wb["Observações (ajustes)"][1]]
    texto = cab_obs.index("Texto")
    assert any(l[0] == "Financeiro v1 #01" and "alinhar escopo" in l[texto] for l in obs)


# ------------------------------------------- processo a desenhar (diagramas)

def test_catalogo_marca_financeiro_como_processo_a_desenhar(client):
    cat = {m["key"]: m for m in client.get("/api/ativos/modulos").json()}
    # o Projetos desenha o processo na visão Fluxos do Dispatcher, não na aba de módulo
    assert {k for k, m in cat.items() if m["processo"]} == {"financeiro"}
    assert "ainda não está desenhado" in cat["financeiro"]["descricao"]


def _diagrama(client, fluxo, titulo="Fluxo de aprovação", **extra):
    resp = client.post("/api/diagramas", json={
        "fluxo": fluxo, "kind": "ideal", "titulo": titulo,
        "mermaid": "flowchart TD\n  n1[Início] --> n2[Fim]", **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_diagrama_de_modulo_fica_separado_dos_fluxos_do_dispatcher(client):
    fin = _diagrama(client, "financeiro")
    proj = _diagrama(client, "projetos", titulo="Fluxo de projetos")
    try:
        ids_fin = [d["id"] for d in client.get("/api/diagramas", params={"fluxo": "financeiro"}).json()]
        assert fin["id"] in ids_fin and proj["id"] not in ids_fin
        assert [d["id"] for d in client.get("/api/diagramas", params={"fluxo": "projetos"}).json()] == [proj["id"]]
        # os fluxos A/B/C não enxergam os desenhos dos módulos
        for fluxo in ("A", "B", "C"):
            ids = {d["id"] for d in client.get("/api/diagramas", params={"fluxo": fluxo}).json()}
            assert not ids & {fin["id"], proj["id"]}
    finally:
        for d in (fin, proj):
            client.delete(f"/api/diagramas/{d['id']}")


def test_novidades_do_diagrama_de_modulo_vao_pra_trilha_dos_ajustes(client):
    d = _diagrama(client, "financeiro", titulo="Aprovação de pagamento")
    try:
        client.patch(f"/api/diagramas/{d['id']}", json={"descricao": "primeira versão"})
        ajustes = [a["texto"] for a in client.get("/api/atividades", params={"fluxo": "ATIVOS"}).json()]
        assert any('"Aprovação de pagamento" (Financeiro) criado' in t for t in ajustes)
        # e não poluem as Novidades do Fluxo C do Dispatcher
        fluxo_c = [a["texto"] for a in client.get("/api/atividades", params={"fluxo": "C"}).json()]
        assert not any("Aprovação de pagamento" in t for t in fluxo_c)
        client.delete(f"/api/diagramas/{d['id']}")
        ajustes = [a["texto"] for a in client.get("/api/atividades", params={"fluxo": "ATIVOS"}).json()]
        assert any('"Aprovação de pagamento" (Financeiro) excluído' in t for t in ajustes)
    finally:
        client.delete(f"/api/diagramas/{d['id']}")


def test_diagrama_de_fluxo_do_dispatcher_continua_na_trilha_do_fluxo(client):
    d = _diagrama(client, "B", titulo="Desenho do Fluxo B de teste")
    try:
        fluxo_b = [a["texto"] for a in client.get("/api/atividades", params={"fluxo": "B"}).json()]
        assert any("Desenho do Fluxo B de teste" in t and "(" not in t for t in fluxo_b)
    finally:
        client.delete(f"/api/diagramas/{d['id']}")


# -------------------------------------------- Dispatcher, Geral e módulo incorporado

def test_catalogo_diz_quais_modulos_moram_no_dispatcher(client):
    cat = {m["key"]: m for m in client.get("/api/ativos/modulos").json()}
    assert "fluxo-a" not in cat          # o Fluxo A não é módulo: a finalização vive nas Situações
    assert cat["projetos"]["dispatcher_fluxo"] == "projetos"
    assert [k for k, m in cat.items() if m["dispatcher_fluxo"]] == ["projetos"]
    assert all(cat[k]["dispatcher_fluxo"] is None for k in ("ativos", "plataforma", "financeiro"))
    assert cat["plataforma"]["label"] == "Geral" and "Dashboard" in cat["plataforma"]["descricao"]
    assert "dashboard" not in cat


def test_dashboard_e_relatorios_estao_no_geral(client):
    geral = {a["titulo"]: a for a in _ajustes(client, modulo="plataforma")}
    assert {"Finalização do Dashboard", "Relatórios da ferramenta com exportação"} <= set(geral)
    assert sorted(a["numero"] for a in geral.values()) == [1, 2, 3, 4, 5, 6]
    # a chave antiga ainda funciona na criação (conector/script que não foi atualizado)
    criado = _novo(client, modulo="dashboard")
    assert (criado["modulo"], criado["versao"]) == ("plataforma", "v1")


def test_migracao_leva_o_dashboard_pro_geral_sem_repetir_numero():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        def novo(modulo, versao, numero, titulo):
            db.add(models.AtivoAjuste(modulo=modulo, versao=versao, numero=numero, titulo=titulo,
                                      atual="a", esperado="b"))
        novo("plataforma", "v1", 1, "SLA")
        novo("plataforma", "v1", 2, "Perfis")
        novo("dashboard", "v1", 1, "Dashboard")
        novo("dashboard", "v1", 2, "Relatórios")
        novo("dashboard", "v2", 1, "Dashboard v2")        # leva que o Geral ainda não tem
        novo("financeiro", "v1", 1, "Financeiro")          # outro módulo não é tocado
        db.commit()

        assert seed_data.migrar_modulos_aposentados(db) == 3
        assert seed_data.migrar_modulos_aposentados(db) == 0      # idempotente
        db.expire_all()
        geral = db.query(models.AtivoAjuste).filter_by(modulo="plataforma").order_by(
            models.AtivoAjuste.versao, models.AtivoAjuste.numero).all()
        assert [(a.versao, a.numero, a.titulo) for a in geral] == [
            ("v1", 1, "SLA"), ("v1", 2, "Perfis"), ("v1", 3, "Dashboard"), ("v1", 4, "Relatórios"),
            ("v2", 1, "Dashboard v2")]
        assert db.query(models.AtivoAjuste).filter_by(modulo="dashboard").count() == 0
        assert db.query(models.AtivoAjuste).filter_by(modulo="financeiro").one().numero == 1

        # o seed das pendências depois da migração reconhece os itens (título igual) e não duplica
        # os que a LPD já tinha no módulo antigo
        db.add(models.AtivoAjuste(modulo="dashboard", versao="v1", numero=1,
                                  titulo="Finalização do Dashboard", atual="a", esperado="b"))
        db.commit()
        seed_data.migrar_modulos_aposentados(db)
        seed_data.seed_pendencias_lpd(db)
        titulos = [a.titulo for a in db.query(models.AtivoAjuste).filter_by(modulo="plataforma", versao="v1")]
        assert titulos.count("Finalização do Dashboard") == 1
    finally:
        db.close()


def test_diagrama_do_projetos_fica_na_trilha_do_proprio_fluxo(client):
    """O Projetos é uma aba de fluxo do Dispatcher: o desenho dele aparece nas Novidades
    do fluxo "projetos", não nas dos ajustes (que é o caso do Financeiro)."""
    d = _diagrama(client, "projetos", titulo="Desenho do Projetos de teste")
    try:
        proj = [a["texto"] for a in client.get("/api/atividades", params={"fluxo": "projetos"}).json()]
        assert any("Desenho do Projetos de teste" in t for t in proj)
        ajustes = [a["texto"] for a in client.get("/api/atividades", params={"fluxo": "ATIVOS"}).json()]
        assert not any("Desenho do Projetos de teste" in t for t in ajustes)
    finally:
        client.delete(f"/api/diagramas/{d['id']}")


TITULOS_FINANCEIRO = [
    "Valores do serviço — os 3 cenários", "Cenário 1 — Contratual (N1, M1 e S1)",
    "Cenário 2 — Projetos (D1)", "Cenário 3 — Atendimento CLT",
]


def _diagramas_financeiro(client):
    return {d["titulo"]: d for d in client.get("/api/diagramas", params={"fluxo": "financeiro"}).json()}


def test_financeiro_nasce_com_a_visao_geral_e_um_diagrama_por_cenario(client):
    from app import seed_data

    diagramas = _diagramas_financeiro(client)
    assert [t for t in TITULOS_FINANCEIRO if t in diagramas] == TITULOS_FINANCEIRO
    assert all(diagramas[t]["kind"] == "ideal" for t in TITULOS_FINANCEIRO)
    # a visão geral vem primeiro, depois os cenários, na ordem
    ordem = [d["titulo"] for d in client.get("/api/diagramas", params={"fluxo": "financeiro"}).json()
             if d["titulo"] in TITULOS_FINANCEIRO]
    assert ordem == TITULOS_FINANCEIRO

    conteudo = {
        TITULOS_FINANCEIRO[0]: ("Tiflux", "define a sigla", "N1, M1 ou S1", "valor vem da campanha",
                                "valores já conhecidos", "guarda o valor contratual de cada sigla"),
        TITULOS_FINANCEIRO[1]: ("N1, M1 ou S1", "Valor da sigla vem do cadastro do técnico", "Rede Credenciada",
                                "sem obrigação de aceitar todos", "valor contratual atrelado ao técnico",
                                "pedágio, estacionamento ou materiais", "Despesa aprovada?",
                                "despesa entra junto, no fim do chamado"),
        TITULOS_FINANCEIRO[2]: ("sigla D1", "orçamento", "campanha", "técnico: campanha enviada aos pais, com ou sem filhos",
                                "lista de chamados da campanha", "chamado cai para o pai e para os filhos",
                                "Filho nunca vê o valor"),
        TITULOS_FINANCEIRO[3]: ("sigla CLT na abertura do chamado", "Operação", "Valores já conhecidos",
                                "Sem negociação financeira"),
    }
    for titulo, trechos in conteudo.items():
        mermaid = diagramas[titulo]["mermaid"]
        for trecho in trechos:
            assert trecho in mermaid, (titulo, trecho)
        # toda caixa citada foi definida (senão o Mermaid desenha uma caixa com o id cru)
        definidos = set(re.findall(r'\b(n\d+)\s*[\[{(]', mermaid))
        citados = set(re.findall(r'\bn\d+\b', mermaid))
        assert citados == definidos, titulo
        # texto curto pra ler: nenhuma caixa vira parágrafo
        rotulos = re.findall(r'"([^"]+)"', mermaid)
        assert rotulos and max(len(r) for r in rotulos) <= 80, titulo
        # as cores dos tipos de card usados estão definidas (senão o botão/notificação fica sem cor)
        for classe in re.findall(r'^\s*class [\w,]+ (\w+);', mermaid, re.M):
            assert f"classDef {classe} " in mermaid, (titulo, classe)

    # usa os outros tipos de card do editor, não só caixas: decisão, botão e notificação
    todos = "\n".join(diagramas[t]["mermaid"] for t in TITULOS_FINANCEIRO)
    assert re.search(r'\bn\d+\{"', todos)                    # decisão
    assert re.search(r'\bn\d+\("', todos)                    # botão (ação de sistema)
    assert re.search(r'\bn\d+\(\["🔔 Notifica o técnico: ', todos)   # notificação ao técnico

    # idempotente: outra rodada do seed não duplica nem sobrescreve o que o time editar
    alvo = diagramas[TITULOS_FINANCEIRO[1]]
    client.patch(f"/api/diagramas/{alvo['id']}", json={"descricao": "editado pelo time"})
    db = SessionLocal()
    try:
        assert seed_data.seed_diagrams(db) == 0
    finally:
        db.close()
    de_novo = _diagramas_financeiro(client)
    assert len([t for t in TITULOS_FINANCEIRO if t in de_novo]) == 4
    assert de_novo[TITULOS_FINANCEIRO[1]]["descricao"] == "editado pelo time"
    # o Projetos (aba de fluxo do Dispatcher) segue sem desenho: nada foi inventado pra ele
    assert client.get("/api/diagramas", params={"fluxo": "projetos"}).json() == []


def test_diagramas_dos_cenarios_entram_mesmo_com_outro_desenho_no_financeiro():
    """Se alguém já criou um diagrama na aba (o tipo padrão ali é "como deveria funcionar"),
    o seed não pode deixar de trazer os dos cenários — mas também não mexe no que existe."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(models.FlowDiagram(fluxo="financeiro", kind="ideal", titulo="Rascunho do time",
                                  mermaid="flowchart TD\n n1[a] --> n2[b]", descricao="meu texto"))
        db.commit()
        seed_data.seed_diagrams(db)
        titulos = sorted(d.titulo for d in db.query(models.FlowDiagram).filter_by(fluxo="financeiro"))
        assert titulos == sorted(["Rascunho do time", *TITULOS_FINANCEIRO])
        # nada do que o time tinha é alterado
        rascunho = db.query(models.FlowDiagram).filter_by(titulo="Rascunho do time").one()
        assert (rascunho.descricao, rascunho.seeded) == ("meu texto", False)
        # idempotente: nem duplica o semeado, nem desfaz edição dele
        semeado = db.query(models.FlowDiagram).filter_by(titulo=TITULOS_FINANCEIRO[0]).one()
        semeado.descricao, semeado.seeded = "editado", False    # editar pela tela zera o seeded
        db.commit()
        assert seed_data.seed_diagrams(db) == 0
        assert db.query(models.FlowDiagram).filter_by(fluxo="financeiro").count() == 5
        assert db.query(models.FlowDiagram).filter_by(titulo=TITULOS_FINANCEIRO[0]).one().descricao == "editado"
    finally:
        db.close()


def test_diagrama_de_fluxo_do_dispatcher_segue_so_quando_nao_ha_nenhum():
    """A regra antiga continua valendo pros fluxos A/B/C: se o time já tem um diagrama do
    fluxo+tipo, o modelo inicial não entra."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(models.FlowDiagram(fluxo="C", kind="ideal", titulo="Meu Fluxo C", mermaid="flowchart TD\n n1[a] --> n2[b]"))
        db.commit()
        seed_data.seed_diagrams(db)
        assert [d.titulo for d in db.query(models.FlowDiagram).filter_by(fluxo="C", kind="ideal")] == ["Meu Fluxo C"]
    finally:
        db.close()


# ------------------------------------------- Fluxo A: finalização como situações

TITULOS_FLUXO_A = [i["titulo"] for i in seed_data.FLUXO_A_FINALIZACAO]


def _banco():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_finalizacao_do_fluxo_a_nasce_como_situacoes_do_fluxo_a(client):
    sits = [s for s in client.get("/api/situacoes").json() if s["fluxo"] == "A"]
    assert sorted(s["titulo"] for s in sits) == sorted(TITULOS_FLUXO_A) and len(sits) == 7
    # cada uma é uma situação de um estágio só, com o que deve ficar como resultado esperado
    for s in sits:
        assert len(s["estagios"]) == 1
        assert s["estagios"][0]["resultado_esperado"] and s["estagios"][0]["status"] == "Não testado"
        assert s["origem"] == "Pendências da LPD — finalização do Fluxo A"
    bug = next(s for s in sits if s["titulo"].startswith("BUG:"))
    assert "Tipo: Bug · Prioridade: Alta" in bug["descricao"]
    # nada disso ficou no backlog de ajustes (e os fluxos B/C não ganharam nada)
    assert not [a for a in _ajustes(client) if a["titulo"] in TITULOS_FLUXO_A]
    assert not [s for s in client.get("/api/situacoes").json()
                if s["fluxo"] in ("B", "C") and s["titulo"] in TITULOS_FLUXO_A]


def test_seed_do_fluxo_a_e_idempotente_e_nao_repete_o_que_ja_existe():
    from app.models import Situacao

    db = _banco()
    try:
        # o time já tinha uma das situações no Fluxo A (título escrito de leve diferente)
        db.add(Situacao(code="SIT-90", fluxo="A", titulo="busca de chamados ", descricao="a minha"))
        db.commit()
        assert seed_data.migrar_fluxo_a_para_situacoes(db) == 6        # 7 menos a que já existia
        assert seed_data.migrar_fluxo_a_para_situacoes(db) == 0        # idempotente
        sits = db.query(Situacao).filter_by(fluxo="A").all()
        assert len(sits) == 7
        assert [s.descricao for s in sits if s.code == "SIT-90"] == ["a minha"]    # não tocou
        assert len({s.code for s in sits}) == 7

        # excluída (exclusão suave) não ressuscita no próximo boot
        db.query(Situacao).filter_by(fluxo="A").first().active = False
        db.commit()
        assert seed_data.migrar_fluxo_a_para_situacoes(db) == 0
        assert db.query(Situacao).filter_by(fluxo="A").count() == 7
    finally:
        db.close()


def test_migracao_leva_os_ajustes_do_fluxo_a_pra_situacoes_sem_perder_nada():
    from datetime import datetime

    from app.models import (
        Situacao, SituacaoObservation, SituacaoScreenshot, AtivoAjuste, AtivoAjusteObservation,
        AtivoAjusteObservationRevision, AtivoAjustePrint,
    )

    db = _banco()
    try:
        feito = AtivoAjuste(
            modulo="fluxo-a", versao="v1", numero=1, titulo="Busca de chamados", tipo="Melhoria",
            area="Fluxo A — estético", prioridade="Média", atual="a busca", esperado="busca nova",
            observacao="decidimos no kickoff", retorno="LPD vai entregar", prazo="2026-12-01",
            validacao="Aprovado", validado_por="Rafa", validado_em=datetime(2026, 11, 2),
            validacao_operacao="Reprovado", validado_por_operacao="Operação",
        )
        db.add(feito)
        db.flush()
        nota = AtivoAjusteObservation(ajuste_id=feito.id, autor="Bruna", texto="conferir com a operação",
                                      cor="vermelho", nivel="operacao")
        db.add(nota)
        db.flush()
        db.add(AtivoAjusteObservationRevision(observation_id=nota.id, texto="texto antigo", autor="Bruna"))
        db.add(AtivoAjustePrint(ajuste_id=feito.id, filename="p.png", content_type="image/png", data=b"\x89PNG",
                                uploaded_by="Rafa"))
        db.add(AtivoAjuste(modulo="fluxo-a", versao="v1", numero=2, titulo="Item descartado", tipo="Bug",
                           area="Fluxo A — funcionamento", prioridade="Alta", atual="x", esperado="y",
                           status="descartado"))
        db.add(AtivoAjuste(modulo="ativos", versao="v2", numero=1, titulo="Outro módulo", atual="x", esperado="y"))
        db.commit()

        seed_data.migrar_fluxo_a_para_situacoes(db)
        assert seed_data.migrar_fluxo_a_para_situacoes(db) == 0

        # saiu do backlog, só o que era do Fluxo A (o de outro módulo segue lá)
        restantes = [a.titulo for a in db.query(AtivoAjuste).all()]
        assert restantes == ["Outro módulo"]

        sit = db.query(Situacao).filter_by(fluxo="A", titulo="Busca de chamados").one()
        est = sit.estagios[0]
        assert (est.status, est.testado_por) == ("Aprovado", "Rafa")
        assert (est.status_operacao, est.testado_por_operacao) == ("Reprovado", "Operação")
        textos = {o.texto: o for o in est.observations}
        assert "decidimos no kickoff" in textos
        assert any("LPD vai entregar" in t and "2026-12-01" in t for t in textos)
        migrada = textos["conferir com a operação"]
        assert (migrada.autor, migrada.cor, migrada.nivel) == ("Bruna", "vermelho", "operacao")
        assert [r.texto for r in migrada.revisions] == ["texto antigo"]
        assert [(p.filename, p.data) for p in est.screenshots] == [("p.png", b"\x89PNG")]
        # não duplicou: uma situação só pra esse título, e as 7 da lista existem uma vez cada
        assert db.query(Situacao).filter_by(fluxo="A").count() == 8     # 7 da lista + "Item descartado"
        assert db.query(Situacao).filter_by(fluxo="A", titulo="Item descartado").one().active is False
    finally:
        db.close()


def test_modelo_inicial_nao_editado_acompanha_o_seed_e_o_editado_fica():
    """Quem já subiu a versão antiga do diagrama (e não mexeu) recebe a nova; quem editou, não."""
    db = _banco()
    try:
        seed_data.seed_diagrams(db)
        d = db.query(models.FlowDiagram).filter_by(titulo=TITULOS_FINANCEIRO[0]).one()
        atual = d.mermaid
        d.mermaid, d.descricao = "flowchart TD\n    n1[Versão antiga] --> n2[x]", "descrição antiga"
        assert d.seeded is True
        db.commit()

        seed_data.seed_diagrams(db)                      # ninguém editou: volta pra versão do seed
        db.refresh(d)
        assert d.mermaid == atual and d.seeded is True
        assert db.query(models.FlowDiagram).filter_by(fluxo="financeiro").count() == 4

        d.mermaid, d.seeded = "flowchart TD\n    n1[Do time] --> n2[x]", False       # o time editou
        db.commit()
        seed_data.seed_diagrams(db)
        db.refresh(d)
        assert "Do time" in d.mermaid
    finally:
        db.close()