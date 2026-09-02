from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ScreenshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime] = None


class ObservationRevisionOut(BaseModel):
    """Uma versão anterior do texto — a trilha das atualizações da observação."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    texto: str
    cor: Optional[str] = None
    autor: Optional[str] = None
    editado_por: Optional[str] = None
    created_at: Optional[datetime] = None


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    autor: Optional[str] = None
    texto: str
    cor: Optional[str] = None   # "verde", "vermelho" ou None (sem marcação)
    editado_por: Optional[str] = None
    editado_em: Optional[datetime] = None
    created_at: Optional[datetime] = None
    revisions: List[ObservationRevisionOut] = []


class ObservationCreate(BaseModel):
    texto: str
    autor: Optional[str] = None
    # "verde" (deu certo) ou "vermelho" (problema). Vazio/ausente = sem cor.
    cor: Optional[str] = None


class ObservationUpdate(BaseModel):
    """Atualiza o texto de uma observação. O texto anterior não some: vira mais
    uma linha da trilha (`revisions`)."""
    texto: str
    autor: Optional[str] = None
    # cor ausente (None) = não mexe na cor atual; mande "neutro" para tirá-la.
    cor: Optional[str] = None


class TestCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    fluxo: str = "C"
    grupo: str
    estagio: str
    estagio_num: Optional[int] = None
    frente: str
    tipo: str
    prioridade: str
    origem: str
    pre_condicao: str
    passos: str
    resultado_esperado: str
    problema_encontrado: Optional[str] = None
    status: str
    observacao: Optional[str] = ""
    testado_por: Optional[str] = None
    chamado: Optional[str] = None
    user_managed: Optional[bool] = False
    updated_at: Optional[datetime] = None
    screenshots: List[ScreenshotOut] = []
    observations: List[ObservationOut] = []


class TestCaseUpdate(BaseModel):
    status: Optional[str] = None
    testado_por: Optional[str] = None
    # dado de execução (do testador) — nunca tocado pelo seed
    chamado: Optional[str] = None
    # campos descritivos — editáveis na tela; ao mudar qualquer um, o caso
    # vira user_managed e o seed para de sobrescrevê-lo.
    fluxo: Optional[str] = None
    grupo: Optional[str] = None
    estagio: Optional[str] = None
    frente: Optional[str] = None
    tipo: Optional[str] = None
    prioridade: Optional[str] = None
    origem: Optional[str] = None
    pre_condicao: Optional[str] = None
    passos: Optional[str] = None
    resultado_esperado: Optional[str] = None
    problema_encontrado: Optional[str] = None


class TestCaseCreate(BaseModel):
    code: Optional[str] = None          # gerado automaticamente se vazio
    fluxo: str = "C"
    grupo: str = "Grupo C"
    estagio: str
    frente: str = "A definir"
    tipo: str = "Manual"
    prioridade: str = "Média"
    origem: str = "Criado no console"
    pre_condicao: str = ""
    passos: str = ""
    resultado_esperado: str
    problema_encontrado: Optional[str] = None
    chamado: Optional[str] = None


class SitScreenshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime] = None


class SitObservationRevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    texto: str
    cor: Optional[str] = None
    autor: Optional[str] = None
    editado_por: Optional[str] = None
    created_at: Optional[datetime] = None


class SitObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    autor: Optional[str] = None
    texto: str
    cor: Optional[str] = None   # "verde", "vermelho" ou None (sem marcação)
    editado_por: Optional[str] = None
    editado_em: Optional[datetime] = None
    created_at: Optional[datetime] = None
    revisions: List[SitObservationRevisionOut] = []


class SitObservationCreate(BaseModel):
    texto: str
    autor: Optional[str] = None
    cor: Optional[str] = None


class SitObservationUpdate(BaseModel):
    texto: str
    autor: Optional[str] = None
    # cor ausente (None) = não mexe na cor atual; mande "neutro" para tirá-la.
    cor: Optional[str] = None


class SituacaoEstagioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordem: int = 0
    nome: str
    frente: str
    passos: Optional[str] = ""
    resultado_esperado: str
    status: str
    testado_por: Optional[str] = None
    updated_at: Optional[datetime] = None
    screenshots: List[SitScreenshotOut] = []
    observations: List[SitObservationOut] = []


class SituacaoEstagioCreate(BaseModel):
    nome: str
    frente: str = "Transversal"
    passos: Optional[str] = ""
    resultado_esperado: str
    ordem: Optional[int] = None


class SituacaoEstagioUpdate(BaseModel):
    nome: Optional[str] = None
    frente: Optional[str] = None
    passos: Optional[str] = None
    resultado_esperado: Optional[str] = None
    ordem: Optional[int] = None
    status: Optional[str] = None
    testado_por: Optional[str] = None


class SituacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    fluxo: str = "C"
    titulo: str
    descricao: str
    origem: Optional[str] = None
    chamado: Optional[str] = None
    user_managed: Optional[bool] = False
    updated_at: Optional[datetime] = None
    estagios: List[SituacaoEstagioOut] = []


class SituacaoCreate(BaseModel):
    code: Optional[str] = None
    fluxo: str = "C"
    titulo: str
    descricao: str
    origem: str = "Criado no console"


class SituacaoUpdate(BaseModel):
    fluxo: Optional[str] = None
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    origem: Optional[str] = None
    # dado de execução (do testador) — não é "conteúdo" da situação, não marca user_managed
    chamado: Optional[str] = None


class SummaryOut(BaseModel):
    total: int
    counts: dict
    pct_executado: float


class MeetingNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fluxo: str = "C"
    estagio: Optional[str] = None
    texto: str
    autor: Optional[str] = None
    cobrado: bool = False
    cobrado_em: Optional[datetime] = None
    resolvido: bool = False
    resolvido_em: Optional[datetime] = None
    retorno: Optional[str] = ""
    prazo: Optional[str] = None
    retorno_em: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MeetingNoteCreate(BaseModel):
    fluxo: str = "C"
    estagio: Optional[str] = None
    texto: str
    autor: Optional[str] = None


class MeetingNoteUpdate(BaseModel):
    texto: Optional[str] = None
    estagio: Optional[str] = None
    cobrado: Optional[bool] = None
    resolvido: Optional[bool] = None
    retorno: Optional[str] = None
    prazo: Optional[str] = None


class FlowDiagramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fluxo: str = "C"
    kind: str = "atual"
    titulo: str
    descricao: Optional[str] = ""
    mermaid: str
    ordem: Optional[int] = 0
    atualizado_por: Optional[str] = None
    seeded: Optional[bool] = False
    updated_at: Optional[datetime] = None


class FlowDiagramCreate(BaseModel):
    fluxo: str = "C"
    kind: str = "atual"
    titulo: str
    descricao: Optional[str] = ""
    mermaid: str
    ordem: Optional[int] = 0
    atualizado_por: Optional[str] = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fluxo: str = "C"
    tipo: str
    texto: str
    autor: Optional[str] = None
    case_code: Optional[str] = None
    created_at: Optional[datetime] = None


class TeamViewOut(BaseModel):
    perfil: str
    fluxo: str = "C"
    last_seen_id: int = 0


class TeamViewMark(BaseModel):
    perfil: str
    fluxo: str = "C"
    last_seen_id: int


class AgendaEventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    descricao: Optional[str] = ""
    data: str
    hora_inicio: Optional[str] = None
    hora_fim: Optional[str] = None
    tipo: str = "compromisso"
    concluido: bool = False
    autor: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AgendaEventoCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = ""
    data: str
    hora_inicio: Optional[str] = None
    hora_fim: Optional[str] = None
    tipo: Optional[str] = "compromisso"
    autor: Optional[str] = None


class AgendaEventoUpdate(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    data: Optional[str] = None
    hora_inicio: Optional[str] = None
    hora_fim: Optional[str] = None
    tipo: Optional[str] = None
    concluido: Optional[bool] = None


class TodoTarefaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    descricao: Optional[str] = ""
    status: str = "a_fazer"
    posicao: int = 0
    responsavel: Optional[str] = None
    autor: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TodoTarefaCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = ""
    status: str = "a_fazer"
    responsavel: Optional[str] = None
    autor: Optional[str] = None


class TodoTarefaUpdate(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    status: Optional[str] = None
    posicao: Optional[int] = None
    responsavel: Optional[str] = None


class FlowDiagramUpdate(BaseModel):
    fluxo: Optional[str] = None
    kind: Optional[str] = None
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    mermaid: Optional[str] = None
    ordem: Optional[int] = None
    atualizado_por: Optional[str] = None


class TecnicoObservacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    autor: Optional[str] = None
    texto: str
    tipo: Optional[str] = None   # positivo / melhoria / problema / None
    ajuste_id: Optional[int] = None    # item da Gestão de Ativos que este relato gerou
    ajuste_ref: Optional[str] = None   # como ele é chamado na reunião: "v2 #07"
    created_at: Optional[datetime] = None


class VirarAjuste(BaseModel):
    """Transforma o relato de um técnico em item do backlog da Gestão de Ativos.
    `atual` já vem do texto dele; o resto é o que a Faiston preenche ao revisar."""
    titulo: str
    tipo: Optional[str] = None        # Bug / Melhoria — sem isso, deduz do tipo do relato
    versao: Optional[str] = None
    area: Optional[str] = "Track One (app do técnico)"
    prioridade: Optional[str] = "Média"
    atual: Optional[str] = None       # ausente = usa o texto do técnico
    esperado: Optional[str] = ""
    observacao: Optional[str] = None  # ausente = registra quem relatou e quando
    autor: Optional[str] = None


class TecnicoObservacaoCreate(BaseModel):
    texto: str
    autor: Optional[str] = None
    tipo: Optional[str] = None


class TecnicoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    telefone: str
    papel: str = "tecnico"
    regional: Optional[str] = None
    lider_nome: Optional[str] = None
    status: str = "a_contatar"
    autor: Optional[str] = None
    fase_id: Optional[int] = None          # leva do piloto em que ele entrou
    token: Optional[str] = None            # chave do link /formulario/{token}
    nota: Optional[int] = None             # nota geral que ele deu no app (1 a 5)
    etapas_testadas: Optional[str] = None  # etapas exercitadas, separadas por "|"
    respondido_em: Optional[datetime] = None
    convidado_em: Optional[datetime] = None
    instalado_em: Optional[datetime] = None
    concluido_em: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    observacoes: List[TecnicoObservacaoOut] = []


class TecnicoCreate(BaseModel):
    nome: str
    telefone: str
    papel: Optional[str] = "tecnico"
    regional: Optional[str] = None
    lider_nome: Optional[str] = None
    autor: Optional[str] = None


class TecnicoUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    papel: Optional[str] = None
    regional: Optional[str] = None
    lider_nome: Optional[str] = None
    status: Optional[str] = None


class TecnicoMensagemOut(BaseModel):
    tecnico_id: int
    telefone: str
    mensagem: str
    wa_link: str


class PilotoFaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    descricao: Optional[str] = ""
    status: str = "planejada"
    ordem: int = 0
    meta_concluidos: Optional[int] = None
    meta_nota: Optional[float] = None
    meta_etapa: Optional[int] = None
    iniciada_em: Optional[datetime] = None
    liberada_em: Optional[datetime] = None
    autor: Optional[str] = None
    created_at: Optional[datetime] = None
    # contagem preenchida pelo router. Não pode se chamar "tecnicos": o modelo tem
    # um relationship com esse nome e o Pydantic leria a lista no lugar do número.
    total_tecnicos: int = 0


class PilotoFaseCreate(BaseModel):
    nome: str
    descricao: Optional[str] = ""
    meta_concluidos: Optional[int] = None
    meta_nota: Optional[float] = None
    meta_etapa: Optional[int] = None
    autor: Optional[str] = None


class PilotoFaseUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    status: Optional[str] = None
    ordem: Optional[int] = None
    meta_concluidos: Optional[int] = None
    meta_nota: Optional[float] = None
    meta_etapa: Optional[int] = None


class AdicionarNaFase(BaseModel):
    """Quem entra na fase: uma lista de ids escolhidos a dedo, ou tudo que bate
    num filtro da base (é assim que "toda a regional de Campinas" entra de uma vez
    sem clicar em cinquenta nomes)."""
    tecnico_ids: List[int] = []
    regional: Optional[str] = None
    busca: Optional[str] = None
    papel: Optional[str] = None
    # por padrão não rouba técnico que já está em outra fase
    incluir_de_outras_fases: bool = False


class TecnicoResumoOut(BaseModel):
    """Versão leve pra listar a base inteira sem arrastar observações junto —
    com milhares de cadastros, a lista completa era megabytes de JSON."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    telefone: str
    papel: str = "tecnico"
    regional: Optional[str] = None
    status: str = "a_contatar"
    fase_id: Optional[int] = None


class BaseTecnicosOut(BaseModel):
    total: int
    itens: List[TecnicoResumoOut] = []


class VincularAjuste(BaseModel):
    """Aponta o relato para um ajuste que já existe — é assim que vários técnicos
    relatando o mesmo ponto viram um item com vários relatos."""
    ajuste_id: int


class LimparBaseTecnicos(BaseModel):
    """Apagar a base inteira não pode acontecer por um clique errado nem por uma
    chamada solta na API: exige a palavra APAGAR escrita à mão."""
    confirmar: str


class FormularioResposta(BaseModel):
    """O que o técnico mandou pelo formulário público (/formulario/{token}).
    Todos os campos são opcionais — ele responde o que quiser, desde que
    responda alguma coisa."""
    nota: Optional[int] = None            # 1 a 5
    etapas: List[str] = []                # etapas do fluxo que conseguiu usar
    positivo: Optional[str] = ""          # o que funcionou bem
    melhoria: Optional[str] = ""          # o que precisa melhorar
    problema: Optional[str] = ""          # erro/travamento encontrado
    comentario: Optional[str] = ""        # campo livre — vira nota geral


class AtivoAjustePrintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime] = None


class AtivoAjusteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    versao: str = "v2"
    numero: int = 0
    titulo: str
    tipo: str = "Melhoria"
    area: Optional[str] = None
    prioridade: str = "Média"
    atual: Optional[str] = ""
    esperado: Optional[str] = ""
    observacao: Optional[str] = ""
    status: str = "levantado"
    responsavel: Optional[str] = None
    autor: Optional[str] = None
    retorno: Optional[str] = ""
    prazo: Optional[str] = None
    retorno_em: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    prints: List[AtivoAjustePrintOut] = []


class AtivoAjusteCreate(BaseModel):
    versao: Optional[str] = "v2"
    numero: Optional[int] = None      # None = próximo número livre da versão
    titulo: str
    tipo: Optional[str] = "Melhoria"
    area: Optional[str] = None
    prioridade: Optional[str] = "Média"
    atual: Optional[str] = ""
    esperado: Optional[str] = ""
    observacao: Optional[str] = ""
    status: Optional[str] = "levantado"
    responsavel: Optional[str] = None
    autor: Optional[str] = None


class AtivoAjusteUpdate(BaseModel):
    versao: Optional[str] = None
    numero: Optional[int] = None
    titulo: Optional[str] = None
    tipo: Optional[str] = None
    area: Optional[str] = None
    prioridade: Optional[str] = None
    atual: Optional[str] = None
    esperado: Optional[str] = None
    observacao: Optional[str] = None
    status: Optional[str] = None
    responsavel: Optional[str] = None
    retorno: Optional[str] = None
    prazo: Optional[str] = None
