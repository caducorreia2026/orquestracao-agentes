# Como trabalhamos com Git neste projeto

Tutorial para a equipa: **Guidyanne, Carlos, Ruben e Eduardo**.

Leiam isto uma vez do início ao fim. Depois usem a **Cábula** no fim do ficheiro no dia a dia.

---

## As 4 regras de ouro

1. **Ninguém faz push direto para a `main`.** Tudo entra por Pull Request (PR).
2. **Cada pessoa trabalha na sua branch** e, sempre que possível, **só na sua pasta**.
3. **Fazer `git pull` da `main` antes de começar a trabalhar**, todos os dias.
4. **Nunca fazer commit do `.env`** (tem o token do GitHub).

---

## Parte 1 — Preparar o computador (só uma vez)

### 1.1 Instalar o Git

- **Windows:** descarregar em https://git-scm.com/download/win e instalar com as opções por defeito. Usar o **Git Bash** para os comandos deste tutorial.
- **Mac:** abrir o Terminal e escrever `git --version`. Se não estiver instalado, o Mac oferece-se para instalar.

Confirmar:
```bash
git --version
```

### 1.2 Dizer ao Git quem és

Usa o mesmo e-mail da tua conta do GitHub:
```bash
git config --global user.name "O Teu Nome"
git config --global user.email "o-teu-email@exemplo.com"
git config --global init.defaultBranch main
git config --global pull.rebase false
```

### 1.3 Ligar o Git à tua conta do GitHub

A forma mais simples é com o **GitHub CLI**:

- Instalar: https://cli.github.com
- Depois:
```bash
gh auth login
```
Escolher: `GitHub.com` → `HTTPS` → `Yes` (autenticar o Git) → `Login with a web browser`.

A partir daqui, o `git push` funciona sem pedir password.

---

## Parte 2 — Criar o repositório (só UMA pessoa faz isto)

> Combinem quem é. Os outros saltam para a Parte 3.

1. No GitHub: **New repository**
   - Nome: `orquestracao-agentes`
   - **Private**
   - Marcar **Add a README file**
2. **Settings → Collaborators → Add people**: adicionar os outros três.
3. **Settings → Branches → Add branch ruleset** (ou *Add rule*) para a branch `main`:
   - ✅ Require a pull request before merging
   - ✅ Require approvals: **1**
   - ✅ Block force pushes
4. Criar a estrutura inicial de pastas (ver Parte 3.2), com o `.gitignore`, o `.env.example` e este `CONTRIBUTING.md`, e fazer o primeiro PR com isso.

---

## Parte 3 — Clonar o repositório (cada pessoa, uma vez)

### 3.1 Clonar

Escolham uma pasta onde guardam projetos (ex.: `Documentos/projetos`) e:
```bash
cd ~/Documentos/projetos
git clone https://github.com/<dono>/orquestracao-agentes.git
cd orquestracao-agentes
```

### 3.2 Estrutura do repositório

```
orquestracao-agentes/
├── analisador/        ← Guidyanne
├── issue_manager/     ← Carlos
├── programador/       ← Ruben
├── revisor/           ← Eduardo
├── orquestrador/      ← Eduardo
├── shared/            ← modelos de dados entre agentes (mexer só depois de falar com a equipa)
├── tests/             ← test_<agente>.py de cada um
├── .env.example
├── .gitignore
├── requirements.txt
├── CONTRIBUTING.md
└── README.md
```

### 3.3 Preparar o Python e o `.env`

```bash
python -m venv .venv
# Windows (Git Bash):
source .venv/Scripts/activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env      # e preencher com o TEU token
pytest -q                 # tudo tem de passar
```

O `.env` é **pessoal**. Cada um cria o seu token. Nunca o partilhem nem façam commit dele.

---

## Parte 4 — O ciclo de trabalho (todos os dias)

É sempre isto. Exemplo do Carlos a melhorar a deteção de duplicados:

### Passo 1 — Atualizar a `main`
```bash
git checkout main
git pull
```

### Passo 2 — Criar uma branch para a tarefa
Nome: `<nome>/<o-que-vais-fazer>`, em minúsculas e com hífenes.
```bash
git checkout -b carlos/dedup-com-embeddings
```

Exemplos de nomes:
- `guidyanne/analise-pylint`
- `ruben/criar-branch-automatica`
- `eduardo/loop-de-tentativas`

### Passo 3 — Trabalhar e fazer commits pequenos
```bash
git status                    # ver o que mudou
git add issue_manager/ tests/test_issue_manager.py
git commit -m "Adiciona deteção de duplicados com embeddings"
```

Dicas:
- **Antes de cada commit, olhem para o `git status`.** Se aparecer `.env`, **parem** (ver Parte 7).
- Prefiram `git add <pasta>` a `git add .`, para não apanharem ficheiros que não são vossos.
- Um commit = uma alteração com sentido. Melhor 5 commits pequenos do que 1 gigante.

**Mensagens de commit:** no imperativo, em português, a dizer *o que* faz:
- ✅ `Corrige cálculo da semelhança de títulos`
- ✅ `Adiciona testes para issues duplicadas`
- ❌ `update`, `alterações`, `asdf`

### Passo 4 — Enviar para o GitHub
Na primeira vez:
```bash
git push -u origin carlos/dedup-com-embeddings
```
Nas seguintes, só:
```bash
git push
```

### Passo 5 — Abrir o Pull Request
1. Abrir o repositório no GitHub. Aparece um aviso amarelo: **Compare & pull request**. Clicar.
2. Confirmar: **base: `main`** ← **compare: a tua branch**.
3. Título claro e descrição com:
   - **O que muda**
   - **Como testar** (ex.: `pytest tests/test_issue_manager.py`)
   - **Afeta outros agentes?** (sim/não, e quais)
4. Em **Reviewers**, escolher um colega.
5. **Create pull request**.

### Passo 6 — Revisão
- O colega lê, comenta e aprova (**Approve**) ou pede alterações (**Request changes**).
- Se pedir alterações: corriges **na mesma branch**, fazes commit e `git push`. O PR atualiza sozinho.

### Passo 7 — Merge e limpeza
Depois de aprovado, quem abriu o PR carrega em **Squash and merge** e depois em **Delete branch**.

No teu computador:
```bash
git checkout main
git pull
git branch -d carlos/dedup-com-embeddings
```

E volta ao Passo 1 para a próxima tarefa.

---

## Parte 5 — Como rever o PR de um colega

1. Ler as alterações no separador **Files changed**.
2. Se quiseres testar no teu computador:
   ```bash
   git fetch
   git checkout ruben/criar-branch-automatica
   pytest -q
   git checkout main          # voltar no fim
   ```
3. Comentar em linhas específicas (clicar no `+` ao lado da linha).
4. **Review changes** → *Approve* ou *Request changes*.

O que verificar:
- Os testes passam?
- Mexe em pastas de outra pessoa ou em `shared/`? Se sim, essa pessoa sabe?
- Há tokens, passwords ou `.env` no código?

---

## Parte 6 — A tua branch ficou desatualizada (e conflitos)

Se a `main` avançou enquanto trabalhavas (ou o GitHub diz *"This branch has conflicts"*):

```bash
git checkout main
git pull
git checkout carlos/dedup-com-embeddings
git merge main
```

### Se aparecer um conflito

O Git avisa `CONFLICT (content): Merge conflict in requirements.txt`. Abre o ficheiro e vês algo assim:

```
<<<<<<< HEAD
requests
pydantic>=2
=======
requests
langgraph
>>>>>>> main
```

- Entre `<<<<<<< HEAD` e `=======` está a **tua** versão.
- Entre `=======` e `>>>>>>> main` está a versão da **main**.

Edita o ficheiro para ficar como deve ser (aqui, manter as duas bibliotecas) e **apaga as linhas com `<<<<<<<`, `=======` e `>>>>>>>`**:

```
requests
pydantic>=2
langgraph
```

Depois:
```bash
git add requirements.txt
git commit -m "Resolve conflito com a main"
pytest -q
git push
```

**Dica:** o VS Code mostra botões *Accept Current / Accept Incoming / Accept Both* em cima de cada conflito, o que ajuda muito.

Se o conflito for em código de outra pessoa e não tiveres a certeza, **pergunta-lhe** antes de escolher.

---

## Parte 7 — Problemas comuns e como resolver

### "Fiz commit na `main` sem querer" (ainda não fiz push)
```bash
git branch carlos/o-meu-trabalho     # guarda os commits numa branch nova
git reset --hard origin/main          # volta a main ao que está no GitHub
git checkout carlos/o-meu-trabalho
```

### "Quero desfazer o último commit" (ainda não fiz push)
```bash
git reset --soft HEAD~1    # desfaz o commit, mas mantém as alterações
```

### "Comecei a mexer nos ficheiros e esqueci-me de criar a branch"
Se ainda não fizeste commit, basta:
```bash
git checkout -b carlos/nome-da-tarefa
```
As alterações vêm contigo.

### "Preciso de mudar de branch mas tenho alterações por guardar"
```bash
git stash          # guarda as alterações de lado
git checkout outra-branch
# ...
git checkout a-minha-branch
git stash pop      # recupera as alterações
```

### "Fiz commit do `.env` / do token" ⚠️
1. **Revoga o token imediatamente**: GitHub → Settings → Developer settings → Personal access tokens → apagar.
2. Cria um token novo e coloca-o no teu `.env`.
3. Tira o ficheiro do Git:
   ```bash
   git rm --cached .env
   git commit -m "Remove .env do repositório"
   git push
   ```
4. **Avisa a equipa.**

O passo 1 é o que importa: mesmo apagado, o token continua no histórico. Por isso o token antigo tem de deixar de funcionar.

### "O `git push` foi rejeitado"
- `rejected ... (fetch first)`: alguém fez push para a mesma branch. Faz `git pull` e depois `git push`.
- `protected branch`: estás a tentar fazer push para a `main`. Cria uma branch (Parte 4, Passo 2).

---

## Parte 8 — Organização da equipa no GitHub

- **Issues do repositório do projeto** = tarefas da equipa (ex.: *"Agente 2: ligar PR à issue"*), cada uma atribuída a uma pessoa.
  - Não confundir com as issues que os **agentes** criam no **repositório de teste**.
- No PR, escrevam `Closes #12` na descrição. Quando for feito o merge, a tarefa #12 fecha sozinha.
- **Projects** (separador *Projects* → *New project* → *Board*): quadro com *A fazer / Em curso / Em revisão / Feito*.

### Repositórios de teste
- **Durante o desenvolvimento:** cada um usa o **seu** repositório de teste (cópia do `repo-teste-bugs`), para não misturarem issues e branches criadas pelos agentes.
- **Para a demo final:** um único repositório de teste partilhado, com o sistema completo.

### Alterações em `shared/`
Os modelos de dados entre agentes (`BugReport`, `IssueResult`, ...) são o "contrato" entre vocês. Mudar um campo pode partir o agente de outra pessoa. Regra: **falar com a equipa primeiro** e pedir revisão a quem usa esse modelo.

---

## Cábula

```bash
# Começar o dia
git checkout main
git pull

# Nova tarefa
git checkout -b <nome>/<tarefa>

# Guardar trabalho
git status
git add <pasta-ou-ficheiros>
git commit -m "Mensagem clara no imperativo"
git push                 # 1.ª vez: git push -u origin <nome>/<tarefa>

# Abrir PR no GitHub → pedir revisão → Squash and merge → Delete branch

# Depois do merge
git checkout main
git pull
git branch -d <nome>/<tarefa>

# Trazer novidades da main para a tua branch
git checkout main && git pull
git checkout <nome>/<tarefa>
git merge main

# Ver em que branch estou e o histórico
git branch
git log --oneline --graph -10
```
