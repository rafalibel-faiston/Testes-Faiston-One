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
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import exists, func as sa_func, or_
from sqlalchemy.orm import Session, aliased, joinedload, selectinload

from .. import formulario, models, schemas
from ..database import get_db
from . import ativos

router = APIRouter(tags=["tecnicos"])
# páginas abertas no navegador (sem o prefixo /api) — o formulário que o técnico
# recebe por WhatsApp e abre no celular
pagina_router = APIRouter(tags=["tecnicos"])

BRT = timezone(timedelta(hours=-3))

PAPEIS = {"tecnico", "lider"}
VINCULO_LABELS = {"direto": "Direto", "repasse": "Repasse", "clt": "CLT"}
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

# textos enviados exatamente como definidos com o Rafa — {nome} e {remetente}
# (quem do time manda: o responsável pelo técnico) são substituídos na hora de
# gerar o link do WhatsApp.
# sem responsável definido, a mensagem sai no nome de quem escreveu os textos
REMETENTE_PADRAO = "Rafael"
TEMPLATE_TECNICO = """Olá, {nome}. Aqui é o {remetente}, da Faiston.

Você foi selecionado para participar de um teste de um novo sistema da Faiston, o *Faiston One*.

O que você precisa fazer:
1. Instalar o aplicativo *Track One* (o link será enviado a seguir)
2. Preencher suas competências e especialidades no cadastro do aplicativo — esse preenchimento é obrigatório: sem essa informação, o chamado não será direcionado a você
3. Manter as notificações push ativadas no celular
4. Manter a localização do celular ativada — é por meio dela que o sistema identifica os chamados disponíveis na sua região
5. Continuar seguindo o fluxo normalmente pelo GO.ON, da mesma forma que já faz hoje
6. Em paralelo, você também passará a utilizar o aplicativo novo — é por meio dele que acompanharemos todo o andamento do atendimento
7. Nos próximos dias, alguns chamados reais da Grande São Paulo passarão por esse teste. Quando um chamado for oferecido a você, basta aceitá-lo pelo aplicativo, como de costume — atenção: ao aceitar, você estará confirmando que tem condições de atender o chamado conforme a localidade informada

Importante: trata-se apenas de um teste — a forma de atendimento continua a mesma: deslocamento, atendimento e preenchimento da RAT seguem normalmente. A diferença é que o aplicativo novo passará a rodar em paralelo com o GO.ON, para que tenhamos visibilidade completa do fluxo.

Qualquer dúvida ou dificuldade no aplicativo, pode me chamar diretamente por aqui. Peço que confirme quando concluir a instalação.

Agradeço a participação."""

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

# mandada pro técnico já cadastrado quando a fase passa a rodar com chamados
# reais (ex.: Fase 2 - Acionamento SP) — diferente do convite genérico, já
# fala da instalação do Track One, do cadastro de competências (obrigatório
# pro chamado ser direcionado) e do fluxo em paralelo com o GO.ON
TEMPLATE_ACIONAMENTO = """Olá, {nome}. Aqui é o {remetente}, da Faiston.

Você foi selecionado para participar de um teste de um novo sistema da Faiston, o *Faiston One*.

O que você precisa fazer:
1. Instalar o aplicativo *Track One* (o link será enviado a seguir)
2. Preencher suas competências e especialidades no cadastro do aplicativo — esse preenchimento é obrigatório: sem essa informação, o chamado não será direcionado a você
3. Manter as notificações push ativadas no celular
4. Manter a localização do celular ativada — é por meio dela que o sistema identifica os chamados disponíveis na sua região
5. Continuar seguindo o fluxo normalmente pelo GO.ON, da mesma forma que já faz hoje
6. Em paralelo, você também passará a utilizar o aplicativo novo — é por meio dele que acompanharemos todo o andamento do atendimento
7. Nos próximos dias, alguns chamados reais da Grande São Paulo passarão por esse teste. Quando um chamado for oferecido a você, basta aceitá-lo pelo aplicativo, como de costume — atenção: ao aceitar, você estará confirmando que tem condições de atender o chamado conforme a localidade informada

Importante: trata-se apenas de um teste — a forma de atendimento continua a mesma: deslocamento, atendimento e preenchimento da RAT seguem normalmente. A diferença é que o aplicativo novo passará a rodar em paralelo com o GO.ON, para que tenhamos visibilidade completa do fluxo.

Qualquer dúvida ou dificuldade no aplicativo, pode me chamar diretamente por aqui. Peço que confirme quando concluir a instalação."""

# follow-up logo depois do convite: confirma se o técnico conseguiu instalar o
# Track One E fazer o cadastro (competências) — sem o cadastro completo o
# chamado não é direcionado pra ele, então instalar sozinho não basta
TEMPLATE_FOLLOWUP = """Fala, {nome}! Tudo certo?
Passando pra saber como foi com o Track One:

1. Conseguiu instalar o aplicativo?
2. Conseguiu fazer o cadastro e preencher suas competências e especialidades? Sem esse cadastro completo o chamado não é direcionado pra você.

Se travou em alguma etapa, me fala onde que eu te ajudo por aqui."""

# cobrança de quem parou no meio do caminho — muda conforme onde ele travou, que
# é a diferença entre "instala aí" e "usa no próximo atendimento"
TEMPLATES_COBRANCA = {
    "convidado": """Fala, {nome}! Tudo certo?
Passando pra lembrar do Track One — ficou de marcar a instalação comigo e ainda não conseguimos fechar.
São 10 minutinhos pra instalar e eu te passo o manual na hora. Quando fica bom pra você?""",
    "instalado": """Fala, {nome}! Tudo certo?
Você já está com o Track One instalado — é só usar no seu próximo atendimento, do começo ao fim.
Qualquer coisa estranha me chama, e no fim eu te mando um link rapidinho pra contar como foi. Fechou?""",
    "em_teste": """Fala, {nome}! Tudo certo?
Vi que você já usou o Track One no atendimento — só falta me contar como foi, são 2 minutinhos:

{link}

Seu retorno é o que ajusta o app antes de liberar pra todo mundo. Valeu!""",
}


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


# o APK sobe pela tela e fica sempre neste endereço — é o link que vai no convite
CAMINHO_APK = "/app/track-one.apk"
APK_TAMANHO_MAX = 200 * 1024 * 1024
APK_CONTENT_TYPE = "application/vnd.android.package-archive"
# trecho dos templates que promete o link do app — com APK no sistema, vira o link
PROMESSA_LINK_APK = "(o link será enviado a seguir)"


def _link_apk(db: Session, base_url: str) -> Optional[str]:
    """Link de download do APK do Track One, ou None se ninguém subiu ainda."""
    if not db.query(models.InstaladorApp.id).first():
        return None
    return f"{(base_url or '').rstrip('/')}{CAMINHO_APK}"


def _com_apk(texto: str, apk_link: Optional[str]) -> str:
    """Põe o link do APK dentro da mensagem: no lugar do "(o link será enviado a
    seguir)" quando o template promete o link, ou no fim quando não promete."""
    if not apk_link:
        return texto
    if PROMESSA_LINK_APK in texto:
        return texto.replace(PROMESSA_LINK_APK, f"— baixe e instale pelo link:\n{apk_link}")
    return f"{texto}\n\nLink pra instalar o Track One:\n{apk_link}"


def _mensagem_para(
    tecnico: models.Tecnico, tipo: str = "convite", base_url: str = "", apk_link: Optional[str] = None,
) -> str:
    """Monta o texto pronto pra mandar: o convite (antes do teste, conforme o
    papel), o pedido de feedback com o link do formulário (depois dele) ou a
    cobrança de quem travou no meio (que muda conforme a etapa onde parou).

    `apk_link` (ver _link_apk) vai embutido em toda mensagem que pede pra
    instalar o app — o wa.me não anexa arquivo, então o APK vai como link."""
    primeiro_nome = (tecnico.nome or "").strip().split(" ")[0] or tecnico.nome
    # quem manda é o responsável pela fila desse técnico (Luis, Rafael, Renato…)
    remetente = (tecnico.responsavel or "").strip() or REMETENTE_PADRAO
    link = f"{(base_url or '').rstrip('/')}/formulario/{tecnico.token or ''}"
    if tipo == "cobranca":
        # quem ainda nem foi convidado não tem o que cobrar: recebe o convite
        template = TEMPLATES_COBRANCA.get(tecnico.status)
        if not template:
            return _mensagem_para(tecnico, "convite", base_url, apk_link)
        texto = template.format(nome=primeiro_nome, link=link)
        # só quem ainda não instalou precisa do APK de novo
        return _com_apk(texto, apk_link) if tecnico.status == "convidado" else texto
    if tipo == "feedback":
        return TEMPLATE_FEEDBACK.format(nome=primeiro_nome, link=link)
    if tipo == "followup":
        # vai com o APK de novo: se ele não conseguiu instalar, o link já está ali
        return _com_apk(TEMPLATE_FOLLOWUP.format(nome=primeiro_nome), apk_link)
    if tipo == "acionamento":
        return _com_apk(TEMPLATE_ACIONAMENTO.format(nome=primeiro_nome, remetente=remetente), apk_link)
    if tecnico.papel == "lider":
        # o líder só avisa o time — quem instala é cada técnico, no convite dele
        return TEMPLATE_LIDER.format(nome=primeiro_nome)
    return _com_apk(TEMPLATE_TECNICO.format(nome=primeiro_nome, remetente=remetente), apk_link)


def _versao_da_fase(tecnico: models.Tecnico) -> Optional[str]:
    """A build que a fase do técnico está testando agora. Gravada em cada relato
    no momento em que ele entra: se a LP subir uma versão nova no meio do piloto,
    o que já foi relatado continua apontando pra build em que aconteceu."""
    return tecnico.fase.versao_app if tecnico.fase else None


def _get_tecnico_or_404(db: Session, tecnico_id: int) -> models.Tecnico:
    tecnico = db.query(models.Tecnico).filter(models.Tecnico.id == tecnico_id).first()
    if not tecnico:
        raise HTTPException(status_code=404, detail="Técnico não encontrado")
    return tecnico


# vínculo do técnico com a Faiston
VINCULOS_TECNICO = {"direto", "repasse", "clt"}
# filtro por vínculo: os três tipos, repasse cujo direto não está na base, ou
# quem a planilha não classificou
VINCULOS = VINCULOS_TECNICO | {"repasse_sem_direto", "sem_vinculo"}


def _filtra_vinculo(q, vinculo: Optional[str]):
    if not vinculo:
        return q
    if vinculo not in VINCULOS:
        raise HTTPException(
            status_code=400,
            detail="Vínculo inválido — use direto, repasse, clt, repasse_sem_direto ou sem_vinculo.",
        )
    if vinculo == "sem_vinculo":
        return q.filter(models.Tecnico.vinculo.is_(None))
    if vinculo == "repasse_sem_direto":
        return q.filter(models.Tecnico.vinculo == "repasse", models.Tecnico.direto_id.is_(None))
    return q.filter(models.Tecnico.vinculo == vinculo)


def _filtra_busca(q, busca: Optional[str]):
    """Nome, código do técnico ou código do direto — o código de um direto acha
    ele e os repasses dele."""
    if not busca or not busca.strip():
        return q
    termo = f"%{busca.strip()}%"
    return q.filter(or_(
        models.Tecnico.nome.ilike(termo),
        models.Tecnico.codigo.ilike(termo),
        models.Tecnico.direto_codigo.ilike(termo),
    ))


def _vinculo_valido(vinculo: Optional[str]) -> Optional[str]:
    vinculo = (vinculo or "").strip().lower() or None
    if vinculo is not None and vinculo not in VINCULOS_TECNICO:
        raise HTTPException(status_code=400, detail='Vínculo inválido — use "direto", "repasse" ou "clt".')
    return vinculo


# teto de segurança da lista com observações — acima de qualquer fase real
LIMITE_FASE = 10000

FASE_STATUSES = ["planejada", "em_andamento", "concluida", "liberada"]


@router.get("/tecnicos", response_model=List[schemas.TecnicoOut])
def list_tecnicos(
    status: Optional[str] = None,
    papel: Optional[str] = None,
    regional: Optional[str] = None,
    busca: Optional[str] = None,
    fase_id: Optional[int] = None,
    vinculo: Optional[str] = None,
    responsavel: Optional[str] = None,
    limite: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Lista completa (com observações) — é o que alimenta os cards.

    Dentro de uma fase vem a fase inteira: a tela desenha os cards aos poucos e
    conta status/filtros em cima dessa lista, então cortar escondia técnico da
    fase (a fase 1 tinha 412 e só 300 apareciam). Sem fase, a lista continua
    limitada — pra varrer a base inteira, use /tecnicos/base, leve e paginada.
    """
    na_fase = fase_id is not None and fase_id > 0
    if limite is None:
        limite = LIMITE_FASE if na_fase else 300
    q = (
        db.query(models.Tecnico)
        .options(
            # selectin, não joined: com LIMIT, o join das observações multiplica as
            # linhas e obriga o banco a paginar uma subquery
            selectinload(models.Tecnico.observacoes).joinedload(models.TecnicoObservacao.ajuste),
            selectinload(models.Tecnico.direto),
            selectinload(models.Tecnico.repasses),
        )
    )
    if fase_id is not None:
        q = q.filter(models.Tecnico.fase_id == (fase_id if fase_id > 0 else None))
    if status:
        q = q.filter(models.Tecnico.status == status)
    if papel:
        q = q.filter(models.Tecnico.papel == papel)
    if regional:
        q = q.filter(models.Tecnico.regional == regional)
    q = _filtra_busca(q, busca)
    q = _filtra_vinculo(q, vinculo)
    if responsavel:
        q = q.filter(models.Tecnico.responsavel == responsavel.strip())
    return q.order_by(models.Tecnico.nome).limit(max(1, min(limite, LIMITE_FASE))).all()


@router.get("/tecnicos/base", response_model=schemas.BaseTecnicosOut)
def base_tecnicos(
    busca: Optional[str] = None,
    regional: Optional[str] = None,
    papel: Optional[str] = None,
    sem_fase: bool = False,
    fase_id: Optional[int] = None,
    vinculo: Optional[str] = None,
    limite: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """A base inteira em formato leve e paginado — sem observações, sem token.

    É o que a tela usa pra escolher quem entra numa fase: com quatro mil
    cadastros, mandar a lista completa era mais de um mega de JSON por abertura.
    """
    q = db.query(models.Tecnico)
    if sem_fase:
        q = q.filter(models.Tecnico.fase_id.is_(None))
    if fase_id is not None:
        q = q.filter(models.Tecnico.fase_id == fase_id)
    if regional:
        q = q.filter(models.Tecnico.regional == regional)
    if papel:
        q = q.filter(models.Tecnico.papel == papel)
    q = _filtra_busca(q, busca)
    q = _filtra_vinculo(q, vinculo)
    total = q.count()
    itens = (
        q.options(selectinload(models.Tecnico.direto), selectinload(models.Tecnico.repasses))
        .order_by(models.Tecnico.nome)
        .offset(max(0, offset))
        .limit(max(1, min(limite, 200)))
        .all()
    )
    return {"total": total, "itens": itens}


@router.get("/tecnicos/regionais")
def listar_regionais(db: Session = Depends(get_db)):
    """As regionais que existem na base, com quantos técnicos cada uma tem — é
    por aqui que se monta uma fase por região sem digitar o nome na mão."""
    linhas = (
        db.query(models.Tecnico.regional, sa_func.count(models.Tecnico.id))
        .filter(models.Tecnico.regional.isnot(None), models.Tecnico.regional != "")
        .group_by(models.Tecnico.regional)
        .order_by(sa_func.count(models.Tecnico.id).desc())
        .all()
    )
    return [{"regional": r, "total": n} for r, n in linhas]


def _data_fase(valor: Optional[str], campo: str) -> Optional[str]:
    """Normaliza a data de uma fase pra "AAAA-MM-DD" (o que o <input type=date>
    manda). Aceita também "DD/MM/AAAA", que é como a gente escreve na mão.
    Vazio vira None — é assim que se apaga o prazo."""
    texto = (valor or "").strip()
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail=f"Data inválida em {campo}: use DD/MM/AAAA.")


# as 27 unidades da federação, por região — a ordem é a que o seletor mostra
UFS_POR_REGIAO = {
    "Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
    "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Centro-Oeste": ["DF", "GO", "MT", "MS"],
    "Sudeste": ["ES", "MG", "RJ", "SP"],
    "Sul": ["PR", "RS", "SC"],
}
UFS = {uf for lista in UFS_POR_REGIAO.values() for uf in lista}


def _ufs_fase(valores: List[str]) -> Optional[str]:
    """Valida e grava as UFs da fase como "SP,RJ" (maiúsculas, sem repetir,
    em ordem alfabética — a mesma fase sempre vira o mesmo texto)."""
    siglas = {(v or "").strip().upper() for v in valores} - {""}
    invalidas = siglas - UFS
    if invalidas:
        raise HTTPException(status_code=400, detail=f"UF inválida: {', '.join(sorted(invalidas))}.")
    return ",".join(sorted(siglas)) or None


def _checa_janela(data_inicio: Optional[str], prazo: Optional[str]) -> None:
    # o formato AAAA-MM-DD compara certo como texto
    if data_inicio and prazo and prazo < data_inicio:
        raise HTTPException(status_code=400, detail="O prazo da fase é anterior ao início.")


def _colocar_na_fase(tecnico: models.Tecnico, fase: models.PilotoFase) -> bool:
    """Põe o técnico na fase. Devolve True se ele mudou de lugar.

    Só é "reaproveitar" quando ele já vinha de outra fase de fato — a primeira
    entrada (vindo da base geral, fase_id None) não tem progresso nenhum pra
    resetar, e não pode invalidar o token que já foi mandado pro técnico pelo
    WhatsApp. Vindo de outra fase, é teste novo, não continuação do anterior: o
    progresso de QA (status, nota, etapas, link do formulário) de lá não pode
    vazar pra cá. O relato já registrado em tecnico_observacoes fica intocado —
    é histórico, não se apaga."""
    if tecnico.fase_id == fase.id:
        return False
    veio_de_outra_fase = tecnico.fase_id is not None
    tecnico.fase_id = fase.id
    if veio_de_outra_fase:
        tecnico.status = "a_contatar"
        tecnico.nota = None
        tecnico.etapas_testadas = None
        tecnico.convidado_em = None
        tecnico.instalado_em = None
        tecnico.concluido_em = None
        tecnico.respondido_em = None
        tecnico.token = models.novo_token_tecnico()
    return True


def _fase_em_andamento(fase: models.PilotoFase) -> None:
    # colocar gente na fase é o que a tira do papel
    if fase.status == "planejada":
        fase.status = "em_andamento"
        fase.iniciada_em = fase.iniciada_em or datetime.now(timezone.utc)


def _distribui_por_uf(db: Session) -> dict:
    """Põe cada técnico sem fase na fase que cobre a UF dele (as UFs marcadas na
    fase, as mesmas do mapa). Só mexe em quem está sem fase — ninguém é tirado
    de uma fase nem tem o progresso resetado — e só usa fase que ainda não
    acabou (planejada ou em andamento). UF marcada em mais de uma fase fica na
    primeira pela ordem, e volta em `ufs_em_mais_de_uma_fase`.

    Não muda o status da fase: a fase 3 planejada recebe o pessoal dela, mas
    continua planejada até alguém começar."""
    db.flush()   # o import acabou de criar gente: sem o flush a consulta não vê
    fases = db.query(models.PilotoFase).filter(
        models.PilotoFase.status.in_(("planejada", "em_andamento")),
        models.PilotoFase.ufs.isnot(None),
    ).order_by(models.PilotoFase.ordem, models.PilotoFase.id).all()
    fase_da_uf = {}
    repetidas = {}
    for fase in fases:
        for uf in fase.ufs.split(","):
            if uf in fase_da_uf:
                repetidas.setdefault(uf, [fase_da_uf[uf].nome]).append(fase.nome)
            else:
                fase_da_uf[uf] = fase
    por_fase = {}
    sem_fase_na_uf = {}
    sem_uf = 0
    for t in db.query(models.Tecnico).filter(models.Tecnico.fase_id.is_(None)).all():
        uf = (t.regional or "").strip().upper()
        if uf not in UFS:
            sem_uf += 1
            continue
        fase = fase_da_uf.get(uf)
        if fase is None:
            sem_fase_na_uf[uf] = sem_fase_na_uf.get(uf, 0) + 1
            continue
        _colocar_na_fase(t, fase)
        por_fase[fase.id] = por_fase.get(fase.id, 0) + 1
    db.flush()
    return {
        "distribuidos": sum(por_fase.values()),
        "fases": [{"id": f.id, "nome": f.nome, "ufs": f.ufs.split(","), "tecnicos": por_fase[f.id]}
                  for f in fases if f.id in por_fase],
        # UF que tem técnico mas nenhuma fase cobre — falta marcar ela em alguma fase
        "ufs_sem_fase": dict(sorted(sem_fase_na_uf.items())),
        "sem_uf": sem_uf,
        "ufs_em_mais_de_uma_fase": [{"uf": uf, "fases": nomes} for uf, nomes in sorted(repetidas.items())],
    }


@router.post("/piloto/fases/distribuir")
def distribuir_por_regiao(db: Session = Depends(get_db)):
    """Distribui a base pelas fases conforme as UFs marcadas em cada uma — é o
    "subi a base do Brasil inteiro, agora cada região cai na sua fase"."""
    resultado = _distribui_por_uf(db)
    db.commit()
    return resultado


def _divide_por_uf(tecnicos, pessoas: List[str], ja_tem: dict) -> dict:
    """Reparte `tecnicos` entre `pessoas` por UF e devolve {pessoa: [técnicos]}.

    Meta: todo mundo termina com a mesma quantidade (contando o que já tinha,
    em `ja_tem`). A UF vai inteira pra quem tem mais espaço; a UF que não cabe
    inteira em ninguém é repartida — na ordem do código do direto, pra o direto
    e os repasses dele (que costumam dividir o número) ficarem juntos."""
    total = len(tecnicos) + sum(ja_tem.values())
    n = len(pessoas)
    meta = {p: total // n + (1 if i < total % n else 0) for i, p in enumerate(pessoas)}
    espaco = {p: max(0, meta[p] - ja_tem.get(p, 0)) for p in pessoas}
    por_uf = {}
    for t in tecnicos:
        por_uf.setdefault((t.regional or "").strip().upper() or "—", []).append(t)
    destino = {p: [] for p in pessoas}
    for uf in sorted(por_uf, key=lambda u: (-len(por_uf[u]), u)):
        grupo = sorted(por_uf[uf], key=lambda t: (_chave_codigo(t.direto_codigo or t.codigo), _norm_txt(t.nome)))
        while grupo:
            # quem tem mais espaço; empate vai pra ordem da lista
            pessoa = max(pessoas, key=lambda p: (espaco[p], -pessoas.index(p)))
            leva = len(grupo) if espaco[pessoa] >= len(grupo) else max(espaco[pessoa], 1)
            destino[pessoa].extend(grupo[:leva])
            espaco[pessoa] -= leva
            grupo = grupo[leva:]
    return destino


@router.post("/piloto/fases/{fase_id}/dividir")
def dividir_fase(fase_id: int, payload: schemas.DividirFase, db: Session = Depends(get_db)):
    """Divide os técnicos da fase entre as pessoas do time, por UF — cada uma
    trabalha a própria fila (filtro "Meus" na tela)."""
    fase = db.query(models.PilotoFase).filter(models.PilotoFase.id == fase_id).first()
    if not fase:
        raise HTTPException(status_code=404, detail="Fase não encontrada")
    pessoas = []
    for p in payload.pessoas:
        p = (p or "").strip()
        if p and _norm_txt(p) not in {_norm_txt(x) for x in pessoas}:
            pessoas.append(p)
    if not pessoas:
        raise HTTPException(status_code=400, detail="Informe ao menos uma pessoa.")
    tecnicos = db.query(models.Tecnico).filter(models.Tecnico.fase_id == fase_id).all()
    # "luis" e "Luís" são a mesma pessoa: grava sempre com a grafia da lista
    grafia = {_norm_txt(p): p for p in pessoas}
    ja_tem = {}
    a_dividir = []
    for t in tecnicos:
        dono = grafia.get(_norm_txt(t.responsavel)) if t.responsavel else None
        if payload.manter_atribuidos and dono:
            t.responsavel = dono
            ja_tem[dono] = ja_tem.get(dono, 0) + 1
        else:
            a_dividir.append(t)
    destino = _divide_por_uf(a_dividir, pessoas, ja_tem)
    for pessoa, lista in destino.items():
        for t in lista:
            t.responsavel = pessoa
    db.commit()
    resumo = []
    for p in pessoas:
        dele = [t for t in tecnicos if t.responsavel == p]
        ufs = {}
        for t in dele:
            uf = (t.regional or "").strip().upper() or "—"
            ufs[uf] = ufs.get(uf, 0) + 1
        resumo.append({"pessoa": p, "tecnicos": len(dele), "novos": len(destino[p]),
                       "ufs": dict(sorted(ufs.items(), key=lambda kv: -kv[1]))})
    return {"fase": {"id": fase.id, "nome": fase.nome}, "divididos": len(a_dividir), "pessoas": resumo}


@router.get("/piloto/fases", response_model=List[schemas.PilotoFaseOut])
def listar_fases(db: Session = Depends(get_db)):
    fases = db.query(models.PilotoFase).order_by(
        models.PilotoFase.ordem, models.PilotoFase.id
    ).all()
    contagem = dict(
        db.query(models.Tecnico.fase_id, sa_func.count(models.Tecnico.id))
        .filter(models.Tecnico.fase_id.isnot(None))
        .group_by(models.Tecnico.fase_id)
        .all()
    )
    concluidos_por_fase = dict(
        db.query(models.Tecnico.fase_id, sa_func.count(models.Tecnico.id))
        .filter(models.Tecnico.fase_id.isnot(None), models.Tecnico.status == "concluido")
        .group_by(models.Tecnico.fase_id)
        .all()
    )
    saida = []
    for f in fases:
        dados = schemas.PilotoFaseOut.model_validate(f)
        dados.total_tecnicos = contagem.get(f.id, 0)
        dados.concluidos = concluidos_por_fase.get(f.id, 0)
        saida.append(dados)
    return saida


@router.post("/piloto/fases", response_model=schemas.PilotoFaseOut, status_code=201)
def criar_fase(payload: schemas.PilotoFaseCreate, db: Session = Depends(get_db)):
    nome = (payload.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Nome da fase vazio.")
    data_inicio = _data_fase(payload.data_inicio, "início")
    prazo = _data_fase(payload.prazo, "prazo")
    _checa_janela(data_inicio, prazo)
    maior = db.query(sa_func.max(models.PilotoFase.ordem)).scalar() or 0
    fase = models.PilotoFase(
        nome=nome,
        descricao=payload.descricao or "",
        status="planejada",
        ordem=maior + 1,
        versao_app=(payload.versao_app or "").strip() or None,
        meta_concluidos=payload.meta_concluidos,
        meta_nota=payload.meta_nota,
        meta_etapa=payload.meta_etapa,
        data_inicio=data_inicio,
        prazo=prazo,
        ufs=_ufs_fase(payload.ufs),
        autor=(payload.autor or "").strip() or None,
    )
    db.add(fase)
    db.commit()
    db.refresh(fase)
    return fase


@router.patch("/piloto/fases/{fase_id}", response_model=schemas.PilotoFaseOut)
def atualizar_fase(fase_id: int, payload: schemas.PilotoFaseUpdate, db: Session = Depends(get_db)):
    fase = db.query(models.PilotoFase).filter(models.PilotoFase.id == fase_id).first()
    if not fase:
        raise HTTPException(status_code=404, detail="Fase não encontrada")
    if payload.nome is not None:
        nome = payload.nome.strip()
        if not nome:
            raise HTTPException(status_code=400, detail="Nome da fase vazio.")
        fase.nome = nome
    if payload.descricao is not None:
        fase.descricao = payload.descricao
    if payload.status is not None:
        if payload.status not in FASE_STATUSES:
            raise HTTPException(status_code=400, detail="Situação de fase inválida.")
        fase.status = payload.status
        agora = datetime.now(timezone.utc)
        if payload.status == "em_andamento" and fase.iniciada_em is None:
            fase.iniciada_em = agora
        if payload.status == "liberada" and fase.liberada_em is None:
            fase.liberada_em = agora
    if payload.ordem is not None:
        fase.ordem = payload.ordem
    if payload.versao_app is not None:
        fase.versao_app = payload.versao_app.strip() or None
    for campo in ("meta_concluidos", "meta_nota", "meta_etapa"):
        valor = getattr(payload, campo)
        if valor is not None:
            setattr(fase, campo, valor or None)
    if payload.data_inicio is not None:
        fase.data_inicio = _data_fase(payload.data_inicio, "início")
    if payload.prazo is not None:
        fase.prazo = _data_fase(payload.prazo, "prazo")
    _checa_janela(fase.data_inicio, fase.prazo)
    if payload.ufs is not None:
        fase.ufs = _ufs_fase(payload.ufs)
    db.commit()
    db.refresh(fase)
    return fase


@router.delete("/piloto/fases/{fase_id}")
def excluir_fase(fase_id: int, db: Session = Depends(get_db)):
    """Remove a fase. Os técnicos não são apagados — voltam pra base geral."""
    fase = db.query(models.PilotoFase).filter(models.PilotoFase.id == fase_id).first()
    if not fase:
        raise HTTPException(status_code=404, detail="Fase não encontrada")
    soltos = (
        db.query(models.Tecnico).filter(models.Tecnico.fase_id == fase_id)
        .update({"fase_id": None}, synchronize_session=False)
    )
    db.delete(fase)
    db.commit()
    return {"deleted": fase_id, "tecnicos_soltos": soltos}


@router.post("/piloto/fases/{fase_id}/tecnicos")
def adicionar_na_fase(fase_id: int, payload: schemas.AdicionarNaFase, db: Session = Depends(get_db)):
    """Coloca técnicos na fase: por lista de ids ou por filtro da base.

    O filtro é o que faz "toda a regional de Campinas" entrar de uma vez. Quem já
    está em outra fase fica de fora por padrão — mover alguém de fase tem que ser
    escolha explícita, senão uma seleção ampla esvazia a fase do vizinho.

    O técnico não precisa ser reimportado pra isso — a base já tem todo mundo desde
    a primeira planilha, aqui só se escolhe quem testa nessa leva. Reaproveitar o
    mesmo técnico numa fase seguinte reseta o progresso de QA dele (status, nota,
    etapas testadas, link do formulário): é teste novo, não continuação do anterior.
    """
    fase = db.query(models.PilotoFase).filter(models.PilotoFase.id == fase_id).first()
    if not fase:
        raise HTTPException(status_code=404, detail="Fase não encontrada")

    q = db.query(models.Tecnico)
    if payload.tecnico_ids:
        q = q.filter(models.Tecnico.id.in_(payload.tecnico_ids))
    else:
        if payload.regional:
            q = q.filter(models.Tecnico.regional == payload.regional)
        if payload.papel:
            q = q.filter(models.Tecnico.papel == payload.papel)
        q = _filtra_busca(q, payload.busca)
        q = _filtra_vinculo(q, payload.vinculo)
        # sem filtro nenhum só passa se pedir "todos" explicitamente — um payload
        # vazio por engano não pode jogar a base inteira dentro da fase
        if not (payload.regional or payload.papel or payload.busca or payload.vinculo or payload.todos):
            raise HTTPException(status_code=400, detail="Escolha técnicos ou informe um filtro.")
    if not payload.incluir_de_outras_fases:
        q = q.filter((models.Tecnico.fase_id.is_(None)) | (models.Tecnico.fase_id == fase_id))

    movidos = sum(1 for t in q.all() if _colocar_na_fase(t, fase))
    if movidos:
        _fase_em_andamento(fase)
    db.commit()
    total = db.query(models.Tecnico).filter(models.Tecnico.fase_id == fase_id).count()
    return {"adicionados": movidos, "na_fase": total}


@router.delete("/piloto/fases/{fase_id}/tecnicos/{tecnico_id}")
def tirar_da_fase(fase_id: int, tecnico_id: int, db: Session = Depends(get_db)):
    tecnico = _get_tecnico_or_404(db, tecnico_id)
    if tecnico.fase_id != fase_id:
        raise HTTPException(status_code=400, detail="Esse técnico não está nessa fase.")
    tecnico.fase_id = None
    db.commit()
    return {"tecnico_id": tecnico_id, "fase_id": None}


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


# palavras que aparecem em quase todo relato e não dizem nada sobre o problema —
# sem tirá-las, o "mais citado" viraria "que, não, para, app"
TERMOS_IGNORADOS = {
    "para", "pelo", "pela", "como", "mais", "muito", "quando", "porque", "também",
    "ainda", "então", "isso", "esse", "essa", "aqui", "está", "estava", "tem",
    "ter", "foi", "ser", "sempre", "nunca", "tudo", "todo", "toda", "cada",
    "mas", "sem", "com", "uma", "num", "numa", "dos", "das", "nos", "nas",
    "que", "não", "sim", "vez", "vezes", "pra", "pro", "meu", "minha", "seu",
    "sua", "ele", "ela", "eles", "elas", "você", "voce", "gente", "coisa",
    # domínio: aparecem em todo relato do piloto e não separam um problema do outro
    "app", "aplicativo", "track", "one", "sistema", "celular", "consegui",
    "consegue", "fazer", "ficou", "ficar", "deu", "dar", "usar", "uso",
}


def _termos_mais_citados(observacoes, limite: int = 8):
    """Conta as palavras que mais aparecem nos relatos de problema e melhoria.

    É uma heurística de leitura rápida, não classificação: serve pra alguém bater
    o olho e perceber "notificação apareceu 12 vezes" antes de abrir relato por
    relato. O agrupamento que vale de verdade é o vínculo com o ajuste."""
    contagem = {}
    forma_original = {}
    for o in observacoes:
        if o.tipo not in ("problema", "melhoria"):
            continue
        vistos_na_nota = set()   # a mesma palavra repetida num relato conta uma vez
        for palavra in (o.texto or "").split():
            limpa = "".join(c for c in palavra if c.isalpha() or c == "-").strip("-")
            if len(limpa) < 4:
                continue
            chave = _norm_txt(limpa)
            if chave in TERMOS_IGNORADOS or chave in vistos_na_nota:
                continue
            vistos_na_nota.add(chave)
            contagem[chave] = contagem.get(chave, 0) + 1
            forma_original.setdefault(chave, limpa.lower())
    ordenados = sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {"termo": forma_original[chave], "total": n}
        for chave, n in ordenados[:limite] if n > 1   # citado uma vez só não é padrão
    ]


@router.get("/tecnicos/piloto")
def painel_piloto(
    fase_id: Optional[int] = None,
    meta_concluidos: int = 10,
    meta_nota: float = 4.0,
    meta_etapa: int = 5,
    dias_parado: int = 3,
    db: Session = Depends(get_db),
):
    """Os números que respondem "já dá pra liberar o Track One pra todo mundo?".

    Junta o funil de adoção, a cobertura de cada etapa do fluxo (de nada adianta
    40 técnicos testando se ninguém fechou RAT pelo app), as notas, os termos que
    mais aparecem nos relatos e os ajustes que já saíram do piloto — e fecha com
    os critérios de liberação batidos contra as metas.
    """
    # o piloto anda por fase, então a régua também é por fase: uma fase de 12
    # técnicos numa capital não tem a mesma meta de uma de 60 no interior
    fase = None
    if fase_id:
        fase = db.query(models.PilotoFase).filter(models.PilotoFase.id == fase_id).first()
        if not fase:
            raise HTTPException(status_code=404, detail="Fase não encontrada")
        meta_concluidos = fase.meta_concluidos or meta_concluidos
        meta_nota = fase.meta_nota or meta_nota
        meta_etapa = fase.meta_etapa or meta_etapa

    q = db.query(models.Tecnico).options(
        joinedload(models.Tecnico.observacoes).joinedload(models.TecnicoObservacao.ajuste)
    )
    if fase_id:
        q = q.filter(models.Tecnico.fase_id == fase_id)
    tecnicos = q.all()
    total = len(tecnicos)
    por_status = {s: 0 for s in STATUSES}
    for t in tecnicos:
        por_status[t.status] = por_status.get(t.status, 0) + 1

    # no funil, cada etapa conta quem chegou nela OU passou dela — é o que mostra
    # onde o piloto está travando, e não só onde cada um parou
    caminho = [s for s in STATUSES if s != "sem_retorno"]
    alcancou = {}
    for i, etapa in enumerate(caminho):
        alcancou[etapa] = sum(por_status.get(e, 0) for e in caminho[i:])
    funil = [
        {
            "key": etapa,
            "label": STATUS_LABELS[etapa],
            "total": alcancou[etapa],
            "pct": round(alcancou[etapa] / total * 100) if total else 0,
            "parados": por_status.get(etapa, 0),
        }
        for etapa in caminho
    ]

    responderam = [t for t in tecnicos if t.respondido_em]
    etapas_contagem = {etapa: 0 for etapa in formulario.ETAPAS}
    for t in tecnicos:
        for etapa in (t.etapas_testadas or "").split("|"):
            if etapa in etapas_contagem:
                etapas_contagem[etapa] += 1
    cobertura = [
        {
            "etapa": etapa,
            "curto": formulario.ETAPAS_CURTAS.get(etapa, etapa),
            "total": n,
            "pct": round(n / len(responderam) * 100) if responderam else 0,
            "ok": n >= meta_etapa,
        }
        for etapa, n in etapas_contagem.items()
    ]

    notas = [t.nota for t in tecnicos if t.nota]
    media = round(sum(notas) / len(notas), 1) if notas else None
    distribuicao = [{"nota": n, "total": sum(1 for x in notas if x == n)} for n in (1, 2, 3, 4, 5)]

    todas_obs = [o for t in tecnicos for o in t.observacoes]
    relatos = {
        "positivo": sum(1 for o in todas_obs if o.tipo == "positivo"),
        "melhoria": sum(1 for o in todas_obs if o.tipo == "melhoria"),
        "problema": sum(1 for o in todas_obs if o.tipo == "problema"),
        "no_backlog": sum(1 for o in todas_obs if o.ajuste_id),
    }

    # ajustes que nasceram do piloto, ordenados por quantos técnicos relataram o
    # mesmo ponto — é a fila de prioridade real pra levar pra LP
    por_ajuste = {}
    for o in todas_obs:
        if o.ajuste_id:
            por_ajuste.setdefault(o.ajuste_id, []).append(o)
    ranking = []
    for ajuste_id, obs_list in por_ajuste.items():
        ajuste = obs_list[0].ajuste
        if not ajuste:
            continue
        ranking.append({
            "ajuste_id": ajuste_id,
            "ref": f"{ajuste.versao} #{ajuste.numero:02d}",
            "titulo": ajuste.titulo,
            "tipo": ajuste.tipo,
            "status": ajuste.status,
            "relatos": len(obs_list),
        })
    ranking.sort(key=lambda a: (-a["relatos"], a["ref"]))

    # quem travou no meio do funil: o piloto morre de silêncio, não de bug, então
    # essa lista é o que evita perder técnico por falta de cobrança
    agora = datetime.now(timezone.utc)

    def _dias(quando):
        if not quando:
            return None
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=timezone.utc)
        return (agora - quando).days

    parados = []
    for t in tecnicos:
        if t.status not in ("convidado", "instalado", "em_teste"):
            continue
        marco = {"convidado": t.convidado_em, "instalado": t.instalado_em}.get(t.status) or t.updated_at
        dias = _dias(marco)
        if dias is None or dias < dias_parado:
            continue
        parados.append({
            "id": t.id, "nome": t.nome, "status": t.status,
            "status_label": STATUS_LABELS[t.status], "dias": dias,
        })
    parados.sort(key=lambda p: -p["dias"])

    concluidos = por_status.get("concluido", 0)
    etapas_ok = sum(1 for c in cobertura if c["ok"])
    criterios = [
        {
            "nome": f"{meta_concluidos} técnicos com teste concluído",
            "atual": concluidos, "meta": meta_concluidos, "ok": concluidos >= meta_concluidos,
        },
        {
            "nome": f"Nota média igual ou acima de {meta_nota}",
            "atual": media if media is not None else 0, "meta": meta_nota,
            "ok": media is not None and media >= meta_nota,
        },
        {
            "nome": f"Cada etapa testada por {meta_etapa}+ técnicos",
            "atual": etapas_ok, "meta": len(formulario.ETAPAS),
            "ok": etapas_ok == len(formulario.ETAPAS),
        },
        {
            "nome": "Nenhum problema relatado fora do backlog",
            "atual": relatos["no_backlog"], "meta": relatos["problema"],
            "ok": relatos["problema"] == 0 or relatos["no_backlog"] >= relatos["problema"],
        },
    ]

    return {
        "fase": (
            {"id": fase.id, "nome": fase.nome, "status": fase.status,
             "liberada_em": fase.liberada_em.isoformat() if fase.liberada_em else None}
            if fase else None
        ),
        "total": total,
        "responderam": len(responderam),
        "funil": funil,
        "sem_retorno": por_status.get("sem_retorno", 0),
        "cobertura": cobertura,
        "notas": {"media": media, "respostas": len(notas), "distribuicao": distribuicao},
        "relatos": relatos,
        "termos": _termos_mais_citados(todas_obs),
        "parados": parados[:8],
        "parados_total": len(parados),
        "dias_parado": dias_parado,
        "ranking_ajustes": ranking[:6],
        "criterios": criterios,
        "liberado": all(c["ok"] for c in criterios),
    }


@router.post("/tecnicos/observacoes/{observacao_id}/vincular-ajuste", response_model=schemas.TecnicoOut)
def vincular_ajuste(observacao_id: int, payload: schemas.VincularAjuste, db: Session = Depends(get_db)):
    """Aponta o relato para um ajuste que já existe, em vez de criar outro.

    É o que faz dez técnicos reclamando da mesma coisa virarem um item com dez
    relatos — sem isso, o backlog encheria de duplicata e ninguém saberia qual
    ponto dói mais."""
    obs = db.query(models.TecnicoObservacao).filter(models.TecnicoObservacao.id == observacao_id).first()
    if not obs:
        raise HTTPException(status_code=404, detail="Observação não encontrada")
    ajuste = db.query(models.AtivoAjuste).filter(models.AtivoAjuste.id == payload.ajuste_id).first()
    if not ajuste:
        raise HTTPException(status_code=404, detail="Ajuste não encontrado")
    obs.ajuste_id = ajuste.id
    db.commit()
    tecnico = _get_tecnico_or_404(db, obs.tecnico_id)
    db.refresh(tecnico)
    return tecnico


@router.post("/tecnicos/limpar")
def limpar_base(payload: schemas.LimparBaseTecnicos, db: Session = Depends(get_db)):
    """Zera a base de técnicos — apaga os cadastros e o feedback junto.

    Serve pra recomeçar a importação do zero quando a planilha de origem estava
    errada. Com `fase_id`, apaga só quem está naquela fase (a base de teste em
    uso) e deixa o resto da base intacto. Não tem volta, então exige a palavra
    APAGAR: um DELETE disparado sem querer (ou um clique errado na tela) não
    passa daqui.
    """
    if (payload.confirmar or "").strip().upper() != "APAGAR":
        raise HTTPException(
            status_code=400,
            detail='Confirmação inválida — para zerar a base, mande {"confirmar": "APAGAR"}.',
        )
    fase = None
    tecnicos_q = db.query(models.Tecnico)
    if payload.fase_id is not None:
        fase = db.query(models.PilotoFase).filter(models.PilotoFase.id == payload.fase_id).first()
        if not fase:
            raise HTTPException(status_code=404, detail="Fase não encontrada")
        tecnicos_q = tecnicos_q.filter(models.Tecnico.fase_id == fase.id)
    ids = [t.id for t in tecnicos_q.with_entities(models.Tecnico.id)]
    obs_q = db.query(models.TecnicoObservacao).filter(models.TecnicoObservacao.tecnico_id.in_(ids))
    observacoes = obs_q.count()
    # as observações são apagadas explicitamente: no delete em massa quem cuidaria
    # disso seria o ON DELETE CASCADE do banco, e o SQLite local não o aplica por
    # padrão — sem isso, o histórico ficaria órfão em vez de sumir junto
    obs_q.delete(synchronize_session=False)
    # repasse que fica (em outra fase) e tinha o direto apagado perde a ligação
    # com o cadastro, em vez de apontar pra um id que não existe mais — o nome e
    # o código do direto continuam gravados nele
    db.query(models.Tecnico).filter(
        models.Tecnico.direto_id.in_(ids), models.Tecnico.id.notin_(ids),
    ).update({models.Tecnico.direto_id: None}, synchronize_session=False)
    db.query(models.Tecnico).filter(models.Tecnico.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return {
        "tecnicos_apagados": len(ids),
        "observacoes_apagadas": observacoes,
        "fase": {"id": fase.id, "nome": fase.nome} if fase else None,
    }


def religar_repasses(db: Session) -> dict:
    """Liga ao direto todo repasse que ainda está sem ele, pelo código do direto.

    No import o repasse só acha o direto que já está na base ou na mesma
    planilha — o direto que entra depois (outra planilha, outra região) ficava
    sem os repasses dele. Isto roda no fim de cada importação e na subida do
    app, então a ligação se acerta sozinha. Com mais de um direto com o mesmo
    código, desempata pelo número (o repasse costuma estar com o do direto);
    sem desempate, fica sem ligar e volta em `ambiguos`."""
    db.flush()   # o import acabou de criar o direto: sem o flush a consulta não vê
    diretos = {}
    for t in db.query(models.Tecnico).filter(_nao_repasse(), models.Tecnico.codigo.isnot(None)).all():
        diretos.setdefault(_chave_codigo(t.codigo), []).append(t)
    religados = 0
    ambiguos = set()
    soltos = db.query(models.Tecnico).filter(
        models.Tecnico.vinculo == "repasse",
        models.Tecnico.direto_id.is_(None),
        models.Tecnico.direto_codigo.isnot(None),
    ).all()
    for r in soltos:
        achados = diretos.get(_chave_codigo(r.direto_codigo), [])
        if len(achados) > 1:
            achados = [d for d in achados if d.telefone == r.telefone] or achados
        if len(achados) != 1:
            if achados:
                ambiguos.add(r.direto_codigo)
            continue
        direto = achados[0]
        r.direto = direto
        r.direto_nome = r.direto_nome or direto.nome
        religados += 1
    db.flush()
    return {"religados": religados, "ambiguos": sorted(ambiguos)}


def _nao_repasse():
    # vinculo NULL também conta: "!= 'repasse'" sozinho deixaria o NULL de fora
    return or_(models.Tecnico.vinculo.is_(None), models.Tecnico.vinculo != "repasse")


def _liga_direto(db: Session, tecnico: models.Tecnico, nome: Optional[str], codigo: Optional[str]):
    """Grava o direto do repasse (nome e código como vieram) e liga no cadastro
    dele quando ele está na base — pelo código e, sem código, pelo nome."""
    nome = (nome or "").strip() or None
    codigo = (codigo or "").strip() or None
    direto = None
    if codigo:
        achados = db.query(models.Tecnico).filter(
            models.Tecnico.codigo == codigo, _nao_repasse(),
        ).limit(2).all()
        direto = achados[0] if len(achados) == 1 else None
    if direto is None and nome:
        achados = [t for t in db.query(models.Tecnico).filter(_nao_repasse()).all()
                   if _norm_txt(t.nome) == _norm_txt(nome)]
        direto = achados[0] if len(achados) == 1 else None
    if direto is tecnico:
        direto = None
    tecnico.direto = direto
    tecnico.direto_nome = nome or (direto.nome if direto else None)
    tecnico.direto_codigo = codigo or (direto.codigo if direto else None)


@router.post("/tecnicos/religar")
def religar(db: Session = Depends(get_db)):
    """Liga na mão os repasses sem direto (o import e a subida do app já fazem)."""
    resultado = religar_repasses(db)
    db.commit()
    return resultado


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
        vinculo=_vinculo_valido(payload.vinculo),
        codigo=(payload.codigo or "").strip() or None,
        autor=(payload.autor or "").strip() or None,
        token=models.novo_token_tecnico(),
        status="a_contatar",
    )
    if tecnico.vinculo == "repasse":
        _liga_direto(db, tecnico, payload.direto_nome, payload.direto_codigo)
    db.add(tecnico)
    db.commit()
    db.refresh(tecnico)
    return tecnico


# --------------------------------------------------------------- APK do Track One
# antes das rotas /tecnicos/{tecnico_id}: senão "apk" cai como id de técnico


def _apk_out(instalador: models.InstaladorApp, base_url: str) -> schemas.InstaladorAppOut:
    return schemas.InstaladorAppOut(
        filename=instalador.filename, tamanho=instalador.tamanho, uploaded_by=instalador.uploaded_by,
        created_at=instalador.created_at, link=f"{base_url.rstrip('/')}{CAMINHO_APK}",
    )


@router.get("/tecnicos/apk", response_model=Optional[schemas.InstaladorAppOut])
def info_apk(request: Request, db: Session = Depends(get_db)):
    """Qual APK está indo no convite agora (null = nenhum ainda)."""
    instalador = db.query(models.InstaladorApp).order_by(models.InstaladorApp.id.desc()).first()
    return _apk_out(instalador, str(request.base_url)) if instalador else None


@router.post("/tecnicos/apk", response_model=schemas.InstaladorAppOut, status_code=201)
async def subir_apk(
    request: Request,
    file: UploadFile = File(...),
    autor: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    """Sobe o APK do Track One. Substitui o anterior — o link da mensagem é fixo,
    então quem recebe o convite depois já baixa a build nova."""
    nome = (file.filename or "").strip()
    if not nome.lower().endswith(".apk"):
        raise HTTPException(status_code=400, detail="Envie o arquivo .apk do Track One.")
    conteudo = await file.read(APK_TAMANHO_MAX + 1)
    if len(conteudo) > APK_TAMANHO_MAX:
        raise HTTPException(status_code=413, detail="APK maior que 200 MB.")
    # APK é um zip: sem a assinatura "PK" no começo, não é um instalador válido
    if not conteudo.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="Esse arquivo não é um APK válido.")
    db.query(models.InstaladorApp).delete(synchronize_session=False)
    instalador = models.InstaladorApp(
        filename=nome, tamanho=len(conteudo), data=conteudo, uploaded_by=(autor or "").strip() or None,
    )
    db.add(instalador)
    db.commit()
    db.refresh(instalador)
    return _apk_out(instalador, str(request.base_url))


@router.delete("/tecnicos/apk")
def remover_apk(db: Session = Depends(get_db)):
    """Tira o APK — a mensagem volta a prometer o link "a seguir"."""
    removidos = db.query(models.InstaladorApp).delete(synchronize_session=False)
    db.commit()
    return {"deleted": removidos}


@pagina_router.get(CAMINHO_APK)
def baixar_apk(db: Session = Depends(get_db)):
    """O link que o técnico toca no WhatsApp: baixa o APK direto no celular."""
    instalador = db.query(models.InstaladorApp).order_by(models.InstaladorApp.id.desc()).first()
    if not instalador:
        raise HTTPException(status_code=404, detail="O APK do Track One ainda não foi disponibilizado.")
    return Response(
        content=instalador.data,
        media_type=APK_CONTENT_TYPE,
        headers={
            "Content-Disposition": 'attachment; filename="track-one.apk"',
            # o link é fixo e a build muda: nada de cache servindo APK velho
            "Cache-Control": "no-store",
        },
    )


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
    # "campo enviado" (mesmo como null, pra voltar a "não informado") é o que
    # importa, não "diferente de None"
    if "vinculo" in payload.model_fields_set:
        tecnico.vinculo = _vinculo_valido(payload.vinculo)
    if "codigo" in payload.model_fields_set:
        tecnico.codigo = (payload.codigo or "").strip() or None
    if "responsavel" in payload.model_fields_set:
        tecnico.responsavel = (payload.responsavel or "").strip() or None
    if tecnico.vinculo == "repasse":
        if {"direto_nome", "direto_codigo"} & payload.model_fields_set:
            _liga_direto(
                db, tecnico,
                payload.direto_nome if "direto_nome" in payload.model_fields_set else tecnico.direto_nome,
                payload.direto_codigo if "direto_codigo" in payload.model_fields_set else tecnico.direto_codigo,
            )
    else:
        # só repasse tem direto
        tecnico.direto = None
        tecnico.direto_nome = tecnico.direto_codigo = None
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
    `tipo=convite` (padrão) chama pra instalação, `tipo=acionamento` avisa que a
    fase passou a rodar com chamados reais (ex.: Fase 2 - Acionamento SP) e
    `tipo=followup` pergunta se o técnico conseguiu instalar e fazer o cadastro
    e `tipo=feedback` pede o retorno depois do atendimento e leva o link do
    formulário. O wa.me só pré-preenche texto, então o APK vai embutido como
    link de download (quando já subiram um em /tecnicos/apk)."""
    tecnico = _get_tecnico_or_404(db, tecnico_id)
    base_url = str(request.base_url)
    apk_link = _link_apk(db, base_url)
    mensagem = _mensagem_para(tecnico, tipo=tipo, base_url=base_url, apk_link=apk_link)
    wa_link = f"https://wa.me/{tecnico.telefone}?text={quote(mensagem)}"
    return schemas.TecnicoMensagemOut(
        tecnico_id=tecnico.id, telefone=tecnico.telefone, mensagem=mensagem, wa_link=wa_link,
        apk_link=apk_link,
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
        chamado=(payload.chamado or "").strip() or None,
        versao_app=(payload.versao_app or "").strip() or _versao_da_fase(tecnico),
    ))
    db.commit()
    db.refresh(tecnico)
    return tecnico


@router.post("/tecnicos/observacoes/{observacao_id}/virar-ajuste", response_model=schemas.TecnicoOut)
def virar_ajuste(observacao_id: int, payload: schemas.VirarAjuste, db: Session = Depends(get_db)):
    """Transforma o relato de um técnico em item do backlog da Gestão de Ativos.

    É a ponte que faltava entre o piloto e o time de dev: o que o técnico contou
    vira um item no formato que a LP já trabalha ("como está hoje / como deve
    ser"), e a observação guarda qual ajuste ela gerou — assim dá pra ver, no card
    dele, que aquele ponto já foi levado, e não levantar duas vezes a mesma coisa.
    """
    obs = db.query(models.TecnicoObservacao).filter(models.TecnicoObservacao.id == observacao_id).first()
    if not obs:
        raise HTTPException(status_code=404, detail="Observação não encontrada")
    if obs.ajuste_id:
        raise HTTPException(status_code=400, detail="Esse relato já virou um ajuste.")
    tecnico = _get_tecnico_or_404(db, obs.tecnico_id)

    titulo = (payload.titulo or "").strip()
    if not titulo:
        raise HTTPException(status_code=400, detail="Título vazio.")
    # relato de problema é bug; o resto entra como melhoria
    tipo = (payload.tipo or "").strip() or ("Bug" if obs.tipo == "problema" else "Melhoria")
    if tipo not in ativos.TIPOS:
        raise HTTPException(status_code=400, detail="Tipo inválido — use Bug ou Melhoria.")
    prioridade = (payload.prioridade or "Média").strip()
    if prioridade not in ativos.PRIORIDADES:
        prioridade = "Média"
    versao = ativos._norm_versao(payload.versao) if payload.versao else _versao_ativa(db)

    quando = obs.created_at.strftime("%d/%m/%Y") if obs.created_at else "durante o teste"
    origem = f"Relatado por {tecnico.nome} no teste do Track One ({quando})."

    ajuste = models.AtivoAjuste(
        versao=versao,
        numero=ativos._next_numero(db, versao),
        titulo=titulo,
        tipo=tipo,
        area=(payload.area or "Track One (app do técnico)").strip() or None,
        prioridade=prioridade,
        atual=(payload.atual if payload.atual is not None else obs.texto),
        esperado=payload.esperado or "",
        observacao=(payload.observacao if payload.observacao is not None else origem),
        status="levantado",
        autor=(payload.autor or "").strip() or None,
    )
    db.add(ajuste)
    db.flush()          # precisa do id do ajuste pra amarrar na observação
    obs.ajuste_id = ajuste.id
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


def _versao_ativa(db: Session) -> str:
    """A leva mais recente do backlog da Gestão de Ativos — é pra onde vai o item
    criado a partir de um relato, pra ele cair junto do que o time está tratando
    agora, e não numa rodada antiga já fechada."""
    versoes = [v for (v,) in db.query(models.AtivoAjuste.versao).distinct().all() if v]
    if not versoes:
        return "v2"

    def rank(v: str) -> int:
        digitos = "".join(c for c in v if c.isdigit())
        return int(digitos) if digitos else 0

    return max(versoes, key=rank)


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

    chamado = (payload.chamado or "").strip() or None
    versao = _versao_da_fase(tecnico)
    for tipo, texto in respostas:
        if texto:
            db.add(models.TecnicoObservacao(
                tecnico_id=tecnico.id, autor=tecnico.nome, texto=texto, tipo=tipo,
                chamado=chamado, versao_app=versao,
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
    # DIRETO / REPASSE / CLT
    "tipo_vinculo": {"tipo", "vinculo", "tipo de vinculo", "tipo vinculo", "contratacao",
                     "tipo de contratacao", "regime"},
    # o código do próprio técnico — todo técnico tem
    "codigo": {"codigo", "cod", "codigo do tecnico", "codigo tecnico", "cod tecnico",
               "codigo de parc", "codigo parc", "cod parc", "codigo do parc", "codigo_parc", "parc"},
    # repasse: quem é o direto dele, o código e (sem número próprio) o celular do direto
    "direto_nome": {"direto", "tecnico direto", "nome do direto", "direto responsavel", "parc direto"},
    "direto_codigo": {"codigo do direto", "codigo direto", "cod direto", "cod do direto",
                      "codigo parc direto", "codigo do parc direto"},
    # base de Agentes: "ES PARC1998" = direto PARC1998; "ES PARC1700 REPASSE" =
    # repasse que trabalha debaixo do direto PARC1700 (a UF na frente é ignorada)
    "agente": {"agente", "agentes", "codigo agente", "exemplificacao (agentes)", "exemplificacao agentes"},
    "direto_telefone": {"celular do direto", "telefone do direto", "numero do direto", "whatsapp do direto"},
    "papel": {"papel", "funcao", "função", "cargo"},
    "regional": {"regional", "cidade", "regiao", "praca", "uf"},
    "lider_nome": {"lider", "lider_nome", "lider direto", "responde a", "supervisor"},
}
# coluna opcional que distribui a planilha entre as fases. Só casa pelo nome
# exato (sem o fallback por "contém"): base exportada de outro sistema pode ter
# uma "Fase do contrato" que não tem nada a ver com o piloto.
COLUNA_FASE = {"fase", "fase do piloto", "leva"}
# colunas que só casam pelo nome exato — e são procuradas antes das outras: pelo
# "contém", "celular" pegaria "Celular do Direto" e "nome" pegaria "Nome do Direto"
COLUNAS_SO_EXATAS = {"tipo_vinculo", "codigo", "agente", "direto_nome", "direto_codigo", "direto_telefone"}


def _chave_codigo(codigo) -> str:
    """Código pra comparar: sem acento, maiúscula nem espaço — "PARC 1020" e
    "parc1020" são o mesmo."""
    return re.sub(r"\s+", "", _norm_txt(codigo))


def _le_agente(valor: str):
    """"ES PARC1700 REPASSE" -> ("PARC1700 REPASSE", "PARC1700", True);
    "SP  PARC4153" -> ("PARC4153", "PARC4153", False). A UF na frente e os
    espaços duplos saem; sem um PARC reconhecível, devolve o texto limpo."""
    texto = " ".join((valor or "").split())
    if not texto:
        return None, None, False
    repasse = "repasse" in _norm_txt(texto)
    m = re.search(r"PARC\s*(\d+)", texto, re.IGNORECASE)
    if not m:
        return texto, None, repasse
    parc = f"PARC{m.group(1)}"
    return (f"{parc} REPASSE" if repasse else parc), parc, repasse


def _vinculo_da_planilha(valor: str) -> Optional[str]:
    """Valor da coluna Tipo -> direto / repasse / clt (None = não reconhecido)."""
    v = _norm_txt(valor)
    if not v:
        return None
    if "repasse" in v:
        return "repasse"
    if "clt" in v:
        return "clt"
    if "direto" in v or v in ("parc", "pj"):
        return "direto"
    return None


@router.get("/tecnicos/exportar")
def exportar_piloto(fase_id: Optional[int] = None, db: Session = Depends(get_db)):
    """O piloto como planilha — pra levar pra reunião sem depender do link.

    Três abas: os técnicos com o andamento de cada um, o feedback linha a linha
    (com chamado, versão e o ajuste que gerou) e o resumo com os critérios.
    """
    fase = None
    if fase_id:
        fase = db.query(models.PilotoFase).filter(models.PilotoFase.id == fase_id).first()
        if not fase:
            raise HTTPException(status_code=404, detail="Fase não encontrada")

    q = db.query(models.Tecnico).options(
        joinedload(models.Tecnico.observacoes).joinedload(models.TecnicoObservacao.ajuste),
        selectinload(models.Tecnico.direto),
        selectinload(models.Tecnico.repasses),
    )
    if fase_id:
        q = q.filter(models.Tecnico.fase_id == fase_id)
    tecnicos = q.order_by(models.Tecnico.nome).all()
    painel = painel_piloto(fase_id=fase_id, db=db)

    wb = Workbook()
    cabecalho_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")

    def escreve_cabecalho(ws, colunas, larguras):
        ws.append(colunas)
        for i in range(1, len(colunas) + 1):
            c = ws.cell(row=1, column=i)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = cabecalho_fill
        for i, w in enumerate(larguras, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

    ws = wb.active
    ws.title = "Técnicos"
    escreve_cabecalho(
        ws,
        ["Nome", "Telefone", "Papel", "Regional", "Líder", "Situação", "Nota",
         "Etapas testadas", "Respondeu em", "Anotações", "Vínculo", "Código", "Direto", "Código do direto",
         "Responsável"],
        [28, 18, 10, 18, 20, 16, 7, 46, 18, 11, 10, 18, 28, 18, 16],
    )
    for t in tecnicos:
        ws.append([
            t.nome, t.telefone,
            "Líder" if t.papel == "lider" else "Técnico",
            t.regional or "", t.lider_nome or "",
            STATUS_LABELS.get(t.status, t.status),
            t.nota or "",
            (t.etapas_testadas or "").replace("|", " · "),
            t.respondido_em.astimezone(BRT).strftime("%d/%m/%Y %H:%M") if t.respondido_em else "",
            len(t.observacoes),
            VINCULO_LABELS.get(t.vinculo, ""), t.codigo or "",
            t.direto_nome or "", t.direto_codigo or "",
            t.responsavel or "",
        ])

    ws2 = wb.create_sheet("Feedback")
    escreve_cabecalho(
        ws2,
        ["Técnico", "Tipo", "Relato", "Chamado", "Versão", "Virou ajuste", "Quando"],
        [26, 12, 70, 12, 10, 14, 18],
    )
    TIPO_LABEL = {"positivo": "Achou bom", "melhoria": "Melhoria", "problema": "Problema"}
    for t in tecnicos:
        for o in t.observacoes:
            ws2.append([
                t.nome, TIPO_LABEL.get(o.tipo, "Nota geral"), o.texto,
                o.chamado or "", o.versao_app or "", o.ajuste_ref or "",
                o.created_at.astimezone(BRT).strftime("%d/%m/%Y %H:%M") if o.created_at else "",
            ])
    for linha in ws2.iter_rows(min_row=2):
        linha[2].alignment = Alignment(wrap_text=True, vertical="top")

    ws3 = wb.create_sheet("Resumo")
    escreve_cabecalho(ws3, ["Indicador", "Atual", "Meta", "Situação"], [46, 12, 12, 16])
    ws3.append(["Técnicos na fase", painel["total"], "", ""])
    ws3.append(["Responderam o formulário", painel["responderam"], "", ""])
    ws3.append(["Nota média", painel["notas"]["media"] or "—", "", ""])
    ws3.append([])
    for c in painel["criterios"]:
        ws3.append([c["nome"], c["atual"], c["meta"], "OK" if c["ok"] else "Falta"])
    ws3.append([])
    ws3.append(["Cobertura do fluxo", "", "", ""])
    for c in painel["cobertura"]:
        ws3.append([f"  {c['etapa']}", c["total"], "", "OK" if c["ok"] else "Abaixo"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    apelido = "".join(ch for ch in (fase.nome if fase else "piloto") if ch.isalnum() or ch in " -_").strip()
    nome_arquivo = f"TrackOne_{apelido or 'piloto'}_{datetime.now(BRT).strftime('%Y-%m-%d')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/tecnicos/modelo")
def baixar_modelo_importacao():
    """Planilha modelo pra importar a base de técnicos de uma vez em /tecnicos/importar."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Técnicos"
    # "fase" é opcional: preenchida, a linha já cai direto naquela fase do piloto
    # formato da base de Agentes: "Tipo" = Direto / Repasse / CLT; "Agente" traz o
    # PARC — no direto é o código dele, no repasse ("... REPASSE") é o PARC do
    # direto dele, que é como o repasse é ligado ao direto. "fase" é opcional
    ws.append(["Técnico", "Tipo", "UF", "Agente", "Telefone", "fase"])
    ws.append(["João Silva", "Direto", "SP", "SP PARC1020", "(11) 99999-8888", "Fase 1 — SP capital"])
    ws.append(["Pedro Alves", "Repasse", "SP", "SP PARC1020 REPASSE", "(11) 97777-6666", "Fase 1 — SP capital"])
    ws.append(["Marcos Souza", "CLT", "SP", "", "(11) 98888-7777", ""])
    for i, largura in enumerate([30, 10, 6, 24, 18, 22], start=1):
        ws.column_dimensions[get_column_letter(i)].width = largura
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
    file: UploadFile = File(...),
    autor: Optional[str] = Form(default=None),
    fase_id: Optional[int] = Form(default=None),
    distribuir: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    """Sobe a base de técnicos de uma vez a partir de uma planilha .xlsx (colunas:
    nome, telefone e, opcionais, papel/regional/lider — ver /tecnicos/modelo).

    Quem já está na base (mesmo telefone) tem o cadastro atualizado em vez de ser
    rejeitado — reimportar a planilha nova é sincronizar, não duplicar; o que é
    progresso de QA (status, nota, etapas, feedback) nunca é tocado. Linha sem
    nome/telefone, telefone inválido ou telefone repetido dentro da própria
    planilha entra no relatório de rejeitados, sem travar as demais.

    É também o jeito de montar uma fase inteira de uma vez, sem escolher um por
    um na base: com `fase_id`, todo mundo que entrou pela planilha vai pra essa
    fase; sem ele, uma coluna "fase" na planilha distribui cada linha na fase
    com aquele nome (criada na hora se ainda não existir). Mandar pra fase pela
    planilha é escolha explícita, então quem estava em outra fase é movido —
    com o progresso resetado, como em adicionar_na_fase.

    Com a coluna "tipo" (DIRETO / REPASSE / CLT) grava o vínculo de cada um, e
    a coluna "codigo" o código do técnico. Repasse diz quem é o direto dele
    ("direto" e "codigo do direto"): o direto é achado na planilha ou na base
    pelo código e, sem código, pelo nome. Repasse sem número próprio pode vir
    com o telefone vazio — entra com o "celular do direto" ou com o número do
    cadastro do direto, e pode repetir o número do direto sem ser rejeitado.
    Repasse sem direto informado ou com direto não achado volta nos avisos."""
    fase_fixa = None
    if fase_id is not None:
        fase_fixa = db.query(models.PilotoFase).filter(models.PilotoFase.id == fase_id).first()
        if not fase_fixa:
            raise HTTPException(status_code=404, detail="Fase não encontrada")
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
    # as colunas "só exatas" primeiro, pra que o fallback por "contém" das outras
    # não roube "Celular do Direto" ou "Nome do Direto"
    for campo, aliases in sorted(COLUNAS_IMPORTACAO.items(), key=lambda kv: kv[0] not in COLUNAS_SO_EXATAS):
        # 1ª passada: coluna com o nome exato (ex.: "Nome", "Telefone"). 2ª passada
        # (fallback): a base pode vir de outro sistema com coluna composta — ex.
        # "Endereço - Cidade" cai em "regional" por conter "cidade".
        achou = None
        for i, h in enumerate(cabecalho):
            if i not in usadas and h in aliases:
                achou = i
                break
        if achou is None and campo not in COLUNAS_SO_EXATAS:
            # alias de 2 letras ("uf") só vale exato — contido, casa com qualquer coisa
            for i, h in enumerate(cabecalho):
                if i not in usadas and any(a in h for a in aliases if len(a) > 2):
                    achou = i
                    break
        if achou is not None:
            idx[campo] = achou
            usadas.add(achou)
    if "nome" not in idx or "telefone" not in idx:
        raise HTTPException(status_code=400, detail="A planilha precisa ter as colunas 'nome' e 'telefone'.")
    if fase_fixa is None:
        for i, h in enumerate(cabecalho):
            if i not in usadas and h in COLUNA_FASE:
                idx["fase"] = i
                break

    def valor(row, campo):
        i = idx.get(campo)
        if i is None or i >= len(row) or row[i] is None:
            return ""
        v = row[i]
        if isinstance(v, float) and v.is_integer():
            v = int(v)   # telefone salvo como número: sem o ".0" virando dígito a mais
        return str(v).strip()

    # quem já está na base, pelo telefone e pelo código — reimportar a planilha
    # atualizada não rejeita esse pessoal, atualiza o cadastro deles (ver abaixo)
    # (lista: o repasse sem número próprio divide o número com o direto)
    ja_na_base = {}
    base_por_codigo = {}
    for t in db.query(models.Tecnico).all():
        ja_na_base.setdefault(t.telefone, []).append(t)
        if t.codigo:
            base_por_codigo.setdefault(_chave_codigo(t.codigo), []).append(t)

    # fases por nome normalizado — "Fase 2", "fase 2 " e "FASE 2" são a mesma
    fases_por_nome = {_norm_txt(f.nome): f for f in db.query(models.PilotoFase).all()}
    fases_criadas = []
    por_fase = {}            # fase.id -> quantos da planilha entraram nela

    def fase_da_linha(row):
        if fase_fixa is not None:
            return fase_fixa
        nome_fase = valor(row, "fase")
        if not nome_fase:
            return None
        chave = _norm_txt(nome_fase)
        fase = fases_por_nome.get(chave)
        if fase is None:
            maior = db.query(sa_func.max(models.PilotoFase.ordem)).scalar() or 0
            fase = models.PilotoFase(
                nome=nome_fase, descricao="", status="planejada", ordem=maior + 1,
                autor=(autor or "").strip() or None,
            )
            db.add(fase)
            db.flush()   # precisa do id pra pôr o técnico nela
            fases_por_nome[chave] = fase
            fases_criadas.append(fase.nome)
        return fase

    def manda_pra_fase(tecnico, fase):
        if fase is None:
            return
        _colocar_na_fase(tecnico, fase)
        _fase_em_andamento(fase)
        por_fase[fase.id] = por_fase.get(fase.id, 0) + 1

    criados = 0
    atualizados = 0
    em_branco = 0
    rejeitados = []
    avisos = []
    tem_tipo = "tipo_vinculo" in idx
    tem_codigo = "codigo" in idx or "agente" in idx
    # quantos entraram de cada tipo e quantos vieram sem o código
    vinculos = {"direto": 0, "repasse": 0, "clt": 0, "sem_tipo": 0, "sem_codigo": 0}

    def rejeita(r, motivo):
        rejeitados.append({
            "linha": r["linha"], "nome": r["nome"], "telefone": r["telefone_bruto"], "motivo": motivo,
        })

    def avisa(r, motivo):
        avisos.append({"linha": r["linha"], "nome": r["nome"], "telefone": r["telefone_bruto"], "motivo": motivo})

    # 1ª passada: lê e valida linha por linha. O repasse só é gravado depois dos
    # diretos (2ª passada) — é de lá que sai o direto dele e, quando ele não tem
    # número próprio, o telefone
    validas = []
    for linha_num, row in enumerate(linhas[1:], start=2):
        r = {"linha": linha_num, "row": row, "nome": valor(row, "nome"),
             "telefone_bruto": valor(row, "telefone")}
        if not r["nome"] and not r["telefone_bruto"]:
            em_branco += 1
            continue  # linha em branco — não é erro, só não tem nada nela
        r["vinculo"] = _vinculo_da_planilha(valor(row, "tipo_vinculo"))
        r["codigo"] = valor(row, "codigo") or None
        r["direto_nome"] = valor(row, "direto_nome") or None
        r["direto_codigo"] = valor(row, "direto_codigo") or None
        cod_agente, parc_agente, repasse_agente = _le_agente(valor(row, "agente"))
        if cod_agente:
            # sem coluna Tipo, o "REPASSE" do Agente decide
            if r["vinculo"] is None and parc_agente:
                r["vinculo"] = "repasse" if repasse_agente else "direto"
            r["codigo"] = r["codigo"] or cod_agente
            # no repasse, o PARC do Agente é o do direto dele
            if r["vinculo"] == "repasse" and parc_agente:
                r["direto_codigo"] = r["direto_codigo"] or parc_agente
        r["direto_telefone"] = valor(row, "direto_telefone") or None
        r["repasse"] = r["vinculo"] == "repasse"
        if not r["nome"]:
            rejeita(r, "sem nome")
            continue
        if r["repasse"] and not r["telefone_bruto"]:
            # sem número próprio: chega nele pelo número do direto
            r["telefone_bruto"] = r["direto_telefone"] or ""
        if not r["telefone_bruto"] and not r["repasse"]:
            rejeita(r, "sem telefone")
            continue
        r["telefone"] = None
        if r["telefone_bruto"]:
            try:
                r["telefone"] = _norm_telefone(r["telefone_bruto"])
            except HTTPException:
                rejeita(r, "telefone inválido")
                continue
        validas.append(r)

    usados = set()           # cadastros da base já casados com alguma linha

    def acha_existente(r):
        """Pelo código (quando só um cadastro tem aquele código); senão mesmo
        número + mesmo nome; senão, pra quem não é repasse, o dono do número.
        Repasse não casa só pelo número: ele pode estar com o número do direto."""
        if r["codigo"]:
            por_codigo = [t for t in base_por_codigo.get(_chave_codigo(r["codigo"]), []) if id(t) not in usados]
            if len(por_codigo) == 1:
                return por_codigo[0]
        candidatos = [t for t in ja_na_base.get(r["telefone"], []) if id(t) not in usados]
        for t in candidatos:
            if _norm_txt(t.nome) == _norm_txt(r["nome"]):
                return t
        if not r["repasse"]:
            for t in candidatos:
                if t.vinculo != "repasse":
                    return t
        return None

    def grava(r, direto=None):
        nonlocal criados, atualizados
        row = r["row"]
        papel_txt = _norm_txt(valor(row, "papel"))
        papel = "lider" if papel_txt in ("lider", "lider de equipe", "supervisor") else "tecnico"
        regional = valor(row, "regional") or None
        lider_nome = valor(row, "lider_nome") or None

        tecnico = acha_existente(r)
        if tecnico:
            # atualiza o cadastro, nunca o andamento do teste: status, nota,
            # etapas e feedback são progresso de QA e não vêm da planilha
            tecnico.nome = r["nome"]
            tecnico.papel = papel
            if tecnico.telefone != r["telefone"]:
                # casou pelo código com o número trocado: vale o da planilha
                ja_na_base.setdefault(r["telefone"], []).append(tecnico)
                tecnico.telefone = r["telefone"]
            if regional:
                tecnico.regional = regional
            if lider_nome:
                tecnico.lider_nome = lider_nome
            if not tecnico.token:
                tecnico.token = models.novo_token_tecnico()
            atualizados += 1
        else:
            tecnico = models.Tecnico(
                nome=r["nome"], telefone=r["telefone"], papel=papel,
                regional=regional, lider_nome=lider_nome,
                autor=(autor or "").strip() or None,
                token=models.novo_token_tecnico(),
                status="a_contatar",
            )
            db.add(tecnico)
            ja_na_base.setdefault(r["telefone"], []).append(tecnico)
            criados += 1
        usados.add(id(tecnico))
        vinculos[r["vinculo"] or "sem_tipo"] += 1
        if not r["codigo"]:
            vinculos["sem_codigo"] += 1
        if r["codigo"]:
            tecnico.codigo = r["codigo"]
        if r["vinculo"]:
            tecnico.vinculo = r["vinculo"]
        if tecnico.vinculo == "repasse":
            tecnico.direto = direto
            tecnico.direto_nome = r["direto_nome"] or (direto.nome if direto else None)
            tecnico.direto_codigo = r["direto_codigo"] or (direto.codigo if direto else None)
        elif r["vinculo"]:
            tecnico.direto = None
            tecnico.direto_nome = tecnico.direto_codigo = None
        manda_pra_fase(tecnico, fase_da_linha(row))
        return tecnico

    # 2ª passada: direto, CLT e quem não tem tipo — cada número é de um só
    diretos_por_codigo = {}  # código normalizado -> diretos da planilha
    diretos_por_nome = {}    # nome normalizado -> diretos da planilha
    linha_do_numero = {}     # telefone -> 1ª linha que trouxe o número
    for r in validas:
        if r["repasse"]:
            continue
        if r["telefone"] in linha_do_numero:
            rejeita(r, f"telefone repetido na planilha (já veio na linha {linha_do_numero[r['telefone']]})")
            continue
        linha_do_numero[r["telefone"]] = r["linha"]
        tecnico = grava(r)
        if tecnico.vinculo != "repasse":
            if tecnico.codigo:
                diretos_por_codigo.setdefault(_chave_codigo(tecnico.codigo), []).append(tecnico)
            diretos_por_nome.setdefault(_norm_txt(tecnico.nome), []).append(tecnico)

    base_nao_repasse = [t for lista in ja_na_base.values() for t in lista
                        if t.vinculo != "repasse" and id(t) not in usados]

    def acha_direto(r):
        """O direto do repasse: pelo código; sem código (ou código que não bate),
        pelo nome; e, por último, pelo celular do direto. Na planilha primeiro,
        depois na base. Ambíguo fica sem direto — melhor no aviso do que ligado
        ao direto errado."""
        tel_direto = None
        if r["direto_telefone"]:
            try:
                tel_direto = _norm_telefone(r["direto_telefone"])
            except HTTPException:
                pass
        if r["direto_codigo"]:
            chave = _chave_codigo(r["direto_codigo"])
            achados = diretos_por_codigo.get(chave) or [
                t for t in base_nao_repasse if t.codigo and _chave_codigo(t.codigo) == chave]
            if len(achados) > 1 and r["telefone"]:
                # dois diretos com o mesmo código: o do repasse é o dono do número dele
                achados = [t for t in achados if t.telefone == r["telefone"]] or achados
            if len(achados) == 1:
                return achados[0]
        if r["direto_nome"]:
            chave = _norm_txt(r["direto_nome"])
            achados = diretos_por_nome.get(chave) or [
                t for t in base_nao_repasse if _norm_txt(t.nome) == chave]
            if len(achados) > 1 and tel_direto:
                achados = [t for t in achados if t.telefone == tel_direto]
            if len(achados) == 1:
                return achados[0]
        if tel_direto:
            achados = [t for t in ja_na_base.get(tel_direto, []) if t.vinculo != "repasse"]
            if len(achados) == 1:
                return achados[0]
        return None

    # 3ª passada: repasse — liga no direto e, sem número próprio, usa o dele
    repasse_sem_direto = 0
    vistos = {}              # (telefone, nome) -> linha, pra não cadastrar a mesma pessoa duas vezes
    for r in validas:
        if not r["repasse"]:
            continue
        direto = acha_direto(r)
        if r["telefone"] is None:
            if direto is None:
                rejeita(r, "repasse sem telefone e sem direto achado pra usar o número dele")
                continue
            r["telefone"] = direto.telefone
            r["telefone_bruto"] = direto.telefone
        chave = (r["telefone"], _norm_txt(r["nome"]))
        if chave in vistos:
            rejeita(r, f"telefone repetido na planilha (já veio na linha {vistos[chave]})")
            continue
        vistos[chave] = r["linha"]
        grava(r, direto=direto)
        if direto is None:
            repasse_sem_direto += 1
            if r["direto_nome"] or r["direto_codigo"]:
                quem = " / ".join(x for x in (r["direto_nome"], r["direto_codigo"]) if x)
                avisa(r, f"direto \"{quem}\" não encontrado na planilha nem na base")
            else:
                avisa(r, "repasse sem direto informado")
    rejeitados.sort(key=lambda e: e["linha"])
    # base do Brasil inteiro numa planilha só: com `distribuir`, quem ficou sem
    # fase cai na fase que cobre a UF dele
    distribuicao = _distribui_por_uf(db) if distribuir and fase_fixa is None else None
    # repasse que já estava na base esperando o direto que só chegou agora
    religacao = religar_repasses(db)
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
        # quantos da planilha caíram em cada fase — o retorno de "subi a fase 2"
        "fases": [
            {"id": f.id, "nome": f.nome, "tecnicos": por_fase[f.id]}
            for f in fases_por_nome.values() if f.id in por_fase
        ] if fase_fixa is None else (
            [{"id": fase_fixa.id, "nome": fase_fixa.nome, "tecnicos": por_fase.get(fase_fixa.id, 0)}]
        ),
        "fases_criadas": fases_criadas,
        # direto / repasse / CLT — só quando a planilha tem a coluna Tipo ou Código
        "vinculos": {**vinculos, "repasse_sem_direto": repasse_sem_direto} if (tem_tipo or tem_codigo) else None,
        "avisos": avisos,
        "distribuicao": distribuicao,
        "religacao": religacao,
    }
