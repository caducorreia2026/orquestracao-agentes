# Orquestrador Central

Agente de orquestração que coordena, via **LangGraph StateGraph**, os quatro agentes do projecto multi-agente:

| Slot | Agente | Implementador | Estado |
|------|--------|---------------|--------|
| 1 | Analisador | Guidyanne | ✅ Implementado (`analisador/`) |
| 2 | Gestor de Issues | Carlos | ✅ Implementado (`issue_manager/`) |
| 3 | Programador | Ruben | ✅ Implementado (`programador/`) |
| 4 | Revisor & Testador | Eduardo | ✅ Implementado (este módulo) |

O Orquestrador não implementa qualquer agente individual — ele **coordena** o fluxo entre eles, decide quando reenviar ao programador (retry) e quando abrir o Pull Request.

## Arquitetura

```
START
  │
  ▼
analyzer  (Guidyanne — stub)
  │
  ▼
issue_manager  (Carlos — stub)
  │
  ▼
programmer  (Ruben — stub)
  │
  ▼
reviewer  (Eduardo — implementado: pytest via subprocess)
  │
  ├─► tests_passed  ──────────► create_pr ──► END
  │
  ├─► tests_failed & retry<3  ──► programmer (ciclo repete)
  │
  └─► tests_failed & retry>=3 ──► END (stop limpo)
```

## Estrutura do módulo

```
orquestrador/
├── __init__.py     # expõe API pública + orquestrador compilado
├── __main__.py     # CLI:  python -m orquestrador <repo> "<bug>" <issue>
├── state.py        # TypedDict AgentState (contrato partilhado)
├── agent.py        # classe Revisorteste + função eduardo_reviewer_node
├── graph.py        # build_graph(), should_retry_or_pr, orchestrator
├── pyproject.toml  # packaging + deps + ruff/mypy/pytest config
└── README.md       # este ficheiro
```

### `AgentState` (state.py)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `repo_path` | `str` | Caminho absoluto do repositório alvo |
| `bug_description` | `str` | Texto livre descrevendo o bug |
| `issue_number` | `int` | Número da issue no GitHub |
| `branch_name` | `str \| None` | Branch de trabalho (criada pelo Carlos) |
| `test_results` | `str` | Output capturado da última run de pytest |
| `retry_count` | `int` | Número de tentativas falhas (0..3) |
| `status` | `str` | Fase corrente (`"tests_passed"`, `"tests_failed"`, `"issue_created"`, `"pr_created"`, etc.) |

## Como instalar

```bash
pip install -e ".[dev]"
```

## Como usar

### Como CLI:

```bash
python -m orquestrador /caminho/ao/repo "descrição do bug" 42
```

### Como biblioteca / LangGraph:

```python
from orquestrador.graph import orchestrator, build_graph
from orquestrador.state import AgentState

initial_state: AgentState = {
    "repo_path": "/caminho/ao/repo",
    "bug_description": "Bug crítico na função calcular_desconto",
    "issue_number": 42,
    "branch_name": None,
    "test_results": "",
    "retry_count": 0,
    "status": "ready",
}

# recursion_limit=50 é o limite de segurança contra loops infinitos
final = orchestrator.invoke(initial_state, config={"recursion_limit": 50})

print(final["status"])        # "pr_created"
print(final["retry_count"])   # 0 (testes passaram de primeira)
```

### Como nó num graph maior:

```python
from langgraph.graph import StateGraph
from orquestrador.graph import orchestrator

graph = StateGraph(dict)
graph.add_node("orquestrador", orchestrator.invoke)
# ... integrar com outros agentes ...
compiled = graph.compile()
```

## Lógica de retry (`should_retry_or_pr`)

| Condição | Decisão | Destino |
|----------|---------|---------|
| `status == "tests_passed"` | Criar PR | `create_pr` → `END` |
| `status == "tests_failed"` e `retry_count < 3` | Reenviar ao programador | `programmer` (ciclo repete) |
| `status == "tests_failed"` e `retry_count >= 3` | Parar | `END` (encerra limpo) |

## Testes

```bash
pytest tests/ -q       # 12 testes, todos passam
```
