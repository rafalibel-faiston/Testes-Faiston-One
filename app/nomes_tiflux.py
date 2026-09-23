"""O nome padrão do chamado de teste no Tiflux.

Cada chamado aberto pra rodar um teste precisa de um título, e cada um vinha
com um nome diferente — "[TESTE IA] - TESTE", "[TESTE IA] - ", "CHAMADO
IMEDIATO…" sem prefixo nenhum. Depois fica impossível achar no Tiflux qual
chamado foi de qual teste.

A regra aqui é uma só, pra todo teste do console:

    [TESTE IA] - FC-04-APP-02 - T01 - MOSTRA AGUARDANDO INÍCIO

* `[TESTE IA]` — o prefixo que o time já usa na mesa de teste;
* o código do teste (caso `FC-…` ou situação `SIT-…`) — o que liga o chamado
  ao card do console;
* a rodada: `T` pra validação técnica, `O` pra validação na operação, e o
  número da vez. Refazer o mesmo teste gera `T02`, `T03`… — nome parecido,
  mas nunca igual a um que já foi usado;
* um resumo curto do que está sendo testado, pra ler o chamado sem abrir o card.

O número de cada rodada fica gravado (`models.NomeTiflux`), então não repete
nem se o nome antigo foi apagado da tela.
"""
import re

from . import niveis

PREFIXO = "[TESTE IA]"
SEP = " - "
# letra da rodada por nível — o mesmo teste rodado pela operação não se
# confunde com o meu
LETRA_NIVEL = {niveis.NIVEL_INTERNO: "T", niveis.NIVEL_OPERACAO: "O"}
# título inteiro, pra caber na listagem do Tiflux sem cortar o que importa
MAX_TITULO = 90
MIN_RESUMO = 12


def rodada(nivel: str, seq: int) -> str:
    return f"{LETRA_NIVEL[nivel]}{seq:02d}"


def resumo(texto: str, limite: int) -> str:
    """Encurta a descrição do teste pra caber no título: tira aspas e
    símbolos que só poluem, passa pra maiúscula (como o time já escreve no
    Tiflux) e corta numa palavra inteira."""
    texto = (texto or "").replace("\n", " ")
    texto = re.sub(r"[\"'“”‘’`|]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" .;:-—")
    texto = texto.upper()
    if len(texto) <= limite:
        return texto
    corte = texto[: limite + 1].rsplit(" ", 1)[0].rstrip(" ,.;:-—(")
    return corte or texto[:limite]


def montar(code: str, nivel: str, seq: int, descricao: str = "") -> str:
    base = SEP.join([PREFIXO, code.upper(), rodada(nivel, seq)])
    espaco = MAX_TITULO - len(base) - len(SEP)
    curto = resumo(descricao, max(espaco, MIN_RESUMO))
    return base + SEP + curto if curto else base

