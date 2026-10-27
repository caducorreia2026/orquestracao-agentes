# Agente 2 — Gestor de Issues

Parte do sistema de orquestração de agentes (Guidyanne → **Carlos** → Ruben → Eduardo).

```
Agente 1 (BugReport) ──► [ validar ] ──► [ procurar duplicados ] ──► [ criar issue ] ──► Agente 3
                              │                    │                       │
                          rejected            duplicate               created
                                          (comenta na issue)    (labels + branch_name)

Depois do PR (Agente 3/4) ──► link_pull_request(): "Closes #N" no PR + comentário na issue
```

## Estrutura

| Ficheiro | O que faz |
|---|---|
| `issue_manager/models.py` | Contratos: `BugReport` (entrada) e `IssueResult` (saída). **Combinar com a equipa.** |
| `issue_manager/github_client.py` | Chamadas à API REST do GitHub + allowlist de repositórios |
| `issue_manager/dedup.py` | Duplicados em 3 camadas: fingerprint → semelhança de texto → LLM (opcional) |
| `issue_manager/agent.py` | O agente: validar, criar, ligar PR, audit log, nó LangGraph |
| `tests/` | 11 testes com GitHub falso (sem rede) |
| `demo.py` | Corre o exemplo do desconto contra o repo de teste real |

## Correr

```bash
pip install requests pydantic pytest
pytest -q                # testes, sem precisar de token
cp .env.example .env     # preencher token + repo de teste
python demo.py           # cria a issue no GitHub
python demo.py           # 2.ª vez: deteta duplicado e só comenta
```

## Integração com os outros agentes

- **Guidyanne (Agente 1)** envia um dict com os campos de `BugReport`. Se faltar algo, o Pydantic rejeita logo.
- **Ruben (Agente 3)** recebe `issue_number` e `branch_name` (`fix/issue-<n>-<slug>`) e no PR põe `Closes #<n>`.
- **Eduardo (orquestrador)** adiciona o nó:

```python
from issue_manager import IssueManagerAgent, GitHubClient, make_langgraph_node
graph.add_node("issue_manager", make_langgraph_node(IssueManagerAgent(GitHubClient(repo))))
graph.add_conditional_edges("issue_manager",
    lambda s: "programador" if s["issue"]["status"] != "rejected" else END)
```

## Decisões (para a apresentação)

- **A IA não decide os casos claros.** Duplicados exatos e óbvios são detetados de forma determinística; o LLM só entra na zona cinzenta (semelhança 0.45–0.85). Previsível, testável e funciona sem modelo.
- **"Devidamente fundamentado"** = `reproduced=True` + evidência objetiva (output do teste). Sem isso, a issue não é criada.
- **Fingerprint escondido** no corpo (`<!-- bug-fingerprint: … -->`) permite reconhecer o mesmo bug entre execuções.
- **Segurança:** allowlist de repos, token fine-grained sem `Contents: write`, caminhos de ficheiros só relativos, e o merge fica sempre para um humano (o `Closes #N` só fecha a issue quando alguém aprova o PR).
- **Histórico:** cada ação vai para `logs/issue_manager.jsonl` com o motivo.

## Limitações / melhorias

- `list_issues` lê só as primeiras 100 issues com a label `auto-bug` (chega para o repo de teste; depois, paginação).
- Semelhança por `difflib` é simples; poderia usar embeddings locais.
- Prioridade vem da severidade do Analisador; podia combinar com nº de ocorrências.
