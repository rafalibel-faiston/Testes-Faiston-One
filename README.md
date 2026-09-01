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
  models.py            # TestCase, Observation (+ ObservationRevision, a trilha), Screenshot
  schemas.py            # Pydantic
  seed_data.py           # os 51 casos de teste (fonte: dashboard LP 02/07) + migração de observações antigas
  routers/cases.py        # API: listar/atualizar casos, observações, upload/download/remover print, resumo
  routers/ativos.py        # API: ajustes do módulo Gestão de Ativos (v2 e as próximas levas)
  routers/relatorio.py      # página /relatorio — a pauta da reunião semanal
  relatorio.py               # monta o HTML da pauta (usado pela rota e pelo script)
  assets/                     # CSS e logo da marca Faiston embutidos na pauta
  mcp_server.py                # servidor MCP (ver seção "Conectar no Claude/Cowork" abaixo)
static/
  index.html, style.css, app.js   # frontend
tools/
  relatorio_reuniao.py            # gera a pauta como arquivo .html
```

## Conectar no Claude/Cowork via MCP

O app expõe um servidor MCP em `/mcp` com um subconjunto das operações (listar
casos, ver detalhe, atualizar status, adicionar observação, resumo de execução
e o quadro de tarefas), pra dar pra pedir essas coisas em linguagem natural
direto do Claude, sem abrir a tela.

O servidor MCP faz um mini fluxo OAuth: ao "Vincular" o conector, o Claude
abre uma telinha (`/mcp-login`) pedindo o `MCP_TOKEN` como senha — só depois
disso ele ganha acesso. Isso é necessário porque a tela de conectores do
Claude/Cowork sempre tenta vincular via OAuth (não aceita um token solto na
URL).

### 1. Configurar as variáveis

- **`MCP_TOKEN`** — a senha pedida na telinha de login.
  - Local: defina no seu `.env` (gere um valor com
    `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`).
  - Railway: serviço web → aba **Variables** → **New Variable** → `MCP_TOKEN`.
- **`PUBLIC_BASE_URL`** — a URL pública do app, sem barra no final (ex.:
  `https://web-production-xxxx.up.railway.app`). Necessária pro OAuth saber
  pra onde redirecionar; sem ela, o vínculo falha em produção.
  - Railway: mesma aba **Variables** → `PUBLIC_BASE_URL` com o domínio do
    serviço (Settings → Networking → o domínio gerado).

Depois de configurar as duas, redeploy o serviço.

### 2. Adicionar o conector

Com o app rodando (local ou no domínio do Railway), a URL do servidor MCP é
`https://<seu-dominio>/mcp`.

- **Claude.ai / Claude Cowork (Settings → Conectores → Adicionar conector
  personalizado)**: cole `https://<seu-dominio>/mcp` no campo de URL, deixe os
  campos de OAuth Client ID/Secret em branco, e clique **Adicionar**. Na tela
  seguinte ("Vincular"), o Claude abre a telinha de login — digite o
  `MCP_TOKEN` e pronto.
- **Claude Code (CLI)**, alternativa sem OAuth (usa header direto):
  ```bash
  claude mcp add --transport http fluxo-c https://<seu-dominio>/mcp \
    --header "Authorization: Bearer <MCP_TOKEN>"
  ```

Depois disso as ferramentas (`listar_casos`, `obter_caso`,
`atualizar_status_caso`, `adicionar_observacao`, `atualizar_observacao`, `resumo_execucao`,
`listar_tarefas`, `criar_tarefa`, `listar_ajustes_ativos`, `criar_ajuste_ativos`)
ficam disponíveis pra pedir direto na
conversa, tipo "marca o FC-12 como aprovado" ou "lista os casos reprovados do
Grupo B".

Detalhe técnico: o "login" fica guardado em memória do processo — se o
serviço reiniciar no Railway, o conector pode precisar ser vinculado de novo
(o token de acesso emitido dura 30 dias, sem renovação automática).

## Pauta da reunião semanal (`/relatorio`)

Toda semana a conversa com o time de dev começa pela mesma pergunta — *o que
ainda não está aprovado?*. Em vez de garimpar isso na tela caso a caso, o app
serve a resposta pronta em **`/relatorio`**: uma página só, no padrão visual da
Faiston, com tudo que está em aberto, na ordem em que interessa discutir:

1. **Pontos para a reunião** — os que ainda não foram resolvidos, separados
   entre *aguardando retorno* (já cobrados da outra ponta) e *a levantar*.
2. **Reprovados e bloqueados** — tudo que falhou numa lista só, caso de teste
   solto e estágio de situação lado a lado, com o problema encontrado e
   **todas** as observações anotadas. Num estágio reprovado cada observação
   costuma ser um ajuste diferente sendo pedido, não variação do mesmo
   comentário — mostrar só a última perdia o resto da conversa.
3. **Situações — onde cada cenário parou** — os próximos estágios da fila de
   cada situação (no máximo três; a lista inteira viraria parede de texto). O
   que está reprovado já apareceu no item 2.
4. **Ajustes da Gestão de Ativos** — os que ainda não foram validados, no
   formato *hoje é assim / deveria ser assim*, agrupados por leva.
5. **Testes ainda não executados** — a fila, resumida por estágio.

A pauta cobre **os três fluxos de uma vez**: a reunião é uma só, e um estágio
reprovado no Fluxo B precisa da mesma conversa que um do Fluxo C. Quando há
item de mais de um fluxo, cada linha ganha a etiqueta do fluxo. Pra ver um
fluxo isolado, `/relatorio?fluxo=C`.

No topo ficam os números da semana em aberto. O resto é lista: cada seção é
uma sequência de linhas pra ler de cima pra baixo, sem gráfico nenhum — numa
reunião projetada o que conta é conseguir ler o item e decidir.

O botão **Pauta da reunião**, ao lado do *Exportar Excel*, abre a página do
fluxo aberto numa aba nova — dá pra projetar direto ou imprimir em PDF (o CSS
já tem regras de impressão).

### Anotar o retorno do time

Cada **ponto** e cada **ajuste** da pauta tem um campo *Retorno do time*: uma
data (o prazo que eles prometeram) e um texto livre (o que ficou combinado).
Dá pra preencher durante a própria reunião, direto na página — o botão salva na
API na hora, e `Ctrl+Enter` no texto salva sem tirar a mão do teclado.

O retorno fica guardado no ponto/ajuste, então também aparece no painel de
Pontos e no card do ajuste na tela normal do app; no ajuste dá pra editar
também pelo modal de edição (✎).

Num arquivo `.html` gerado pelo script não há servidor pra receber, então lá o
retorno aparece só como leitura — o que já foi anotado continua visível.

A página é montada na hora, a partir do banco: não tem cache e não precisa de
geração prévia. Como todo o resto do app, é aberta — quem tem o link vê.

Pra ter a mesma pauta como **arquivo** (mandar por e-mail, anexar na ata,
guardar a foto da semana):

```bash
python3 tools/relatorio_reuniao.py --base-url https://SEU-APP.up.railway.app
# gera relatorio-reuniao.html na pasta atual

# guardando também os JSONs que originaram a pauta
python3 tools/relatorio_reuniao.py --base-url https://SEU-APP.up.railway.app --dump-dir ./dump

# e, depois, remontar a mesma pauta sem rede
python3 tools/relatorio_reuniao.py --json-dir ./dump --out pauta-11-08.html
```

O HTML é autocontido (CSS e logo embutidos, sem CDN) — abre offline e pode ser
anexado num e-mail sem quebrar.

## Colar print (Ctrl+V)

Print é a evidência mais rápida de anexar e a mais difícil de contestar, então dá
pra colar imagem direto da área de transferência em três lugares: **caso de
teste** e **estágio de situação** (Dispatcher) e **ajuste** (Gestão de Ativos).

Como a tela mostra vários cards ao mesmo tempo, colar precisa de um destino:
clique no card onde a imagem deve entrar — ele ganha uma borda azul e a caixinha
de anexo passa a dizer *Ctrl+V pra colar* — e cole. Colar sem ter escolhido um
card mostra um aviso em vez de anexar em algum lugar aleatório. Arrastar o
arquivo pra cima da caixinha ou clicar nela pra escolher no disco continua
funcionando como antes.

Com um modal aberto o Ctrl+V volta a ser colagem de texto nos campos dele, sem
anexar imagem.

## Gestão de Ativos — ajustes (v2 e as próximas)

O módulo **Gestão de Ativos** do Faiston One já está no ar; a aba *Gestão de
Ativos* aqui no console é o backlog dos ajustes pedidos em cima dele. A aba
aparece pros dois perfis: a Faiston levanta os ajustes, a LP é quem desenvolve
— sem ver a lista, a LP dependia de alguém repassar item por item. (Agenda e
Todo continuam só da Faiston: são planejamento interno do time.) Cada ajuste é
um item no formato que o time já usa:

- **como está hoje** (`atual`) × **como deve ser** (`esperado`);
- classificado como **Bug** (está quebrado) ou **Melhoria** (funciona, mas
  precisa evoluir);
- com área/tela, prioridade, responsável e situação (Levantado → Em análise →
  Em desenvolvimento → Entregue → Validado, ou Descartado).

A lista sai **ordenada por prioridade** (Alta → Média → Baixa → A definir), com o
número do item como desempate — tela, API e MCP usam o mesmo critério. O número
não muda de lugar junto: ele é a identidade do ajuste ("o ajuste 4"), não a
posição na fila.

Os 7 ajustes levantados pra **v2** vêm semeados (`seed_ativos_ajustes` em
`app/seed_data.py`) — idempotente: redeploy não duplica nem sobrescreve o que o
time já editou ou moveu de situação na tela.

**Próximas levas:** o campo `versao` agrupa a rodada de ajustes e não tem nada
chumbado no código. Ao cadastrar um ajuste digitando uma versão que ainda não
existe (`v3`, `v4`…), a aba dessa versão aparece sozinha na tela, com o histórico
das anteriores intacto ao lado. Dá pra cadastrar pela tela (**Novo ajuste**) ou
pelo Claude, via a tool MCP `criar_ajuste_ativos`.

### Prints no ajuste

Cada ajuste aceita imagens — normalmente o print da tela do Faiston One mostrando
o comportamento atual (ver **Colar print (Ctrl+V)** acima). Ficam salvas no
próprio banco e somem junto se o ajuste for excluído.

### API

- `GET  /api/ativos/ajustes` — lista os ajustes com seus prints (filtros opcionais: `versao`, `tipo`, `status`)
- `POST /api/ativos/ajustes` — cadastra um ajuste (sem `numero`, ele entra na sequência da versão)
- `PATCH /api/ativos/ajustes/{id}` — edita qualquer campo, inclusive mover de versão
- `DELETE /api/ativos/ajustes/{id}` — remove o ajuste (e os prints dele)
- `POST /api/ativos/ajustes/{id}/prints` — anexa um print (multipart, campo `file`; até 8MB, só imagem)
- `GET  /api/ativos/prints/{id}` — exibe o print
- `DELETE /api/ativos/prints/{id}` — remove o print

## API

- `GET  /api/cases` — lista todos os casos com observações e prints
- `PATCH /api/cases/{code}` — atualiza status / testado_por (não mexe mais em observação — ver abaixo)
- `POST /api/cases/{code}/observacoes` — adiciona uma nova observação ao histórico do caso
  (body: `{"texto": "...", "autor": "..."}`). Cada nota guarda seu próprio autor — se outra
  pessoa comentar depois, o nome dela aparece só naquela nota, sem apagar as anteriores.
- `PATCH /api/observacoes/{id}` — atualiza o texto de uma observação
  (body: `{"texto": "...", "autor": "..."}`). O texto anterior não some: vira uma versão
  na trilha da observação — ver abaixo.
- `DELETE /api/observacoes/{id}` — remove uma observação específica (leva a trilha junto)
- `PATCH /api/situacao-observacoes/{id}` — mesma coisa pra observação de estágio de situação
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

### Trilha de atualizações da observação

Uma observação raramente nasce pronta: o ponto é levantado, a LP ajusta, o time
reteste e o que estava escrito deixa de valer. Em vez de apagar e reescrever (ou
empilhar dez notas soltas repetindo o mesmo assunto), dá pra **atualizar a própria
observação**: o texto novo passa a valer e o anterior vira uma versão guardada na
trilha, com quem escreveu e quem substituiu.

Na tela, cada observação tem um lápis (atualizar) e, quando já foi atualizada, um
botão `trilha (N)` que abre as versões anteriores em ordem — a leitura completa de
como o ponto evoluiu. O cabeçalho mostra `atualizada dd/mm hh:mm por Fulano`, e a
pauta da reunião (`/relatorio`) traz a data da atualização junto da observação.

Vale pros dois lugares em que a observação existe: caso de teste (`Observation` →
`ObservationRevision`) e estágio de situação (`SituacaoObservation` →
`SituacaoObservationRevision`). Cada atualização também entra nas Novidades
(trilha de atividades). Apagar a observação apaga a trilha dela junto.

## Técnicos — QA do Track One

Aba **Técnicos** (só perfil Faiston, ao lado de Agenda e Todo) — a base dos técnicos
e líderes de equipe convidados a testar o **Track One** (o app novo que acompanha o
atendimento do chamado até o fechamento da RAT) antes de liberar geral. Ela resolve os
dois pedidos que geraram esse módulo: ter um lugar só pra acompanhar quem já foi
chamado, o que cada um relatou e um jeito rápido de mandar o convite pra cada técnico
sem escrever a mensagem toda vez.

Cada técnico tem:

- **Dados**: nome, telefone (WhatsApp), papel (**Técnico** ou **Líder de equipe**),
  regional e, quando é técnico, o nome do líder direto — pra cruzar rápido quem
  responde a quem.
- **Funil de QA**: `a_contatar` → `convidado` → `instalado` → `em_teste` →
  `concluido` (ou `sem_retorno`, quando ele não respondeu). A data de quando entrou
  em cada estágio-chave (convidado/instalado/concluído) fica registrada.
- **Feedback do teste**: histórico de observações, cada uma marcada como
  **Achou bom**, **Melhoria** ou **Problema** (ou nota geral, sem marcação) — é o
  "o que ele achou bom / o que precisa melhorar / o que deu problema" pedido pra
  acompanhar o piloto.

### Convite pronto (WhatsApp)

O botão **Enviar convite pelo WhatsApp** no card do técnico monta a mensagem certa
pro papel dele (as duas mensagens combinadas com o Rafa — uma pro técnico direto,
outra pro líder avisando que o time dele vai ser chamado), já com o nome
substituído, e abre `wa.me/<telefone>?text=...` com o texto preenchido. Como esse
link só leva texto (não anexa arquivo), o **APK** e o **manual de uso** são enviados
à parte, na própria conversa do WhatsApp — o modal do convite lembra disso e tem um
botão pra copiar o texto caso prefira colar manualmente. Gerar o convite pela
primeira vez já move o técnico de "a contatar" pra "convidado" automaticamente.

Os textos dos dois convites vivem em `app/routers/tecnicos.py`
(`TEMPLATE_TECNICO` / `TEMPLATE_LIDER`) e são espelhados em `static/app.js` — mudar
a mensagem exige editar os dois lugares (mesmo padrão de duplicação que o resto do
app já usa entre a lista de status do Python e a do JS).

### API

- `GET  /api/tecnicos` — lista (filtros opcionais: `status`, `papel`, `regional`, `busca`)
- `GET  /api/tecnicos/resumo` — contagem por status + total de feedback por tipo
- `POST /api/tecnicos` — cadastra (telefone sem DDI de 10/11 dígitos ganha o 55 na frente sozinho)
- `PATCH /api/tecnicos/{id}` — edita dados ou muda o status (grava a data automaticamente)
- `DELETE /api/tecnicos/{id}` — remove
- `GET  /api/tecnicos/{id}/mensagem` — devolve o texto do convite pronto + o link do WhatsApp
- `POST /api/tecnicos/{id}/observacoes` — registra uma nota (`texto`, `autor`, `tipo` opcional: positivo/melhoria/problema)
- `DELETE /api/tecnicos/observacoes/{id}` — remove uma nota

Também dá pra pedir isso direto no Claude via MCP: `listar_tecnicos`, `criar_tecnico`,
`gerar_mensagem_tecnico`, `atualizar_status_tecnico`, `adicionar_observacao_tecnico`
(ver "Conectar no Claude/Cowork via MCP" acima).

## Ticket filho — pendente

O caso `FC-TKFILHO-01` (Grupo D) está como placeholder — falta descrever o gatilho
e o comportamento esperado antes de testar. Edite direto na tela (agora dá pra
registrar isso no histórico de observações) ou me avise que eu atualizo o `seed_data.py`.
