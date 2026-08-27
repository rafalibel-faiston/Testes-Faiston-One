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


# cores que uma observação pode ter. Sem cor (None) é o padrão: a observação
# comum, que só registra algo. Verde e vermelho são a leitura rápida de quem
# passa o olho na tela — deu certo / tem problema.
CORES_OBS = ("verde", "vermelho")


def normaliza_cor(valor):
    """Aceita "verde"/"vermelho" e qualquer forma de "sem cor" — None, "",
    "neutro" —, que vira None (observação sem marcação). Cor desconhecida vira
    erro em vez de gravar um valor que a tela não sabe pintar."""
    from fastapi import HTTPException

    if valor is None:
        return None
    cor = str(valor).strip().lower()
    if cor in ("", "neutro", "nenhuma", "sem"):
        return None
    if cor not in CORES_OBS:
        raise HTTPException(
            status_code=400,
            detail='Cor inválida — use "verde", "vermelho" ou "neutro".',
        )
    return cor


def normaliza_prazo(valor):
    """Aceita "AAAA-MM-DD" (o formato que o <input type=date> manda) e devolve
    None quando o campo vem vazio — limpar o prazo é uma operação válida.
    Formato inválido vira erro em vez de gravar lixo que ninguém consegue ler
    depois."""
    from datetime import date
    from fastapi import HTTPException

    if valor is None:
        return None
    valor = valor.strip()
    if not valor:
        return None
    try:
        date.fromisoformat(valor)
    except ValueError:
        raise HTTPException(status_code=400, detail="Prazo inválido — use o formato AAAA-MM-DD.")
    return valor
