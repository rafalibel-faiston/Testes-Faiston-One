"""O nome padrão do chamado de teste no Tiflux.

Cada chamado aberto pra rodar um teste precisa de um título, e cada um vinha
com um nome diferente — "[TESTE IA] - TESTE", "[TESTE IA] - ", "CHAMADO
IMEDIATO…" sem prefixo nenhum. Depois fica impossível achar no Tiflux qual
chamado foi de qual teste.

A regra aqui é uma só, pra qualquer teste — de uma situação do console, de um
caso, ou um teste avulso que não está cadastrado em lugar nenhum:

    [TESTE IA] - ATRIBUIR TÉCNICO MANUALMENTE - T01

* `[TESTE IA]` — o prefixo que o time já usa na mesa de teste;
* o assunto: o título da situação, o resultado esperado do caso ou o que a
  pessoa digitou, em maiúscula e cortado numa palavra inteira;
* a rodada: `T` pra validação técnica, `OP` pra validação na operação, e o
  número da vez. Refazer o mesmo teste gera `T02`, `T03`… — nome parecido,
  mas nunca igual a um que já foi usado.

A rodada conta pelo assunto (sem ligar pra acento e caixa), não pelo card: dois
testes com o mesmo assunto dividem a sequência, então o nome final nunca se
repete. O número de cada rodada fica gravado (`models.NomeTiflux`).
"""
import re
import unicodedata

from . import niveis

PREFIXO = "[TESTE IA]"
SEP = " - "
# marca da rodada por nível — o mesmo teste rodado pela operação não se
# confunde com o meu
MARCA_NIVEL = {niveis.NIVEL_INTERNO: "T", niveis.NIVEL_OPERACAO: "OP"}
# título inteiro, pra caber na listagem do Tiflux sem cortar o que importa
MAX_TITULO = 90
# espaço reservado pra rodada mais longa (" - OP99"), assim o assunto sai
# igual nos dois níveis e a sequência não se divide por causa de um corte
_RESERVA_RODADA = len(SEP) + 4
_LIMITE_ASSUNTO = MAX_TITULO - len(PREFIXO) - len(SEP) - _RESERVA_RODADA


def rodada(nivel: str, seq: int) -> str:
    return f"{MARCA_NIVEL[nivel]}{seq:02d}"


def assunto(texto: str) -> str:
    """Encurta o assunto pra caber no título: tira aspas e símbolos que só
    poluem, passa pra maiúscula (como o time já escreve no Tiflux) e corta
    numa palavra inteira."""
    texto = (texto or "").replace("\n", " ")
    texto = re.sub(r"[\"'“”‘’`|]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" .;:-—")
    texto = texto.upper()
    # quem cola o nome antigo do chamado não fica com o prefixo duplicado
    if texto.startswith(PREFIXO):
        texto = texto[len(PREFIXO):].strip(" .;:-—")
    if len(texto) <= _LIMITE_ASSUNTO:
        return texto
    corte = texto[: _LIMITE_ASSUNTO + 1].rsplit(" ", 1)[0].rstrip(" ,.;:-—(")
    return corte or texto[:_LIMITE_ASSUNTO]


def chave(texto_assunto: str) -> str:
    """Identidade do assunto pra contar a rodada: "DISTÂNCIA" e "DISTANCIA"
    são o mesmo teste."""
    sem_acento = "".join(
        ch for ch in unicodedata.normalize("NFD", texto_assunto or "")
        if unicodedata.category(ch) != "Mn"
    )
    return re.sub(r"[^A-Z0-9]+", " ", sem_acento.upper()).strip()


def montar(texto_assunto: str, nivel: str, seq: int) -> str:
    return SEP.join([PREFIXO, assunto(texto_assunto), rodada(nivel, seq)])


def assunto_do_nome(nome: str) -> str:
    """O assunto de um nome já gerado — o que fica entre o prefixo e a rodada.
    As rodadas seguintes reaproveitam o texto da primeira, então só o número
    muda, mesmo que a pessoa digite sem acento ou com outra caixa."""
    return nome[len(PREFIXO) + len(SEP):].rsplit(SEP, 1)[0]
