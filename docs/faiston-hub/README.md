# Faiston Hub — passo a passo para a próxima conversa

Esta pasta é o pacote de partida do **Faiston Hub**, que vai morar num
repositório novo. Ela fica na branch `claude/practical-cori-oqtesa` do
`Testes-Faiston-One` só para ser transportada; **nada aqui é carregado pelo
Console de Testes** e a `main` dele não muda.

| Arquivo | Pra quê |
|---|---|
| `ESPECIFICACAO.md` | O que construir: escopo, modelo de dados, fluxos de login/MFA, checklist de segurança, ordem dos PRs |
| `CLAUDE-hub.md` | Regras do projeto que o Claude lê automaticamente no repo novo |
| `README.md` | Este passo a passo |

---

## 1. Criar o repositório (GitHub, ~2 min)

1. github.com → **New repository**.
2. Nome: `faiston-hub`.
3. Visibilidade: **Private** (obrigatório, porque vai ter autenticação e, depois, dados de RH).
4. Marque **Add a README** (assim já nasce com a `main`; o Claude precisa de um commit inicial).
5. **Create repository**.

## 2. Dar acesso ao Claude

- Se o app **Claude** no GitHub foi instalado com "All repositories", não precisa fazer nada.
- Se foi com "Only select repositories": acesse
  https://github.com/apps/claude/installations/select_target, escolha sua conta,
  adicione `faiston-hub` e salve.

## 3. Abrir a sessão nova

1. claude.ai/code → **New session** → escolha o repo `rafalibel-faiston/faiston-hub`.
2. Cole o prompt abaixo inteiro.

```text
Vamos começar o Faiston Hub neste repositório (vazio).

1. Adicione com acesso de leitura o repo rafalibel-faiston/Testes-Faiston-One e
   leia, da branch claude/practical-cori-oqtesa, os arquivos:
   - docs/faiston-hub/ESPECIFICACAO.md
   - docs/faiston-hub/CLAUDE-hub.md
   Copie a ESPECIFICACAO.md para docs/ESPECIFICACAO.md e o CLAUDE-hub.md como CLAUDE.md na
   raiz deste repo. A partir daí, eles são a fonte da verdade.
2. Copie também app/assets/faiston-light.css e app/assets/logo-faiston-full.svg
   daquele repo (só como referência de identidade visual). Não altere nada no
   Testes-Faiston-One: ele está em uso pelo pessoal da LPD.
3. Siga a seção 9 da especificação ("Ordem de implementação"). Faça os passos
   1 a 4 nesta sessão, cada um num commit separado, com testes passando
   (ruff, pytest, bandit) antes de cada commit.
4. Trabalhe só na branch que esta sessão indicar. Não mexa na main.
5. Antes de cadastrar ou integrar qualquer sistema no hub, me peça os repos e
   os arquivos de cada um (seção "Sistemas que você precisa me mandar" do
   README). Não invente URL, stack ou estrutura de sistema que eu ainda não
   mandei. Quando eu mandar um repo, adicione só com acesso de leitura e
   não altere nada nele.
6. No fim, me mostre o que ficou pronto, o que falta do checklist de segurança
   (seção 6) e como eu rodo localmente.
```

> Se a sessão for longa demais, nas próximas conversas basta dizer
> "continua a ordem de implementação a partir do passo N".

## 4. Railway (quando o passo 12 chegar, não antes)

1. **New Project → Deploy from GitHub repo** → `faiston-hub`, branch de deploy: **`main`**.
2. **+ New → Database → PostgreSQL** (ou use o Neon e cole a URL com `sslmode=require`).
3. No serviço web, aba **Variables**: preencha tudo da §8 da especificação.
   `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`. Gere `SECRET_KEY` e
   `MFA_ENCRYPTION_KEYS` com os comandos da tabela. **Guarde a
   `MFA_ENCRYPTION_KEYS` num cofre:** se ela for perdida, todo mundo precisa
   recadastrar o MFA.
4. **Settings → Networking → Generate Domain**, e coloque esse domínio em `ALLOWED_HOSTS` e `PUBLIC_BASE_URL`.
5. Primeiro admin: no Railway, abra o shell do serviço e rode
   `python -m cli create-admin --email rafael.libel@faiston.com --nome "Rafael"`.
   Abra o link que aparecer, defina a senha e cadastre o MFA.
6. Pelo admin, convide o seu parceiro e cadastre as URLs dos serviços
   (Console de Testes, Dashboard-Faiston, Sistema-Giro).

## 5. Proteger a `main` (GitHub → Settings → Branches)

**Add rule** para `main`: *Require a pull request before merging*, *Require
status checks to pass* (o job de CI) e *Do not allow force pushes*.

---

## Decisões já tomadas (pra não rediscutir)

- Login próprio por e-mail + senha, **só por convite**, sem Microsoft/Entra ID por enquanto.
- MFA (TOTP no app autenticador) no primeiro acesso e em todo dispositivo novo,
  com "confiar por 30 dias". Admin sempre usa MFA.
- O hub não mexe em nenhum sistema existente nesta fase, só aponta para eles.
- O Console de Testes continua aberto para a LPD. O papel `parceiro` já está
  previsto no modelo de dados para quando ele entrar atrás do login.

## Sistemas que você precisa me mandar

**Obrigatório:** antes de o hub cadastrar ou integrar qualquer sistema, mande
para o Claude **todos os repositórios e arquivos** de cada um. Sem isso, ele não
tem como conferir a stack, as rotas, o `/health`, a URL de produção nem o jeito
de autenticar de cada sistema, e não vai chutar nada disso.

| Sistema | O que mandar | Status |
|---|---|---|
| Faiston One — Console de Testes | repo `rafalibel-faiston/Testes-Faiston-One` + URL de produção (Railway) | repo já conhecido; falta a URL |
| Faiston Ops | repo `rafalibel-faiston/Dashboard-Faiston` + URL de produção | pendente |
| Giro | repo `rafalibel-faiston/Sistema-Giro` + URL de produção | pendente |
| Painéis gerenciais | repos e/ou arquivos (`.pbix`, links do Power BI, planilhas) de cada painel | pendente (você ainda vai pegar) |
| RH — Automação | o que já existir: levantamento do processo, planilhas, fluxos, documentos | pendente |
| Outros candidatos | `Apresenta-o-Indicadores`, `Overviwe-Logistica-Faiston`, `Consolidado-MC-s`, `sgb-operation`: confirmar se entram | a confirmar |

Como mandar:
- **Repo do GitHub:** diga o nome (`dono/repo`) na conversa e o Claude adiciona
  com acesso de leitura. Se for privado, o app Claude no GitHub precisa ter
  acesso a ele (ver o passo 2).
- **Arquivos soltos** (`.pbix`, planilhas, PDFs, prints): anexe na conversa.
- Junto com cada sistema, informe: a URL de produção, quem usa, se tem login e
  se tem dado sensível (cliente, colaborador, contrato).

## Pendências suas

- [ ] **Mandar todos os repos e arquivos dos sistemas** (tabela acima), incluindo os dos painéis gerenciais e do RH.
- [ ] Levantar as URLs de produção do Console, do Dashboard-Faiston e do Sistema-Giro.
- [ ] Decidir provedor de e-mail (SMTP do M365 ou Resend) para o "esqueci minha senha" na fase 2.
