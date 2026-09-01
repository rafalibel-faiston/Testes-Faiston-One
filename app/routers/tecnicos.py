"""QA do Track One — o app novo que os técnicos vão usar do chamado até o
fechamento da RAT.

Cada técnico (ou líder de equipe) convidado a testar vira uma linha aqui, com
o funil de QA (a contatar -> convidado -> instalado -> em teste -> concluído)
e o histórico do que ele relatou no teste (o que achou bom, o que precisa
melhorar, o que deu problema). Este módulo também monta a mensagem de convite
pronta pra abrir no WhatsApp — o texto muda conforme o papel (técnico direto
ou líder avisando a equipe), com o nome já substituído.
"""
import io
import unicodedata
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["tecnicos"])

PAPEIS = {"tecnico", "lider"}
# funil de QA: do convite até o teste no atendimento real virar feedback registrado
STATUSES = ["a_contatar", "convidado", "instalado", "em_teste", "concluido", "sem_retorno"]
STATUS_LABELS = {
    "a_contatar": "A contatar",
    "convidado": "Convidado",
    "instalado": "App instalado",
    "em_teste": "Em teste",
    "concluido": "Teste concluído",
    "sem_retorno": "Sem retorno",
}
TIPOS_OBS = {"positivo", "melhoria", "problema"}

# textos enviados exatamente como definidos com o Rafa — {nome} é a única
# substituição feita na hora de gerar o link do WhatsApp.
TEMPLATE_TECNICO = """Fala, {nome}! Tudo certo?
Estamos lançando um app novo pra técnicos (Track One) e você foi selecionado pra testar antes de liberar geral.
O que ele faz:

* Acompanha o fluxo inteiro do atendimento, desde o chamado atribuído a você até o fechamento da RAT, tudo pelo app
* Mostra rastreio e previsão de entrega quando o atendimento precisa de peça
* Você confirma o recebimento do equipamento direto por lá

Vou te chamar pra fazer a instalação e já passo o manual de uso na hora. Depois é só usar normal no seu próximo atendimento, do começo ao fim, e qualquer coisa estranha (tela que não atualiza, notificação que não chega, informação que falta) me avisa direto — print ajuda muito.
Bora marcar a instalação?"""

TEMPLATE_LIDER = """Fala, {nome}! Tudo certo?
Estamos lançando um app novo pra técnicos (Track One) e já vou entrar em contato direto com o seu time pra fazer a instalação. Só queria te avisar antes.
O que ele faz:

* Acompanha o fluxo inteiro do atendimento, desde o chamado atribuído ao técnico até o fechamento da RAT, tudo pelo app
* Mostra rastreio e previsão de entrega quando precisa de peça
* O técnico confirma o recebimento do equipamento direto por lá

Tem manual de uso, vou passar junto na instalação com cada um. Pode avisar o pessoal que eu vou chamar eles nos próximos dias pra instalar e usar no próximo atendimento?"""


def _norm_txt(valor) -> str:
    """Normaliza texto de célula de planilha pra comparar sem acento/maiúscula:
    "Líder" e "lider" caem no mesmo lugar, célula vazia (None) vira string vazia."""
    if valor is None:
        return ""
    texto = str(valor).strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _norm_telefone(valor: str) -> str:
    digitos = "".join(c for c in (valor or "") if c.isdigit())
    if not digitos:
        raise HTTPException(status_code=400, detail="Telefone vazio.")
    # sem DDI (10 ou 11 dígitos = DDD + número) -> assume Brasil
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    if len(digitos) < 12:
        raise HTTPException(status_code=400, detail="Telefone inválido — inclua DDD (e DDI, se não for Brasil).")
    return digitos


def _mensagem_para(tecnico: models.Tecnico) -> str:
    template = TEMPLATE_LIDER if tecnico.papel == "lider" else TEMPLATE_TECNICO
    primeiro_nome = (tecnico.nome or "").strip().split(" ")[0] or tecnico.nome
    return template.format(nome=primeiro_nome)


def _get_tecnico_or_404(db: Session, tecnico_id: int) -> models.Tecnico:
    tecnico = db.query(models.Tecnico).filter(models.Tecnico.id == tecnico_id).first()
    if not tecnico:
        raise HTTPException(status_code=404, detail="Técnico não encontrado")
    return tecnico


@router.get("/tecnicos", response_model=List[schemas.TecnicoOut])
def list_tecnicos(
    status: Optional[str] = None,
    papel: Optional[str] = None,
    regional: Optional[str] = None,
    busca: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Tecnico).options(joinedload(models.Tecnico.observacoes))
    if status:
        q = q.filter(models.Tecnico.status == status)
    if papel:
        q = q.filter(models.Tecnico.papel == papel)
    if regional:
        q = q.filter(models.Tecnico.regional == regional)
    if busca:
        termo = f"%{busca.strip()}%"
        q = q.filter(models.Tecnico.nome.ilike(termo))
    return q.order_by(models.Tecnico.nome).all()


@router.get("/tecnicos/resumo")
def resumo_tecnicos(db: Session = Depends(get_db)):
    tecnicos = db.query(models.Tecnico).options(joinedload(models.Tecnico.observacoes)).all()
    counts = {s: 0 for s in STATUSES}
    feedback = {"positivo": 0, "melhoria": 0, "problema": 0}
    for t in tecnicos:
        counts[t.status] = counts.get(t.status, 0) + 1
        for o in t.observacoes:
            if o.tipo in feedback:
                feedback[o.tipo] += 1
    return {"total": len(tecnicos), "counts": counts, "feedback": feedback}


@router.post("/tecnicos", response_model=schemas.TecnicoOut, status_code=201)
def create_tecnico(payload: schemas.TecnicoCreate, db: Session = Depends(get_db)):
    nome = (payload.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Nome vazio.")
    papel = (payload.papel or "tecnico").strip()
    if papel not in PAPEIS:
        raise HTTPException(status_code=400, detail='Papel inválido — use "tecnico" ou "lider".')
    tecnico = models.Tecnico(
        nome=nome,
        telefone=_norm_telefone(payload.telefone),
        papel=papel,
        regional=(payload.regional or "").strip() or None,
        lider_nome=(payload.lider_nome or "").strip() or None,
        autor=(payload.autor or "").strip() or None,
        status="a_contatar",
    )
    db.add(tecnico)
    db.commit()
    db.refresh(tecnico)
    return tecnico


@router.patch("/tecnicos/{tecnico_id}", response_model=schemas.TecnicoOut)
def update_tecnico(tecnico_id: int, payload: schemas.TecnicoUpdate, db: Session = Depends(get_db)):
    tecnico = _get_tecnico_or_404(db, tecnico_id)
    if payload.nome is not None:
        nome = payload.nome.strip()
        if not nome:
            raise HTTPException(status_code=400, detail="Nome vazio.")
        tecnico.nome = nome
    if payload.telefone is not None:
        tecnico.telefone = _norm_telefone(payload.telefone)
    if payload.papel is not None:
        if payload.papel not in PAPEIS:
            raise HTTPException(status_code=400, detail='Papel inválido — use "tecnico" ou "lider".')
        tecnico.papel = payload.papel
    if payload.regional is not None:
        tecnico.regional = payload.regional.strip() or None
    if payload.lider_nome is not None:
        tecnico.lider_nome = payload.lider_nome.strip() or None
    if payload.status is not None:
        if payload.status not in STATUSES:
            raise HTTPException(status_code=400, detail="Status inválido.")
        tecnico.status = payload.status
        agora = datetime.now(timezone.utc)
        if payload.status == "convidado" and tecnico.convidado_em is None:
            tecnico.convidado_em = agora
        elif payload.status == "instalado" and tecnico.instalado_em is None:
            tecnico.instalado_em = agora
        elif payload.status == "concluido" and tecnico.concluido_em is None:
            tecnico.concluido_em = agora
    db.commit()
    db.refresh(tecnico)
    return tecnico


@router.delete("/tecnicos/{tecnico_id}")
def delete_tecnico(tecnico_id: int, db: Session = Depends(get_db)):
    tecnico = _get_tecnico_or_404(db, tecnico_id)
    db.delete(tecnico)
    db.commit()
    return {"deleted": tecnico_id}


@router.get("/tecnicos/{tecnico_id}/mensagem", response_model=schemas.TecnicoMensagemOut)
def mensagem_tecnico(tecnico_id: int, db: Session = Depends(get_db)):
    """Monta o convite pronto (texto + link do WhatsApp) pra esse técnico —
    o link do WhatsApp só pré-preenche texto; o APK/manual vai por fora, na
    própria conversa, já que o wa.me não anexa arquivo."""
    tecnico = _get_tecnico_or_404(db, tecnico_id)
    mensagem = _mensagem_para(tecnico)
    wa_link = f"https://wa.me/{tecnico.telefone}?text={quote(mensagem)}"
    return schemas.TecnicoMensagemOut(
        tecnico_id=tecnico.id, telefone=tecnico.telefone, mensagem=mensagem, wa_link=wa_link,
    )


@router.post("/tecnicos/{tecnico_id}/observacoes", response_model=schemas.TecnicoOut, status_code=201)
def add_observacao(tecnico_id: int, payload: schemas.TecnicoObservacaoCreate, db: Session = Depends(get_db)):
    tecnico = _get_tecnico_or_404(db, tecnico_id)
    texto = (payload.texto or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Observação vazia.")
    tipo = (payload.tipo or "").strip() or None
    if tipo is not None and tipo not in TIPOS_OBS:
        raise HTTPException(status_code=400, detail='Tipo inválido — use "positivo", "melhoria" ou "problema".')
    db.add(models.TecnicoObservacao(
        tecnico_id=tecnico.id,
        autor=(payload.autor or "").strip() or None,
        texto=texto,
        tipo=tipo,
    ))
    db.commit()
    db.refresh(tecnico)
    return tecnico


@router.delete("/tecnicos/observacoes/{observacao_id}", response_model=schemas.TecnicoOut)
def delete_observacao(observacao_id: int, db: Session = Depends(get_db)):
    obs = db.query(models.TecnicoObservacao).filter(models.TecnicoObservacao.id == observacao_id).first()
    if not obs:
        raise HTTPException(status_code=404, detail="Observação não encontrada")
    tecnico = _get_tecnico_or_404(db, obs.tecnico_id)
    db.delete(obs)
    db.commit()
    db.refresh(tecnico)
    return tecnico


# colunas aceitas na planilha de importação — cada chave aceita algumas variações
# de nome (sem acento/maiúscula, já que _norm_txt normaliza os dois lados)
COLUNAS_IMPORTACAO = {
    "nome": {"nome", "tecnico", "nome do tecnico", "nome completo"},
    "telefone": {"telefone", "whatsapp", "celular", "fone", "numero"},
    "papel": {"papel", "funcao", "função", "cargo", "tipo"},
    "regional": {"regional", "cidade", "regiao", "praca"},
    "lider_nome": {"lider", "lider_nome", "lider direto", "responde a", "supervisor"},
}


@router.get("/tecnicos/modelo")
def baixar_modelo_importacao():
    """Planilha modelo pra importar a base de técnicos de uma vez em /tecnicos/importar."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Técnicos"
    ws.append(["nome", "telefone", "papel", "regional", "lider"])
    ws.append(["João Silva", "(11) 99999-8888", "tecnico", "SP capital", "Carlos Souza"])
    ws.append(["Marcos Souza", "(11) 98888-7777", "lider", "Interior SP", ""])
    ws.column_dimensions[get_column_letter(1)].width = 26
    ws.column_dimensions[get_column_letter(2)].width = 20
    ws.column_dimensions[get_column_letter(3)].width = 12
    ws.column_dimensions[get_column_letter(4)].width = 20
    ws.column_dimensions[get_column_letter(5)].width = 20
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="modelo_tecnicos.xlsx"'},
    )


@router.post("/tecnicos/importar")
async def importar_tecnicos(
    file: UploadFile = File(...), autor: Optional[str] = Form(default=None), db: Session = Depends(get_db)
):
    """Sobe a base de técnicos de uma vez a partir de uma planilha .xlsx (colunas:
    nome, telefone e, opcionais, papel/regional/lider — ver /tecnicos/modelo).
    Linha sem nome ou telefone, ou com telefone já cadastrado, vira erro reportado
    (não trava a importação das demais)."""
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Envie um arquivo .xlsx.")
    data = await file.read()
    try:
        wb = load_workbook(io.BytesIO(data), data_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Não consegui abrir a planilha — confira o formato.")
    linhas = list(wb.active.iter_rows(values_only=True))
    if not linhas:
        raise HTTPException(status_code=400, detail="Planilha vazia.")

    cabecalho = [_norm_txt(c) for c in linhas[0]]
    idx = {}
    usadas = set()
    for campo, aliases in COLUNAS_IMPORTACAO.items():
        # 1ª passada: coluna com o nome exato (ex.: "Nome", "Telefone"). 2ª passada
        # (fallback): a base pode vir de outro sistema com coluna composta — ex.
        # "Endereço - Cidade" cai em "regional" por conter "cidade".
        achou = None
        for i, h in enumerate(cabecalho):
            if i not in usadas and h in aliases:
                achou = i
                break
        if achou is None:
            for i, h in enumerate(cabecalho):
                if i not in usadas and any(a in h for a in aliases):
                    achou = i
                    break
        if achou is not None:
            idx[campo] = achou
            usadas.add(achou)
    if "nome" not in idx or "telefone" not in idx:
        raise HTTPException(status_code=400, detail="A planilha precisa ter as colunas 'nome' e 'telefone'.")

    def valor(row, campo):
        i = idx.get(campo)
        if i is None or i >= len(row) or row[i] is None:
            return ""
        return str(row[i]).strip()

    telefones_existentes = {t for (t,) in db.query(models.Tecnico.telefone).all()}
    criados = []
    erros = []
    for linha_num, row in enumerate(linhas[1:], start=2):
        nome = valor(row, "nome")
        telefone_bruto = valor(row, "telefone")
        if not nome and not telefone_bruto:
            continue  # linha em branco — ignora sem contar como erro
        if not nome or not telefone_bruto:
            erros.append({"linha": linha_num, "motivo": "nome ou telefone vazio"})
            continue
        try:
            telefone = _norm_telefone(telefone_bruto)
        except HTTPException as err:
            erros.append({"linha": linha_num, "motivo": err.detail})
            continue
        if telefone in telefones_existentes:
            erros.append({"linha": linha_num, "motivo": f"telefone {telefone} já cadastrado"})
            continue
        papel = "lider" if _norm_txt(valor(row, "papel")) in ("lider", "lider de equipe", "supervisor") else "tecnico"
        db.add(models.Tecnico(
            nome=nome, telefone=telefone, papel=papel,
            regional=valor(row, "regional") or None,
            lider_nome=valor(row, "lider_nome") or None,
            autor=(autor or "").strip() or None,
            status="a_contatar",
        ))
        telefones_existentes.add(telefone)
        criados.append(nome)
    db.commit()
    return {"criados": len(criados), "nomes": criados, "erros": erros}
