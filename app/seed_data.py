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


# "Problema encontrado" original (planilha-mãe do projeto, Dispatcher_Andamento —
# aba "Ajustes Fluxo C", 19/06/2026), casado por (estágio, frente, resultado_esperado)
# com o texto que já usávamos aqui. Só entram pares com correspondência EXATA de texto
# — itens refinados/adicionados depois dessa planilha ficam sem "problema encontrado"
# (a exportação cai pro texto de Passos nesses casos) em vez de arriscar um match errado.
_ORIGINAL_PROBLEMA = {
    (1, 'OPR', 'Novo chamado aparece no painel com o estado certo'): 'Chamado não aparece no painel',
    (2, 'APP', 'Novo chamado aparece e pode ser aceito (caminho normal)'): 'Novo chamado não estava aparecendo corretamente para aceite no aplicativo.',
    (3, 'OPR', 'Painel passa para "Técnico Confirmado", fiel'): 'Após o aceite do técnico, o painel não refletia corretamente o status de técnico confirmado.',
    (3, 'APP', 'Ao aceitar, o chamado sai da lista e o passo avança'): 'Após o aceite, o aplicativo não atualizava corretamente a lista e o avanço de etapa.',
    (4, 'OPR', 'Painel mostra "Agendado", fiel'): 'O painel não refletia corretamente o status de agendamento do chamado.',
    (4, 'APP', 'Mostra "Aguardando início" (não "Em rota")'): 'O aplicativo exibia status incorreto na etapa de agendamento.',
    (4, 'APP', '"Iniciar" bloqueado até confirmar e chegar a data'): 'O botão “Iniciar” ficava disponível antes da confirmação e da data prevista.',
    (5, 'OPR', 'Painel mostra "Deslocamento", fiel'): 'O painel não refletia corretamente o início do deslocamento do técnico.',
    (5, 'APP', 'Passo avança para "Em Rota"'): 'A barra de progresso não avançava corretamente para a etapa de deslocamento.',
    (5, 'APP', 'Botão "Navegar" abre a rota até o endereço'): 'O técnico não conseguia iniciar a navegação pela rota do atendimento.',
    (6, 'OPR', 'Painel mostra "Aguardando Liberação", fiel'): 'Painel não está mostrando o botão "Aguardando liberação"',
    (6, 'APP', 'Botão "Acesso Liberado" reconectado e funcional'): 'Não está funcionando o botão "Acesso liberado"',
    (6, 'APP', 'A etapa aparece com o rótulo "Aguardando Liberação de Acesso"'): 'Aguardando liberação de acesso não aparece',
    (6, 'APP', 'O técnico registra "Acesso Liberado" e então toca "Iniciar Atendimento" — sem etapa de liberação pelo operador'): 'Mudança de fluxo',
    (7, 'OPR', 'Painel mostra "Em Execução" e recebe os horários de chegada/início'): 'Não está aparecendo data e hora de chegada do técnico',
    (7, 'APP', 'Tela "Em Atendimento"; cronômetro mede o tempo real'): 'SLA não estava sendo contabilizado',
    (7, 'APP', '"Concluir" removido da visão do técnico'): 'Opção "Concluir" tirar da visualização do técnico',
    (8, 'OPR', 'Painel mostra "Suporte N2"; operador conduz "Acompanhamento Concluído"'): 'N2 deve realizar o acompanhamento',
    (8, 'APP', 'Técnico sem ação; botões indevidos ocultos por perfil'): 'Técnico está tendo ação nesse ticket',
    (9, 'OPR', 'Painel mostra o chamado aguardando relatório/revisão, fiel'): 'Não estava mostrando o relatorio',
    (9, 'APP', 'Tela da RAT abre e é enviada pelo app, mesmo abrindo do zero'): 'RAT não encaminhada ao técnico',
    (10, 'OPR', 'Tela de revisão (aprovar/recusar, ver fotos e assinatura), fiel'): 'Tela não estava aparecendo dados da rat',
    (10, 'APP', 'Corrigido: ao recusar, "Corrigir RAT" preserva fotos e assinatura'): 'Fotos não anexando no app',
    (11, 'OPR', 'Painel mostra "Concluído" e encerra o bloco de revisão'): 'Não aparece opção "Concluido"',
    (11, 'APP', 'Tela mostra "Concluído"'): 'Não aparece opção "Concluido"',
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
        problema_encontrado=_ORIGINAL_PROBLEMA.get((stage_num, front, text)),
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
        problema_encontrado=p["quote"],
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

# ---------------------------------------------------------------------------
# Evolução da semana de 29/07: tempo de espera por aceite configurável, os dois
# prazos distintos de "Ocorrência" (sem aceite × não confirmar presença),
# horário de início da RAT pela liberação de acesso, e distância de trajeto
# real no app do técnico. Cenários com pré-condição/passos próprios (mais
# detalhados que o template genérico acima) porque cada um exige montar uma
# situação específica no chamado de teste para reproduzir o comportamento.
# Fonte: dashboard_flowC_1507, atualização de 29/07/2026.
# ---------------------------------------------------------------------------
_EVOL_2907 = [
    dict(frente="Operador (web)", prioridade="Alta",
         pre_condicao="Operador logado no painel web, com acesso à tela Configurações → Notificações.",
         passos='1) Abrir Configurações → Notificações. 2) Alterar o tempo de espera por aceite do despacho para um valor dentro do intervalo permitido (ex.: 10 minutos) e salvar. 3) Disparar a busca de um chamado de teste sem que nenhum técnico aceite.',
         resultado_esperado='O campo aceita valores entre 5 e 120 minutos (padrão 30) e salva a alteração. Passado o tempo configurado sem nenhum técnico aceitar a busca, o chamado vai automaticamente para "Ocorrência" — o disparo pode levar até 5 min a mais que o valor configurado.'),
    dict(frente="Operador (web)", prioridade="Média",
         pre_condicao="Operador logado no painel web, com acesso à tela Configurações → Notificações.",
         passos='1) Em Configurações → Notificações, tentar salvar o tempo de espera por aceite com um valor abaixo de 5 minutos. 2) Tentar salvar novamente com um valor acima de 120 minutos.',
         resultado_esperado='O sistema não aceita valores fora do intervalo de 5 a 120 minutos — bloqueia o salvamento ou ajusta ao limite mais próximo, nunca permitindo menos de 5 nem mais de 120 minutos.'),
    dict(frente="Operador (web)", prioridade="Alta",
         pre_condicao="Chamado de teste pronto para disparar a busca de técnico; tempo de espera por aceite configurado e conhecido (ex.: 30 min).",
         passos='1) Disparar a busca do chamado de teste. 2) Antes do prazo se esgotar, ir em Configurações → Notificações e alterar o tempo de espera por aceite para um valor diferente (ex.: 5 min). 3) Continuar sem que nenhum técnico aceite e aguardar o desfecho.',
         resultado_esperado='A busca já em andamento mantém o tempo original configurado no momento do disparo — não encurta nem estende para o novo valor. Apenas os próximos disparos passam a usar o novo tempo configurado.'),
    dict(frente="Transversal", prioridade="Alta",
         pre_condicao="Chamado de teste com técnico(s) de teste orientados a não aceitar a busca; tempo de espera por aceite configurado e conhecido.",
         passos='1) Disparar a busca do chamado de teste. 2) Não aceitar em nenhum técnico (app nem link do WhatsApp) durante todo o tempo configurado. 3) Esgotado o prazo, conferir o chamado no painel do operador e no app do técnico.',
         resultado_esperado='Esgotado o tempo de espera por aceite sem nenhum técnico aceitar, o chamado ("sem aceite") muda automaticamente para "Ocorrência": some da lista de disponíveis do técnico e fica bloqueado em visualização, detalhe e aceite (app e link do WhatsApp). Só volta a ficar ofertável quando o operador usa "Re-disparar busca".'),
    dict(frente="Operador (web)", prioridade="Média",
         pre_condicao="Operador logado no painel web, com acesso à tela Configurações → Notificações.",
         passos='1) Abrir Configurações → Notificações. 2) Ler os textos/rótulos dos campos relacionados a ocorrência, incluindo o campo antes chamado "Prazo para ocorrência".',
         resultado_esperado='A tela explica que um chamado pode ir para "Ocorrência" em dois momentos distintos: (a) ninguém aceita a busca dentro do tempo configurado, ou (b) o técnico aceita mas não confirma a presença antes do horário agendado. O campo antigo "Prazo para ocorrência" aparece renomeado para "Prazo final de confirmação de presença", sem confundir os dois prazos.'),
    dict(frente="App do técnico", prioridade="Alta",
         pre_condicao='Chamado de teste agendado e aceito por um técnico de teste; "Prazo final de confirmação de presença" configurado e conhecido.',
         passos='1) Técnico aceita o chamado agendado, sem confirmar a presença em seguida. 2) Ignorar o lembrete/pedido de confirmação de presença até o prazo final configurado se esgotar. 3) Esgotado o prazo, conferir o chamado no painel do operador e no app do técnico.',
         resultado_esperado='Esgotado o "Prazo final de confirmação de presença" sem o técnico confirmar, o chamado vai para "Ocorrência" por um motivo distinto do "sem aceite" (o técnico havia aceitado, mas não confirmou presença), some da agenda do técnico e segue o mesmo tratamento de ocorrência — bloqueado para aceite até a operação usar "Re-disparar busca".'),
    dict(frente="Operador (web)", prioridade="Média",
         pre_condicao="Chamado de teste em andamento, com acesso ao Tiflux/relatório do atendimento.",
         passos='1) Levar um chamado de teste até o técnico registrar "Acesso Liberado". 2) Conferir no Tiflux o campo "Hora Início da Atividade" desse atendimento. 3) Comparar com o horário em que o técnico havia aceitado o chamado.',
         resultado_esperado='O horário de início registrado corresponde ao momento em que o chamado entra em "Aguardando Liberação" (liberação de acesso, quando o atendimento realmente começa) — não ao horário em que o técnico aceitou o chamado. O horário de término permanece correto, sem alteração.'),
    dict(frente="App do técnico", prioridade="Média",
         pre_condicao="Técnico de teste logado no app, com um chamado de teste cujo endereço tenha distância por rota perceptivelmente maior que a distância em linha reta.",
         passos='1) Abrir o detalhe do chamado de teste no app do técnico. 2) Conferir a distância exibida abaixo do endereço. 3) Comparar com a distância informada na mensagem do WhatsApp recebida para o mesmo chamado.',
         resultado_esperado='A distância exibida no app é a distância de deslocamento por rota (por vias), igual à da mensagem do WhatsApp — não mais a distância em linha reta, que ficava visivelmente menor que o trajeto real (ex.: ~13 km em linha reta para um trajeto real de ~23 km por rota).'),
]
_evol_start = len(_DELTA_RAW) + 1
for i, d in enumerate(_EVOL_2907, start=_evol_start):
    _group_c.append(dict(
        code=f"FC-DELTA-{i:02d}",
        grupo="Grupo C",
        estagio_num=None,
        estagio="Transversal · Evolução da semana",
        frente=d["frente"],
        tipo="Validação (comprovar ao vivo)",
        prioridade=d["prioridade"],
        pre_condicao=d["pre_condicao"],
        passos=d["passos"],
        resultado_esperado=d["resultado_esperado"],
        origem="O que evoluiu esta semana (29/07)",
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
    "pre_condicao", "passos", "resultado_esperado", "problema_encontrado", "origem",
]


def migrate_schema(engine):
    """Adiciona colunas novas em tabelas que já existem — create_all() só cria
    tabelas do zero, não altera as existentes. Idempotente: checa as colunas
    atuais antes de qualquer ALTER.
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    pg = engine.dialect.name == "postgresql"
    stmts = []

    if "test_cases" in existing_tables:
        cols = {c["name"] for c in insp.get_columns("test_cases")}
        if "fluxo" not in cols:
            stmts.append("ALTER TABLE test_cases ADD COLUMN fluxo VARCHAR NOT NULL DEFAULT 'C'")
        if "active" not in cols:
            stmts.append("ALTER TABLE test_cases ADD COLUMN active BOOLEAN NOT NULL DEFAULT "
                         + ("TRUE" if pg else "1"))
        if "user_managed" not in cols:
            stmts.append("ALTER TABLE test_cases ADD COLUMN user_managed BOOLEAN NOT NULL DEFAULT "
                         + ("FALSE" if pg else "0"))
        if "chamado" not in cols:
            stmts.append("ALTER TABLE test_cases ADD COLUMN chamado VARCHAR")
        if "problema_encontrado" not in cols:
            stmts.append("ALTER TABLE test_cases ADD COLUMN problema_encontrado TEXT")

    if "meeting_notes" in existing_tables:
        note_cols = {c["name"] for c in insp.get_columns("meeting_notes")}
        if "estagio" not in note_cols:
            stmts.append("ALTER TABLE meeting_notes ADD COLUMN estagio VARCHAR")
        if "cobrado" not in note_cols:
            stmts.append("ALTER TABLE meeting_notes ADD COLUMN cobrado BOOLEAN NOT NULL DEFAULT "
                         + ("FALSE" if pg else "0"))
        if "cobrado_em" not in note_cols:
            stmts.append("ALTER TABLE meeting_notes ADD COLUMN cobrado_em "
                         + ("TIMESTAMP WITH TIME ZONE" if pg else "TIMESTAMP"))
        if "resolvido_em" not in note_cols:
            stmts.append("ALTER TABLE meeting_notes ADD COLUMN resolvido_em "
                         + ("TIMESTAMP WITH TIME ZONE" if pg else "TIMESTAMP"))
        if "retorno" not in note_cols:
            stmts.append("ALTER TABLE meeting_notes ADD COLUMN retorno TEXT")
        if "prazo" not in note_cols:
            stmts.append("ALTER TABLE meeting_notes ADD COLUMN prazo VARCHAR")
        if "retorno_em" not in note_cols:
            stmts.append("ALTER TABLE meeting_notes ADD COLUMN retorno_em "
                         + ("TIMESTAMP WITH TIME ZONE" if pg else "TIMESTAMP"))

    if "ativo_ajustes" in existing_tables:
        aj_cols = {c["name"] for c in insp.get_columns("ativo_ajustes")}
        if "retorno" not in aj_cols:
            stmts.append("ALTER TABLE ativo_ajustes ADD COLUMN retorno TEXT")
        if "prazo" not in aj_cols:
            stmts.append("ALTER TABLE ativo_ajustes ADD COLUMN prazo VARCHAR")
        if "retorno_em" not in aj_cols:
            stmts.append("ALTER TABLE ativo_ajustes ADD COLUMN retorno_em "
                         + ("TIMESTAMP WITH TIME ZONE" if pg else "TIMESTAMP"))

    if "situacoes" in existing_tables:
        sit_cols = {c["name"] for c in insp.get_columns("situacoes")}
        if "chamado" not in sit_cols:
            stmts.append("ALTER TABLE situacoes ADD COLUMN chamado VARCHAR")

    # trilha das observações: quem atualizou o texto e quando (o texto anterior
    # vai pras tabelas *_observation_revisions, criadas pelo create_all)
    for tabela in ("observations", "situacao_observations"):
        if tabela in existing_tables:
            obs_cols = {c["name"] for c in insp.get_columns(tabela)}
            if "editado_por" not in obs_cols:
                stmts.append(f"ALTER TABLE {tabela} ADD COLUMN editado_por VARCHAR")
            if "editado_em" not in obs_cols:
                stmts.append(f"ALTER TABLE {tabela} ADD COLUMN editado_em "
                             + ("TIMESTAMP WITH TIME ZONE" if pg else "TIMESTAMP"))

    # cor da observação (verde/vermelho) — nas observações e nas versões da
    # trilha; NULL nas antigas, que continuam sendo observações sem marcação
    for tabela in ("observations", "situacao_observations",
                   "observation_revisions", "situacao_observation_revisions"):
        if tabela in existing_tables:
            if "cor" not in {c["name"] for c in insp.get_columns(tabela)}:
                stmts.append(f"ALTER TABLE {tabela} ADD COLUMN cor VARCHAR")

    # formulário de feedback do técnico (link por token) + o que ele respondeu
    if "tecnicos" in existing_tables:
        tec_cols = {c["name"] for c in insp.get_columns("tecnicos")}
        if "token" not in tec_cols:
            stmts.append("ALTER TABLE tecnicos ADD COLUMN token VARCHAR")
        if "nota" not in tec_cols:
            stmts.append("ALTER TABLE tecnicos ADD COLUMN nota INTEGER")
        if "etapas_testadas" not in tec_cols:
            stmts.append("ALTER TABLE tecnicos ADD COLUMN etapas_testadas TEXT")
        if "respondido_em" not in tec_cols:
            stmts.append("ALTER TABLE tecnicos ADD COLUMN respondido_em "
                         + ("TIMESTAMP WITH TIME ZONE" if pg else "TIMESTAMP"))

    # relato do técnico que virou item do backlog da Gestão de Ativos
    if "tecnico_observacoes" in existing_tables:
        obs_tec_cols = {c["name"] for c in insp.get_columns("tecnico_observacoes")}
        if "ajuste_id" not in obs_tec_cols:
            stmts.append("ALTER TABLE tecnico_observacoes ADD COLUMN ajuste_id INTEGER")

    if "agenda_eventos" in existing_tables:
        ag_cols = {c["name"] for c in insp.get_columns("agenda_eventos")}
        if "tipo" not in ag_cols:
            stmts.append("ALTER TABLE agenda_eventos ADD COLUMN tipo VARCHAR NOT NULL DEFAULT 'compromisso'")
        if "concluido" not in ag_cols:
            stmts.append("ALTER TABLE agenda_eventos ADD COLUMN concluido BOOLEAN NOT NULL DEFAULT "
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


FLOW_C_IDEAL = """flowchart TD
    A[01 · Criar OS] --> B[02 · Buscando Tecnico]
    B --> C[03 · Tec. Aceitou]
    C --> D[04 · Agendado]
    D --> E[05 · Tec. em Deslocamento]
    E --> F[06 · Aguardando Liberacao]
    F --> G[07 · Tec. em Atendimento]
    G --> H{Precisa de N2?}
    H -- Sim --> I[08 · Acompanhamento N2]
    H -- Nao --> J[09 · Aguardando RAT]
    I --> J
    J --> K[10 · Em Revisao]
    K --> L{RAT aprovada?}
    L -- Sim --> M[11 · Atividade Concluida]
    L -- Nao --> J
"""

FLOW_C_ATUAL = """flowchart TD
    A[01 · Criar OS] --> B[02 · Buscando Tecnico]
    B -. as vezes precisa Reenviar busca .-> B
    B --> C[03 · Tec. Aceitou]
    C --> D[04 · Agendado]
    D --> E[05 · Tec. em Deslocamento]
    E --> F[06 · Aguardando Liberacao]
    F --> G[07 · Tec. em Atendimento]
    G --> G2[Operador clica Acompanhamento Concluido]
    G2 --> J[09 · Aguardando RAT]
    J --> K[10 · Em Revisao]
    K --> M[11 · Atividade Concluida]
"""

# Diagramas iniciais por fluxo. O time pode editar/adicionar depois; o seed só
# cria estes quando ainda NAO existe nenhum diagrama daquele fluxo (idempotente).
SEED_DIAGRAMS = [
    dict(
        fluxo="C", kind="ideal", ordem=0,
        titulo="Fluxo C — como deveria funcionar",
        descricao="Caminho ideal do despacho NEXO, do Criar OS ate a Atividade "
                  "Concluida, com os dois pontos de decisao (escalonamento N2 e "
                  "aprovacao da RAT).",
        mermaid=FLOW_C_IDEAL,
    ),
    dict(
        fluxo="C", kind="atual", ordem=0,
        titulo="Fluxo C — como esta funcionando hoje",
        descricao="Comportamento observado nos testes: a busca de tecnico as vezes "
                  "exige 'Reenviar busca' manual, e quem encerra o estagio 07 e o "
                  "OPERADOR (clicando em 'Acompanhamento Concluido'), nao o tecnico. "
                  "Edite este diagrama conforme forem aparecendo mais situacoes reais.",
        mermaid=FLOW_C_ATUAL,
    ),
]


def seed_diagrams(db):
    """Cria os diagramas iniciais de fluxo na primeira subida. Idempotente:
    para cada (fluxo, kind) do SEED_DIAGRAMS, só insere se ainda não houver
    NENHUM diagrama daquele fluxo+kind no banco — assim nunca sobrescreve o que
    o time editou ou os diagramas extras que criaram."""
    from .models import FlowDiagram

    added = 0
    for d in SEED_DIAGRAMS:
        exists = (
            db.query(FlowDiagram)
            .filter(FlowDiagram.fluxo == d["fluxo"], FlowDiagram.kind == d["kind"])
            .first()
        )
        if exists:
            continue
        db.add(FlowDiagram(seeded=True, **d))
        added += 1
    if added:
        db.commit()
    return added


def backfill_tecnico_tokens(db):
    """Dá um token de formulário aos técnicos cadastrados antes de o formulário
    existir. Idempotente: só preenche quem está sem token."""
    from .models import Tecnico, novo_token_tecnico

    sem_token = db.query(Tecnico).filter(Tecnico.token.is_(None)).all()
    for tecnico in sem_token:
        tecnico.token = novo_token_tecnico()
    if sem_token:
        db.commit()
    return len(sem_token)


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


# ---------------------------------------------------------------------------
# SITUAÇÕES — cenários contados passo a passo por estágios do chamado, dentro
# do Fluxo C, ao lado dos Grupos A/B/C/D (não os substitui). Cada situação usa
# a régua padrão dos 12 estágios do fluxo como ponto de partida, mas pode
# inserir estágios próprios quando o cenário desvia do caminho normal (ex.:
# "vai para Ocorrência" no meio do caminho) — o time pode editar tudo na tela.
# ---------------------------------------------------------------------------
def _sit_estagio(nome, frente, resultado_esperado, passos="", status=None):
    return dict(nome=nome, frente=frente, resultado_esperado=resultado_esperado,
                passos=passos, status=status or "Não testado")


SITUACOES_SEED = [
    dict(
        code="SIT-01",
        fluxo="C",
        titulo="Chamado agendado — técnico aceita, sem ocorrência",
        descricao=(
            "Cenário de referência (sem desvio): um chamado é criado com data agendada, um "
            "técnico aceita a busca dentro do prazo, confirma presença e o atendimento é "
            "concluído do início ao fim sem nenhuma ocorrência no meio do caminho."
        ),
        origem="Cenários de evolução da semana (29/07)",
        estagios=[
            _sit_estagio("01 · Criar OS", "Operador (web)",
                "Chamado é criado com data e hora agendadas e aparece no painel do operador no estado inicial correto."),
            _sit_estagio("02 · Buscando Técnico", "Transversal",
                "Sistema dispara a busca de técnico; o chamado fica disponível para aceite (app e link do WhatsApp) "
                "dentro do tempo de espera por aceite configurado, sem esgotar o prazo."),
            _sit_estagio("03 · Téc. Aceitou", "App do técnico",
                "Um técnico aceita a busca antes do prazo se esgotar; o chamado sai da lista de disponíveis e "
                "nenhuma ocorrência é gerada."),
            _sit_estagio("04 · Agendado", "App do técnico",
                'Chamado passa para "Agendado"; "Iniciar Deslocamento" fica bloqueado até a data marcada. O lembrete '
                "de confirmação (~24h antes) e o pedido de confirmação de execução (~2h antes) chegam normalmente, e "
                'o técnico confirma presença dentro do "Prazo final de confirmação de presença" — sem gerar ocorrência.'),
            _sit_estagio("05 · Téc. em Deslocamento", "App do técnico",
                'No dia agendado, com a presença já confirmada, "Iniciar Deslocamento" é liberado; o painel do '
                'operador passa a mostrar "Em Rota".'),
            _sit_estagio("06 · Aguardando Liberação", "App do técnico",
                'Técnico chega ao local, registra "Acesso Liberado" e toca "Iniciar Atendimento"; o horário de início '
                "registrado passa a refletir este momento (liberação de acesso), não o do aceite."),
            _sit_estagio("07 · Téc. em Atendimento", "App do técnico",
                'Atendimento decorre normalmente; o cronômetro mede o tempo real e o painel mostra "Em Execução" com '
                "os horários de chegada/início."),
            _sit_estagio("08 · Acompanhamento N2", "Operador (web)",
                "Não aplicável neste cenário — o atendimento é concluído sem necessidade de escalonamento ao "
                "suporte N2.", status="N/A"),
            _sit_estagio("09 · Aguardando RAT", "Operador (web)",
                'Operador clica "Acompanhamento Concluído"; o sistema solicita a RAT ao técnico, que abre e envia '
                "normalmente."),
            _sit_estagio("10 · Em Revisão", "Operador (web)",
                "Técnico envia a RAT; operador revisa fotos e assinatura e aprova sem apontar nenhuma correção."),
            _sit_estagio("11 · Atividade Concluída", "Operador (web)",
                'Painel mostra "Concluído"; o técnico é liberado e o app também mostra o chamado como concluído.'),
            _sit_estagio("12 · Notificações (transversal)", "Transversal",
                "Cada marco do fluxo (aceite, confirmação de presença, deslocamento, liberação, conclusão) dispara "
                "notificação por push/WhatsApp corretamente — nenhum alerta de ocorrência é disparado neste cenário."),
        ],
    ),
    dict(
        code="SIT-02",
        fluxo="C",
        titulo="Chamado imediato com reagendamento, ocorrência no meio",
        descricao=(
            "Um chamado criado para atendimento imediato (sem data marcada) precisa ser "
            "reagendado depois do aceite — e, na nova data, o técnico não confirma presença a "
            "tempo, gerando uma ocorrência antes de o atendimento ser retomado por outro técnico."
        ),
        origem="Cenários de evolução da semana (29/07)",
        estagios=[
            _sit_estagio("01 · Criar OS", "Operador (web)",
                "Chamado é criado sem data marcada (atendimento imediato) e aparece no painel do operador."),
            _sit_estagio("02 · Buscando Técnico", "Transversal",
                "Busca é disparada imediatamente; um técnico aceita dentro do tempo de espera por aceite configurado."),
            _sit_estagio("03 · Téc. Aceitou", "App do técnico",
                "Técnico aceita o chamado, mas identifica que não pode atender agora e solicita o reagendamento "
                "pelo app."),
            _sit_estagio("04 · Agendado (reagendamento)", "Operador (web)",
                "Operador reagenda o chamado para uma nova data; a partir daqui, o chamado passa a exigir "
                'confirmação de presença dentro do "Prazo final de confirmação de presença" para essa nova data.'),
            _sit_estagio("Ocorrência por não confirmar presença", "Transversal",
                'O técnico não confirma a presença para a nova data dentro do prazo configurado; o chamado vai para '
                '"Ocorrência" (motivo: não confirmação — distinto de "sem aceite"), some da agenda do técnico e fica '
                "bloqueado para aceite/visualização (app e link do WhatsApp)."),
            _sit_estagio("Ocorrência — retomada pela operação", "Operador (web)",
                'Operador usa "Re-disparar busca"; o chamado volta a ficar ofertável e um novo técnico pode '
                "aceitá-lo normalmente."),
            _sit_estagio("05 · Téc. em Deslocamento", "App do técnico",
                'Um novo técnico aceita a nova busca, confirma presença e inicia o deslocamento; painel mostra '
                '"Em Rota".'),
            _sit_estagio("06 · Aguardando Liberação", "App do técnico",
                'Técnico chega, registra "Acesso Liberado" e inicia o atendimento.'),
            _sit_estagio("07 · Téc. em Atendimento", "App do técnico",
                "Atendimento decorre normalmente até a conclusão."),
            _sit_estagio("08 · Acompanhamento N2", "Operador (web)",
                "Não aplicável neste cenário — não há escalonamento ao N2.", status="N/A"),
            _sit_estagio("09 · Aguardando RAT", "Operador (web)",
                'Operador clica "Acompanhamento Concluído"; RAT é solicitada e enviada normalmente.'),
            _sit_estagio("10 · Em Revisão", "Operador (web)",
                "Operador aprova a RAT sem pendências."),
            _sit_estagio("11 · Atividade Concluída", "Operador (web)",
                "Chamado é concluído; técnico é liberado."),
            _sit_estagio("12 · Notificações (transversal)", "Transversal",
                "O histórico no Tiflux registra o reagendamento e a ocorrência corretamente, com os comentários "
                "automáticos de cada marco (incluindo o motivo da ocorrência)."),
        ],
    ),
    dict(
        code="SIT-03",
        fluxo="C",
        titulo="Chamado sem aceite (ocorrência por falta de aceite)",
        descricao=(
            "Nenhum técnico aceita a busca dentro do tempo de espera configurado; o chamado deve "
            'ir automaticamente para "Ocorrência" por falta de aceite — cenário curto, encerra '
            "antes de chegar ao deslocamento."
        ),
        origem="Cenários de evolução da semana (29/07)",
        estagios=[
            _sit_estagio("01 · Criar OS", "Operador (web)",
                "Chamado é criado e aparece no painel do operador, pronto para a busca de técnico."),
            _sit_estagio("02 · Buscando Técnico — busca disparada", "Transversal",
                "Sistema dispara a busca; o tempo de espera por aceite está configurado e conhecido (ex.: 10 min)."),
            _sit_estagio("Prazo de aceite esgota sem ninguém aceitar", "Transversal",
                "Nenhum técnico aceita a busca (app nem link do WhatsApp) durante todo o tempo configurado."),
            _sit_estagio("Chamado vai para Ocorrência (sem aceite)", "Transversal",
                'Esgotado o tempo, o chamado muda automaticamente para "Ocorrência"; some da lista de disponíveis '
                "do técnico e fica bloqueado em visualização, detalhe e aceite."),
            _sit_estagio("Ocorrência — chamado bloqueado", "App do técnico",
                "Tentativas de abrir o chamado pelo app ou pelo link do WhatsApp são bloqueadas enquanto ele "
                "estiver em Ocorrência."),
            _sit_estagio("Re-disparar busca", "Operador (web)",
                'Operador usa "Re-disparar busca"; o chamado volta a ficar ofertável a técnicos, saindo do estado '
                "de Ocorrência."),
        ],
    ),
    dict(
        code="SIT-04",
        fluxo="C",
        titulo="Chamado com ocorrência por não confirmar presença",
        descricao=(
            'Um técnico aceita um chamado agendado, mas não confirma a presença antes do "Prazo '
            'final de confirmação de presença"; o chamado deve ir para "Ocorrência" por um motivo '
            'distinto do "sem aceite".'
        ),
        origem="Cenários de evolução da semana (29/07)",
        estagios=[
            _sit_estagio("01 · Criar OS", "Operador (web)",
                "Chamado é criado com data agendada e aparece no painel."),
            _sit_estagio("02 · Buscando Técnico", "Transversal",
                "Busca é disparada normalmente."),
            _sit_estagio("03 · Téc. Aceitou", "App do técnico",
                "Um técnico aceita o chamado agendado dentro do tempo de espera por aceite."),
            _sit_estagio("04 · Agendado — aguardando confirmação de presença", "App do técnico",
                "O lembrete de confirmação (~24h antes) e o pedido de confirmação de execução (~2h antes) chegam "
                'normalmente; o "Prazo final de confirmação de presença" está configurado e conhecido.'),
            _sit_estagio("Técnico não confirma presença", "App do técnico",
                "O técnico ignora os lembretes e não confirma presença dentro do prazo final configurado."),
            _sit_estagio("Chamado vai para Ocorrência (não confirmar)", "Transversal",
                'Esgotado o prazo, o chamado vai para "Ocorrência" por um motivo distinto do "sem aceite" (o '
                "técnico havia aceitado, mas não confirmou); some da agenda do técnico e fica bloqueado para aceite."),
            _sit_estagio("Re-disparar busca", "Operador (web)",
                'Operador usa "Re-disparar busca"; o chamado volta a ficar ofertável a outro técnico, seguindo o '
                'mesmo tratamento de ocorrência do cenário "sem aceite".'),
        ],
    ),
]


def seed_situacoes(db):
    """Cria as situações iniciais na primeira subida. Idempotente por código:
    só insere quando o code está totalmente ausente da tabela — nunca sobrescreve
    o que o time editou ou apagou (soft delete mantém o code presente, então
    uma situação excluída não ressuscita num redeploy)."""
    from .models import Situacao, SituacaoEstagio

    added = 0
    for s in SITUACOES_SEED:
        if db.query(Situacao).filter(Situacao.code == s["code"]).first():
            continue
        sit = Situacao(
            code=s["code"], fluxo=s.get("fluxo", "C"), titulo=s["titulo"],
            descricao=s["descricao"], origem=s.get("origem"),
        )
        db.add(sit)
        db.flush()
        for i, e in enumerate(s["estagios"], start=1):
            db.add(SituacaoEstagio(
                situacao_id=sit.id,
                ordem=i,
                nome=e["nome"],
                frente=e.get("frente", "Transversal"),
                passos=e.get("passos", ""),
                resultado_esperado=e["resultado_esperado"],
                status=e.get("status", "Não testado"),
            ))
        added += 1
    if added:
        db.commit()
    return added


# ---------------------------------------------------------------------------
# Plano de Testes – Operação Logística (14/08 a 04/09/2026)
# Fonte: cronograma passado pelo time em 14/08/2026. 3 semanas de validação da
# ferramenta junto ao time operacional logístico, com acompanhamento paralelo
# em Excel e desmame gradual da planilha na semana final.
# ---------------------------------------------------------------------------

_DUPLAS_S1 = (
    "- Ezequiel (ferramenta) / Diego (planilha)\n"
    "- Alice (ferramenta) / Kauan (planilha)\n"
    "- Ronald (ferramenta) / Lucas (planilha)\n"
    "- Raquel (ferramenta) / Grazi (planilha)"
)
_DUPLAS_S2 = (
    "- Diego (ferramenta) / Ezequiel (planilha)\n"
    "- Kauan (ferramenta) / Alice (planilha)\n"
    "- Lucas (ferramenta) / Ronald (planilha)\n"
    "- Grazi (ferramenta) / Raquel (planilha)"
)
_RELATORIO_DIARIO_DESC = (
    "Cada dupla entrega ao final do dia:\n"
    "- Erros identificados\n"
    "- Bugs encontrados\n"
    "- Sugestões de melhoria\n"
    "- Dificuldades encontradas durante a utilização\n"
    "- Chamados tratados\n"
    "- Divergências entre ferramenta e base operacional\n"
    "- Pontos que necessitam de acompanhamento"
)

AGENDA_OPERACAO_LOGISTICA = [
    dict(
        titulo="Kickoff — Input de todas as bases na ferramenta",
        data="2026-08-14",
        tipo="marco",
        descricao="Input de todas as bases operacionais na ferramenta, garantindo que "
                   "todas as informações necessárias estejam disponíveis para o início "
                   "dos testes. Marca o início do Plano de Testes – Operação Logística "
                   "(14/08 a 04/09/2026, 3 semanas).",
    ),
    dict(
        titulo="Início Semana 1 — Teste ao vivo do fluxo completo (mesa NTT)",
        data="2026-08-17",
        tipo="marco",
        descricao="Teste ao vivo com o fluxo completo da operação logística, acompanhando "
                   "o processo de ponta a ponta em cenário real. Mesa para teste: NTT "
                   "(provisória). Objetivo: validar o funcionamento da ferramenta dentro "
                   "da rotina operacional, identificando erros, bugs, dificuldades, "
                   "divergências e oportunidades de melhoria.\n\n"
                   "Duplas — um integrante testa na ferramenta, o outro alimenta a base em "
                   "Excel em paralelo:\n" + _DUPLAS_S1,
    ),
    *[
        dict(
            titulo="Entrega do relatório diário — Semana 1",
            data=d,
            hora_inicio="17:30",
            tipo="relatorio",
            descricao=_RELATORIO_DIARIO_DESC,
        )
        for d in ["2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21"]
    ],
    dict(
        titulo="Revisão do processo + feedback dos pontos focais (fechamento Semana 1)",
        data="2026-08-21",
        tipo="revisao",
        descricao="Revisão do processo junto às operações, em paralelo aos testes: avaliar "
                   "se os erros e dificuldades identificados são da ferramenta ou do "
                   "próprio processo operacional. Coletar feedback dos pontos focais das "
                   "operações sobre o funcionamento do processo e definir os ajustes "
                   "necessários antes de avançar para a Semana 2.",
    ),
    dict(
        titulo="Início Semana 2 — Inversão das duplas",
        data="2026-08-24",
        tipo="marco",
        descricao="Inversão das responsabilidades dentro das duplas: quem testou a "
                   "ferramenta na Semana 1 passa a alimentar a base operacional, e "
                   "vice-versa — garantindo que todos participem ativamente e tenham "
                   "experiência prática na ferramenta.\n\n" + _DUPLAS_S2,
    ),
    *[
        dict(
            titulo="Entrega do relatório diário — Semana 2",
            data=d,
            hora_inicio="17:30",
            tipo="relatorio",
            descricao=_RELATORIO_DIARIO_DESC,
        )
        for d in ["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"]
    ],
    dict(
        titulo="Checkpoint — erros operacionais x erros de ferramenta",
        data="2026-08-26",
        tipo="checkpoint",
        descricao="Verificação dos erros operacionais, principalmente relacionados à "
                   "abertura dos chamados, com o objetivo de diferenciar possíveis falhas "
                   "da ferramenta de erros relacionados à execução do processo.",
    ),
    dict(
        titulo="Início Semana 3 — Testes finais + Plano de Desmame da Planilha",
        data="2026-08-31",
        tipo="marco",
        descricao="Testes finais com a operação logística, considerando os ajustes, erros "
                   "e melhorias levantados nas semanas anteriores. Foco em validar a "
                   "estabilidade da ferramenta e avaliar se está preparada para substituir "
                   "o processo hoje feito pela planilha.\n\n"
                   "Início também do Plano de Desmame da Planilha — os 9 passos estão no "
                   "quadro de tarefas (Todo), coluna 'A Fazer'.",
    ),
    dict(
        titulo="Encerramento — Resultado esperado do Plano de Testes",
        data="2026-09-04",
        tipo="marco",
        descricao="Ao final das 3 semanas, definir:\n"
                   "- Se a ferramenta está apta para utilização definitiva\n"
                   "- Quais erros ou melhorias ainda precisam ser tratados\n"
                   "- Se existem riscos operacionais para a retirada da planilha\n"
                   "- Quais processos ainda precisam de ajustes\n"
                   "- Se a operação está preparada para trabalhar exclusivamente na nova "
                   "ferramenta\n"
                   "- Se o fluxo completo da operação logística está funcionando "
                   "corretamente de ponta a ponta\n\n"
                   "Objetivo final: concluir os testes com segurança, validar o "
                   "funcionamento da ferramenta em ambiente operacional e realizar a "
                   "transição da planilha para a ferramenta de forma controlada, reduzindo "
                   "riscos e garantindo a continuidade da operação.",
    ),
]

TODO_DESMAME_PLANILHA = [
    "Reduzir gradualmente a utilização da planilha",
    "Priorizar o registro das atividades diretamente na ferramenta",
    "Comparar os dados registrados na ferramenta com a base de controle",
    "Monitorar possíveis divergências ou perda de informações",
    "Validar se os principais fluxos operacionais estão funcionando corretamente",
    "Consolidar os erros e pendências identificados",
    "Definir os responsáveis pelas correções necessárias",
    "Validar junto à operação se a ferramenta está apta para utilização definitiva",
    "Definir o momento adequado para encerramento da utilização da planilha",
]


def seed_agenda_operacao_logistica(db):
    """Cronograma do Plano de Testes – Operação Logística (14/08 a 04/09/2026) na
    Agenda do time Faiston. Idempotente por (titulo, data): só insere o que ainda
    não existe, então não duplica em redeploys nem apaga o que o time editou."""
    from .models import AgendaEvento

    added = 0
    for ev in AGENDA_OPERACAO_LOGISTICA:
        exists = (
            db.query(AgendaEvento)
            .filter(AgendaEvento.titulo == ev["titulo"], AgendaEvento.data == ev["data"])
            .first()
        )
        if exists:
            continue
        db.add(AgendaEvento(
            titulo=ev["titulo"],
            descricao=ev.get("descricao", ""),
            data=ev["data"],
            hora_inicio=ev.get("hora_inicio"),
            hora_fim=ev.get("hora_fim"),
            tipo=ev.get("tipo", "compromisso"),
            autor="Plano de Testes",
        ))
        added += 1
    if added:
        db.commit()
    return added


def seed_todo_desmame_planilha(db):
    """Os 9 passos do Plano de Desmame da Planilha (Semana 3) como cartões no
    quadro de tarefas, coluna 'A Fazer'. Idempotente por título."""
    from sqlalchemy import func as sa_func
    from .models import TodoTarefa

    added = 0
    max_pos = db.query(sa_func.max(TodoTarefa.posicao)).filter(TodoTarefa.status == "a_fazer").scalar() or 0
    for i, passo in enumerate(TODO_DESMAME_PLANILHA, start=1):
        titulo = f"Desmame {i}/9 — {passo}"
        if db.query(TodoTarefa).filter(TodoTarefa.titulo == titulo).first():
            continue
        max_pos += 1
        db.add(TodoTarefa(
            titulo=titulo,
            descricao="Plano de Desmame da Planilha — Semana 3 (31/08 a 04/09/2026) do "
                      "Plano de Testes – Operação Logística.",
            status="a_fazer",
            posicao=max_pos,
            autor="Plano de Testes",
        ))
        added += 1
    if added:
        db.commit()
    return added


# ---------------------------------------------------------------------------
# Gestão de Ativos — ajustes da v2
# ---------------------------------------------------------------------------
# Levantamento feito pela Faiston sobre o módulo de Gestão de Ativos que já está
# no ar: cada item traz "como está hoje" (atual) e "como deve ser" (esperado),
# classificado como Bug (está quebrado) ou Melhoria (funciona, mas precisa
# evoluir). As próximas levas entram como versao="v3" etc. — pela tela ou aqui.
AJUSTES_GESTAO_ATIVOS_V2 = [
    {
        "numero": 1,
        "titulo": "Entrada Manual não atribui Cliente e Valor",
        "tipo": "Bug",
        "area": "Entrada",
        "prioridade": "Alta",
        "atual": "Ao criar uma entrada manual (manual entry) de ativo, os campos Cliente e Valor "
                 "não são preenchidos/associados ao registro.",
        "esperado": "A entrada manual deve gravar corretamente Cliente e Valor no momento do "
                    "cadastro, igual acontece nos outros fluxos de entrada.",
    },
    {
        "numero": 2,
        "titulo": "Cotação por Email — múltiplas modalidades no mesmo envio",
        "tipo": "Melhoria",
        "area": "Cotação",
        "prioridade": "Média",
        "atual": "O fluxo de cotação por email não suporta pedir duas modalidades (Convencional + "
                 "Emergencial) pra mesma transportadora num único email.",
        "esperado": "Permitir que, num mesmo envio de cotação, sejam solicitados os dois tipos de "
                    "frete (Convencional e Emergencial), com as duas respostas capturadas/associadas "
                    "corretamente ao chamado.",
    },
    {
        "numero": 3,
        "titulo": "Tracking — responsável, sinalização de tratamento e alerta de prazo",
        "tipo": "Melhoria",
        "area": "Tracking",
        "prioridade": "Alta",
        "atual": "• Não existe controle de responsável (owner) pelo chamado — o sistema só identifica "
                 "se houve alguma atualização no dia, sem exigir isso nem indicar quem está tratando.\n"
                 "• Não há sinalização visual (flag/status) mostrando se o chamado já foi tratado ou "
                 "ainda está pendente.\n"
                 "• Não existe alerta (notification/alert) quando o chamado está se aproximando da "
                 "data de entrega.",
        "esperado": "• Campo de responsável por chamado, com atualização diária obrigatória.\n"
                    "• Indicador visual claro (badge ou cor) mostrando se o chamado foi tratado hoje "
                    "ou está pendente.\n"
                    "• Alerta automático quando a data de entrega estiver próxima (definir prazo de "
                    "antecedência — ex.: 1 ou 2 dias antes).",
    },
    {
        "numero": 4,
        "titulo": "Técnico Retira — falta opção de seguir com GRM",
        "tipo": "Bug",
        "area": "Expedição",
        "prioridade": "Alta",
        "atual": "Ao abrir um ticket com a opção de entrega \"Técnico Retira\", o sistema pula direto "
                 "pra emissão de Nota Fiscal, sem oferecer a opção de seguir com GRM.",
        "esperado": "Ao selecionar \"Técnico Retira\", o sistema deve oferecer as duas opções de saída "
                    "— GRM ou Nota Fiscal.",
    },
    {
        "numero": 5,
        "titulo": "Localização detalhada dentro do estoque",
        "tipo": "Melhoria",
        "area": "Estoque",
        "prioridade": "Média",
        "atual": "O item fica vinculado apenas ao estoque (warehouse) como um todo, sem sublocalização.",
        "esperado": "Criar um nível de localização dentro do estoque (pallet 1, pallet 2, armário 1, "
                    "armário 2, etc.), pra saber onde exatamente o item está fisicamente, não só em "
                    "qual estoque.",
    },
    {
        "numero": 6,
        "titulo": "Status/histórico de condição do equipamento (GOOD/BAD)",
        "tipo": "Melhoria",
        "area": "Reversa",
        "prioridade": "Média",
        "atual": "Não existe controle histórico da condição de saída/retorno do equipamento — alguns "
                 "equipamentos costumam sair GOOD e voltar como reversa BAD, mas isso não é rastreado.",
        "esperado": "Registrar o status de condição (GOOD/BAD) a cada movimentação/reversa do "
                    "equipamento, permitindo ver o histórico e identificar equipamentos com tendência "
                    "recorrente de retorno BAD.",
    },
    {
        "numero": 7,
        "titulo": "Travar valor do equipamento até vínculo com cotação",
        "tipo": "Melhoria",
        "area": "Entrada",
        "prioridade": "Média",
        "atual": "Não há trava (lock) do valor lançado na entrada do equipamento.",
        "esperado": "Travar o valor informado na entrada até que o serial seja vinculado a uma cotação; "
                    "nesse momento, o sistema deve preencher automaticamente esse valor na cotação "
                    "(auto-fill), evitando divergência manual.",
    },
]


def seed_ativos_ajustes(db):
    """Os ajustes levantados pra v2 da Gestão de Ativos. Idempotente por
    (versao, titulo): só insere o que ainda não existe, então redeploy não
    duplica nem sobrescreve o que o time editou/moveu de status na tela."""
    from .models import AtivoAjuste

    added = 0
    for item in AJUSTES_GESTAO_ATIVOS_V2:
        exists = (
            db.query(AtivoAjuste)
            .filter(AtivoAjuste.versao == "v2", AtivoAjuste.titulo == item["titulo"])
            .first()
        )
        if exists:
            continue
        db.add(AtivoAjuste(
            versao="v2",
            numero=item["numero"],
            titulo=item["titulo"],
            tipo=item["tipo"],
            area=item.get("area"),
            prioridade=item.get("prioridade", "Média"),
            atual=item["atual"],
            esperado=item["esperado"],
            observacao="",
            status="levantado",
            autor="Levantamento Faiston",
        ))
        added += 1
    if added:
        db.commit()
    return added
