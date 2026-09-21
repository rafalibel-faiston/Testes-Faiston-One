"""Os dois níveis de teste — o meu e o da operação.

Um caso passar na minha mão não quer dizer que passa na operação: o caminho
que eu faço é o caminho que eu conheço, e a operação usa o sistema do jeito
dela. Por isso cada caso (e cada estágio de situação) carrega DOIS status
independentes:

* `status`            — nível "interno": o meu teste, o da validação técnica.
* `status_operacao`   — nível "operação": o teste feito por quem opera de verdade.

O status que vale pra fora (relatório, exportação, KPI) é o consolidado
(`status_geral`): só é **Aprovado** quando os dois níveis passam. Enquanto só
um passou, o caso fica num estado intermediário explícito — ninguém dá um
caso como pronto porque funcionou na máquina de quem construiu.
"""

NAO_TESTADO = "Não testado"
APROVADO = "Aprovado"
REPROVADO = "Reprovado"
BLOQUEADO = "Bloqueado"
NA = "N/A"

# os status que podem ser gravados em CADA nível (o que a tela e a API aceitam)
VALID_STATUSES = {NAO_TESTADO, APROVADO, REPROVADO, BLOQUEADO, NA}

# estados intermediários — nunca são gravados, só saem do consolidado
VALIDACAO_INTERNA = "Validação interna"    # passou comigo, falta a operação
VALIDACAO_OPERACAO = "Validação operação"  # passou na operação, falta o meu teste

# tudo que o consolidado pode devolver
STATUSES_GERAIS = VALID_STATUSES | {VALIDACAO_INTERNA, VALIDACAO_OPERACAO}

NIVEL_INTERNO = "interno"
NIVEL_OPERACAO = "operacao"
NIVEIS = (NIVEL_INTERNO, NIVEL_OPERACAO)
NIVEL_LABEL = {NIVEL_INTERNO: "Meu teste", NIVEL_OPERACAO: "Operação"}

# só conta como resolvido quando os dois níveis fecharam
STATUS_OK = {APROVADO, NA}
STATUS_PROBLEMA = {REPROVADO, BLOQUEADO}
STATUS_PENDENTE = {NAO_TESTADO, VALIDACAO_INTERNA, VALIDACAO_OPERACAO}


def normaliza_nivel(nivel) -> str:
    """Aceita 'interno'/'operacao' (e os apelidos óbvios). Vazio = interno."""
    n = (nivel or "").strip().lower()
    if n in ("", NIVEL_INTERNO, "meu", "meu teste", "interna"):
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
      4. um lado aprovado e o outro ainda em aberto = validação parcial.
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
        return VALIDACAO_INTERNA
    if operacao == APROVADO:
        return VALIDACAO_OPERACAO
    return NAO_TESTADO


def executado(interno, operacao) -> bool:
    """O caso saiu do zero? Basta um dos níveis ter sido rodado."""
    return (interno or NAO_TESTADO) != NAO_TESTADO or (operacao or NAO_TESTADO) != NAO_TESTADO
