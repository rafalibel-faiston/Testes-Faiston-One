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


def _hoje() -> str:
    return datetime.now(BRT).strftime("%d/%m/%Y")


def _ultima_obs(observacoes, cor, nivel=None):
    """Texto da observação mais recente com a cor pedida (vermelho = problema,
    verde = resolvido). Prefere as do mesmo nível, mas cai pra qualquer uma."""
    candidatas = [o for o in observacoes if getattr(o, "cor", None) == cor and (o.texto or "").strip()]
    do_nivel = [o for o in candidatas if getattr(o, "nivel", None) == nivel]
    escolhida = (do_nivel or candidatas or [None])[-1]
    return escolhida.texto.strip() if escolhida else None


def _mensagem(*, titulo, tipo, problema, resultado, nivel, por, chamado=None):
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
    linhas.append(f"• {niveis.NIVEL_LABEL[nivel]}: aprovada{quem} em {_hoje()}")
    if chamado:
        linhas.append(f"• Chamado de teste: {chamado}")
    linhas.append("")
    if nivel == niveis.NIVEL_OPERACAO:
        linhas.append("A operação já validou — vale avisar o time para fechar o assunto.")
    else:
        linhas.append("Pedimos que a operação confira no dia a dia e nos dê o retorno.")
    return "\n".join(linhas)


def _guardar(db, *, fluxo, origem, codigo, titulo, nivel, por, mensagem):
    """Cria o lembrete. Se já existe um em aberto (ainda não comunicado) pro mesmo
    item e nível — reprovou e aprovou de novo antes de alguém avisar —, atualiza
    ele em vez de empilhar duplicata."""
    aberto = (
        db.query(models.ResolvidoComunicar)
        .filter(
            models.ResolvidoComunicar.origem == origem,
            models.ResolvidoComunicar.codigo == codigo,
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
    )
    db.add(item)
    return item


def registrar_caso(db, case, nivel, por):
    """Um caso de teste foi de Reprovado para Aprovado em `nivel`."""
    chamado = case.chamado if nivel == niveis.NIVEL_INTERNO else case.chamado_operacao
    titulo = f"{case.code} · {case.estagio}"
    return _guardar(
        db, fluxo=case.fluxo, origem="caso", codigo=case.code, titulo=titulo,
        nivel=nivel, por=por,
        mensagem=_mensagem(
            titulo=titulo, tipo=case.frente,
            problema=_ultima_obs(case.observations, "vermelho", nivel) or (case.problema_encontrado or "").strip() or None,
            resultado=(case.resultado_esperado or "").strip() or None,
            nivel=nivel, por=por, chamado=chamado,
        ),
    )


def registrar_estagio(db, sit, est, nivel, por):
    """Um estágio de situação foi de Reprovado para Aprovado em `nivel`."""
    chamado = sit.chamado if nivel == niveis.NIVEL_INTERNO else sit.chamado_operacao
    titulo = f"{sit.code} · {est.nome} ({sit.titulo})"
    return _guardar(
        db, fluxo=sit.fluxo, origem="situacao", codigo=sit.code, titulo=titulo,
        nivel=nivel, por=por,
        mensagem=_mensagem(
            titulo=titulo, tipo=est.frente,
            problema=_ultima_obs(est.observations, "vermelho", nivel),
            resultado=(est.resultado_esperado or "").strip() or None,
            nivel=nivel, por=por, chamado=chamado,
        ),
    )


def registrar_ajuste(db, ajuste, nivel, por):
    """Um ajuste da Gestão de Ativos foi de Reprovado para Aprovado em `nivel`.
    Aqui o tipo é conhecido — Bug ou Melhoria —, então a mensagem diz se é
    correção ou feature nova."""
    titulo = f"Ajuste #{ajuste.numero} ({ajuste.versao}) · {ajuste.titulo}"
    return _guardar(
        db, fluxo="ATIVOS", origem="ajuste", codigo=f"AJT-{ajuste.id}", titulo=titulo,
        nivel=nivel, por=por,
        mensagem=_mensagem(
            titulo=titulo, tipo="correção de bug" if ajuste.tipo == "Bug" else "melhoria",
            problema=(ajuste.atual or "").strip() or None,
            resultado=(ajuste.esperado or "").strip() or None,
            nivel=nivel, por=por,
        ),
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
