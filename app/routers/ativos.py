"""Ajustes do módulo Gestão de Ativos (Faiston One).

Cada ajuste é um item "como está hoje / como deve ser", classificado como Bug ou
Melhoria e agrupado por versão da leva (v2, v3...). A tela lê tudo daqui — não há
nada de v2 chumbado no código: para abrir a próxima rodada de ajustes basta
cadastrar itens com a versão nova.
"""
import io
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..activity import log as log_activity, normaliza_cor, normaliza_prazo, snippet
from ..database import get_db
from ..relatorio import AJUSTE_LABEL

router = APIRouter(tags=["ativos"])

TIPOS = {"Bug", "Melhoria"}
PRIORIDADES = {"Alta", "Média", "Baixa", "A definir"}
# ciclo de vida do ajuste, do levantamento até a validação na tela do Faiston One
STATUSES = {"levantado", "analise", "desenvolvimento", "entregue", "validado", "descartado"}

# mesmos limites dos prints dos casos de teste
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}

# "fluxo" da trilha de Novidades pros ajustes — a Gestão de Ativos não tem fluxo
# A/B/C, mas reaproveita a mesma trilha (activity_log/team_views) com essa chave fixa.
FLUXO_ATIVOS = "ATIVOS"


def _norm_versao(valor: Optional[str], padrao: str = "v2") -> str:
    v = (valor or "").strip().lower()
    if not v:
        return padrao
    # aceita "2", "V2", "v2 " e grava sempre no formato "v2"
    if v.isdigit():
        v = "v" + v
    return v


def _next_numero(db: Session, versao: str) -> int:
    maior = (
        db.query(sa_func.max(models.AtivoAjuste.numero))
        .filter(models.AtivoAjuste.versao == versao)
        .scalar()
    )
    return (maior or 0) + 1


@router.get("/ativos/ajustes", response_model=List[schemas.AtivoAjusteOut])
def list_ajustes(
    versao: Optional[str] = None,
    tipo: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.AtivoAjuste).options(
        joinedload(models.AtivoAjuste.prints),
        joinedload(models.AtivoAjuste.observations).joinedload(models.AtivoAjusteObservation.revisions),
    )
    if versao:
        q = q.filter(models.AtivoAjuste.versao == _norm_versao(versao))
    if tipo:
        q = q.filter(models.AtivoAjuste.tipo == tipo)
    if status:
        q = q.filter(models.AtivoAjuste.status == status)
    return q.order_by(
        models.AtivoAjuste.versao, models.AJUSTE_PRIORIDADE_ORDEM,
        models.AtivoAjuste.numero, models.AtivoAjuste.id,
    ).all()


@router.post("/ativos/ajustes", response_model=schemas.AtivoAjusteOut, status_code=201)
def create_ajuste(payload: schemas.AtivoAjusteCreate, db: Session = Depends(get_db)):
    titulo = (payload.titulo or "").strip()
    if not titulo:
        raise HTTPException(status_code=400, detail="Título vazio.")
    versao = _norm_versao(payload.versao)
    tipo = (payload.tipo or "Melhoria").strip()
    if tipo not in TIPOS:
        raise HTTPException(status_code=400, detail="Tipo inválido — use Bug ou Melhoria.")
    prioridade = (payload.prioridade or "Média").strip()
    if prioridade not in PRIORIDADES:
        prioridade = "Média"
    status = (payload.status or "levantado").strip()
    if status not in STATUSES:
        status = "levantado"
    ajuste = models.AtivoAjuste(
        versao=versao,
        numero=payload.numero if payload.numero else _next_numero(db, versao),
        titulo=titulo,
        tipo=tipo,
        area=(payload.area or "").strip() or None,
        prioridade=prioridade,
        atual=payload.atual or "",
        esperado=payload.esperado or "",
        observacao=payload.observacao or "",
        status=status,
        responsavel=(payload.responsavel or "").strip() or None,
        autor=(payload.autor or "").strip() or None,
    )
    db.add(ajuste)
    db.flush()  # garante ajuste.id pra amarrar o evento da trilha de Novidades
    log_activity(db, FLUXO_ATIVOS, "ajuste", f'Ajuste #{ajuste.numero} criado em {ajuste.versao}: "{titulo}"',
                 autor=ajuste.autor, case_code=f"AJT-{ajuste.id}")
    db.commit()
    db.refresh(ajuste)
    return ajuste


@router.patch("/ativos/ajustes/{ajuste_id}", response_model=schemas.AtivoAjusteOut)
def update_ajuste(ajuste_id: int, payload: schemas.AtivoAjusteUpdate, db: Session = Depends(get_db)):
    ajuste = db.query(models.AtivoAjuste).filter(models.AtivoAjuste.id == ajuste_id).first()
    if not ajuste:
        raise HTTPException(status_code=404, detail="Ajuste não encontrado")
    status_antigo = ajuste.status
    if payload.titulo is not None:
        titulo = payload.titulo.strip()
        if not titulo:
            raise HTTPException(status_code=400, detail="Título vazio.")
        ajuste.titulo = titulo
    if payload.versao is not None:
        nova = _norm_versao(payload.versao, ajuste.versao)
        if nova != ajuste.versao:
            ajuste.versao = nova
            # ao mudar de versão o número antigo pode já existir lá — renumera pro fim
            if payload.numero is None:
                ajuste.numero = _next_numero(db, nova)
    if payload.numero is not None:
        ajuste.numero = payload.numero
    if payload.tipo is not None:
        if payload.tipo not in TIPOS:
            raise HTTPException(status_code=400, detail="Tipo inválido — use Bug ou Melhoria.")
        ajuste.tipo = payload.tipo
    if payload.area is not None:
        ajuste.area = payload.area.strip() or None
    if payload.prioridade is not None and payload.prioridade in PRIORIDADES:
        ajuste.prioridade = payload.prioridade
    if payload.atual is not None:
        ajuste.atual = payload.atual
    if payload.esperado is not None:
        ajuste.esperado = payload.esperado
    if payload.observacao is not None:
        ajuste.observacao = payload.observacao
    if payload.status is not None:
        if payload.status not in STATUSES:
            raise HTTPException(status_code=400, detail="Status inválido.")
        ajuste.status = payload.status
    if payload.responsavel is not None:
        ajuste.responsavel = payload.responsavel.strip() or None
    if payload.retorno is not None:
        retorno = payload.retorno.strip()
        ajuste.retorno = retorno
        ajuste.retorno_em = sa_func.now() if retorno else None
    if payload.prazo is not None:
        ajuste.prazo = normaliza_prazo(payload.prazo)

    # a Novidade registra a mudança de situação (é a que interessa acompanhar);
    # uma edição de conteúdo sem trocar situação também entra, mas mais discreta.
    # Retorno/prazo sozinhos (autosave da pauta) não geram evento — vira ruído.
    if payload.status is not None and ajuste.status != status_antigo:
        log_activity(db, FLUXO_ATIVOS, "ajuste",
                     f'Ajuste #{ajuste.numero} ({ajuste.versao}) mudou para "{AJUSTE_LABEL.get(ajuste.status, ajuste.status)}": {ajuste.titulo}',
                     case_code=f"AJT-{ajuste.id}")
    elif payload.titulo is not None or payload.atual is not None or payload.esperado is not None:
        log_activity(db, FLUXO_ATIVOS, "ajuste",
                     f'Ajuste #{ajuste.numero} ({ajuste.versao}) editado: "{ajuste.titulo}"',
                     case_code=f"AJT-{ajuste.id}")

    db.commit()
    db.refresh(ajuste)
    return ajuste


@router.delete("/ativos/ajustes/{ajuste_id}")
def delete_ajuste(ajuste_id: int, db: Session = Depends(get_db)):
    ajuste = db.query(models.AtivoAjuste).filter(models.AtivoAjuste.id == ajuste_id).first()
    if not ajuste:
        raise HTTPException(status_code=404, detail="Ajuste não encontrado")
    log_activity(db, FLUXO_ATIVOS, "ajuste", f'Ajuste #{ajuste.numero} ({ajuste.versao}) excluído: "{ajuste.titulo}"',
                 case_code=f"AJT-{ajuste.id}")
    db.delete(ajuste)
    db.commit()
    return {"deleted": ajuste_id}


def _get_ajuste_or_404(db: Session, ajuste_id: int) -> models.AtivoAjuste:
    ajuste = (
        db.query(models.AtivoAjuste)
        .options(
            joinedload(models.AtivoAjuste.prints),
            joinedload(models.AtivoAjuste.observations).joinedload(models.AtivoAjusteObservation.revisions),
        )
        .filter(models.AtivoAjuste.id == ajuste_id)
        .first()
    )
    if not ajuste:
        raise HTTPException(status_code=404, detail="Ajuste não encontrado")
    return ajuste


@router.post("/ativos/ajustes/{ajuste_id}/observacoes", response_model=schemas.AtivoAjusteOut)
def add_ajuste_observation(ajuste_id: int, payload: schemas.ObservationCreate, db: Session = Depends(get_db)):
    """Adiciona uma nova nota ao histórico do ajuste — nunca sobrescreve as anteriores,
    cada uma guarda o autor de quem escreveu. Mesma ideia das notas do Dispatcher."""
    ajuste = _get_ajuste_or_404(db, ajuste_id)
    texto = (payload.texto or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Nota vazia.")
    db.add(models.AtivoAjusteObservation(
        ajuste_id=ajuste.id, autor=payload.autor, texto=texto, cor=normaliza_cor(payload.cor),
    ))
    log_activity(db, FLUXO_ATIVOS, "ajuste-obs",
                 f'Nota em ajuste #{ajuste.numero} ({ajuste.versao}): "{snippet(texto)}"',
                 autor=payload.autor, case_code=f"AJT-{ajuste.id}")
    db.commit()
    db.refresh(ajuste)
    return ajuste


@router.patch("/ativos/observacoes/{observation_id}", response_model=schemas.AtivoAjusteOut)
def update_ajuste_observation(observation_id: int, payload: schemas.ObservationUpdate, db: Session = Depends(get_db)):
    """Atualiza o texto de uma nota guardando a versão anterior na trilha —
    a nota evolui sem apagar o que já foi dito."""
    obs = (
        db.query(models.AtivoAjusteObservation)
        .filter(models.AtivoAjusteObservation.id == observation_id)
        .first()
    )
    if not obs:
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    texto = (payload.texto or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Nota vazia.")
    ajuste = _get_ajuste_or_404(db, obs.ajuste_id)
    # cor ausente no payload = não mexe na cor atual (só o texto está sendo salvo)
    cor = normaliza_cor(payload.cor) if payload.cor is not None else obs.cor
    if texto == obs.texto and cor == obs.cor:
        return ajuste
    if texto != obs.texto:
        db.add(models.AtivoAjusteObservationRevision(
            observation_id=obs.id, texto=obs.texto, cor=obs.cor,
            autor=obs.autor, editado_por=payload.autor,
        ))
        obs.texto = texto
        obs.editado_por = payload.autor
        obs.editado_em = sa_func.now()
        log_activity(db, FLUXO_ATIVOS, "ajuste-obs",
                     f'Nota atualizada em ajuste #{ajuste.numero} ({ajuste.versao}): "{snippet(texto)}"',
                     autor=payload.autor, case_code=f"AJT-{ajuste.id}")
    elif cor != obs.cor:
        marca = cor or "sem cor"
        log_activity(db, FLUXO_ATIVOS, "ajuste-obs",
                     f'Nota do ajuste #{ajuste.numero} ({ajuste.versao}) marcada como {marca}: "{snippet(texto)}"',
                     case_code=f"AJT-{ajuste.id}")
    obs.cor = cor
    db.commit()
    db.refresh(ajuste)
    return ajuste


@router.delete("/ativos/observacoes/{observation_id}", response_model=schemas.AtivoAjusteOut)
def delete_ajuste_observation(observation_id: int, db: Session = Depends(get_db)):
    obs = (
        db.query(models.AtivoAjusteObservation)
        .filter(models.AtivoAjusteObservation.id == observation_id)
        .first()
    )
    if not obs:
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    ajuste = _get_ajuste_or_404(db, obs.ajuste_id)
    db.delete(obs)
    log_activity(db, FLUXO_ATIVOS, "ajuste-obs",
                 f'Nota removida do ajuste #{ajuste.numero} ({ajuste.versao})', case_code=f"AJT-{ajuste.id}")
    db.commit()
    db.refresh(ajuste)
    return ajuste


@router.post("/ativos/ajustes/{ajuste_id}/prints", response_model=schemas.AtivoAjusteOut)
async def upload_print(
    ajuste_id: int,
    file: UploadFile = File(...),
    uploaded_by: str = Form(default=None),
    db: Session = Depends(get_db),
):
    """Anexa um print ao ajuste. É por aqui que passa o Ctrl+V da tela: o
    navegador entrega a imagem da área de transferência como arquivo."""
    ajuste = _get_ajuste_or_404(db, ajuste_id)
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Envie apenas imagens (png, jpg, webp, gif).")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Imagem maior que 8MB.")
    db.add(models.AtivoAjustePrint(
        ajuste_id=ajuste.id,
        filename=file.filename or "print.png",
        content_type=file.content_type,
        data=data,
        uploaded_by=(uploaded_by or "").strip() or None,
    ))
    db.commit()
    db.refresh(ajuste)
    return ajuste


@router.get("/ativos/prints/{print_id}")
def get_print(print_id: int, db: Session = Depends(get_db)):
    shot = db.query(models.AtivoAjustePrint).filter(models.AtivoAjustePrint.id == print_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Print não encontrado")
    return StreamingResponse(io.BytesIO(shot.data), media_type=shot.content_type)


@router.delete("/ativos/prints/{print_id}", response_model=schemas.AtivoAjusteOut)
def delete_print(print_id: int, db: Session = Depends(get_db)):
    shot = db.query(models.AtivoAjustePrint).filter(models.AtivoAjustePrint.id == print_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Print não encontrado")
    ajuste = _get_ajuste_or_404(db, shot.ajuste_id)
    db.delete(shot)
    db.commit()
    db.refresh(ajuste)
    return ajuste
