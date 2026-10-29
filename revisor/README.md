# Agente Revisor

Agente de um sistema multi-agente que executa o **pytest** num repositório local
(via `subprocess`), capta stdout/stderr e devolve um **JSON estruturado** com:

- código de saída do pytest
- resumo agregado (total / passed / failed / errors / skipped / duração)
- lista de falhas com tipo de erro, mensagem, traceback e passos de reprodução
- saída bruta capturada (truncada)

A saída é compatível com o formato esperado pelo **Hermes / LangGraph** (estado
`dict` com `messages` + payload `revisor_result`).

## Estrutura do módulo

| Ficheiro | O que faz |
|---|---|
| `agente_revisor/agent.py` | Classe `RevisorAgent` — orquestra runner → parser → formatter. |
| `agente_revisor/pytest_runner.py` | `PytestRunner`, `PytestRun`, `run_pytest`, `PytestNotFoundError` — execução isolada via subprocess. |
| `agente_revisor/formatter.py` | `build_result()` — converte `PytestRun` em `RevisorResult`. |
| `agente_revisor/error_parser.py` | `parse_failures`, `parse_summary` — parsing da saída do pytest (regex, sem plugins). |
| `agente_revisor/schemas.py` | `RevisorResult`, `Failure`, `Summary` — schemas Pydantic. |
| `agente_revisor/__main__.py` | Entry-point CLI (`python -m agente_revisor` / `agente-revisor`). |

## Instalação

```bash
pip install -e ".[dev]"
```

## Uso como biblioteca

```python
from agente_revisor.agent import RevisorAgent

agent = RevisorAgent()
state = {"repo_path": "/path/to/repo", "pytest_args": ["-x", "--tb=short"]}
result = agent.run(state)
print(result["revisor_result"].model_dump_json(indent=2))
```

## Uso na CLI

```bash
agente-revisor --repo /path/to/repo --pytest-args -x --tb short --timeout 600 --indent 2
```

## Esquema da saída

```json
{
  "agent": "revisor",
  "timestamp": "2026-10-29T12:00:00Z",
  "repo_path": "/path/to/repo",
  "status": "failed",
  "exit_code": 1,
  "summary": {
    "total": 10,
    "passed": 8,
    "failed": 2,
    "errors": 0,
    "skipped": 0,
    "duration_seconds": 3.45
  },
  "failures": [
    {
      "test_id": "tests/test_foo.py::test_bar",
      "file": "tests/test_foo.py",
      "test_name": "test_bar",
      "line": 42,
      "error_type": "AssertionError",
      "error_message": "assert 1 == 2",
      "traceback": "...",
      "reproduction_steps": [
        "cd /path/to/repo",
        "pytest tests/test_foo.py::test_bar -v --tb=long"
      ]
    }
  ],
  "raw_output": "...",
  "error": null
}
```

### Campos do `RevisorResult`

| Campo | Tipo | Descrição |
|---|---|---|
| `agent` | `Literal["revisor"]` | Identidade do agente (sempre `"revisor"`). |
| `timestamp` | `str` | Timestamp UTC ISO-8601 da execução. |
| `repo_path` | `str` | Caminho absoluto do repositório testado. |
| `status` | `Literal["passed", "failed", "error", "no_tests"]` | Resultado da execução. |
| `exit_code` | `int` | Código de saída do processo pytest (0, 1, 5, ...). `-1` em caso de erro fatal (timeout / pytest não encontrado). |
| `summary` | `Summary` | Contadores agregados. |
| `failures` | `list[Failure]` | Detalhes de cada teste falhado. |
| `raw_output` | `str` | Saída bruta truncada (máx. 20 000 chars). |
| `error` | `str \| None` | Erro fatal (ex.: pytest não encontrado), quando aplicável. |

### Regras de `status`

| Condição | `status` |
|---|---|
| `returncode == 0` | `"passed"` |
| `returncode == 5` (sem testes) | `"no_tests"` |
| `returncode` outro + `summary.errors > 0` e `summary.failed == 0` | `"error"` |
| Caso contrário | `"failed"` |

## Integração com LangGraph

```python
from langgraph.graph import StateGraph
from agente_revisor.agent import RevisorAgent

builder = StateGraph(dict)
builder.add_node("revisor", RevisorAgent().as_node())
# ... adicionar outros agentes ...
graph = builder.compile()
```

### Node function

`RevisorAgent().as_node()` devolve uma função `(_node)` que aceita um estado
`dict` e devolve:

```python
{
    "revisor_result": RevisorResult,
    "messages": [result.to_langgraph_message()],
}
```

Onde `to_langgraph_message()` produz:

```python
{
    "role": "system",
    "name": "revisor",
    "content": result.model_dump_json(indent=2),
}
```

## Runner injetável

O `RevisorAgent` aceita um `runner` customizado para facilitar testes sem tocar
em `subprocess`:

```python
from agente_revisor.agent import RevisorAgent
from agente_revisor.pytest_runner import PytestRun

def fake_runner(**kwargs):
    return PytestRun(
        returncode=1,
        stdout="FAILED tests/x.py::y - AssertionError: boom\n",
        stderr="",
        cmd=["pytest"],
    )

agent = RevisorAgent(runner=fake_runner)
out = agent.run({"repo_path": "/repo"})
```

## Testes

```bash
pip install -e ".[dev]"
pytest -q
```

Os testes cobrem:
- Parser (falhas, resumo, reprodução, casos de classe, output vazio)
- Formatter (status `passed` / `failed` / `no_tests`, truncamento, serialização JSON)
- Agente (runner mockado, erro de pytest não encontrado, função `as_node`)
- CLI entry-point (`__main__`)
- End-to-end com pytest real num repositório de teste temporário
