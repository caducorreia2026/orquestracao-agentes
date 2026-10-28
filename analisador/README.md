# Agente Analisador

Agente de um sistema multi-agente que executa o **pytest** num repositório local
(via `subprocess`), captura os erros e devolve um **JSON estruturado** com:

- ficheiros afetados
- tipo de erro
- passos de reprodução

A saída é compatível com o formato esperado pelo **Hermes / LangGraph** (estado
`dict` com `messages` + payload `analisador_result`).

## Instalação

```bash
pip install -e ".[dev]"
```

## Uso como biblioteca

```python
from agente_analisador.agent import AnalisadorAgent

agent = AnalisadorAgent()
state = {"repo_path": "/path/to/repo", "pytest_args": ["-x", "--tb=short"]}
result = agent.run(state)
print(result["analisador_result"].model_dump_json(indent=2))
```

## Uso na CLI

```bash
agente-analisador --repo /path/to/repo --pytest-args -x --tb short
```

## Esquema da saída

```json
{
  "agent": "analisador",
  "timestamp": "2026-10-26T14:23:00Z",
  "repo_path": "/path/to/repo",
  "status": "failed",
  "summary": { "total": 10, "passed": 8, "failed": 2, "errors": 0, "skipped": 0 },
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
        "pytest tests/test_foo.py::test_bar -v"
      ]
    }
  ]
}
```

## Integração LangGraph

```python
from langgraph.graph import StateGraph
from agente_analisador.agent import AnalisadorAgent

builder = StateGraph(dict)
builder.add_node("analisador", AnalisadorAgent().as_node())
# ... adicionar outros agentes ...
graph = builder.compile()
```
