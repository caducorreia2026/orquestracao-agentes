# Agente Programador

Agente de um sistema multi-agente que, dada uma issue e um ficheiro com bug,
**aplica a correção numa branch Git isolada** e cria um commit automático.

## Funcionalidades

1. Cria e muda para a branch `fix/issue-{id}` (isolada do `main`).
2. Lê o conteúdo atual do ficheiro de código.
3. Aplica a correção via um **fixer callable injetável** (por defeito,
   substituição textual `old_code` -> `new_code`; pode ser um LLM).
4. Guarda o ficheiro e faz commit automático com mensagem clara.

A saída é compatível com o formato esperado pelo **Hermes / LangGraph**
(estado `dict` com `messages` + payload `programador_result`).

## Instalação

```bash
pip install -e ".[dev]"
```

## Uso como biblioteca

```python
from agente_programador.agent import ProgramadorAgent

agent = ProgramadorAgent()
state = {
    "repo_path": "/caminho/ao/repo",
    "issue_id": "42",
    "file_path": "src/calc.py",
    "problem_description": "divisão por zero quando b é 0",
    "old_code": "def divide(a, b):\n    return a / b\n",
    "new_code": "def divide(a, b):\n    if b == 0:\n        raise ValueError('divisor não pode ser zero')\n    return a / b\n",
}
out = agent.run(state)
print(out["programador_result"].model_dump_json(indent=2))
```

### Fixer customizado (ex.: LLM)

```python
from agente_programador.agent import ProgramadorAgent

def llm_fixer(file_path, current_content, problem_description, state):
    # chamar o LLM e devolver o código corrigido
    return fixed_content

agent = ProgramadorAgent(fixer=llm_fixer)
```

## Uso na CLI

```bash
agente-programador \
  --repo /caminho/ao/repo \
  --issue-id 42 \
  --file src/calc.py \
  --problem "divisão por zero quando b é 0" \
  --old-code "return a / b" \
  --new-code "if b == 0: raise ValueError('não pode ser zero')"
```

## Integração LangGraph

```python
from langgraph.graph import StateGraph
from agente_programador.agent import ProgramadorAgent

builder = StateGraph(dict)
builder.add_node("programador", ProgramadorAgent().as_node())
# ... adicionar outros agentes ...
graph = builder.compile()
```

## Esquema da saída

```json
{
  "agent": "programador",
  "timestamp": "2026-10-28T15:00:00Z",
  "repo_path": "/caminho/ao/repo",
  "issue_id": "42",
  "branch": "fix/issue-42",
  "file_path": "src/calc.py",
  "changed": true,
  "commit": "a1b2c3d...",
  "commit_message": "fix: resolve issue #42 - ... (src/calc.py)",
  "error": null
}
```
