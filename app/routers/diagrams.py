import json
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..activity import log as log_activity
from ..database import get_db
from ..modulos import desenha_processo, label as modulo_label
from .ativos import FLUXO_ATIVOS

router = APIRouter(tags=["diagrams"])

KINDS = {"atual", "ideal"}


def _trilha(fluxo: str) -> str:
    """O "fluxo" da trilha de Novidades. Os diagramas dos fluxos do Dispatcher (A/B/C e
    Projetos, que é uma aba de fluxo) aparecem nas Novidades do fluxo; os de um módulo
    com aba própria (Financeiro) aparecem nas Novidades dos módulos de ajustes, que é
    onde a aba dele lê."""
    return FLUXO_ATIVOS if desenha_processo(fluxo) else fluxo


def _onde(fluxo: str) -> str:
    return f" ({modulo_label(fluxo)})" if desenha_processo(fluxo) else ""


@router.get("/diagramas", response_model=List[schemas.FlowDiagramOut])
def list_diagrams(fluxo: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.FlowDiagram)
    if fluxo:
        q = q.filter(models.FlowDiagram.fluxo == fluxo)
    return q.order_by(
        models.FlowDiagram.fluxo,
        models.FlowDiagram.kind,
        models.FlowDiagram.ordem,
        models.FlowDiagram.id,
    ).all()


@router.post("/diagramas", response_model=schemas.FlowDiagramOut, status_code=201)
def create_diagram(payload: schemas.FlowDiagramCreate, db: Session = Depends(get_db)):
    titulo = (payload.titulo or "").strip()
    mermaid = (payload.mermaid or "").strip()
    if not titulo:
        raise HTTPException(status_code=400, detail="Título vazio.")
    if not mermaid:
        raise HTTPException(status_code=400, detail="Diagrama vazio.")
    kind = payload.kind if payload.kind in KINDS else "atual"
    diagram = models.FlowDiagram(
        fluxo=payload.fluxo or "C",
        kind=kind,
        titulo=titulo,
        descricao=payload.descricao or "",
        mermaid=mermaid,
        ordem=payload.ordem or 0,
        atualizado_por=payload.atualizado_por,
        seeded=False,
    )
    db.add(diagram)
    log_activity(db, _trilha(diagram.fluxo), "diagrama", f'Diagrama "{titulo}"{_onde(diagram.fluxo)} criado',
                 autor=payload.atualizado_por)
    db.commit()
    db.refresh(diagram)
    return diagram


@router.patch("/diagramas/{diagram_id}", response_model=schemas.FlowDiagramOut)
def update_diagram(diagram_id: int, payload: schemas.FlowDiagramUpdate, db: Session = Depends(get_db)):
    diagram = db.query(models.FlowDiagram).filter(models.FlowDiagram.id == diagram_id).first()
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagrama não encontrado")
    if payload.titulo is not None:
        titulo = payload.titulo.strip()
        if not titulo:
            raise HTTPException(status_code=400, detail="Título vazio.")
        diagram.titulo = titulo
    if payload.mermaid is not None:
        mermaid = payload.mermaid.strip()
        if not mermaid:
            raise HTTPException(status_code=400, detail="Diagrama vazio.")
        diagram.mermaid = mermaid
    if payload.descricao is not None:
        diagram.descricao = payload.descricao
    if payload.kind is not None and payload.kind in KINDS:
        diagram.kind = payload.kind
    if payload.fluxo is not None:
        diagram.fluxo = payload.fluxo
    if payload.ordem is not None:
        diagram.ordem = payload.ordem
    if payload.atualizado_por is not None:
        diagram.atualizado_por = payload.atualizado_por
    # qualquer edição do time "assume" o diagrama — o seed nunca mais o toca
    diagram.seeded = False

    # trilha de atividades: o editor salva sozinho a cada mexida, então uma
    # sessão de edição vira UM evento só — não re-loga se o último evento deste
    # diagrama foi há menos de 15 min. Comparação defensiva pra funcionar tanto
    # no SQLite (created_at ingênuo) quanto no Postgres (com timezone).
    from datetime import datetime, timezone, timedelta
    ref = f"diagrama:{diagram.id}"
    latest = (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.case_code == ref)
        .order_by(models.ActivityLog.id.desc())
        .first()
    )
    skip = False
    if latest and latest.created_at:
        try:
            ca = latest.created_at
            now = datetime.now(timezone.utc) if ca.tzinfo else datetime.utcnow()
            skip = (now - ca) < timedelta(minutes=15)
        except Exception:
            skip = False
    if not skip:
        log_activity(db, _trilha(diagram.fluxo), "diagrama",
                     f'Diagrama "{diagram.titulo}"{_onde(diagram.fluxo)} atualizado',
                     autor=diagram.atualizado_por, case_code=ref)

    db.commit()
    db.refresh(diagram)
    return diagram


@router.delete("/diagramas/{diagram_id}")
def delete_diagram(diagram_id: int, db: Session = Depends(get_db)):
    diagram = db.query(models.FlowDiagram).filter(models.FlowDiagram.id == diagram_id).first()
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagrama não encontrado")
    log_activity(db, _trilha(diagram.fluxo), "diagrama",
                 f'Diagrama "{diagram.titulo}"{_onde(diagram.fluxo)} excluído')
    # O seed roda a cada subida do app e recriaria o que veio dele: guarda que este foi excluído
    # de propósito. Só vale quando o título ainda é o do seed (um diagrama renomeado já não é
    # reconhecido por ele).
    from ..seed_data import SEED_DIAGRAMS
    if any(d["fluxo"] == diagram.fluxo and d["titulo"] == diagram.titulo for d in SEED_DIAGRAMS):
        ja = db.query(models.DiagramaSeedRemovido).filter(
            models.DiagramaSeedRemovido.fluxo == diagram.fluxo,
            models.DiagramaSeedRemovido.titulo == diagram.titulo,
        ).first()
        if not ja:
            db.add(models.DiagramaSeedRemovido(fluxo=diagram.fluxo, titulo=diagram.titulo))
    db.query(models.DiagramaTela).filter(models.DiagramaTela.diagrama_id == diagram_id).delete(
        synchronize_session=False)
    db.delete(diagram)
    db.commit()
    return {"deleted": diagram_id}


# ---------------------------------------------------------------- telinhas (protótipo por etapa)

NO_ID_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")


def _tela_out(t: models.DiagramaTela) -> schemas.TelaOut:
    try:
        blocos = json.loads(t.blocos or "[]")
    except ValueError:
        blocos = []
    return schemas.TelaOut(
        id=t.id, diagrama_id=t.diagrama_id, no_id=t.no_id, dispositivo=t.dispositivo or "celular",
        titulo=t.titulo or "", legenda=t.legenda or "", blocos=blocos,
        atualizado_por=t.atualizado_por, updated_at=t.updated_at,
    )


@router.get("/diagramas-telas", response_model=List[schemas.TelaOut])
def list_telas(fluxo: Optional[str] = None, db: Session = Depends(get_db)):
    """Todas as telinhas dos diagramas de um fluxo (ou de todos). A tela carrega uma vez só,
    junto com os diagramas, em vez de uma chamada por diagrama."""
    q = db.query(models.DiagramaTela)
    if fluxo:
        q = q.join(models.FlowDiagram, models.FlowDiagram.id == models.DiagramaTela.diagrama_id).filter(
            models.FlowDiagram.fluxo == fluxo)
    return [_tela_out(t) for t in q.order_by(models.DiagramaTela.id).all()]


@router.put("/diagramas/{diagram_id}/telas/{no_id}", response_model=schemas.TelaOut)
def save_tela(diagram_id: int, no_id: str, payload: schemas.TelaIn, db: Session = Depends(get_db)):
    """Cria ou substitui a telinha de uma etapa (a caixa de id `no_id`)."""
    diagram = db.query(models.FlowDiagram).filter(models.FlowDiagram.id == diagram_id).first()
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagrama não encontrado")
    if not NO_ID_RE.match(no_id):
        raise HTTPException(status_code=400, detail="Id de etapa inválido.")
    if not payload.blocos:
        raise HTTPException(status_code=400, detail="A tela precisa de pelo menos um bloco.")
    tela = db.query(models.DiagramaTela).filter(
        models.DiagramaTela.diagrama_id == diagram_id, models.DiagramaTela.no_id == no_id).first()
    novo = tela is None
    if novo:
        tela = models.DiagramaTela(diagrama_id=diagram_id, no_id=no_id)
        db.add(tela)
    tela.dispositivo = payload.dispositivo
    tela.titulo = (payload.titulo or "").strip()
    tela.legenda = (payload.legenda or "").strip()
    tela.blocos = json.dumps([b.model_dump() for b in payload.blocos], ensure_ascii=False)
    tela.atualizado_por = payload.atualizado_por
    nome = tela.titulo or no_id
    log_activity(db, _trilha(diagram.fluxo), "diagrama",
                 f'Tela "{nome}" {"criada" if novo else "atualizada"} no diagrama "{diagram.titulo}"{_onde(diagram.fluxo)}',
                 autor=payload.atualizado_por, case_code=f"diagrama:{diagram.id}")
    db.commit()
    db.refresh(tela)
    return _tela_out(tela)


@router.delete("/diagramas/{diagram_id}/telas/{no_id}")
def delete_tela(diagram_id: int, no_id: str, db: Session = Depends(get_db)):
    tela = db.query(models.DiagramaTela).filter(
        models.DiagramaTela.diagrama_id == diagram_id, models.DiagramaTela.no_id == no_id).first()
    if not tela:
        raise HTTPException(status_code=404, detail="Tela não encontrada")
    diagram = db.query(models.FlowDiagram).filter(models.FlowDiagram.id == diagram_id).first()
    if diagram:
        log_activity(db, _trilha(diagram.fluxo), "diagrama",
                     f'Tela "{tela.titulo or no_id}" excluída do diagrama "{diagram.titulo}"{_onde(diagram.fluxo)}',
                     case_code=f"diagrama:{diagram.id}")
    db.delete(tela)
    db.commit()
    return {"deleted": no_id}
