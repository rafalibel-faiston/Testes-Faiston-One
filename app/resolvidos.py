"""Resolvidos pra comunicar à operação.

Quando um teste vira de **Reprovado** para **Aprovado**, alguém precisa avisar a
operação de que o bug foi corrigido (ou a feature chegou). Este módulo é o ponto
único que detecta essa virada e deixa o lembrete — com a mensagem já rascunhada —
na lista `resolvidos_comunicar`. Os quatro lugares onde um status pode mudar (API
de casos, API de situações, API de ajustes e as ferramentas MCP) só chamam
`registrar_*` depois de gravar o novo status.

A regra é por NÍVEL (técnica ou operação), não pelo consolidado: o caso reprovado
que a técnica reaprova ainda aparece como "Pendente na operação" no consolidado,
e é exatamente aí que a operação precisa ser avisada pra validar.
"""
from datetime import datetime, timedelta, timezone

from . import models, niveis

BRT = timezone(timedelta(hours=-3))


def virou_aprovado(antes, depois) -> bool:
    """Reprovado → Aprovado no mesmo nível. Outras viradas (Bloqueado →
    Aprovado, Não testado → Aprovado) não são "algo que estava quebrado e foi
    consertado", então não geram lembrete."""
    return antes == niveis.REPROVADO and depois == niveis.APROVADO


def _utc(dt):
    """datetime em UTC com fuso — o SQLite devolve sem fuso, o Postgres com."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _data(quando=None) -> str:
    """Data da aprovação em DD/MM/AAAA: a do evento (no resgate) ou a de hoje."""
    return (_utc(quando).astimezone(BRT) if quando else datetime.now(BRT)).strftime("%d/%m/%Y")


def _ultima_obs(observacoes, cor, nivel=None):
    """Texto da observação mais recente com a cor pedida (vermelho = problema,
    verde = resolvido). Prefere as do mesmo nível, mas cai pra qualquer uma."""
    candidatas = [o for o in observacoes if getattr(o, "cor", None) == cor and (o.texto or "").strip()]
    do_nivel = [o for o in candidatas if getattr(o, "nivel", None) == nivel]
    escolhida = (do_nivel or candidatas or [None])[-1]
    return escolhida.texto.strip() if escolhida else None


def _mensagem(*, titulo, tipo, problema, resultado, nivel, por, chamado=None, quando=None):
    """O rascunho que vai pra operação — português claro, sem jargão de teste."""
    quem = f" por {por}" if por else ""
    linhas = [
        "Olá! Um ponto que estava reprovado nos testes foi resolvido:",
        "",
        f"• O que foi: {titulo}" + (f" ({tipo})" if tipo else ""),
    ]
    if problema:
        linhas.append(f"• O problema que havia: {problema}")
    if resultado:
        linhas.append(f"• Como deve funcionar agora: {resultado}")
    linhas.append(f"• {niveis.NIVEL_LABEL[nivel]}: aprovada{quem} em {_data(quando)}")
    if chamado:
        linhas.append(f"• Chamado de teste: {chamado}")
    linhas.append("")
    if nivel == niveis.NIVEL_OPERACAO:
        linhas.append("A operação já validou — vale avisar o time para fechar o assunto.")
    else:
        linhas.append("Pedimos que a operação confira no dia a dia e nos dê o retorno.")
    return "\n".join(linhas)


def _guardar(db, *, fluxo, origem, codigo, titulo, nivel, por, mensagem, quando=None):
    """Cria o lembrete. Se já existe um em aberto (ainda não comunicado) pro mesmo
    item e nível — reprovou e aprovou de novo antes de alguém avisar —, atualiza
    ele em vez de empilhar duplicata. O título entra na conta porque dois estágios
    da mesma situação têm o mesmo código e são coisas diferentes."""
    aberto = (
        db.query(models.ResolvidoComunicar)
        .filter(
            models.ResolvidoComunicar.origem == origem,
            models.ResolvidoComunicar.codigo == codigo,
            models.ResolvidoComunicar.titulo == titulo,
            models.ResolvidoComunicar.nivel == nivel,
            models.ResolvidoComunicar.comunicado.is_(False),
        )
        .first()
    )
    if aberto:
        aberto.titulo, aberto.resolvido_por, aberto.mensagem = titulo, por, mensagem
        return aberto
    item = models.ResolvidoComunicar(
        fluxo=fluxo or "C", origem=origem, codigo=codigo, titulo=titulo,
        nivel=nivel, resolvido_por=por, mensagem=mensagem,
        **({"created_at": _utc(quando)} if quando else {}),
    )
    db.add(item)
    return item


def registrar_caso(db, case, nivel, por, quando=None):
    """Um caso de teste foi de Reprovado para Aprovado em `nivel`."""
    chamado = case.chamado if nivel == niveis.NIVEL_INTERNO else case.chamado_operacao
    titulo = _titulo("caso", case, None)
    return _guardar(
        db, fluxo=case.fluxo, origem="caso", codigo=case.code, titulo=titulo,
        nivel=nivel, por=por,
        mensagem=_mensagem(
            titulo=titulo, tipo=case.frente,
            problema=_ultima_obs(case.observations, "vermelho", nivel) or (case.problema_encontrado or "").strip() or None,
            resultado=(case.resultado_esperado or "").strip() or None,
            nivel=nivel, por=por, chamado=chamado, quando=quando,
        ),
        quando=quando,
    )


def registrar_estagio(db, sit, est, nivel, por, quando=None):
    """Um estágio de situação foi de Reprovado para Aprovado em `nivel`."""
    chamado = sit.chamado if nivel == niveis.NIVEL_INTERNO else sit.chamado_operacao
    titulo = _titulo("situacao", sit, est)
    return _guardar(
        db, fluxo=sit.fluxo, origem="situacao", codigo=sit.code, titulo=titulo,
        nivel=nivel, por=por,
        mensagem=_mensagem(
            titulo=titulo, tipo=est.frente,
            problema=_ultima_obs(est.observations, "vermelho", nivel),
            resultado=(est.resultado_esperado or "").strip() or None,
            nivel=nivel, por=por, chamado=chamado, quando=quando,
        ),
        quando=quando,
    )


def registrar_ajuste(db, ajuste, nivel, por, quando=None):
    """Um ajuste da Gestão de Ativos foi de Reprovado para Aprovado em `nivel`.
    Aqui o tipo é conhecido — Bug ou Melhoria —, então a mensagem diz se é
    correção ou feature nova."""
    titulo = _titulo("ajuste", ajuste, None)
    return _guardar(
        db, fluxo="ATIVOS", origem="ajuste", codigo=f"AJT-{ajuste.id}", titulo=titulo,
        nivel=nivel, por=por,
        mensagem=_mensagem(
            titulo=titulo, tipo="correção de bug" if ajuste.tipo == "Bug" else "melhoria",
            problema=(ajuste.atual or "").strip() or None,
            resultado=(ajuste.esperado or "").strip() or None,
            nivel=nivel, por=por, quando=quando,
        ),
        quando=quando,
    )


def serializa(item) -> dict:
    """Formato único pra API, MCP e pauta."""
    return {
        "id": item.id, "fluxo": item.fluxo, "origem": item.origem, "codigo": item.codigo,
        "titulo": item.titulo, "nivel": item.nivel, "nivel_label": niveis.NIVEL_LABEL.get(item.nivel, item.nivel),
        "resolvido_por": item.resolvido_por, "mensagem": item.mensagem,
        "comunicado": bool(item.comunicado), "comunicado_em": item.comunicado_em,
        "comunicado_por": item.comunicado_por, "created_at": item.created_at,
    }


# --------------------------------------------------------------------------- resgate

def _le_evento(ev):
    """(chave, nível, status) de uma linha da trilha de Novidades, ou None se ela
    não é uma mudança de status de nível. A chave identifica "o mesmo teste no
    mesmo nível" — num estágio de situação inclui o nome do estágio, porque cada
    estágio tem a sua própria sequência de status."""
    texto = ev.texto or ""
    cod = ev.case_code or ""
    for nivel, label in niveis.NIVEL_LABEL.items():
        if ev.tipo == "status" and f" · {label} mudou para " in texto:
            prefixo, status = texto.split(f" · {label} mudou para ", 1)
            chave = (cod, prefixo.strip(), nivel)
        elif ev.tipo == "ajuste" and cod.startswith("AJT-") and f" · {label}: " in texto:
            status = texto.split(f" · {label}: ", 1)[1].split(" — ", 1)[0]
            chave = (cod, "", nivel)
        else:
            continue
        status = status.strip()
        if status in niveis.VALID_STATUSES:
            return chave, nivel, status
    return None


def resgatar(db, desde=None, aplicar=False):
    """Reconstrói, pela trilha de Novidades, as viradas Reprovado → Aprovado que
    aconteceram ANTES de existir o lembrete automático.

    A trilha guarda toda mudança de status (só quando muda), então a sequência de
    cada teste/nível sai exata — e vale a mesma regra de hoje: passar por "Não
    testado" no meio não conta. Sem `aplicar` é só simulação (nada é gravado).
    `desde` ("AAAA-MM-DD") ignora viradas anteriores àquele dia. É idempotente:
    o que já tem lembrete (criado ao vivo ou por um resgate anterior) é pulado.
    """
    from datetime import date

    corte = None
    if desde:
        corte = datetime.combine(date.fromisoformat(desde), datetime.min.time(), tzinfo=BRT)

    eventos = (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.tipo.in_(("status", "ajuste")))
        .order_by(models.ActivityLog.id)
        .all()
    )
    ultimo, candidatos = {}, []
    for ev in eventos:
        lido = _le_evento(ev)
        if not lido:
            continue
        chave, nivel, status = lido
        if virou_aprovado(ultimo.get(chave), status):
            candidatos.append((ev, chave, nivel))
        ultimo[chave] = status

    itens, ignorados = [], 0
    for ev, (cod, prefixo, _), nivel in candidatos:
        quando = _utc(ev.created_at)
        if corte and quando < corte:
            continue
        alvo = _localiza(db, cod, prefixo)
        if alvo is None:        # teste excluído, ajuste apagado, estágio renomeado
            ignorados += 1
            continue
        origem, obj, est = alvo
        titulo = _titulo(origem, obj, est)
        ja = [
            r for r in db.query(models.ResolvidoComunicar).filter(
                models.ResolvidoComunicar.origem == origem,
                models.ResolvidoComunicar.codigo == cod,
                models.ResolvidoComunicar.titulo == titulo,
                models.ResolvidoComunicar.nivel == nivel,
            ).all()
            if _utc(r.created_at) >= quando - timedelta(minutes=2)
        ]
        item = {"origem": origem, "codigo": cod, "titulo": titulo, "nivel": nivel,
                "resolvido_por": ev.autor, "quando": quando.isoformat(), "novo": not ja}
        itens.append(item)
        if ja or not aplicar:
            continue
        if origem == "caso":
            registrar_caso(db, obj, nivel, ev.autor, quando=quando)
        elif origem == "situacao":
            registrar_estagio(db, obj, est, nivel, ev.autor, quando=quando)
        else:
            registrar_ajuste(db, obj, nivel, ev.autor, quando=quando)
    if aplicar:
        db.commit()
    novos = sum(1 for i in itens if i["novo"])
    return {
        "aplicado": bool(aplicar), "total": len(itens), "novos": novos,
        "ja_existentes": len(itens) - novos, "ignorados": ignorados, "itens": itens,
    }


def _localiza(db, cod, prefixo):
    """(origem, objeto, estágio) do teste a que a linha da trilha se refere."""
    if cod.startswith("SIT-"):
        sit = db.query(models.Situacao).filter(models.Situacao.code == cod,
                                               models.Situacao.active.is_(True)).first()
        if not sit:
            return None
        nome = prefixo.split(" · ", 1)[1] if " · " in prefixo else ""
        est = next((e for e in sit.estagios if e.nome == nome), None)
        return ("situacao", sit, est) if est else None
    if cod.startswith("AJT-"):
        try:
            ajuste = db.query(models.AtivoAjuste).filter(models.AtivoAjuste.id == int(cod[4:])).first()
        except ValueError:
            return None
        return ("ajuste", ajuste, None) if ajuste else None
    case = db.query(models.TestCase).filter(models.TestCase.code == cod,
                                            models.TestCase.active.is_(True)).first()
    return ("caso", case, None) if case else None


def _titulo(origem, obj, est):
    """O mesmo título que os registrar_* gravam — a conta de duplicata depende disso."""
    if origem == "caso":
        return f"{obj.code} · {obj.estagio}"
    if origem == "situacao":
        return f"{obj.code} · {est.nome} ({obj.titulo})"
    return f"Ajuste #{obj.numero} ({obj.versao}) · {obj.titulo}"
