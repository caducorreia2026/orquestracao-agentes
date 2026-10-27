"""Testes do Agente 2 com um GitHub falso (não precisa de rede nem de token)."""
import json

import pytest

from issue_manager import BugReport, IssueManagerAgent, make_langgraph_node
from issue_manager.github_client import GitHubClient, RepoNotAllowed


class FakeGitHub:
    def __init__(self):
        self.issues, self.comments, self.labels, self.pulls = [], [], set(), {}

    def list_issues(self, labels="", state="all"):
        return [i for i in self.issues if not labels or labels in i["labels"]]

    def create_issue(self, title, body, labels):
        issue = {"number": len(self.issues) + 1, "title": title, "body": body, "labels": labels,
                 "html_url": f"https://github.com/x/y/issues/{len(self.issues) + 1}"}
        self.issues.append(issue)
        return issue

    def comment_issue(self, number, body):
        self.comments.append((number, body))

    def ensure_label(self, name, color, description=""):
        self.labels.add(name)

    def get_pull(self, number):
        return self.pulls[number]

    def update_pull_body(self, number, body):
        self.pulls[number]["body"] = body


def desconto_report(**over):
    data = dict(
        title="Função calcular_desconto aplica 1% em vez de 10%",
        description="calcular_desconto(100) devolve 99 em vez de 90.",
        files=["src/loja/cart.py"],
        reproduction_steps=["pip install -e .", "pytest tests/test_cart.py::test_desconto_10"],
        expected_behavior="calcular_desconto(100) == 90",
        actual_behavior="calcular_desconto(100) == 99",
        evidence="FAILED tests/test_cart.py::test_desconto_10 - assert 99.0 == 90.0",
        failing_test="tests/test_cart.py::test_desconto_10",
        severity="high",
        reproduced=True,
    )
    data.update(over)
    return BugReport(**data)


@pytest.fixture
def agent(tmp_path):
    return IssueManagerAgent(FakeGitHub(), audit_log=tmp_path / "audit.jsonl")


def test_cria_issue_completa(agent):
    r = agent.process(desconto_report())
    assert r.status == "created" and r.issue_number == 1
    assert r.branch_name == "fix/issue-1-funcao-calcular-desconto-aplica-1-em-vez"
    issue = agent.gh.issues[0]
    for parte in ["## Ficheiros envolvidos", "src/loja/cart.py", "## Passos para reproduzir",
                  "## Comportamento esperado", "assert 99.0 == 90.0", "bug-fingerprint"]:
        assert parte in issue["body"]
    assert "priority: P1" in issue["labels"] and "auto-bug" in issue["labels"]


def test_rejeita_bug_nao_reproduzido(agent):
    r = agent.process(desconto_report(reproduced=False))
    assert r.status == "rejected"
    assert agent.gh.issues == []


def test_mesmo_bug_duas_vezes_nao_duplica(agent):
    agent.process(desconto_report())
    r = agent.process(desconto_report(description="Outra execução do analisador, mesmo bug."))
    assert r.status == "duplicate" and r.issue_number == 1
    assert len(agent.gh.issues) == 1
    assert agent.gh.comments and agent.gh.comments[0][0] == 1


def test_titulo_parecido_e_detetado(agent):
    agent.process(desconto_report())
    r = agent.process(desconto_report(title="Funcao calcular_desconto aplica 1% e não 10%",
                                      failing_test=None))
    assert r.status == "duplicate"


def test_bug_diferente_cria_nova_issue(agent):
    agent.process(desconto_report())
    r = agent.process(desconto_report(
        title="Login aceita password vazia sem validação",
        files=["src/auth/login.py"], failing_test="tests/test_login.py::test_vazia",
        evidence="FAILED tests/test_login.py::test_vazia - assert True is False"))
    assert r.status == "created" and r.issue_number == 2


def test_zona_cinzenta_usa_llm(tmp_path):
    chamadas = []
    juiz = lambda rep, iss: chamadas.append(iss["number"]) or True
    a = IssueManagerAgent(FakeGitHub(), audit_log=tmp_path / "a.jsonl", llm_judge=juiz)
    a.process(desconto_report())
    r = a.process(desconto_report(title="Desconto do carrinho calculado de forma errada",
                                  failing_test=None))
    assert chamadas == [1] and r.status == "duplicate"


def test_liga_pr_a_issue(agent):
    agent.process(desconto_report())
    agent.gh.pulls[7] = {"body": "Corrige o cálculo.", "head": {"ref": "fix/issue-1-x"}}
    agent.link_pull_request(1, 7, test_summary="5 passed")
    assert "Closes #1" in agent.gh.pulls[7]["body"]
    assert "PR #7" in agent.gh.comments[-1][1]


def test_audit_log(agent):
    agent.process(desconto_report())
    acoes = [json.loads(l)["action"] for l in agent.audit_path.read_text().splitlines()]
    assert acoes == ["received", "created"]


def test_no_langgraph(agent):
    node = make_langgraph_node(agent)
    out = node({"bug_report": desconto_report().model_dump(mode="json")})
    assert out["issue"]["status"] == "created"


def test_repo_fora_da_allowlist():
    with pytest.raises(RepoNotAllowed):
        GitHubClient("xdsoftware/producao", token="t", allowed_repos={"cadu/repo-teste"})


def test_caminho_absoluto_rejeitado():
    with pytest.raises(ValueError):
        desconto_report(files=["/etc/passwd"])
