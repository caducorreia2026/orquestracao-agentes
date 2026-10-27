# Orquestração de Agentes — Deteção e Resolução de Bugs

Sistema de agentes de IA que analisa um repositório, cria issues, implementa correções, testa e abre Pull Requests para aprovação humana.

| Pasta | Agente | Responsável |
|---|---|---|
| `analisador/` | 1 — Analisador de Código | Guidyanne |
| `issue_manager/` | 2 — Gestor de Issues | Carlos |
| `programador/` | 3 — Programador | Ruben |
| `revisor/` | 4 — Revisor e Testador | Eduardo |
| `orquestrador/` | Orquestrador central | Eduardo |
| `shared/` | Modelos de dados entre agentes | Todos |

## Começar

```bash
pip install -r requirements.txt
cp .env.example .env   # preencher com o teu token
pytest -q
```

Antes de contribuir, ler o [CONTRIBUTING.md](CONTRIBUTING.md).
