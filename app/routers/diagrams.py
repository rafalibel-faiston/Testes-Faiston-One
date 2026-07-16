from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["diagrams"])

KINDS = {"atual", "ideal"}


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
    db.commit()
    db.refresh(diagram)
    return diagram


@router.delete("/diagramas/{diagram_id}")
def delete_diagram(diagram_id: int, db: Session = Depends(get_db)):
    diagram = db.query(models.FlowDiagram).filter(models.FlowDiagram.id == diagram_id).first()
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagrama não encontrado")
    db.delete(diagram)
    db.commit()
    return {"deleted": diagram_id}
