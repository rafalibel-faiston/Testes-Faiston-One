from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ScreenshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime] = None


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    autor: Optional[str] = None
    texto: str
    created_at: Optional[datetime] = None


class ObservationCreate(BaseModel):
    texto: str
    autor: Optional[str] = None


class TestCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    fluxo: str = "C"
    grupo: str
    estagio: str
    estagio_num: Optional[int] = None
    frente: str
    tipo: str
    prioridade: str
    origem: str
    pre_condicao: str
    passos: str
    resultado_esperado: str
    status: str
    observacao: Optional[str] = ""
    testado_por: Optional[str] = None
    chamado: Optional[str] = None
    user_managed: Optional[bool] = False
    updated_at: Optional[datetime] = None
    screenshots: List[ScreenshotOut] = []
    observations: List[ObservationOut] = []


class TestCaseUpdate(BaseModel):
    status: Optional[str] = None
    testado_por: Optional[str] = None
    # dado de execução (do testador) — nunca tocado pelo seed
    chamado: Optional[str] = None
    # campos descritivos — editáveis na tela; ao mudar qualquer um, o caso
    # vira user_managed e o seed para de sobrescrevê-lo.
    fluxo: Optional[str] = None
    grupo: Optional[str] = None
    estagio: Optional[str] = None
    frente: Optional[str] = None
    tipo: Optional[str] = None
    prioridade: Optional[str] = None
    origem: Optional[str] = None
    pre_condicao: Optional[str] = None
    passos: Optional[str] = None
    resultado_esperado: Optional[str] = None


class TestCaseCreate(BaseModel):
    code: Optional[str] = None          # gerado automaticamente se vazio
    fluxo: str = "C"
    grupo: str = "Grupo C"
    estagio: str
    frente: str = "A definir"
    tipo: str = "Manual"
    prioridade: str = "Média"
    origem: str = "Criado no console"
    pre_condicao: str = ""
    passos: str = ""
    resultado_esperado: str
    chamado: Optional[str] = None


class SummaryOut(BaseModel):
    total: int
    counts: dict
    pct_executado: float


class MeetingNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fluxo: str = "C"
    estagio: Optional[str] = None
    texto: str
    autor: Optional[str] = None
    resolvido: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MeetingNoteCreate(BaseModel):
    fluxo: str = "C"
    estagio: Optional[str] = None
    texto: str
    autor: Optional[str] = None


class MeetingNoteUpdate(BaseModel):
    texto: Optional[str] = None
    estagio: Optional[str] = None
    resolvido: Optional[bool] = None
