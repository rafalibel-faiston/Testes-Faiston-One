from sqlalchemy import (
    Column, Integer, String, Text, LargeBinary, DateTime, ForeignKey, Boolean, UniqueConstraint, case,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, expression

from .database import Base


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, index=True, nullable=False)
    fluxo = Column(String, nullable=False, default="C", server_default="C")  # Fluxo A / B / C
    grupo = Column(String, nullable=False)          # Grupo A / B / C / D
    estagio = Column(String, nullable=False)
    estagio_num = Column(Integer, nullable=True)
    frente = Column(String, nullable=False)          # Operador (web) / App do técnico / Transversal / A definir
    tipo = Column(String, nullable=False)
    prioridade = Column(String, nullable=False)
    origem = Column(String, nullable=False)
    pre_condicao = Column(Text, nullable=False)
    passos = Column(Text, nullable=False)
    resultado_esperado = Column(Text, nullable=False)
    # texto original do "problema encontrado" (planilha-mãe do projeto), quando existe —
    # usado na exportação Excel pra reproduzir o formato original com o status atualizado.
    problema_encontrado = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="Não testado")
    observacao = Column(Text, nullable=True, default="")
    testado_por = Column(String, nullable=True)
    chamado = Column(String, nullable=True)     # chamado testado
    # active=False é exclusão suave (some da tela, não ressuscita no deploy, recuperável).
    active = Column(Boolean, nullable=False, default=True, server_default=expression.true())
    # user_managed=True marca um caso que o usuário criou/editou na tela — o seed
    # NUNCA sobrescreve os textos desse caso num redeploy.
    user_managed = Column(Boolean, nullable=False, default=False, server_default=expression.false())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    screenshots = relationship(
        "Screenshot", back_populates="test_case", cascade="all, delete-orphan", order_by="Screenshot.id"
    )
    observations = relationship(
        "Observation", back_populates="test_case", cascade="all, delete-orphan", order_by="Observation.id"
    )


class Situacao(Base):
    """Um cenário descrito por completo (ex.: "chamado sem aceite") que se conta
    passo a passo através de vários estágios do chamado — cada estágio é o
    'mini caso de teste' daquele passo específico dentro da história do cenário.
    Vive dentro de um fluxo (A/B/C), ao lado dos Grupos de casos de teste, sem
    substituí-los."""
    __tablename__ = "situacoes"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, index=True, nullable=False)
    fluxo = Column(String, nullable=False, default="C", server_default="C")
    titulo = Column(String, nullable=False)
    descricao = Column(Text, nullable=False)
    origem = Column(String, nullable=True)
    # um único chamado testado vale pra situação inteira (todos os estágios são
    # passos do mesmo atendimento sendo percorrido, não atendimentos separados)
    chamado = Column(String, nullable=True)
    # active=False é exclusão suave (some da tela, não ressuscita no deploy porque o
    # seed de situações só insere quando o code está totalmente ausente da tabela).
    active = Column(Boolean, nullable=False, default=True, server_default=expression.true())
    user_managed = Column(Boolean, nullable=False, default=False, server_default=expression.false())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    estagios = relationship(
        "SituacaoEstagio", back_populates="situacao", cascade="all, delete-orphan",
        order_by="SituacaoEstagio.ordem",
    )


class SituacaoEstagio(Base):
    """Um estágio do chamado dentro de uma Situação, com seu próprio status,
    observações e prints — igual a um TestCase, só que aninhado sob a situação
    em vez de solto num grupo."""
    __tablename__ = "situacao_estagios"

    id = Column(Integer, primary_key=True)
    situacao_id = Column(Integer, ForeignKey("situacoes.id", ondelete="CASCADE"), nullable=False)
    ordem = Column(Integer, nullable=False, default=0, server_default="0")
    nome = Column(String, nullable=False)           # ex.: "03 · Téc. Aceitou"
    frente = Column(String, nullable=False, default="Transversal")
    passos = Column(Text, nullable=True, default="")
    resultado_esperado = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="Não testado")
    testado_por = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    situacao = relationship("Situacao", back_populates="estagios")
    screenshots = relationship(
        "SituacaoScreenshot", back_populates="estagio", cascade="all, delete-orphan", order_by="SituacaoScreenshot.id"
    )
    observations = relationship(
        "SituacaoObservation", back_populates="estagio", cascade="all, delete-orphan", order_by="SituacaoObservation.id"
    )


class SituacaoObservation(Base):
    __tablename__ = "situacao_observations"

    id = Column(Integer, primary_key=True)
    estagio_id = Column(Integer, ForeignKey("situacao_estagios.id", ondelete="CASCADE"), nullable=False)
    autor = Column(String, nullable=True)
    texto = Column(Text, nullable=False)
    # marcação de cor da observação: "verde" (deu certo, resolvido) ou "vermelho"
    # (problema, pendência). None é a observação normal, sem cor — o padrão de
    # quem só quer anotar algo.
    cor = Column(String, nullable=True)
    # quem atualizou o texto pela última vez e quando — o texto original (e cada
    # versão intermediária) fica guardado em `revisions`, nada se perde na edição.
    editado_por = Column(String, nullable=True)
    editado_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    estagio = relationship("SituacaoEstagio", back_populates="observations")
    revisions = relationship(
        "SituacaoObservationRevision", back_populates="observation",
        cascade="all, delete-orphan", order_by="SituacaoObservationRevision.id",
    )


class SituacaoObservationRevision(Base):
    """Versão anterior do texto de uma observação de estágio — mesma ideia da
    trilha do caso de teste (ver ObservationRevision)."""
    __tablename__ = "situacao_observation_revisions"

    id = Column(Integer, primary_key=True)
    observation_id = Column(
        Integer, ForeignKey("situacao_observations.id", ondelete="CASCADE"), nullable=False
    )
    texto = Column(Text, nullable=False)
    cor = Column(String, nullable=True)
    autor = Column(String, nullable=True)
    editado_por = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    observation = relationship("SituacaoObservation", back_populates="revisions")


class SituacaoScreenshot(Base):
    __tablename__ = "situacao_screenshots"

    id = Column(Integer, primary_key=True)
    estagio_id = Column(Integer, ForeignKey("situacao_estagios.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    data = Column(LargeBinary, nullable=False)
    uploaded_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    estagio = relationship("SituacaoEstagio", back_populates="screenshots")


class MeetingNote(Base):
    """Ponto solto levantado durante os testes pra levar pra reunião — não
    exige nenhum caso de teste executado, só o registro da ideia/dúvida/bug."""
    __tablename__ = "meeting_notes"

    id = Column(Integer, primary_key=True)
    fluxo = Column(String, nullable=False, default="C", server_default="C")
    estagio = Column(String, nullable=True)   # de qual estágio é o ponto, se aplicável
    texto = Column(Text, nullable=False)
    autor = Column(String, nullable=True)
    # cobrado=True: já foi levado/comunicado pra outra parte (LP, etc.) — passo
    # intermediário entre "anotado" e "resolvido", pra saber se falta só cobrar
    # de novo ou se ainda nem foi levantado com eles.
    cobrado = Column(Boolean, nullable=False, default=False, server_default=expression.false())
    cobrado_em = Column(DateTime(timezone=True), nullable=True)
    resolvido = Column(Boolean, nullable=False, default=False, server_default=expression.false())
    resolvido_em = Column(DateTime(timezone=True), nullable=True)
    # o que a outra ponta respondeu quando o ponto foi levado pra reunião, e a
    # data que eles se comprometeram a resolver. Fica separado do `texto` de
    # propósito: um é o que a Faiston levantou, o outro é o que eles devolveram.
    retorno = Column(Text, nullable=True, default="")
    prazo = Column(String, nullable=True)          # "AAAA-MM-DD"
    retorno_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class FlowDiagram(Base):
    """Diagrama Mermaid de um fluxo — descreve como um fluxo está funcionando
    hoje (kind="atual") ou como deveria funcionar (kind="ideal"), com uma
    descrição da situação real. Editável na tela; o seed só cria os iniciais
    quando ainda não existe nenhum diagrama daquele fluxo/kind (não sobrescreve
    o que o time editou)."""
    __tablename__ = "flow_diagrams"

    id = Column(Integer, primary_key=True)
    fluxo = Column(String, nullable=False, default="C", server_default="C")  # Fluxo A / B / C
    kind = Column(String, nullable=False, default="atual", server_default="atual")  # atual / ideal
    titulo = Column(String, nullable=False)
    descricao = Column(Text, nullable=True, default="")   # situação real descrita
    mermaid = Column(Text, nullable=False)                 # código-fonte Mermaid
    ordem = Column(Integer, nullable=True, default=0, server_default="0")
    atualizado_por = Column(String, nullable=True)
    # seeded=True marca um diagrama que veio do seed e ainda não foi editado —
    # assim que o time edita, vira False e o seed nunca mais mexe nele.
    seeded = Column(Boolean, nullable=False, default=False, server_default=expression.false())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class ActivityLog(Base):
    """Trilha de atividades — cada mudança relevante (status, observação, print,
    teste criado/editado, ponto de reunião, diagrama) vira um evento, pra quem
    entra depois ver o que aconteceu desde a última visita sem se perder."""
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True)
    fluxo = Column(String, nullable=False, default="C", server_default="C")
    tipo = Column(String, nullable=False)      # status / obs / print / teste / ponto / diagrama
    texto = Column(Text, nullable=False)       # descrição legível do que aconteceu
    autor = Column(String, nullable=True)
    case_code = Column(String, nullable=True)  # caso relacionado, quando houver
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TeamView(Base):
    """Marca de 'até onde este time já viu as Novidades', por perfil e fluxo.
    Guarda o id do último evento visto (monotônico) em vez de um horário — evita
    qualquer problema de fuso e é o 'login da LP/Faiston': se uma pessoa da LP
    abre as Novidades, marca como visto pra LP toda, em qualquer computador."""
    __tablename__ = "team_views"
    __table_args__ = (UniqueConstraint("perfil", "fluxo", name="uq_team_view_perfil_fluxo"),)

    id = Column(Integer, primary_key=True)
    perfil = Column(String, nullable=False)     # "LP" / "Faiston"
    fluxo = Column(String, nullable=False, default="C", server_default="C")
    last_seen_id = Column(Integer, nullable=False, default=0, server_default="0")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class AgendaEvento(Base):
    """Compromisso da agenda do time Faiston — só aparece pra quem entra como
    Faiston, é compartilhada pelo time todo (sem login por pessoa)."""
    __tablename__ = "agenda_eventos"

    id = Column(Integer, primary_key=True)
    titulo = Column(String, nullable=False)
    descricao = Column(Text, nullable=True, default="")
    data = Column(String, nullable=False)          # "AAAA-MM-DD"
    hora_inicio = Column(String, nullable=True)    # "HH:MM"
    hora_fim = Column(String, nullable=True)        # "HH:MM"
    # categoriza o compromisso pra colorir/filtrar na agenda: marco, relatorio,
    # revisao, checkpoint, reuniao ou compromisso (padrão, genérico).
    tipo = Column(String, nullable=False, default="compromisso", server_default="compromisso")
    # marca compromissos recorrentes (ex.: entrega de relatório diário) como
    # cumpridos, sem precisar excluir o evento da agenda.
    concluido = Column(Boolean, nullable=False, default=False, server_default=expression.false())
    autor = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class TodoTarefa(Base):
    """Cartão do quadro Kanban (A Fazer / Fazendo / Feito) do time Faiston."""
    __tablename__ = "todo_tarefas"

    id = Column(Integer, primary_key=True)
    titulo = Column(String, nullable=False)
    descricao = Column(Text, nullable=True, default="")
    status = Column(String, nullable=False, default="a_fazer", server_default="a_fazer")
    posicao = Column(Integer, nullable=False, default=0, server_default="0")
    responsavel = Column(String, nullable=True)
    autor = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class AtivoAjuste(Base):
    """Um ajuste pedido no módulo Gestão de Ativos do Faiston One.

    Cada linha é um item do tipo "hoje é assim / deveria ser assim", classificado
    como Bug (está quebrado) ou Melhoria (funciona, mas precisa evoluir). O campo
    `versao` agrupa a leva de ajustes ("v2" agora) — quando surgir a próxima
    rodada, é só cadastrar com versao="v3" que a tela ganha a aba nova sozinha,
    sem mexer no código.
    """
    __tablename__ = "ativo_ajustes"

    id = Column(Integer, primary_key=True)
    versao = Column(String, nullable=False, default="v2", server_default="v2")
    # número do item dentro da versão (1, 2, 3...) — é o "#" da lista que o time usa
    # pra se referir ao ajuste em reunião; também define a ordem na tela.
    numero = Column(Integer, nullable=False, default=0, server_default="0")
    titulo = Column(String, nullable=False)
    tipo = Column(String, nullable=False, default="Melhoria", server_default="Melhoria")  # Bug / Melhoria
    # área/tela do sistema afetada (Entrada, Cotação, Tracking, Estoque...) — texto
    # livre de propósito: o vocabulário do módulo ainda está mudando.
    area = Column(String, nullable=True)
    prioridade = Column(String, nullable=False, default="Média", server_default="Média")
    atual = Column(Text, nullable=False, default="")      # como está hoje
    esperado = Column(Text, nullable=False, default="")   # como deve ser
    observacao = Column(Text, nullable=True, default="")  # detalhes, decisões, links
    status = Column(String, nullable=False, default="levantado", server_default="levantado")
    responsavel = Column(String, nullable=True)
    autor = Column(String, nullable=True)
    # retorno do time de dev na reunião e a data prometida — mesma ideia do
    # MeetingNote: o que eles responderam, separado do que a gente pediu.
    retorno = Column(Text, nullable=True, default="")
    prazo = Column(String, nullable=True)          # "AAAA-MM-DD"
    retorno_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    prints = relationship(
        "AtivoAjustePrint", back_populates="ajuste", cascade="all, delete-orphan",
        order_by="AtivoAjustePrint.id",
    )


class AtivoAjustePrint(Base):
    """Print colado (Ctrl+V) ou anexado num ajuste — a imagem do sistema mostrando
    o comportamento atual vale mais que o parágrafo descrevendo ele. Guardado como
    bytes no próprio banco, igual aos prints dos casos de teste."""
    __tablename__ = "ativo_ajuste_prints"

    id = Column(Integer, primary_key=True)
    ajuste_id = Column(Integer, ForeignKey("ativo_ajustes.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    data = Column(LargeBinary, nullable=False)
    uploaded_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ajuste = relationship("AtivoAjuste", back_populates="prints")


# Ordem em que o time ataca os ajustes: Alta primeiro, o que ainda não foi
# priorizado por último. Usada pela API e pelo MCP pra devolver a lista já na
# ordem que a tela mostra.
AJUSTE_PRIORIDADE_ORDEM = case(
    (AtivoAjuste.prioridade == "Alta", 0),
    (AtivoAjuste.prioridade == "Média", 1),
    (AtivoAjuste.prioridade == "Baixa", 2),
    else_=3,
)


class Observation(Base):
    """Uma nota do historico de observacoes de um caso — cada uma com seu proprio autor,
    diferente do campo antigo `TestCase.observacao` (unico, qualquer um sobrescrevia)."""
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    autor = Column(String, nullable=True)
    texto = Column(Text, nullable=False)
    # marcação de cor da observação: "verde" (deu certo, resolvido) ou "vermelho"
    # (problema, pendência). None é a observação normal, sem cor — o padrão de
    # quem só quer anotar algo.
    cor = Column(String, nullable=True)
    # a observação pode ser atualizada quando o ponto evolui (foi ajustado, mudou
    # de entendimento, ganhou detalhe). `texto` é sempre a versão vigente; quem
    # atualizou e quando ficam aqui, e o que estava escrito antes vira uma linha
    # da trilha em `revisions` — editar nunca apaga o que já foi dito.
    editado_por = Column(String, nullable=True)
    editado_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    test_case = relationship("TestCase", back_populates="observations")
    revisions = relationship(
        "ObservationRevision", back_populates="observation",
        cascade="all, delete-orphan", order_by="ObservationRevision.id",
    )


class ObservationRevision(Base):
    """Uma versão anterior do texto de uma observação — a trilha das atualizações.
    Cada edição empurra o texto que estava valendo pra cá, com o autor original da
    versão e quem a substituiu, então dá pra ler a observação do começo ao fim:
    o que foi escrito primeiro, o que virou depois e por quem."""
    __tablename__ = "observation_revisions"

    id = Column(Integer, primary_key=True)
    observation_id = Column(Integer, ForeignKey("observations.id", ondelete="CASCADE"), nullable=False)
    texto = Column(Text, nullable=False)        # o texto que estava valendo antes da edição
    cor = Column(String, nullable=True)         # a cor que essa versão tinha
    autor = Column(String, nullable=True)       # quem tinha escrito essa versão
    editado_por = Column(String, nullable=True) # quem a substituiu
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    observation = relationship("Observation", back_populates="revisions")


class Screenshot(Base):
    __tablename__ = "screenshots"

    id = Column(Integer, primary_key=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    data = Column(LargeBinary, nullable=False)
    uploaded_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    test_case = relationship("TestCase", back_populates="screenshots")
