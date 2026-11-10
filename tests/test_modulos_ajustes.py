"""Módulos do backlog de ajustes: catálogo, migração, seed das pendências da LPD,
numeração por módulo, e a presença do módulo na pauta e no export."""
import io

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import modulos, models, seed_data
from app.database import Base, SessionLocal
from app.routers import ativos

NOVOS = ["plataforma", "financeiro", "projetos", "fluxo-a"]


def _ajustes(client, **filtros):
    return client.get("/api/ativos/ajustes", params=filtros).json()


def _novo(client, **campos):
    corpo = {"titulo": "Item de teste", "atual": "hoje", "esperado": "amanhã", **campos}
    resp = client.post("/api/ativos/ajustes", json=corpo)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ----------------------------------------------------------------- catálogo

def test_catalogo_tem_os_cinco_modulos_na_ordem_das_abas(client):
    cat = client.get("/api/ativos/modulos").json()
    assert [m["key"] for m in cat] == ["ativos", *NOVOS]
    assert {m["key"]: m["versao_padrao"] for m in cat} == {
        "ativos": "v2", "plataforma": "v1", "financeiro": "v1",
        "projetos": "v1", "fluxo-a": "v1",
    }
    assert all(m["label"] and m["titulo"] and m["descricao"] for m in cat)


def test_norm_modulo_nunca_levanta_e_cai_em_ativos():
    for lixo in (None, "", "   ", "nao-existe", 123, 0, [], {}, object()):
        assert modulos.norm_modulo(lixo) == "ativos"
    assert modulos.norm_modulo("  Financeiro ") == "financeiro"
    assert modulos.norm_modulo("FLUXO-A") == "fluxo-a"
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
        assert seed_data.seed_pendencias_lpd(db) == 15
        assert seed_data.seed_pendencias_lpd(db) == 0     # segunda rodada não duplica
        itens = db.query(models.AtivoAjuste).all()
        assert len(itens) == 15

        por_modulo = {}
        for a in itens:
            por_modulo.setdefault(a.modulo, []).append(a)
        assert {k: len(v) for k, v in por_modulo.items()} == {
            "plataforma": 6, "financeiro": 1, "projetos": 1, "fluxo-a": 7}
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
    assert len(por_titulo) == 15
    bug = [a for a in por_titulo.values() if a["tipo"] == "Bug"]
    assert [b["titulo"] for b in bug] == ["BUG: chamado reaparece para aceite após a finalização"]
    assert bug[0]["modulo"] == "fluxo-a" and bug[0]["prioridade"] == "Alta"

    def prio(trecho):
        return {a["prioridade"] for t, a in por_titulo.items() if trecho in t}

    assert prio("Cálculo do SLA") == {"Alta"}
    assert prio("Google Play") == {"Alta"} and prio("Apple App Store") == {"Alta"}
    assert prio("Relatórios") == {"Média"} and prio("Busca de chamados") == {"Média"}
    assert prio("Migração da tela") == {"Média"}
    assert len([t for t in por_titulo if t.startswith("Migração da tela")]) == 3
    assert prio("Vinculação") == {"Alta"} and prio("2ª e 3ª oferta") == {"Alta"}

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

    esperado = {m: proximo(m, "v1") for m in ("financeiro", "plataforma", "fluxo-a")}
    esperado_ativos = proximo("ativos", "v2")
    for modulo in ("financeiro", "plataforma", "fluxo-a"):
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
    assert len(_ajustes(client, modulo="fluxo-a")) == 7
    assert len(_ajustes(client, modulo="plataforma")) == 6
    # a chave antiga do Dashboard filtra o Geral
    assert {a["id"] for a in _ajustes(client, modulo="dashboard")} == {a["id"] for a in _ajustes(client, modulo="plataforma")}
    assert {a["modulo"] for a in _ajustes(client)} >= {"ativos", *NOVOS}      # sem filtro: todos
    assert _ajustes(client, modulo="fluxo-a", tipo="Bug")[0]["titulo"].startswith("BUG:")


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
    fluxo_a = mcp_server.listar_ajustes_ativos(modulo="fluxo-a")
    assert len(fluxo_a) == 7 and {a["modulo"] for a in fluxo_a} == {"fluxo-a"}
    assert mcp_server.listar_ajustes_ativos(modulo="fluxo-a", tipo="Bug")[0]["tipo"] == "Bug"

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
                   "Fluxo A — Finalização · Leva v1",
                   "Gestão de Ativos · Leva v2"):
        assert rotulo in pauta
    assert "Módulo Financeiro" in pauta and "Publicação do app na Apple App Store" in pauta
    # módulos na ordem do catálogo: ativos antes de plataforma, fluxo-a por último
    assert pauta.index("Gestão de Ativos · Leva v2") < pauta.index("Geral · Leva v1") \
        < pauta.index("Financeiro · Leva v1") < pauta.index("Fluxo A — Finalização · Leva v1")


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
    assert modulos_na_planilha >= {"Gestão de Ativos", "Geral", "Financeiro", "Projetos",
                                   "Fluxo A — Finalização"}
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
        assert [d["id"] for d in client.get("/api/diagramas", params={"fluxo": "financeiro"}).json()] == [fin["id"]]
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
    assert cat["fluxo-a"]["dispatcher_fluxo"] == "A"
    assert cat["projetos"]["dispatcher_fluxo"] == "projetos"
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
