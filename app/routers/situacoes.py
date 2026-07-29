import io
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..activity import log as log_activity, snippet
from ..database import get_db
from .cases import VALID_STATUSES, MAX_UPLOAD_BYTES, ALLOWED_CONTENT_TYPES

router = APIRouter(tags=["situacoes"])


def _next_situacao_code(db: Session) -> str:
    existing = {row[0] for row in db.query(models.Situacao.code).all()}
    n = 1
    while f"SIT-{n:02d}" in existing:
        n += 1
    return f"SIT-{n:02d}"


def _situacao_query(db: Session):
    return db.query(models.Situacao).options(
        joinedload(models.Situacao.estagios).joinedload(models.SituacaoEstagio.screenshots),
        joinedload(models.Situacao.estagios).joinedload(models.SituacaoEstagio.observations),
    )


def _get_situacao_or_404(db: Session, code: str) -> models.Situacao:
    sit = (
        _situacao_query(db)
        .filter(models.Situacao.code == code, models.Situacao.active.is_(True))
        .first()
    )
    if not sit:
        raise HTTPException(status_code=404, detail=f"Situação {code} não encontrada")
    return sit


def _get_estagio_in(sit: models.Situacao, estagio_id: int) -> models.SituacaoEstagio:
    est = next((e for e in sit.estagios if e.id == estagio_id), None)
    if not est:
        raise HTTPException(status_code=404, detail="Estágio não encontrado nesta situação")
    return est


@router.get("/situacoes", response_model=List[schemas.SituacaoOut])
def list_situacoes(db: Session = Depends(get_db)):
    return (
        _situacao_query(db)
        .filter(models.Situacao.active.is_(True))
        .order_by(models.Situacao.id)
        .all()
    )


@router.post("/situacoes", response_model=schemas.SituacaoOut, status_code=201)
def create_situacao(payload: schemas.SituacaoCreate, db: Session = Depends(get_db)):
    """Cria uma situação nova pela tela. Marca user_managed=True (o seed não mexe nela)."""
    if not (payload.titulo or "").strip():
        raise HTTPException(status_code=400, detail="Informe o título da situação.")
    if not (payload.descricao or "").strip():
        raise HTTPException(status_code=400, detail="Descreva a situação.")
    code = (payload.code or "").strip() or _next_situacao_code(db)
    if db.query(models.Situacao).filter(models.Situacao.code == code).first():
        raise HTTPException(status_code=400, detail=f"Já existe uma situação com o código {code}.")
    sit = models.Situacao(
        code=code,
        fluxo=payload.fluxo or "C",
        titulo=payload.titulo,
        descricao=payload.descricao,
        origem=payload.origem,
        user_managed=True,
        active=True,
    )
    db.add(sit)
    db.flush()
    log_activity(db, sit.fluxo, "situacao", f"Situação {code} criada ({sit.titulo})", case_code=code)
    db.commit()
    return _get_situacao_or_404(db, code)


@router.get("/situacoes/{code}", response_model=schemas.SituacaoOut)
def get_situacao(code: str, db: Session = Depends(get_db)):
    return _get_situacao_or_404(db, code)


@router.patch("/situacoes/{code}", response_model=schemas.SituacaoOut)
def update_situacao(code: str, payload: schemas.SituacaoUpdate, db: Session = Depends(get_db)):
    sit = _get_situacao_or_404(db, code)

    # dado de execução — do testador, não é "conteúdo" da situação (não vira user_managed)
    if payload.chamado is not None:
        sit.chamado = payload.chamado

    data = payload.model_dump(exclude_unset=True)
    changed = False
    for field in ("fluxo", "titulo", "descricao", "origem"):
        if field in data and data[field] is not None:
            setattr(sit, field, data[field])
            changed = True
    if changed:
        sit.user_managed = True
        log_activity(db, sit.fluxo, "situacao", f"Situação {code} editada", case_code=code)
    db.commit()
    return _get_situacao_or_404(db, code)


@router.delete("/situacoes/{code}")
def delete_situacao(code: str, db: Session = Depends(get_db)):
    """Exclusão suave: some da tela mas não ressuscita no próximo deploy (o seed
    só insere uma situação quando o código dela está totalmente ausente)."""
    sit = _get_situacao_or_404(db, code)
    sit.active = False
    sit.user_managed = True
    log_activity(db, sit.fluxo, "situacao", f"Situação {code} excluída", case_code=code)
    db.commit()
    return {"deleted": code}


@router.post("/situacoes/{code}/estagios", response_model=schemas.SituacaoOut, status_code=201)
def add_estagio(code: str, payload: schemas.SituacaoEstagioCreate, db: Session = Depends(get_db)):
    sit = _get_situacao_or_404(db, code)
    if not (payload.nome or "").strip():
        raise HTTPException(status_code=400, detail="Informe o nome do estágio.")
    if not (payload.resultado_esperado or "").strip():
        raise HTTPException(status_code=400, detail="Informe o resultado esperado do estágio.")
    ordem = payload.ordem
    if ordem is None:
        maxord = (
            db.query(func.max(models.SituacaoEstagio.ordem))
            .filter(models.SituacaoEstagio.situacao_id == sit.id)
            .scalar()
        )
        ordem = (maxord or 0) + 1
    est = models.SituacaoEstagio(
        situacao_id=sit.id,
        ordem=ordem,
        nome=payload.nome,
        frente=payload.frente or "Transversal",
        passos=payload.passos or "",
        resultado_esperado=payload.resultado_esperado,
        status="Não testado",
    )
    db.add(est)
    sit.user_managed = True
    log_activity(db, sit.fluxo, "situacao", f'Estágio "{payload.nome}" adicionado em {code}', case_code=code)
    db.commit()
    return _get_situacao_or_404(db, code)


@router.patch("/situacoes/{code}/estagios/{estagio_id}", response_model=schemas.SituacaoOut)
def update_estagio(code: str, estagio_id: int, payload: schemas.SituacaoEstagioUpdate, db: Session = Depends(get_db)):
    sit = _get_situacao_or_404(db, code)
    est = _get_estagio_in(sit, estagio_id)
    old_status = est.status

    if payload.status is not None:
        if payload.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Status inválido: {payload.status}")
        est.status = payload.status
    if payload.testado_por is not None:
        est.testado_por = payload.testado_por

    data = payload.model_dump(exclude_unset=True)
    touched_descriptive = False
    for field in ("nome", "frente", "passos", "resultado_esperado", "ordem"):
        if field in data and data[field] is not None:
            setattr(est, field, data[field])
            touched_descriptive = True

    if payload.status is not None and payload.status != old_status:
        log_activity(db, sit.fluxo, "status", f"{code} · {est.nome} mudou para {payload.status}",
                     autor=payload.testado_por or est.testado_por, case_code=code)
    if touched_descriptive:
        sit.user_managed = True
        log_activity(db, sit.fluxo, "situacao", f'Estágio "{est.nome}" de {code} editado', case_code=code)

    db.commit()
    return _get_situacao_or_404(db, code)


@router.delete("/situacoes/{code}/estagios/{estagio_id}", response_model=schemas.SituacaoOut)
def delete_estagio(code: str, estagio_id: int, db: Session = Depends(get_db)):
    sit = _get_situacao_or_404(db, code)
    est = _get_estagio_in(sit, estagio_id)
    nome = est.nome
    db.delete(est)
    sit.user_managed = True
    log_activity(db, sit.fluxo, "situacao", f'Estágio "{nome}" removido de {code}', case_code=code)
    db.commit()
    return _get_situacao_or_404(db, code)


@router.post("/situacoes/{code}/estagios/{estagio_id}/observacoes", response_model=schemas.SituacaoOut)
def add_estagio_observation(code: str, estagio_id: int, payload: schemas.SitObservationCreate, db: Session = Depends(get_db)):
    sit = _get_situacao_or_404(db, code)
    est = _get_estagio_in(sit, estagio_id)
    texto = (payload.texto or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Observação vazia.")
    db.add(models.SituacaoObservation(estagio_id=est.id, autor=payload.autor, texto=texto))
    log_activity(db, sit.fluxo, "obs", f'Observação em {code} · {est.nome}: "{snippet(texto)}"',
                 autor=payload.autor, case_code=code)
    db.commit()
    return _get_situacao_or_404(db, code)


@router.delete("/situacao-observacoes/{observation_id}", response_model=schemas.SituacaoOut)
def delete_estagio_observation(observation_id: int, db: Session = Depends(get_db)):
    obs = db.query(models.SituacaoObservation).filter(models.SituacaoObservation.id == observation_id).first()
    if not obs:
        raise HTTPException(status_code=404, detail="Observação não encontrada")
    est = db.query(models.SituacaoEstagio).filter(models.SituacaoEstagio.id == obs.estagio_id).first()
    sit = db.query(models.Situacao).filter(models.Situacao.id == est.situacao_id).first() if est else None
    db.delete(obs)
    if sit:
        log_activity(db, sit.fluxo, "obs", f"Observação removida de {sit.code} · {est.nome}", case_code=sit.code)
    db.commit()
    if not sit:
        raise HTTPException(status_code=404, detail="Situação não encontrada")
    return _get_situacao_or_404(db, sit.code)


@router.post("/situacoes/{code}/estagios/{estagio_id}/screenshots", response_model=schemas.SituacaoOut)
async def upload_estagio_screenshot(
    code: str,
    estagio_id: int,
    file: UploadFile = File(...),
    uploaded_by: str = Form(default=None),
    db: Session = Depends(get_db),
):
    sit = _get_situacao_or_404(db, code)
    est = _get_estagio_in(sit, estagio_id)

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Envie apenas imagens (png, jpg, webp, gif).")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Imagem maior que 8MB.")

    shot = models.SituacaoScreenshot(
        estagio_id=est.id,
        filename=file.filename or "print.png",
        content_type=file.content_type,
        data=data,
        uploaded_by=uploaded_by,
    )
    db.add(shot)
    log_activity(db, sit.fluxo, "print", f"Print anexado em {code} · {est.nome}", autor=uploaded_by, case_code=code)
    db.commit()
    return _get_situacao_or_404(db, code)


@router.get("/situacao-screenshots/{screenshot_id}")
def get_estagio_screenshot(screenshot_id: int, db: Session = Depends(get_db)):
    shot = db.query(models.SituacaoScreenshot).filter(models.SituacaoScreenshot.id == screenshot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Print não encontrado")
    return StreamingResponse(io.BytesIO(shot.data), media_type=shot.content_type)


@router.delete("/situacao-screenshots/{screenshot_id}", response_model=schemas.SituacaoOut)
def delete_estagio_screenshot(screenshot_id: int, db: Session = Depends(get_db)):
    shot = db.query(models.SituacaoScreenshot).filter(models.SituacaoScreenshot.id == screenshot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Print não encontrado")
    est = db.query(models.SituacaoEstagio).filter(models.SituacaoEstagio.id == shot.estagio_id).first()
    sit = db.query(models.Situacao).filter(models.Situacao.id == est.situacao_id).first() if est else None
    db.delete(shot)
    if sit:
        log_activity(db, sit.fluxo, "print", f"Print removido de {sit.code} · {est.nome}", case_code=sit.code)
    db.commit()
    if not sit:
        raise HTTPException(status_code=404, detail="Situação não encontrada")
    return _get_situacao_or_404(db, sit.code)
