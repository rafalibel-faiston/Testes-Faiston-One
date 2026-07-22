from . import models


def log(db, fluxo, tipo, texto, autor=None, case_code=None):
    """Registra um evento na trilha de atividades. Não faz commit — pega
    carona no commit da operação que o gerou (se ela falhar, o evento
    também não entra, mantendo a trilha fiel ao que realmente aconteceu)."""
    db.add(models.ActivityLog(
        fluxo=fluxo or "C", tipo=tipo, texto=texto, autor=autor, case_code=case_code,
    ))


def snippet(texto, n=80):
    texto = (texto or "").strip().replace("\n", " ")
    return texto if len(texto) <= n else texto[: n - 1] + "…"
