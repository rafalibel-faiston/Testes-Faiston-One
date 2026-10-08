# Faiston Hub — instruções para o Claude

Portal central dos projetos da área de Engenharia de IA da Faiston. A
especificação completa está em `docs/ESPECIFICACAO.md`: leia antes de mexer em
qualquer coisa de autenticação, sessão ou permissão.

## Contexto
- Time: Rafael (Rafa) e parceiro, área nova de Engenharia de IA da Faiston.
- O hub **só aponta** para os sistemas que já existem (Console de Testes do
  Faiston One, Dashboard-Faiston/Faiston Ops, Sistema-Giro, painéis). Não alterar
  esses sistemas a partir daqui.
- O Console de Testes é usado pelo pessoal da LPD, que vê os ajustes por ele.
  Nada no hub pode exigir mudança nele nesta fase.

## Comunicação
- Português do Brasil, direto e informal. Termos técnicos em inglês com
  contexto (ex.: "rate limit (limite de tentativas)").
- Commits em português, no imperativo e curtos, como no repo
  `Testes-Faiston-One` (ex.: "Adiciona bloqueio após 5 falhas de login").

## Stack
Python 3.12 · FastAPI · Jinja2 + HTMX · Tailwind compilado · SQLAlchemy 2.0 ·
Alembic · PostgreSQL · argon2-cffi · pyotp · cryptography · pytest · Railway.

## Regras que não se negociam
- Branch: nunca commitar direto na `main`. Trabalhar em branch e abrir PR.
- Toda mudança de schema é uma migração Alembic. Nada de `create_all` fora dos testes.
- Toda rota nova nasce protegida (`require_user` / `require_project` /
  `require_admin`). Rota pública só com justificativa no PR.
- Todo POST/PUT/PATCH/DELETE valida CSRF.
- Nunca logar ou exibir senha, token, segredo TOTP ou código de recuperação. No
  banco, token é sempre hash.
- Nenhum segredo no código ou no repo. Config só via env (`app/config.py`).
- Sem script/estilo de CDN (CSP estrita). Assets em `static/`.
- Evento de autenticação ou permissão → `audit.log(...)`.
- Dados pessoais: coletar o mínimo (LGPD).
- Antes de dizer que terminou: `ruff check .`, `pytest`, `bandit -r app -q`.

## Rodando local
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # preencher SECRET_KEY e MFA_ENCRYPTION_KEYS
alembic upgrade head
python -m cli create-admin --email voce@faiston.com --nome "Seu Nome"
uvicorn app.main:app --reload
```

## Identidade visual
Paleta e fontes da Faiston (ver §7 da especificação). Rodapé com razão social,
CNPJ e site.
