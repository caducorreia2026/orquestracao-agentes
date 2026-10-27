"""Demo do Agente 2 contra o repositório de TESTE no GitHub.

Uso:
    cp .env.example .env   # preencher
    python demo.py              # cria a issue do exemplo do desconto
    python demo.py --llm        # idem, usando o Ollama para a zona cinzenta
"""
import os
import sys

from issue_manager import BugReport, GitHubClient, IssueManagerAgent
from issue_manager.dedup import ollama_judge


def load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)


if __name__ == "__main__":
    load_env()
    gh = GitHubClient(os.environ["GITHUB_REPO"])
    agent = IssueManagerAgent(gh, llm_judge=ollama_judge() if "--llm" in sys.argv else None)

    # Em produção isto vem do Agente 1 (Guidyanne). Aqui está fixo para testar sozinho.
    report = BugReport(
        title="Função calcular_desconto aplica 1% em vez de 10%",
        description="A função calcular_desconto deveria aplicar 10% de desconto ao total, "
                    "mas divide por 100 em vez de multiplicar por 0.10.",
        files=["src/loja/cart.py"],
        reproduction_steps=["pip install -e .", "pytest tests/test_cart.py::test_desconto_10"],
        expected_behavior="calcular_desconto(100) devolve 90.0",
        actual_behavior="calcular_desconto(100) devolve 99.0",
        evidence="FAILED tests/test_cart.py::test_desconto_10 - assert 99.0 == 90.0",
        failing_test="tests/test_cart.py::test_desconto_10",
        severity="high",
        reproduced=True,
    )

    result = agent.process(report)
    print(result.model_dump_json(indent=2))
