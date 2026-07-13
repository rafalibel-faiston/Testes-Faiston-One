# Fluxo C — Console de Teste (Faiston)

Sisteminha pra acompanhar a execução dos testes do Fluxo C (Despacho NEXO) —
só as frentes que a Faiston precisa validar como cliente final: **Operador (web)**
e **App do técnico**. Backend fica fora (responsabilidade do time de LP/NEXO).

Cada caso de teste tem status (Não testado / Aprovado / Reprovado / Bloqueado / N/A),
histórico de observações (com autor) e **upload de prints de tela** (ficam salvos no
Postgres, então qualquer um do time com o link vê o andamento e as evidências — sem
precisar de login).

## Stack

- **Backend**: FastAPI + SQLAlchemy
- **Banco**: PostgreSQL (Railway) — localmente cai pra SQLite automaticamente se
  `DATABASE_URL` não estiver definida
- **Frontend**: HTML/CSS/JS puro, servido pelo próprio FastAPI (`/static`)
- **Prints**: guardados como bytes direto no Postgres (coluna `bytea`) — sem
  depender de S3/Cloudinary. Se o volume de imagens crescer muito no futuro, migrar
  pra um object storage é o próximo passo natural, mas pra uso interno de QA isso
  não deve ser necessário.

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abre em `http://localhost:8000`. Sem configurar nada, usa um arquivo `fluxoc.db`
(SQLite) na pasta do projeto — apaga esse arquivo se quiser resetar os dados locais.

## Deploy no Railway

1. Suba este repositório pro GitHub (`git init` já foi feito aqui — só criar o repo
   vazio no GitHub e rodar `git remote add origin <url> && git push -u origin main`).
2. No Railway: **New Project → Deploy from GitHub repo** e escolha este repositório.
3. No mesmo projeto Railway, clique em **+ New → Database → Add PostgreSQL**. Depois
   vá no serviço web → aba **Variables** → **New Variable** → cole a referência
   `${{Postgres.DATABASE_URL}}` (o Railway não injeta isso automaticamente entre
   serviços — precisa adicionar essa referência na mão uma vez).
4. Confirma que o Railway detectou o `Procfile` / `railway.json` (build via Nixpacks,
   start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`). Se ele pedir,
   defina manualmente o start command com esse mesmo valor.
5. Deploy. Na primeira subida, o app cria as tabelas e semeia os 51 casos de teste
   automaticamente (idempotente — não duplica se você reiniciar o serviço).
6. Pega o domínio público que o Railway gera (Settings → Networking → Generate
   Domain) e manda pra Bruna, Rodrigo e Luís — sem senha, é só abrir o link.

## Estrutura

```
app/
  main.py            # app FastAPI, monta static/, cria tabelas, semeia dados
  database.py         # engine/session — lê DATABASE_URL (Postgres) ou usa SQLite local
  models.py            # TestCase, Observation, Screenshot
  schemas.py            # Pydantic
  seed_data.py           # os 51 casos de teste (fonte: dashboard LP 02/07) + migração de observações antigas
  routers/cases.py        # API: listar/atualizar casos, observações, upload/download/remover print, resumo
static/
  index.html, style.css, app.js   # frontend
```

## API

- `GET  /api/cases` — lista todos os casos com observações e prints
- `PATCH /api/cases/{code}` — atualiza status / testado_por (não mexe mais em observação — ver abaixo)
- `POST /api/cases/{code}/observacoes` — adiciona uma nova observação ao histórico do caso
  (body: `{"texto": "...", "autor": "..."}`). Cada nota guarda seu próprio autor — se outra
  pessoa comentar depois, o nome dela aparece só naquela nota, sem apagar as anteriores.
- `DELETE /api/observacoes/{id}` — remove uma observação específica
- `POST /api/cases/{code}/screenshots` — upload de print (multipart, campo `file`)
- `GET  /api/screenshots/{id}` — baixa/exibe o print
- `DELETE /api/screenshots/{id}` — remove um print
- `GET  /api/summary` — contagem por status e % executado

### Observações com autor por nota

Antes, `TestCase.observacao` era um campo único — se duas pessoas testassem o mesmo
caso, a segunda escrita apagava a primeira e não dava pra saber quem escreveu o quê.
Agora cada observação vira uma linha em `Observation` (autor + texto + data), e o
histórico completo aparece no card, com o nome de quem escreveu cada uma. Na primeira
subida depois desse deploy, o app migra automaticamente qualquer observação antiga
(campo único) pro novo formato, atribuindo o autor a quem estava marcado em "testado
por" — migração idempotente, não duplica em reinicializações seguintes.

## Ticket filho — pendente

O caso `FC-TKFILHO-01` (Grupo D) está como placeholder — falta descrever o gatilho
e o comportamento esperado antes de testar. Edite direto na tela (agora dá pra
registrar isso no histórico de observações) ou me avise que eu atualizo o `seed_data.py`.
