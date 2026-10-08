# Faiston Hub — Especificação (Fase 1)

Portal central da área de Engenharia de IA da Faiston. Reúne num lugar só os
projetos do time (Faiston One, RH, Faiston Ops, Giro, painéis gerenciais) e os
serviços de cada um, com **login próprio (e-mail + senha + MFA)** e controle de
acesso por projeto.

> Documento-fonte para o repositório novo `faiston-hub`. Copiar para
> `docs/ESPECIFICACAO.md` no repo novo e manter atualizado lá.

---

## 1. Escopo da Fase 1

**Entra:**
- Login com e-mail + senha, **sem cadastro aberto** — só por convite.
- **Primeiro acesso autenticado:** convite de uso único → define senha →
  cadastra MFA (TOTP: Microsoft Authenticator / Google Authenticator) → recebe
  códigos de recuperação.
- MFA pedido de novo em **todo dispositivo/navegador novo**, com opção de
  "confiar neste dispositivo" por 30 dias (`MFA_TRUST_DAYS`, `0` = pedir sempre).
  Admin sempre precisa de MFA, sem dispositivo confiável.
- Catálogo: **Projetos → Serviços** (cada serviço é um link para um sistema que
  já existe, com status de saúde).
- Permissão por projeto (RBAC): quem não é membro do projeto nem vê o projeto.
- Painel de administração: usuários, convites, projetos, serviços, membros.
- Trilha de auditoria (audit log) de tudo que envolve autenticação e permissão.

**Não entra agora (fases seguintes):**
- Login Microsoft / Entra ID (SSO).
- Os sistemas existentes (Console de Testes, Giro, Dashboard-Faiston) passarem a
  exigir o login do hub — **nesta fase o hub só aponta para eles; nenhum código
  deles muda.**
- MCP Gateway unificado.
- "Esqueci minha senha" self-service por e-mail (na Fase 1 o reset é feito pelo
  admin, que gera um link de uso único).

### Regra de ouro: não quebrar o Console de Testes

O Console de Testes (repo `Testes-Faiston-One`) é usado hoje pelo pessoal da
**LPD**, que acompanha por ele os ajustes e as validações. Ele continua
exatamente como está: mesmo link, sem login, mesmo deploy. O hub só cadastra o
link dele no catálogo. Quando chegar a fase de colocar o Console atrás do login
do hub, os usuários da LPD vão precisar de um papel de **parceiro externo**
(só leitura + observações, só no projeto Faiston One). Isso já está previsto
no modelo de dados (ver §4), mas não é ativado agora.

---

## 2. Stack

| Camada | Escolha | Por quê |
|---|---|---|
| Linguagem | Python 3.12 | padrão do time |
| Web | FastAPI + Jinja2 + HTMX | renderizado no servidor: sessão em cookie HttpOnly, sem token no navegador |
| CSS | Tailwind **compilado** (CLI standalone), arquivo `.css` versionado | o Tailwind via CDN quebra a CSP estrita |
| JS | HTMX servido localmente (`static/vendor/htmx.min.js`) | sem CDN de script, CSP `script-src 'self'` |
| ORM / migrações | SQLAlchemy 2.0 + **Alembic** | nada de `create_all` em produção |
| Banco | PostgreSQL (Neon ou Railway), `sslmode=require` | |
| Driver | `psycopg[binary]` 3 | |
| Senhas | `argon2-cffi` (Argon2id) | recomendação OWASP |
| MFA | `pyotp` + `segno` (QR em SVG inline) | |
| Criptografia em repouso | `cryptography` (Fernet / MultiFernet) | segredo TOTP cifrado no banco |
| Config | `pydantic-settings` | valida env vars no boot e falha cedo |
| Testes | `pytest`, `httpx` | |
| Qualidade/segurança | `ruff`, `bandit`, `pip-audit`, `gitleaks`, Dependabot | rodam no CI |
| Deploy | Railway (deploy só da `main`) | |

---

## 3. Estrutura do repositório

```
faiston-hub/
  app/
    main.py                 # cria o app, middlewares, routers, desliga /docs em produção
    config.py               # Settings (pydantic-settings)
    db.py                   # engine, SessionLocal, get_db
    models.py               # User, Session, Invite, Project, Service, Membership, AuditLog, ...
    security/
      passwords.py          # hash/verify Argon2id, política de senha, lista de senhas comuns
      sessions.py           # cria/valida/rotaciona/revoga sessão; cookie __Host-
      mfa.py                # TOTP, anti-replay, códigos de recuperação, dispositivo confiável
      csrf.py               # token sincronizador por sessão
      ratelimit.py          # limite por IP e por conta, persistido no Postgres
      headers.py            # middleware de headers de segurança (CSP, HSTS, ...)
      crypto.py             # MultiFernet a partir de MFA_ENCRYPTION_KEYS
      authz.py              # dependências: require_user, require_admin, require_project(role)
    audit.py                # registra eventos no audit_log
    routers/
      auth.py               # /login, /login/mfa, /logout, /convite/{token}, /mfa/cadastro
      account.py            # /conta: trocar senha, sessões ativas, novos códigos de recuperação
      catalog.py            # /, /projetos/{slug}
      admin.py              # /admin/...
      health.py             # /health (sem auth, sem dados)
    services/health_check.py  # checa /health de cada serviço cadastrado (timeout curto)
    templates/              # Jinja2 (autoescape ligado)
    static/
      css/app.css           # Tailwind compilado
      vendor/htmx.min.js
      img/logo-faiston.svg
  alembic/ + alembic.ini
  cli.py                    # python -m cli create-admin  (bootstrap do primeiro admin)
  tailwind.config.js, styles/input.css
  tests/
  .github/workflows/ci.yml
  .github/dependabot.yml
  .pre-commit-config.yaml   # ruff + gitleaks
  .env.example
  requirements.txt / requirements-dev.txt (versões fixadas)
  Procfile / railway.json
  CLAUDE.md
  docs/ESPECIFICACAO.md
  SECURITY.md
```

---

## 4. Modelo de dados

```
users
  id (uuid) · email (único, minúsculo) · nome · password_hash (null até aceitar convite)
  is_admin · is_active · mfa_secret_enc (bytea, cifrado) · mfa_enabled_at
  mfa_last_timestep (anti-replay) · failed_logins · locked_until
  password_changed_at · created_at · last_login_at

sessions                       # sessão no servidor, nunca JWT
  id · user_id · token_hash (sha256, único) · csrf_token
  mfa_ok (bool) · created_at · last_seen_at · expires_at (absoluto)
  ip · user_agent · revoked_at

trusted_devices                # "confiar neste dispositivo"
  id · user_id · token_hash · created_at · expires_at · user_agent · revoked_at

recovery_codes
  id · user_id · code_hash (Argon2) · used_at

invites                        # também usado para reset de senha feito pelo admin
  id · email · token_hash · kind ('convite' | 'reset') · created_by
  expires_at (48h) · used_at · project_roles (json: [{project_id, role}])

projects
  id · slug · nome · descricao · icone · cor · ordem · status ('ativo' | 'em_construcao' | 'arquivado')

services                       # o que abre dentro de cada projeto
  id · project_id · nome · descricao · url · health_url (opcional)
  min_role ('leitor' | 'membro' | 'admin') · ordem · ativo
  last_status ('ok' | 'fora' | 'desconhecido') · last_checked_at

memberships
  user_id · project_id · role ('leitor' | 'membro' | 'admin' | 'parceiro')   # PK composta

login_attempts                 # rate limit que sobrevive a restart
  id · key ('ip:1.2.3.4' | 'user:<id>') · created_at

audit_log                      # só INSERT; a aplicação nunca faz UPDATE/DELETE
  id · at · actor_user_id · event · target · ip · user_agent · details (json, sem segredo)
```

Seed inicial (migração de dados, idempotente) dos projetos e serviços:

| Projeto | Serviço | URL |
|---|---|---|
| Faiston One | Console de Testes (Fluxo C) | URL do Railway do Console |
| Faiston One | Pauta da reunião | `<console>/relatorio` |
| RH — Automação | (em construção) | — |
| Faiston Ops | Dashboard | URL do `Dashboard-Faiston` |
| Giro | Sistema Giro | URL do `Sistema-Giro` |
| Painéis gerenciais | (a definir) | — |

As URLs vêm de variáveis/seed editáveis no admin, **nunca hardcoded no código**.
O Console já tem `GET /health`, que serve de `health_url` dele.

---

## 5. Fluxos de autenticação

### 5.1 Bootstrap
`python -m cli create-admin --email x@faiston.com --nome "..."` gera um
**convite de admin** e imprime o link no terminal. Não existe tela de cadastro
público nem admin padrão com senha fixa.

### 5.2 Convite → primeiro acesso
1. O admin cria o convite (e-mail + projetos/papéis). O sistema gera um token de
   32 bytes (`secrets.token_urlsafe`), grava **só o hash** e mostra o link uma
   única vez para o admin copiar e mandar pelo Teams. (Envio por e-mail via SMTP
   fica para quando houver provedor; deixar a interface `EmailSender` pronta,
   com implementação "console" em dev.)
2. `/convite/{token}`: valida o token (existe, não expirou, não foi usado) e a
   pessoa define a senha (§6.1).
3. Na sequência, obrigatoriamente, vem o cadastro do MFA: o QR é mostrado em SVG
   e só fica ativo depois que a pessoa digita um código válido.
4. São mostrados **10 códigos de recuperação**, uma única vez, com botão de
   baixar `.txt`.
5. O convite é marcado como usado, a sessão é criada já com `mfa_ok=true` e o
   evento vai para o audit log.

### 5.3 Login
1. `/login`: e-mail + senha. A resposta é **sempre a mesma** para usuário
   inexistente, senha errada ou conta inativa ("E-mail ou senha inválidos"). Para
   usuário inexistente também roda um verify contra um hash fictício, para o
   tempo de resposta ser igual (sem enumeração por timing).
2. Senha ok → cria uma sessão **pré-MFA** (`mfa_ok=false`), que só dá acesso a
   `/login/mfa`.
3. Se existe cookie de dispositivo confiável válido para esse usuário (e ele não
   é admin), pula o MFA.
4. `/login/mfa`: código TOTP (janela ±1 passo; rejeita um `timestep` já usado) ou
   código de recuperação (consome). Ok → **rotaciona a sessão** (token novo),
   `mfa_ok=true`, e opcionalmente cria o dispositivo confiável.
5. Tudo vai para o audit log: `login_ok`, `login_falha`, `mfa_ok`, `mfa_falha`,
   `conta_bloqueada`, `recovery_code_usado`.

### 5.4 Bloqueio e rate limit
- Por **conta**: 5 falhas seguidas → bloqueia por 15 min, dobrando a cada novo
  bloqueio (teto de 24h). Zera no login completo.
- Por **IP**: no máximo 20 tentativas de login/MFA em 10 min.
- Persistido no Postgres (`login_attempts`), para não resetar quando o Railway
  reinicia.
- O IP real vem do `X-Forwarded-For` **somente** porque o uvicorn sobe com
  `--proxy-headers --forwarded-allow-ips` restrito ao proxy do Railway.
- Bloqueio de conta envia evento ao audit log e aparece no admin.

### 5.5 Sessão
- Cookie `__Host-fh_session`: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, sem
  `Domain`.
- O valor é um token opaco aleatório; no banco fica só o `sha256`.
- **Timeout por inatividade de 30 min** e **absoluto de 12h**.
- Rotação no login, no MFA e na troca de senha. A troca de senha **derruba todas
  as outras sessões**.
- Em `/conta`: lista de sessões ativas, com "encerrar" individual e "sair de
  todos os dispositivos".
- Logout: revoga no servidor e apaga o cookie.

### 5.6 Reset de senha (Fase 1)
O admin gera um link `kind='reset'`, de uso único e com validade de 1h. A pessoa
define a senha nova, todas as sessões dela são derrubadas e o **MFA continua
valendo**. Se ela perdeu o celular e os códigos de recuperação, o admin pode
"resetar MFA", o que obriga um novo cadastro no próximo login. Tudo auditado.

---

## 6. Checklist de segurança (critério de aceite)

Base: OWASP ASVS nível 2 + NIST 800-63B, mais a LGPD.

### 6.1 Senhas
- [ ] Argon2id com parâmetros OWASP (`time_cost=3`, `memory_cost=64MiB`, `parallelism=4`), `needs_rehash` no login.
- [ ] Mínimo de 12 caracteres, máximo de 128, aceita espaço e unicode, **sem** regra de "maiúscula + símbolo" (NIST).
- [ ] Bloqueia senhas comuns (lista local com top 10k) e senha que contenha o e-mail ou o nome.
- [ ] Nunca logar senha, token, segredo TOTP ou código.

### 6.2 MFA
- [ ] Segredo TOTP cifrado com `MultiFernet` (`MFA_ENCRYPTION_KEYS` aceita várias chaves, para rotação).
- [ ] Anti-replay via `mfa_last_timestep`.
- [ ] Códigos de recuperação com hash e uso único; gerar novos invalida os antigos.
- [ ] O cookie de dispositivo confiável é separado do cookie de sessão, guarda só o hash no banco e é revogável.

### 6.3 Sessão e CSRF
- [ ] Tudo do §5.5.
- [ ] Token CSRF por sessão em **todo** POST/PUT/PATCH/DELETE (campo hidden no form + header `X-CSRF-Token` via HTMX `hx-headers`); comparado com `secrets.compare_digest`.
- [ ] Nenhuma ação que altere estado via GET.

### 6.4 Autorização
- [ ] Negar por padrão: toda rota, exceto `/login`, `/convite`, `/health` e `/static`, exige sessão com `mfa_ok`.
- [ ] `require_project(slug, min_role)` checa a membership no servidor: quem não é membro recebe **404** (não 403, para não revelar que o projeto existe).
- [ ] Rotas `/admin/*` exigem `is_admin` e, em ações sensíveis (criar admin, resetar MFA), **reautenticação** (senha + TOTP nos últimos 5 min).
- [ ] Ninguém consegue remover o último admin ativo.

### 6.5 Headers e transporte
- [ ] `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'; object-src 'none'`. Fontes (Roboto/Roboto Slab) **auto-hospedadas** em `static/fonts`.
- [ ] `Strict-Transport-Security: max-age=63072000; includeSubDomains`.
- [ ] `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` restritiva, `Cross-Origin-Opener-Policy: same-origin`.
- [ ] `Cache-Control: no-store` nas páginas autenticadas.
- [ ] `TrustedHostMiddleware` com `ALLOWED_HOSTS`; redirecionar HTTP→HTTPS em produção.
- [ ] Links de serviços externos com `rel="noopener noreferrer"`.

### 6.6 Aplicação
- [ ] `/docs`, `/redoc` e `/openapi.json` desligados quando `APP_ENV=production`.
- [ ] Handler de erro genérico: sem stack trace para o usuário; log com `request_id`.
- [ ] Jinja com autoescape; nada de `|safe` em dado de usuário.
- [ ] Só ORM / SQL parametrizado; nada de f-string em SQL.
- [ ] Validação com Pydantic em todo input; URL de serviço só `https://` (com `http://localhost` permitido só em dev).
- [ ] Health check de serviços: timeout de 3s, sem seguir redirect para host diferente, só para URLs cadastradas pelo admin (evita SSRF).
- [ ] Limite de tamanho do corpo das requisições.

### 6.7 Segredos, dependências e repositório
- [ ] **Repositório privado.**
- [ ] `.env` no `.gitignore`; `.env.example` sem valor real; `gitleaks` no pre-commit e no CI.
- [ ] O app falha no boot se faltar `SECRET_KEY`/`MFA_ENCRYPTION_KEYS`/`DATABASE_URL` em produção.
- [ ] Versões fixadas no `requirements.txt`; Dependabot semanal; `pip-audit` e `bandit` no CI.
- [ ] Proteção da `main`: só por PR, CI verde obrigatório, sem force-push.

### 6.8 Auditoria e LGPD
- [ ] O `audit_log` registra: login ok/falha, MFA ok/falha, bloqueio, logout, troca de senha, reset, convite criado/usado, papel alterado, usuário desativado, serviço/projeto alterado.
- [ ] O `audit_log` é só INSERT: a aplicação não expõe edição e, se possível, o usuário do banco da app não tem `UPDATE`/`DELETE` nessa tabela.
- [ ] Coleta mínima: nome, e-mail corporativo, IP e user-agent (para segurança). Nada além disso.
- [ ] Retenção: `login_attempts` 30 dias; `audit_log` 1 ano (job de limpeza); sessões expiradas apagadas diariamente.
- [ ] Desativar usuário revoga todas as sessões e dispositivos na hora.
- [ ] `SECURITY.md` explicando como reportar vulnerabilidade internamente.

### 6.9 Testes obrigatórios (pytest)
- Login com senha errada, com usuário inexistente e com conta inativa dá a mesma resposta.
- Bloqueio após 5 falhas e desbloqueio depois do tempo.
- Sessão pré-MFA não acessa o catálogo.
- TOTP reutilizado é rejeitado; código de recuperação só funciona uma vez.
- Convite expirado ou usado é rejeitado; convite só funciona uma vez.
- POST sem CSRF dá 403.
- Usuário sem membership recebe 404 no projeto; não-admin recebe 404/403 no `/admin`.
- Sessão expira por inatividade e pelo tempo absoluto.
- Troca de senha derruba as outras sessões.
- Headers de segurança presentes em toda resposta.
- `/docs` responde 404 em produção.

---

## 7. Telas

Visual: identidade Faiston (paleta abaixo, Roboto/Roboto Slab, logo no topo,
grade sutil de fundo no login). Rodapé com "IS Tech Serviços, Soluções e
Gerenciamento Ltda. · CNPJ 04.416.977/0001-45 · faiston.com".

```
--f-blue-dark:#2226c0  --f-blue:#0054ec  --f-cyan:#00fafb
--f-purple:#960a9c     --f-magenta:#fd11a4  --f-pink:#fd5665
--bg:#f6f7fb --surface:#fff --border:#e6e9f4 --text:#151720 --muted:#7a839c
gradiente marca: linear-gradient(135deg,#2226c0 0%,#960a9c 52%,#fd11a4 100%)
```
(Fonte completa: `app/assets/faiston-light.css` no repo `Testes-Faiston-One`.)

1. **Login**, depois **MFA** (campo de 6 dígitos, link "usar código de recuperação", checkbox "confiar neste dispositivo por 30 dias").
2. **Primeiro acesso**: definir senha (com medidor de força), depois QR do MFA com confirmação, depois os códigos de recuperação.
3. **Início**: cards dos projetos de que a pessoa é membro (ícone, nome, status, quantidade de serviços).
4. **Projeto**: lista de serviços (nome, descrição, bolinha de status ok/fora, botão "Abrir", que abre em nova aba).
5. **Minha conta**: trocar senha, sessões ativas, gerar novos códigos de recuperação.
6. **Admin**: usuários (convidar, desativar, resetar senha, resetar MFA, papéis por projeto), projetos, serviços e audit log (com filtro por usuário/evento/data).

---

## 8. Variáveis de ambiente

| Variável | Exemplo / como gerar |
|---|---|
| `APP_ENV` | `production` / `development` |
| `DATABASE_URL` | `postgresql+psycopg://...?sslmode=require` |
| `SECRET_KEY` | `python -c "import secrets;print(secrets.token_urlsafe(64))"` |
| `MFA_ENCRYPTION_KEYS` | `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` (várias, separadas por vírgula; a primeira cifra) |
| `ALLOWED_HOSTS` | `hub.up.railway.app` |
| `PUBLIC_BASE_URL` | `https://hub.up.railway.app` (monta os links de convite) |
| `SESSION_IDLE_MINUTES` | `30` |
| `SESSION_ABSOLUTE_HOURS` | `12` |
| `MFA_TRUST_DAYS` | `30` (`0` = MFA em todo login) |
| `MFA_ISSUER` | `Faiston Hub` |

Start command no Railway:
`alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`
(O Railway só expõe o serviço pelo proxy dele, então `*` aqui é aceitável. Se
algum dia o serviço ficar exposto direto, restringir.)

---

## 9. Ordem de implementação (cada item = 1 PR pequeno)

1. Esqueleto: FastAPI, config, db, Alembic, `/health`, CI (ruff, pytest, bandit, pip-audit, gitleaks), pre-commit, Dependabot.
2. Middleware de headers de segurança, layout base Jinja + Tailwind compilado + HTMX local + fontes locais.
3. Modelos + migração inicial + `cli create-admin`.
4. Senhas (Argon2id + política) e sessões (cookie, expiração, rotação) + CSRF.
5. Convite → definir senha → cadastro MFA → códigos de recuperação.
6. Login + MFA + dispositivo confiável + rate limit/bloqueio.
7. Audit log em todos os eventos acima.
8. Catálogo (projetos/serviços/memberships) + seed + `require_project`.
9. Admin (usuários, convites, papéis, projetos, serviços, audit log) + reautenticação.
10. Minha conta (troca de senha, sessões ativas, novos códigos).
11. Health check dos serviços (botão manual + job periódico leve).
12. Deploy no Railway + revisão final do checklist §6 (rodar `/security-review`).

Cada PR só entra com os testes da parte dele passando.
