"""Os dois níveis de teste — o meu e o da operação.

Passar na validação técnica não quer dizer que passa na operação: quem
construiu (ou acompanhou) o fluxo percorre o caminho que conhece, e a operação
usa o sistema do jeito dela. Por isso cada caso (e cada estágio de situação) carrega DOIS status
independentes:

* `status`            — nível "interno": a VALIDAÇÃO TÉCNICA, feita por quem
                        acompanha o projeto de perto.
* `status_operacao`   — nível "operação": a VALIDAÇÃO NA OPERAÇÃO, feita por
                        quem usa o sistema no dia a dia.

O status que vale pra fora (relatório, exportação, KPI) é o consolidado
(`status_geral`): só é **Aprovado** quando os dois níveis passam. Enquanto só
um passou, o caso fica num estado intermediário que diz o que falta — ninguém
dá um caso como pronto porque funcionou na máquina de quem construiu.
"""

NAO_TESTADO = "Não testado"
APROVADO = "Aprovado"
REPROVADO = "Reprovado"
BLOQUEADO = "Bloqueado"
NA = "N/A"

# os status que podem ser gravados em CADA nível (o que a tela e a API aceitam)
VALID_STATUSES = {NAO_TESTADO, APROVADO, REPROVADO, BLOQUEADO, NA}

# estados intermediários — nunca são gravados, só saem do consolidado
# passou na validação técnica, a operação ainda não viu
PENDENTE_OPERACAO = "Pendente na operação"
# passou na operação, falta a validação técnica
PENDENTE_TECNICA = "Pendente na técnica"

# tudo que o consolidado pode devolver
STATUSES_GERAIS = VALID_STATUSES | {PENDENTE_OPERACAO, PENDENTE_TECNICA}

NIVEL_INTERNO = "interno"
NIVEL_OPERACAO = "operacao"
NIVEIS = (NIVEL_INTERNO, NIVEL_OPERACAO)
NIVEL_LABEL = {NIVEL_INTERNO: "Validação técnica", NIVEL_OPERACAO: "Validação na operação"}
# forma curta, pra onde o espaço é apertado (botões, cabeçalho de planilha)
NIVEL_CURTO = {NIVEL_INTERNO: "Técnica", NIVEL_OPERACAO: "Operação"}

# só conta como resolvido quando os dois níveis fecharam
STATUS_OK = {APROVADO, NA}
STATUS_PROBLEMA = {REPROVADO, BLOQUEADO}
STATUS_PENDENTE = {NAO_TESTADO, PENDENTE_OPERACAO, PENDENTE_TECNICA}


def normaliza_nivel(nivel) -> str:
    """Aceita 'interno'/'operacao' (e os apelidos óbvios). Vazio = interno."""
    n = (nivel or "").strip().lower()
    if n in ("", NIVEL_INTERNO, "tecnica", "técnica", "meu", "meu teste", "interna"):
        return NIVEL_INTERNO
    if n in (NIVEL_OPERACAO, "operação", "op", "operacional"):
        return NIVEL_OPERACAO
    raise ValueError(f"Nível inválido: {nivel}. Use 'interno' ou 'operacao'.")


def status_geral(interno, operacao) -> str:
    """O status que vale pra fora, a partir dos dois níveis.

    Regras, na ordem:
      1. problema em qualquer nível derruba o caso (Reprovado > Bloqueado);
      2. N/A num nível = aquele nível não se aplica, quem decide é o outro;
      3. Aprovado só com os DOIS níveis aprovados;
      4. um lado aprovado e o outro ainda em aberto = pendente do outro lado.
    """
    interno = interno or NAO_TESTADO
    operacao = operacao or NAO_TESTADO

    if REPROVADO in (interno, operacao):
        return REPROVADO
    if BLOQUEADO in (interno, operacao):
        return BLOQUEADO
    if interno == NA and operacao == NA:
        return NA
    # o nível marcado como N/A sai da conta — o outro responde sozinho
    if interno == NA:
        return APROVADO if operacao == APROVADO else NAO_TESTADO
    if operacao == NA:
        return APROVADO if interno == APROVADO else NAO_TESTADO

    if interno == APROVADO and operacao == APROVADO:
        return APROVADO
    if interno == APROVADO:
        return PENDENTE_OPERACAO
    if operacao == APROVADO:
        return PENDENTE_TECNICA
    return NAO_TESTADO


def executado(interno, operacao) -> bool:
    """O caso saiu do zero? Basta um dos níveis ter sido rodado."""
    return (interno or NAO_TESTADO) != NAO_TESTADO or (operacao or NAO_TESTADO) != NAO_TESTADO
