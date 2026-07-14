# -*- coding: utf-8 -*-
"""
Base de casos de teste do Fluxo C — só as frentes que a Faiston precisa validar
como cliente final: Operador (web) e App do técnico. Backend fica de fora
(responsabilidade do time de LP/NEXO).
Fonte: dashboard_dispatcher_faiston_flowC_comparison, atualização de 02/07/2026.
"""

STAGE_META = {
    1: dict(nome="Criar OS", gatilho="Criar uma OS (manual ou automática) no sistema."),
    2: dict(nome="Buscando Técnico", gatilho='Sistema busca técnico automaticamente após a criação da OS; operador pode clicar em "Reenviar busca".'),
    3: dict(nome="Téc. Aceitou", gatilho='Técnico toca "Aceitar" no app ou aceita pelo link do WhatsApp.'),
    4: dict(nome="Agendado", gatilho='Chamado passa a "Agendado" automaticamente após o aceite; técnico tenta abrir/iniciar antes da data marcada.'),
    5: dict(nome="Téc. em Deslocamento", gatilho='Técnico toca "Iniciar Deslocamento" / "Navegar".'),
    6: dict(nome="Aguardando Liberação", gatilho='Técnico chega ao local, toca "Acesso Liberado" e depois "Iniciar Atendimento".'),
    7: dict(nome="Téc. em Atendimento", gatilho='Atendimento em curso; ao final, o OPERADOR (não o técnico) clica em "Acompanhamento Concluído".'),
    8: dict(nome="Acompanhamento N2", gatilho="Chamado é escalado para o suporte N2 durante o atendimento."),
    9: dict(nome="Aguardando RAT", gatilho="Sistema solicita a RAT ao técnico após o atendimento (ou após N2)."),
    10: dict(nome="Em Revisão", gatilho="Técnico envia a RAT; operador aprova ou recusa o relatório."),
    11: dict(nome="Atividade Concluída", gatilho="Operador aprova a RAT; chamado é concluído e o técnico liberado."),
    12: dict(nome="Notificações (transversal)", gatilho="Qualquer evento do chamado (aceite, chegada, RAT, escalonamento etc.) dispara notificação por push/WhatsApp."),
}
FRONT_LABEL = {"OPR": "Operador (web)", "APP": "App do técnico"}
VERIFY_WHERE = {"OPR": "no painel do operador (web)", "APP": "no app do técnico (NEXO)"}
PRECOND = {
    "OPR": "Operador logado no painel web; chamado de teste visível no quadro.",
    "APP": "Técnico de teste logado no app NEXO; chamado de teste atribuído/disponível.",
}


def _stage_case(stage_num, front, text, status):
    meta = STAGE_META[stage_num]
    tipo = "Validação (comprovar ao vivo)" if status == "done" else "Verificação de pendência (acabamento em curso)"
    prioridade = "Média" if status == "done" else "Alta"
    return dict(
        grupo="Grupo A",
        estagio_num=stage_num,
        estagio=f"{stage_num:02d} · {meta['nome']}",
        frente=FRONT_LABEL[front],
        tipo=tipo,
        prioridade=prioridade,
        pre_condicao=PRECOND[front],
        passos=f"1) {meta['gatilho']} 2) Conferir {VERIFY_WHERE[front]} o comportamento abaixo.",
        resultado_esperado=text,
        origem="Matriz por frente (02/07)",
    )


_STAGES = [
    dict(num=1,
         operador=[("Novo chamado aparece no painel com o estado certo", "done")],
         mobile=[]),
    dict(num=2,
         operador=[("Painel mostra o chamado em alocação/buscando, refletindo fielmente o estado real", "done")],
         mobile=[("Novo chamado aparece e pode ser aceito (caminho normal)", "done")]),
    dict(num=3,
         operador=[('Painel passa para "Técnico Confirmado", fiel', "done")],
         mobile=[("Ao aceitar, o chamado sai da lista e o passo avança", "done")]),
    dict(num=4,
         operador=[('Painel mostra "Agendado", fiel', "done")],
         mobile=[('Mostra "Aguardando início" (não "Em rota")', "done"),
                  ('"Iniciar" bloqueado até confirmar e chegar a data', "done"),
                  ("Exibir só data/hora na tela de agendamento", "todo"),
                  ("Ocultar botões indevidos na tela de agendamento", "todo"),
                  ("Lembrete de confirmação implementado (~24h antes; janela 1–2h em discussão na reunião)", "done")]),
    dict(num=5,
         operador=[('Painel mostra "Deslocamento", fiel', "done")],
         mobile=[('Passo avança para "Em Rota"', "done"),
                  ('Botão "Navegar" abre a rota até o endereço', "done")]),
    dict(num=6,
         operador=[('Painel mostra "Aguardando Liberação", fiel', "done")],
         mobile=[('Botão "Acesso Liberado" reconectado e funcional', "done"),
                  ('A etapa aparece com o rótulo "Aguardando Liberação de Acesso"', "done"),
                  ('O técnico registra "Acesso Liberado" e então toca "Iniciar Atendimento" — sem etapa de liberação pelo operador', "done")]),
    dict(num=7,
         operador=[('Painel mostra "Em Execução" e recebe os horários de chegada/início', "done")],
         mobile=[('Tela "Em Atendimento"; cronômetro mede o tempo real', "done"),
                  ('"Concluir" removido da visão do técnico', "done")]),
    dict(num=8,
         operador=[('Painel mostra "Suporte N2"; operador conduz "Acompanhamento Concluído"', "done")],
         mobile=[("Técnico sem ação; botões indevidos ocultos por perfil", "done"),
                  ("Cor do botão de escalar N2 ajustada", "done")]),
    dict(num=9,
         operador=[("Painel mostra o chamado aguardando relatório/revisão, fiel", "done")],
         mobile=[("Tela da RAT abre e é enviada pelo app, mesmo abrindo do zero", "done"),
                  ("Após enviar a RAT, o app permanece no chamado", "done")]),
    dict(num=10,
         operador=[("Tela de revisão (aprovar/recusar, ver fotos e assinatura), fiel", "done"),
                    ("Foto recém-capturada aparece na revisão", "done"),
                    ("Horários de início/término já vêm preenchidos", "done")],
         mobile=[('Corrigido: ao recusar, "Corrigir RAT" preserva fotos e assinatura', "done")]),
    dict(num=11,
         operador=[('Painel mostra "Concluído" e encerra o bloco de revisão', "done")],
         mobile=[('Tela mostra "Concluído"', "done"),
                  ("Remover o botão de RAT na tela de conclusão", "todo")]),
    dict(num=12,
         operador=[("Cobertura completa das notificações do operador ainda em verificação (a revisão da RAT já foi confirmada)", "todo")],
         mobile=[("Corrigido: o toque abre o chamado correto", "done"),
                  ("O aviso sai da tela ao ser tocado", "done"),
                  ("Entrega do aviso com o app fechado ainda em ajuste", "todo")]),
]

_group_a = []
_seq = {}
for s in _STAGES:
    for front, items in (("OPR", s["operador"]), ("APP", s["mobile"])):
        for text, status in items:
            key = (s["num"], front)
            _seq[key] = _seq.get(key, 0) + 1
            case = _stage_case(s["num"], front, text, status)
            case["code"] = f"FC-{s['num']:02d}-{front}-{_seq[key]:02d}"
            _group_a.append(case)

# ---------------------------------------------------------------------------
# Orientação de data/horário: os testes do estágio "Agendado" só reproduzem o
# comportamento certo se o chamado de teste tiver a data marcada do jeito certo.
# Sem isso, dá pra clicar tudo achando que passou e não ter testado nada.
# ---------------------------------------------------------------------------
_DATA_NOTE_FUTURA = (
    " AGENDE O CHAMADO DE TESTE PARA UMA DATA FUTURA (não hoje) — é a data marcada "
    "que aciona esse comportamento (chamado aparece como agendado e o botão Iniciar fica bloqueado). "
    "Depois, se quiser ver o desbloqueio, reagenda esse mesmo chamado pra hoje e confere que libera."
)
_DATA_NOTE_24H = (
    " Esse item só dá pra confirmar se o chamado de teste for agendado com PELO MENOS 24 HORAS "
    "de antecedência a partir de agora — o lembrete é enviado ~24h antes do horário marcado. "
    "Se não der tempo hoje, marca como Bloqueado e revalida depois."
)
for _case in _group_a:
    if _case.get("estagio_num") != 4:
        continue
    if "lembrete de confirmação" in _case["resultado_esperado"].lower():
        _case["pre_condicao"] += _DATA_NOTE_24H
    else:
        _case["pre_condicao"] += _DATA_NOTE_FUTURA

_PEND_RAW = [
    dict(estagio="02 · Buscando Técnico", status="done",
         quote='O chamado do tipo "Ocorrência" ainda aparece disponível para aceite do técnico, mesmo não devendo estar disponível.',
         esperado='Chamado em "Ocorrência" é bloqueado em visualização, detalhe e aceite (app e link do WhatsApp) — não aparece na lista de disponíveis do técnico. Um chamado em Ocorrência só volta a ficar ofertável quando a operação usa "Re-disparar busca".'),
    dict(estagio="04 · Agendado", status="todo",
         quote='Botão "Ligar" sem funcionalidade na tela de agendamento; solicitado pop-up de confirmação 1–2h antes da atividade.',
         esperado='Botão "Ligar" abre o discador do telefone com o número do solicitante (não altera o estado do chamado). Lembrete de confirmação (push) chega ~24h antes da atividade agendada e o toque abre o chamado — CONFIRMAR EM REUNIÃO se a janela de 24h deve mudar/somar 1–2h.'),
    dict(estagio="05 · Téc. em Deslocamento", status="todo",
         quote="Mapa com localização em tempo real do técnico durante o deslocamento — nova funcionalidade em planejamento, NÃO testar hoje.",
         esperado="Sem comportamento a validar ainda — desenho técnico em elaboração. Acompanhar apenas se já há entregável para teste."),
    dict(estagio="06 · Aguardando Liberação", status="todo",
         quote='Barra de progresso permanece em "Em rota" e deveria mudar para "Em Atendimento" quando o técnico chega.',
         esperado='Chamados agendados mostram "Aguardando início" (não "Em Rota") antes do deslocamento. A barra avança para "Em Atendimento" no toque de "Iniciar Atendimento" (direto na chegada ou após registrar "Acesso Liberado"). Durante a espera pela liberação, a barra ainda mostra "Em Rota" (etapa própria pendente de decisão em reunião).'),
    dict(estagio="08 · Acompanhamento N2", status="todo",
         quote="Cálculo de tempo da atividade incorreto — deveria contar de Aguardando Liberação até Acompanhamento Concluído.",
         esperado='Especificação fechada, correção em implementação: tempo deve contar de "Aguardando Liberação" (ou de "Iniciar Atendimento" se início direto) até o clique do operador em "Acompanhamento Concluído" — não até o envio da RAT. Testar quando a correção estiver disponível.'),
    dict(estagio="10 · Em Revisão", status="todo",
         quote='Fotos do app não apareciam no modo operador; RAT devolvida para correção chegava em branco ao técnico.',
         esperado='Fotos: modo operador recarrega as fotos com endereço válido a cada abertura da revisão — CORRIGIDO, comprovar. Retorno de RAT para correção: operador marca exatamente os campos a corrigir (+observações) e o técnico recebe só esses campos editáveis, preservando o resto preenchido — EM IMPLEMENTAÇÃO, testar ciclo completo rejeitar → corrigir → aprovar quando disponível.'),
    dict(estagio="12 · Notificações (transversal)", status="todo",
         quote="Central de notificações do operador ainda não validada; toque na notificação deveria abrir o chamado certo no mobile.",
         esperado='Mobile: toque na notificação abre o destino correto (chamado ativo, RAT ou lista de disponíveis conforme o tipo) — CORRIGIDO, comprovar. Central do operador: recebidas por mesa, contagem de não lidas, atualização automática, marcar como lida, atalho pro chamado — IMPLEMENTADA, comprovação ao vivo em curso. Pendente: notificação de escalonamento N2 mostra código do técnico em vez do nome; lembrete de 1h antes abre a lista em vez do chamado ativo.'),
    dict(estagio="Transversal · Tiflux", status="done",
         quote="Tiflux só era atualizado quando o técnico aceitava o chamado.",
         esperado="Estágio do Tiflux acompanha o fluxo em TODAS as mudanças de etapa (com reenvio automático em caso de falha). Comentários automáticos em marcos (aceite, deslocamento, conclusão, improdutiva, cancelamento) e campos preenchidos no aceite e início do atendimento. Reagendamentos espelham data/hora no Tiflux. Pendente (proposta): preenchimento automático dos campos de Fechamento a partir da RAT."),
]

_group_b = []
for i, p in enumerate(_PEND_RAW, start=1):
    tipo = "Regressão (defeito corrigido — reteste)" if p["status"] == "done" else "Regressão (em andamento/decisão pendente)"
    _group_b.append(dict(
        code=f"FC-PEND-{i:02d}",
        grupo="Grupo B",
        estagio_num=None,
        estagio=p["estagio"],
        frente="Transversal",
        tipo=tipo,
        prioridade="Alta",
        pre_condicao=(
            "Chamado de teste no estágio indicado; usar o cenário descrito na pendência original (tabela de 02/07)."
            + (" AGENDE COM PELO MENOS 24H DE ANTECEDÊNCIA a partir de agora — precisa dessa janela pra ver o lembrete de confirmação chegar; se não der tempo hoje, marca \"Bloqueado\" e revalida depois."
               if p["estagio"].startswith("04") else "")
        ),
        passos=f'1) Reproduzir o cenário da pendência: "{p["quote"]}" 2) Conferir se o comportamento atual bate com o esperado abaixo.',
        resultado_esperado=p["esperado"],
        origem="Status das pendências (02/07)",
    ))

_DELTA_RAW = [
    dict(frente="APP", texto='Tela do chamado unificada — todas as informações (dados, etapas, RAT, contatos) em uma só tela.'),
    dict(frente="APP", texto='Novas tentativas automáticas ao carregar o chamado, tempo-limite na captura de localização e correção de um travamento na abertura.'),
    dict(frente="OPR", texto='Removida a animação de movimentação dos cartões no quadro do operador (dificultava a leitura).'),
    dict(frente="OPR", texto='Operador é avisado quando um relatório (RAT) é enviado para revisão.'),
]
_group_c = []
for i, d in enumerate(_DELTA_RAW, start=1):
    _group_c.append(dict(
        code=f"FC-DELTA-{i:02d}",
        grupo="Grupo C",
        estagio_num=None,
        estagio="Transversal · Evolução da semana",
        frente=FRONT_LABEL.get(d["frente"], d["frente"]),
        tipo="Validação (comprovar ao vivo)",
        prioridade="Média",
        pre_condicao=PRECOND.get(d["frente"], "Ambiente de teste configurado."),
        passos=f"1) Reproduzir a ação relacionada ({VERIFY_WHERE.get(d['frente'], 'no sistema')}). 2) Conferir o comportamento abaixo.",
        resultado_esperado=d["texto"],
        origem="O que evoluiu esta semana",
    ))

_group_d = [dict(
    code="FC-TKFILHO-01",
    grupo="Grupo D",
    estagio_num=None,
    estagio="A definir",
    frente="A definir",
    tipo="A detalhar",
    prioridade="A definir",
    pre_condicao="[PREENCHER] Em que estágio do fluxo isso acontece? Que ação dispara a abertura do ticket filho?",
    passos="[PREENCHER] Passos para reproduzir a abertura do ticket filho.",
    resultado_esperado="[PREENCHER] Comportamento esperado: como o ticket filho deve ficar vinculado ao pai, o que deve herdar dele, e o que deve acontecer quando o filho ou o pai mudam de status.",
    origem="A detalhar por Rafa",
)]

ALL_CASES = _group_a + _group_b + _group_c + _group_d


# Campos que descrevem O CASO (mudam quando eu melhoro o texto/roteiro).
# Nunca inclui status/observacao/testado_por/screenshots — isso é do Rafa, intocável.
_SYNC_FIELDS = [
    "grupo", "estagio", "estagio_num", "frente", "tipo", "prioridade",
    "pre_condicao", "passos", "resultado_esperado", "origem",
]


def migrate_schema(engine):
    """Adiciona colunas novas (fluxo, active, user_managed) em bancos que já
    existem — create_all() só cria tabelas do zero, não altera as existentes.
    Idempotente: checa as colunas atuais antes de qualquer ALTER.
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "test_cases" not in insp.get_table_names():
        return 0
    cols = {c["name"] for c in insp.get_columns("test_cases")}
    pg = engine.dialect.name == "postgresql"
    stmts = []
    if "fluxo" not in cols:
        stmts.append("ALTER TABLE test_cases ADD COLUMN fluxo VARCHAR NOT NULL DEFAULT 'C'")
    if "active" not in cols:
        stmts.append("ALTER TABLE test_cases ADD COLUMN active BOOLEAN NOT NULL DEFAULT "
                     + ("TRUE" if pg else "1"))
    if "user_managed" not in cols:
        stmts.append("ALTER TABLE test_cases ADD COLUMN user_managed BOOLEAN NOT NULL DEFAULT "
                     + ("FALSE" if pg else "0"))
    if not stmts:
        return 0
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))
    return len(stmts)


def seed(db):
    """Popula/atualiza o banco a cada subida.

    - Caso novo (code inédito): insere com status "Não testado".
    - Caso já existente: SINCRONIZA os campos descritivos (texto do passo,
      resultado esperado etc.) com o que está em ALL_CASES aqui embaixo, mas
      NUNCA mexe em status, observação, testado_por ou nos prints já anexados
      — isso é progresso real de teste e não pode ser perdido num redeploy.
    - Caso marcado user_managed (criado/editado na tela): NÃO sincroniza nada —
      o dono do caso é o usuário, não este arquivo.
    """
    from .models import TestCase

    rows = {c.code: c for c in db.query(TestCase).all()}
    added = 0
    updated = 0
    for case in ALL_CASES:
        row = rows.get(case["code"])
        if row is None:
            db.add(TestCase(status="Não testado", observacao="", **case))
            added += 1
            continue
        if getattr(row, "user_managed", False):
            continue  # usuário assumiu esse caso — não toca nos textos dele
        changed = False
        for field in _SYNC_FIELDS:
            if getattr(row, field) != case.get(field):
                setattr(row, field, case.get(field))
                changed = True
        if changed:
            updated += 1
    if added or updated:
        db.commit()
    return added, updated


def migrate_observations(db):
    """Migração única: casos antigos guardavam UMA observação sem autor no campo
    TestCase.observacao. Agora cada nota vira uma linha em Observation, com autor
    (usa testado_por, se houver). Roda a cada subida mas é idempotente — só cria
    a nota histórica se o caso ainda não tiver nenhuma Observation e o campo
    antigo tiver texto.
    """
    from .models import TestCase, Observation

    cases = (
        db.query(TestCase)
        .filter(TestCase.observacao.isnot(None), TestCase.observacao != "")
        .all()
    )
    migrated = 0
    for case in cases:
        ja_tem = db.query(Observation).filter(Observation.test_case_id == case.id).first()
        if ja_tem:
            continue
        db.add(
            Observation(
                test_case_id=case.id,
                autor=case.testado_por,
                texto=case.observacao,
            )
        )
        migrated += 1
    if migrated:
        db.commit()
    return migrated
