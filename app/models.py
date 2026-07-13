from sqlalchemy import Column, Integer, String, Text, LargeBinary, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, index=True, nullable=False)
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
    status = Column(String, nullable=False, default="Não testado")
    observacao = Column(Text, nullable=True, default="")
    testado_por = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    screenshots = relationship(
        "Screenshot", back_populates="test_case", cascade="all, delete-orphan", order_by="Screenshot.id"
    )
    observations = relationship(
        "Observation", back_populates="test_case", cascade="all, delete-orphan", order_by="Observation.id"
    )


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
