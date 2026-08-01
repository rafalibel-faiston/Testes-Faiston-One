import os

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["auth"])

FAISTON_SENHA = os.getenv("FAISTON_SENHA", "")


class PerfilLogin(BaseModel):
    perfil: str
    senha: str = ""


@router.post("/perfil/entrar")
def entrar_perfil(payload: PerfilLogin):
    if payload.perfil != "Faiston":
        return {"ok": True}
    if not FAISTON_SENHA:
        return {"ok": True}
    return {"ok": payload.senha == FAISTON_SENHA}