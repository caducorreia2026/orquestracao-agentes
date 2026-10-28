# Repo de Teste — Desconto

Repositório **com bugs intencionais** para testar o Agente Analisador.

## Instalação

```bash
pip install -e ".[dev]"
```

## Executar os testes (manualmente)

```bash
pytest
```

Todos os testes de cálculo irão falhar; os testes de validação passam.

## Usar com o Agente Analisador

A partir da raiz do projeto `agente-analisador`:

```bash
agente-analisador --repo repo_teste_desconto --indent 2 > resultado.json
```

Ou em Python:

```python
from agente_analisador.agent import AnalisadorAgent

agent = AnalisadorAgent()
out = agent.run({"repo_path": "repo_teste_desconto"})
print(out["analisador_result"].model_dump_json(indent=2))
```

## Bugs esperados (a serem detetados pelo agente)

1. **Soma em vez de subtrair** — `calculate_discount(100, 10)` devolve `1100`
   em vez de `90`.
2. **Não divide a taxa por 100** — a taxa `10` é usada como `10.0x` em vez de
   `0.10`, produzindo valores absurdos.
