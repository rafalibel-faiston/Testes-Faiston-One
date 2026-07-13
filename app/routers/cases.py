import io
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


def _get_case_or_404(db: Session, code: str) -> models.TestCase:
    case = (
        db.query(models.TestCase)
        .options(joinedload(models.TestCase.screenshots))
        .filter(models.TestCase.code == code)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail=f"Caso {code} não encontrado")
    return case


@router.get("/cases", response_model=List[schemas.TestCaseOut])
def list_cases(db: Session = Depends(get_db)):
    cases = (
        db.query(models.TestCase)
        .options(joinedload(models.TestCase.screenshots))
        .order_by(models.TestCase.grupo, models.TestCase.estagio_num.nulls_last(), models.TestCase.code)
        .all()
    )
    return cases


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
    if payload.observacao is not None:
        case.observacao = payload.observacao
    if payload.testado_por is not None:
        case.testado_por = payload.testado_por
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
