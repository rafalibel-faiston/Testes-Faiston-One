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
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session, joinedload

from .. import formulario, models, schemas
from ..database import get_db

router = APIRouter(tags=["tecnicos"])
# páginas abertas no navegador (sem o prefixo /api) — o formulário que o técnico
# recebe por WhatsApp e abre no celular
pagina_router = APIRouter(tags=["tecnicos"])

BRT = timezone(timedelta(hours=-3))

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

# mandada DEPOIS do atendimento, com o link do formulário — é o que fecha o ciclo
# do teste sem precisar entrevistar cada técnico por mensagem
TEMPLATE_FEEDBACK = """Fala, {nome}! Tudo certo?
Vi que você usou o Track One no atendimento — me conta rapidinho como foi?
São 2 minutinhos, direto no link:

{link}

Pode ser sincero, é justamente pra ajustar o que estiver ruim antes de liberar pra todo mundo. Valeu demais!"""


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


def _mensagem_para(tecnico: models.Tecnico, tipo: str = "convite", base_url: str = "") -> str:
    """Monta o texto pronto pra mandar: o convite (antes do teste, conforme o
    papel) ou o pedido de feedback com o link do formulário (depois dele)."""
    primeiro_nome = (tecnico.nome or "").strip().split(" ")[0] or tecnico.nome
    if tipo == "feedback":
        link = f"{(base_url or '').rstrip('/')}/formulario/{tecnico.token or ''}"
        return TEMPLATE_FEEDBACK.format(nome=primeiro_nome, link=link)
    template = TEMPLATE_LIDER if tecnico.papel == "lider" else TEMPLATE_TECNICO
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


@router.post("/tecnicos/limpar")
def limpar_base(payload: schemas.LimparBaseTecnicos, db: Session = Depends(get_db)):
    """Zera a base de técnicos — apaga todos os cadastros e o feedback junto.

    Serve pra recomeçar a importação do zero quando a planilha de origem estava
    errada. Não tem volta, então exige a palavra APAGAR: um DELETE disparado sem
    querer (ou um clique errado na tela) não passa daqui.
    """
    if (payload.confirmar or "").strip().upper() != "APAGAR":
        raise HTTPException(
            status_code=400,
            detail='Confirmação inválida — para zerar a base, mande {"confirmar": "APAGAR"}.',
        )
    tecnicos = db.query(models.Tecnico).count()
    observacoes = db.query(models.TecnicoObservacao).count()
    # as observações são apagadas explicitamente: no delete em massa quem cuidaria
    # disso seria o ON DELETE CASCADE do banco, e o SQLite local não o aplica por
    # padrão — sem isso, o histórico ficaria órfão em vez de sumir junto
    db.query(models.TecnicoObservacao).delete(synchronize_session=False)
    db.query(models.Tecnico).delete(synchronize_session=False)
    db.commit()
    return {"tecnicos_apagados": tecnicos, "observacoes_apagadas": observacoes}


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
        token=models.novo_token_tecnico(),
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
def mensagem_tecnico(tecnico_id: int, request: Request, tipo: str = "convite", db: Session = Depends(get_db)):
    """Monta a mensagem pronta (texto + link do WhatsApp) pra esse técnico:
    `tipo=convite` (padrão) chama pra instalação, `tipo=feedback` pede o retorno
    depois do atendimento e leva o link do formulário. O link do WhatsApp só
    pré-preenche texto; o APK/manual vai por fora, na própria conversa, já que o
    wa.me não anexa arquivo."""
    tecnico = _get_tecnico_or_404(db, tecnico_id)
    mensagem = _mensagem_para(tecnico, tipo=tipo, base_url=str(request.base_url))
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


@pagina_router.get("/formulario/{token}", response_class=HTMLResponse)
def pagina_formulario(token: str, db: Session = Depends(get_db)):
    """A página que o técnico abre no celular. Link errado devolve uma página
    explicando, não um JSON de erro — quem abre isso não é desenvolvedor."""
    tecnico = _tecnico_por_token(db, token)
    if not tecnico:
        return HTMLResponse(formulario.pagina_invalida(), status_code=404)
    ja_respondeu = ""
    if tecnico.respondido_em:
        quando = tecnico.respondido_em
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=timezone.utc)
        ja_respondeu = quando.astimezone(BRT).strftime("%d/%m")
    return HTMLResponse(
        formulario.montar_html(tecnico.nome, tecnico.token, ja_respondeu),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


def _tecnico_por_token(db: Session, token: str) -> Optional[models.Tecnico]:
    token = (token or "").strip()
    if not token:
        return None
    return db.query(models.Tecnico).filter(models.Tecnico.token == token).first()


@router.post("/formulario/{token}", response_model=schemas.TecnicoOut)
def responder_formulario(token: str, payload: schemas.FormularioResposta, db: Session = Depends(get_db)):
    """Recebe o formulário que o técnico preencheu no celular.

    Cada campo preenchido vira uma observação no card dele com o tipo certo, a
    nota e as etapas ficam no próprio técnico e o status vai pra "concluído" —
    é o retorno chegando na base sem ninguém digitar nada.
    """
    tecnico = _tecnico_por_token(db, token)
    if not tecnico:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")

    respostas = [
        ("positivo", (payload.positivo or "").strip()),
        ("melhoria", (payload.melhoria or "").strip()),
        ("problema", (payload.problema or "").strip()),
        (None, (payload.comentario or "").strip()),
    ]
    etapas = [e.strip() for e in (payload.etapas or []) if e and e.strip()]
    nota = payload.nota if payload.nota in (1, 2, 3, 4, 5) else None
    if not nota and not etapas and not any(texto for _, texto in respostas):
        raise HTTPException(status_code=400, detail="Responda pelo menos um campo.")

    for tipo, texto in respostas:
        if texto:
            db.add(models.TecnicoObservacao(
                tecnico_id=tecnico.id, autor=tecnico.nome, texto=texto, tipo=tipo,
            ))
    if nota:
        tecnico.nota = nota
    if etapas:
        tecnico.etapas_testadas = "|".join(etapas)
    tecnico.respondido_em = datetime.now(timezone.utc)
    # respondeu = testou; só não rebaixa quem já tinha sido marcado como concluído
    if tecnico.status != "concluido":
        tecnico.status = "concluido"
        if tecnico.concluido_em is None:
            tecnico.concluido_em = tecnico.respondido_em
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

    Quem já está na base (mesmo telefone) tem o cadastro atualizado em vez de ser
    rejeitado — reimportar a planilha nova é sincronizar, não duplicar; o que é
    progresso de QA (status, nota, etapas, feedback) nunca é tocado. Linha sem
    nome/telefone, telefone inválido ou telefone repetido dentro da própria
    planilha entra no relatório de rejeitados, sem travar as demais."""
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

    # quem já está na base, pelo telefone — reimportar a planilha atualizada não
    # rejeita esse pessoal, atualiza o cadastro deles (ver abaixo)
    ja_na_base = {t.telefone: t for t in db.query(models.Tecnico).all()}
    vistos_no_arquivo = {}   # telefone -> linha em que apareceu primeiro

    criados = 0
    atualizados = 0
    em_branco = 0
    rejeitados = []
    for linha_num, row in enumerate(linhas[1:], start=2):
        nome = valor(row, "nome")
        telefone_bruto = valor(row, "telefone")
        if not nome and not telefone_bruto:
            em_branco += 1
            continue  # linha em branco — não é erro, só não tem nada nela

        def rejeita(motivo):
            rejeitados.append({
                "linha": linha_num, "nome": nome, "telefone": telefone_bruto, "motivo": motivo,
            })

        if not telefone_bruto:
            rejeita("sem telefone")
            continue
        if not nome:
            rejeita("sem nome")
            continue
        try:
            telefone = _norm_telefone(telefone_bruto)
        except HTTPException:
            rejeita("telefone inválido")
            continue
        if telefone in vistos_no_arquivo:
            rejeita(f"telefone repetido na planilha (já veio na linha {vistos_no_arquivo[telefone]})")
            continue
        vistos_no_arquivo[telefone] = linha_num

        papel = "lider" if _norm_txt(valor(row, "papel")) in ("lider", "lider de equipe", "supervisor") else "tecnico"
        regional = valor(row, "regional") or None
        lider_nome = valor(row, "lider_nome") or None

        existente = ja_na_base.get(telefone)
        if existente:
            # atualiza o cadastro, nunca o andamento do teste: status, nota,
            # etapas e feedback são progresso de QA e não vêm da planilha
            existente.nome = nome
            existente.papel = papel
            if regional:
                existente.regional = regional
            if lider_nome:
                existente.lider_nome = lider_nome
            if not existente.token:
                existente.token = models.novo_token_tecnico()
            atualizados += 1
            continue

        novo = models.Tecnico(
            nome=nome, telefone=telefone, papel=papel,
            regional=regional, lider_nome=lider_nome,
            autor=(autor or "").strip() or None,
            token=models.novo_token_tecnico(),
            status="a_contatar",
        )
        db.add(novo)
        ja_na_base[telefone] = novo
        criados += 1
    db.commit()

    # o resumo é o que responde "por que entraram menos do que a planilha tinha":
    # cada motivo com a sua contagem, em vez de uma lista de mil linhas soltas
    resumo = {}
    for r in rejeitados:
        chave = r["motivo"].split(" (já veio")[0]
        resumo[chave] = resumo.get(chave, 0) + 1
    return {
        "criados": criados,
        "atualizados": atualizados,
        "linhas_planilha": max(len(linhas) - 1, 0),
        "linhas_em_branco": em_branco,
        "rejeitados": len(rejeitados),
        "resumo": resumo,
        "erros": rejeitados,
    }
