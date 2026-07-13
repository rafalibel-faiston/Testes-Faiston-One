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


class TestCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
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
    updated_at: Optional[datetime] = None
    screenshots: List[ScreenshotOut] = []


class TestCaseUpdate(BaseModel):
    status: Optional[str] = None
    observacao: Optional[str] = None
    testado_por: Optional[str] = None


class SummaryOut(BaseModel):
    total: int
    counts: dict
    pct_executado: float
