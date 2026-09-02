#!/usr/bin/env python3
"""Gera a pauta da reunião semanal do time de dev em um HTML único.

Puxa do console de teste tudo que **ainda não está aprovado** — pontos de
reunião em aberto, casos de teste reprovados/bloqueados/não executados,
estágios travados das situações e os ajustes da Gestão de Ativos que ainda
não foram validados — e monta uma página autocontida (CSS e logo embutidos)
pra abrir e apresentar na reunião.

O app também serve essa mesma página ao vivo em `/relatorio`; este script
serve pra gerar um arquivo (mandar por e-mail, anexar na ata, versionar a
foto da semana) ou pra montar a pauta a partir de JSONs já salvos.

Uso:

    python3 tools/relatorio_reuniao.py --base-url https://SEU-APP.up.railway.app
    python3 tools/relatorio_reuniao.py --base-url ... --dump-dir ./dump
    python3 tools/relatorio_reuniao.py --json-dir ./dump    # offline

Sem --base-url, usa a variável de ambiente RELATORIO_BASE_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.relatorio import montar_html  # noqa: E402

ENDPOINTS = {
    "summary": "/api/summary",
    "cases": "/api/cases",
    "notas": "/api/notas",
    "ativos_ajustes": "/api/ativos/ajustes",
    "situacoes": "/api/situacoes",
    "piloto": "/api/piloto/pauta",
}

# quais seções vêm como objeto (o resto é lista) — usado pro fallback quando o
# arquivo/endpoint não existe
SECOES_OBJETO = {"summary", "piloto"}


def fetch(base_url: str, path: str, timeout: int = 60):
    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def carregar(base_url: str | None, json_dir: str | None) -> dict:
    dados = {}
    for nome, path in ENDPOINTS.items():
        if json_dir:
            arquivo = Path(json_dir) / f"{nome}.json"
            if not arquivo.exists():
                print(f"aviso: {arquivo} não encontrado — seção fica vazia", file=sys.stderr)
                dados[nome] = {} if nome in SECOES_OBJETO else []
                continue
            dados[nome] = json.loads(arquivo.read_text(encoding="utf-8"))
        else:
            try:
                dados[nome] = fetch(base_url, path)
            except urllib.error.URLError as exc:
                raise SystemExit(f"erro ao buscar {base_url}{path}: {exc}")
    return dados


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera a pauta da reunião semanal em HTML.")
    parser.add_argument("--base-url", default=os.getenv("RELATORIO_BASE_URL"),
                        help="URL pública do console de teste (ex.: https://app.up.railway.app)")
    parser.add_argument("--json-dir", help="pasta com os JSONs já salvos (modo offline)")
    parser.add_argument("--dump-dir", help="salva os JSONs baixados nesta pasta")
    parser.add_argument("--out", default="relatorio-reuniao.html", help="arquivo HTML de saída")
    args = parser.parse_args()

    if not args.base_url and not args.json_dir:
        parser.error("informe --base-url (ou RELATORIO_BASE_URL) ou --json-dir")

    dados = carregar(args.base_url, args.json_dir)

    if args.dump_dir:
        destino = Path(args.dump_dir)
        destino.mkdir(parents=True, exist_ok=True)
        for nome, conteudo in dados.items():
            (destino / f"{nome}.json").write_text(
                json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8")

    fonte = args.base_url if args.base_url else f"JSONs de {args.json_dir}"
    Path(args.out).write_text(montar_html(dados, fonte), encoding="utf-8")
    print(f"gerado: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
