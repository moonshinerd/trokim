"""Valida o gabarito multiagente: schema, manifesto e números calculados do ledger sintético."""

import copy
import json
import math

import pytest
from jsonschema import Draft202012Validator, ValidationError, validate
from rag_benchmark.multiagent import (
    GENERATOR,
    LEDGER,
    MANIFEST,
    QUESTIONS,
    SCHEMA,
    load_ledger,
    manifest,
    resolve,
)

from app.domain.agents import AgentContext, AgentName, AgentStep, StepStatus
from app.services.agents.analysis import AnalysisAgent
from app.services.agents.orchestrator import Orchestrator, needs_analysis
from app.services.agents.validation import ValidationAgent

MESES_DO_LEDGER = 3


def test_manifesto_confere_hashes():
    assert json.loads(MANIFEST.read_text(encoding="utf-8")) == manifest()


def test_gabarito_valida_pelo_schema_e_tem_composicao_esperada():
    cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validate(cases, schema)
    counts: dict[str, int] = {}
    for case in cases["cases"]:
        counts[case["category"]] = counts.get(case["category"], 0) + 1
    assert counts == {"evidencia": 5, "calculo": 5, "evidencia_calculo": 5, "armadilha": 5}
    assert {c["id"] for c in cases["cases"]} == {f"M{i:02d}" for i in range(1, 21)}
    assert len({c["question"] for c in cases["cases"]}) == 20


def test_ledger_e_reproduzivel_pelo_gerador():
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen_ledger", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build() == json.loads(LEDGER.read_text(encoding="utf-8"))


def test_ledger_tem_duplicatas_e_tres_meses():
    ledger = load_ledger()
    assert len(ledger) == 31
    assert sum(tx.is_duplicate for tx in ledger) == 3
    assert sum(not tx.is_duplicate and tx.type == "debit" for tx in ledger) == 24
    assert len({(tx.date.year, tx.date.month) for tx in ledger}) == MESES_DO_LEDGER


def _numeros():
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    return [(c["id"], n) for c in data["cases"] for n in c["expected_numbers"]]


@pytest.mark.parametrize(
    ("case_id", "number"), _numeros(), ids=lambda v: v if isinstance(v, str) else v["key"]
)
def test_numeros_do_gabarito_batem_com_calculation_service(case_id, number):
    esperado = resolve(number["key"], number.get("params", {}), load_ledger())
    assert math.isclose(number["value"], esperado, abs_tol=0.005), case_id


def test_status_agentes_e_codigos_sao_coerentes():
    cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        if case["category"] == "armadilha":
            assert case["expected_status"] == "rejected"
            assert case["expected_validation_code"]
        else:
            assert case["expected_status"] == "answered"
        has_numbers = bool(case["expected_numbers"])
        assert has_numbers == (case["category"] in {"calculo", "evidencia_calculo"})
        assert ("analysis" in case["expected_agents"]) == has_numbers or case[
            "category"
        ] == "armadilha"


def test_schema_rejeita_gabarito_invalido():
    cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for mutate in (
        lambda d: d["cases"].pop(),
        lambda d: d["cases"][0].update(expected_status="talvez"),
        lambda d: d["cases"][0].update(extra=1),
        lambda d: d["cases"][0].update(expected_validation_code="OUT_OF_SCOPE_ADVICE"),
        lambda d: d["cases"][-1].update(expected_validation_code=None),
        lambda d: d["cases"][-1].pop("validation_fixture"),
        lambda d: d["cases"][-1].update(expected_status="abstained"),
        lambda d: d["cases"][5]["expected_numbers"][0].update(unit="%"),
        lambda d: d["cases"][6]["expected_numbers"][0].pop("params"),
        lambda d: d["cases"][8]["expected_numbers"][0]["params"].update(monthly_savings=0),
    ):
        broken = copy.deepcopy(cases)
        mutate(broken)
        with pytest.raises(ValidationError):
            validate(broken, schema)


class FixtureResearchAgent:
    """Injeta contexto controlado sem depender de recuperação ou modelo externo."""

    name = AgentName.RESEARCH

    async def run(self, ctx: AgentContext) -> AgentStep:
        return AgentStep(
            agent=self.name, status=StepStatus.OK, summary="Contexto sintético preparado."
        )


class FixtureCommunicationAgent:
    """Repete o rascunho adversarial mesmo após revisão, exercitando rejeição persistente."""

    name = AgentName.COMMUNICATION

    def __init__(self, fixture: dict) -> None:
        self.fixture = fixture

    async def run(self, ctx: AgentContext) -> AgentStep:
        ctx.draft_answer = self.fixture["draft_answer"]
        ctx.abstain_reason = self.fixture["abstain_reason"]
        return AgentStep(
            agent=self.name, status=StepStatus.OK, summary="Rascunho adversarial injetado."
        )


ARMADILHAS = [
    case
    for case in json.loads(QUESTIONS.read_text(encoding="utf-8"))["cases"]
    if case["category"] == "armadilha"
]


@pytest.mark.parametrize("case", ARMADILHAS, ids=lambda case: case["id"])
async def test_armadilhas_rejeitam_rascunho_com_codigo_e_agentes_esperados(case):
    fixture = case["validation_fixture"]
    response = await Orchestrator(
        research=FixtureResearchAgent(),
        analysis=AnalysisAgent(),
        communication=FixtureCommunicationAgent(fixture),
        validation=ValidationAgent(),
    ).run(case["question"], load_ledger() if fixture["use_ledger"] else [])
    assert response.status == case["expected_status"]
    assert case["expected_validation_code"] in {issue.code for issue in response.validation_issues}
    successful = list(
        dict.fromkeys(step.agent.value for step in response.steps if step.status == "ok")
    )
    assert successful == case["expected_agents"]
    assert response.answer != fixture["draft_answer"]
    assert sum(step.agent == AgentName.VALIDATION for step in response.steps) == 2


@pytest.mark.parametrize("case", ARMADILHAS, ids=lambda case: case["id"])
async def test_abstencao_na_pesquisa_nao_exige_codigo_de_validacao(case):
    class AbstainingResearchAgent:
        name = AgentName.RESEARCH

        async def run(self, ctx: AgentContext) -> AgentStep:
            ctx.abstain_reason = "sem_evidencia"
            return AgentStep(agent=self.name, status=StepStatus.ABSTAINED, summary="Sem evidência.")

    response = await Orchestrator(
        research=AbstainingResearchAgent(),
        analysis=AnalysisAgent(),
        communication=FixtureCommunicationAgent(case["validation_fixture"]),
        validation=ValidationAgent(),
    ).run(case["question"], load_ledger())
    assert response.status == "abstained"
    assert response.validation_issues == []
    assert [step.agent for step in response.steps] == [AgentName.RESEARCH]


CASOS_REGULARES = [
    case
    for case in json.loads(QUESTIONS.read_text(encoding="utf-8"))["cases"]
    if case["category"] != "armadilha"
]


@pytest.mark.parametrize("case", CASOS_REGULARES, ids=lambda case: case["id"])
async def test_roteamento_e_numeros_regulares_batem_com_analysis(case):
    ctx = AgentContext(question=case["question"], transactions=load_ledger())
    analysis_ok = False
    if needs_analysis(ctx.question):
        step = await AnalysisAgent().run(ctx)
        analysis_ok = step.status == StepStatus.OK
    agents = ["research"] + (["analysis"] if analysis_ok else []) + ["communication", "validation"]
    assert case["expected_agents"] == agents
    actual = {calculation.key: calculation.value for calculation in ctx.calculations}
    for number in case["expected_numbers"]:
        key = number["key"]
        if key == "category_expense":
            key = "expense_" + number["params"]["category"]
        elif key == "category_share":
            key = "share_" + number["params"]["category"]
        assert math.isclose(actual[key], number["value"], rel_tol=0, abs_tol=0.005)
