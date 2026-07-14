import io
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["cases"])

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8MB por print
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
VALID_STATUSES = {"Não testado", "Aprovado", "Reprovado", "Bloqueado", "N/A"}
# campos descritivos que, ao serem editados, tornam o caso "do usuário"
DESCRIPTIVE_FIELDS = {
    "fluxo", "grupo", "estagio", "frente", "tipo", "prioridade",
    "origem", "pre_condicao", "passos", "resultado_esperado",
}


def _parse_stage_num(estagio: str):
    """Deriva o número do estágio do rótulo (ex.: '01 · Criar OS' -> 1) para
    manter a ordenação e o agrupamento do carrossel funcionando."""
    m = re.match(r"\s*(\d+)", estagio or "")
    return int(m.group(1)) if m else None


def _next_manual_code(db: Session) -> str:
    existing = {row[0] for row in db.query(models.TestCase.code).all()}
    n = 1
    while f"FC-MAN-{n:02d}" in existing:
        n += 1
    return f"FC-MAN-{n:02d}"


def _get_case_or_404(db: Session, code: str) -> models.TestCase:
    case = (
        db.query(models.TestCase)
        .options(joinedload(models.TestCase.screenshots), joinedload(models.TestCase.observations))
        .filter(models.TestCase.code == code, models.TestCase.active.is_(True))
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail=f"Caso {code} não encontrado")
    return case


@router.get("/cases", response_model=List[schemas.TestCaseOut])
def list_cases(db: Session = Depends(get_db)):
    cases = (
        db.query(models.TestCase)
        .options(joinedload(models.TestCase.screenshots), joinedload(models.TestCase.observations))
        .filter(models.TestCase.active.is_(True))
        .order_by(models.TestCase.grupo, models.TestCase.estagio_num.nulls_last(), models.TestCase.code)
        .all()
    )
    return cases


@router.post("/cases", response_model=schemas.TestCaseOut, status_code=201)
def create_case(payload: schemas.TestCaseCreate, db: Session = Depends(get_db)):
    """Cria um caso novo pela tela. Marca user_managed=True (o seed não mexe nele)."""
    if not (payload.resultado_esperado or "").strip():
        raise HTTPException(status_code=400, detail="Informe o resultado esperado.")
    code = (payload.code or "").strip() or _next_manual_code(db)
    if db.query(models.TestCase).filter(models.TestCase.code == code).first():
        raise HTTPException(status_code=400, detail=f"Já existe um caso com o código {code}.")
    case = models.TestCase(
        code=code,
        fluxo=payload.fluxo or "C",
        grupo=payload.grupo,
        estagio=payload.estagio,
        estagio_num=_parse_stage_num(payload.estagio),
        frente=payload.frente,
        tipo=payload.tipo,
        prioridade=payload.prioridade,
        origem=payload.origem,
        pre_condicao=payload.pre_condicao,
        passos=payload.passos,
        resultado_esperado=payload.resultado_esperado,
        status="Não testado",
        observacao="",
        user_managed=True,
        active=True,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.delete("/cases/{code}")
def delete_case(code: str, db: Session = Depends(get_db)):
    """Exclusão suave: some da tela mas não ressuscita no próximo deploy."""
    case = _get_case_or_404(db, code)
    case.active = False
    case.user_managed = True  # não deixa o seed re-sincronizar/reviver
    db.commit()
    return {"deleted": code}


@router.get("/cases/{code}", response_model=schemas.TestCaseOut)
def get_case(code: str, db: Session = Depends(get_db)):
    return _get_case_or_404(db, code)


@router.patch("/cases/{code}", response_model=schemas.TestCaseOut)
def update_case(code: str, payload: schemas.TestCaseUpdate, db: Session = Depends(get_db)):
    case = _get_case_or_404(db, code)
    if payload.status is not None:
        if payload.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Status inválido: {payload.status}")
        case.status = payload.status
    if payload.testado_por is not None:
        case.testado_por = payload.testado_por

    # edição de campos descritivos → o caso passa a ser "do usuário"
    data = payload.model_dump(exclude_unset=True)
    touched_descriptive = False
    for field in DESCRIPTIVE_FIELDS:
        if field in data and data[field] is not None:
            setattr(case, field, data[field])
            touched_descriptive = True
    if "estagio" in data and data["estagio"] is not None:
        case.estagio_num = _parse_stage_num(data["estagio"])
    if touched_descriptive:
        case.user_managed = True

    db.commit()
    db.refresh(case)
    return case


@router.post("/cases/{code}/observacoes", response_model=schemas.TestCaseOut)
def add_observation(code: str, payload: schemas.ObservationCreate, db: Session = Depends(get_db)):
    """Adiciona uma nova nota ao historico do caso — nunca sobrescreve as anteriores,
    cada uma guarda o autor de quem escreveu."""
    case = _get_case_or_404(db, code)
    texto = (payload.texto or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Observação vazia.")
    db.add(models.Observation(test_case_id=case.id, autor=payload.autor, texto=texto))
    db.commit()
    db.refresh(case)
    return case


@router.delete("/observacoes/{observation_id}", response_model=schemas.TestCaseOut)
def delete_observation(observation_id: int, db: Session = Depends(get_db)):
    obs = db.query(models.Observation).filter(models.Observation.id == observation_id).first()
    if not obs:
        raise HTTPException(status_code=404, detail="Observação não encontrada")
    case = db.query(models.TestCase).filter(models.TestCase.id == obs.test_case_id).first()
    db.delete(obs)
    db.commit()
    db.refresh(case)
    return case


@router.post("/cases/{code}/screenshots", response_model=schemas.TestCaseOut)
async def upload_screenshot(
    code: str,
    file: UploadFile = File(...),
    uploaded_by: str = Form(default=None),
    db: Session = Depends(get_db),
):
    case = _get_case_or_404(db, code)

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Envie apenas imagens (png, jpg, webp, gif).")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Imagem maior que 8MB.")

    shot = models.Screenshot(
        test_case_id=case.id,
        filename=file.filename or "print.png",
        content_type=file.content_type,
        data=data,
        uploaded_by=uploaded_by,
    )
    db.add(shot)
    db.commit()
    db.refresh(case)
    return case


@router.get("/screenshots/{screenshot_id}")
def get_screenshot(screenshot_id: int, db: Session = Depends(get_db)):
    shot = db.query(models.Screenshot).filter(models.Screenshot.id == screenshot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Print não encontrado")
    return StreamingResponse(io.BytesIO(shot.data), media_type=shot.content_type)


@router.delete("/screenshots/{screenshot_id}", response_model=schemas.TestCaseOut)
def delete_screenshot(screenshot_id: int, db: Session = Depends(get_db)):
    shot = db.query(models.Screenshot).filter(models.Screenshot.id == screenshot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Print não encontrado")
    case = db.query(models.TestCase).filter(models.TestCase.id == shot.test_case_id).first()
    db.delete(shot)
    db.commit()
    db.refresh(case)
    return case


@router.get("/summary", response_model=schemas.SummaryOut)
def summary(db: Session = Depends(get_db)):
    from sqlalchemy import func

    total = db.query(models.TestCase).count()
    counts = {s: 0 for s in VALID_STATUSES}
    rows = db.query(models.TestCase.status, func.count(models.TestCase.id)).group_by(models.TestCase.status).all()
    for status, qtd in rows:
        counts[status] = counts.get(status, 0) + qtd
    executado = total - counts.get("Não testado", 0)
    pct = round((executado / total) * 100, 1) if total else 0.0
    return schemas.SummaryOut(total=total, counts=counts, pct_executado=pct)
