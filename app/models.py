from sqlalchemy import Column, Integer, String, Text, LargeBinary, DateTime, ForeignKey, Boolean, UniqueConstraint
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


class MeetingNote(Base):
    """Ponto solto levantado durante os testes pra levar pra reunião — não
    exige nenhum caso de teste executado, só o registro da ideia/dúvida/bug."""
    __tablename__ = "meeting_notes"

    id = Column(Integer, primary_key=True)
    fluxo = Column(String, nullable=False, default="C", server_default="C")
    estagio = Column(String, nullable=True)   # de qual estágio é o ponto, se aplicável
    texto = Column(Text, nullable=False)
    autor = Column(String, nullable=True)
    resolvido = Column(Boolean, nullable=False, default=False, server_default=expression.false())
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


class Observation(Base):
    """Uma nota do historico de observacoes de um caso — cada uma com seu proprio autor,
    diferente do campo antigo `TestCase.observacao` (unico, qualquer um sobrescrevia)."""
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    autor = Column(String, nullable=True)
    texto = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    test_case = relationship("TestCase", back_populates="observations")


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
