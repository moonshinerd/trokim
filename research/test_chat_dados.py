import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from jsonschema import ValidationError

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "rag_benchmark"))

chat = __import__("chat_dados")
runner = __import__("run_chat_dados")
models = __import__("app.domain.agents", fromlist=["MultiAgentResponse"])


def test_schema_manifest_and_oracle():
    assert len(chat.validate()) == 20


def test_generator_reproducible():
    path = HERE / "synthetic_data/generate_chat_dados.py"
    spec = importlib.util.spec_from_file_location("generate_chat_dados", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ledger = module.generate()
    assert ledger == module.generate() == json.loads(chat.LEDGER.read_text())
    assert {tx["date"][:7] for tx in ledger["transactions"]} == set(ledger["months"])
    assert {a["owner"] for a in ledger["accounts"]} == {"pessoal", "empresa"}
    assert {s["status"] for s in ledger["statements"]} == {"aberta", "fechada"}


def test_oracle_uses_calculation_service(monkeypatch):
    calls = []
    original = chat.CalculationService.calculate_summary

    def tracked(transactions, *args, **kwargs):
        calls.append(len(transactions))
        return original(transactions, *args, **kwargs)

    monkeypatch.setattr(chat.CalculationService, "calculate_summary", tracked)
    for question in chat.validate():
        if question["behavior"] == "answer":
            before = len(calls)
            assert chat.expected_values(question["recipe"], chat.load_library())
            assert len(calls) > before


def test_schema_rejects_extra_field():
    questions = json.loads(chat.QUESTIONS.read_text())
    questions[0]["surpresa"] = True
    with pytest.raises(ValidationError):
        chat.Draft202012Validator(json.loads(chat.SCHEMA.read_text())).validate(questions)


def test_manifest_detects_changed_hash(tmp_path, monkeypatch):
    manifest = json.loads(chat.MANIFEST.read_text())
    manifest["files"]["research/rag_benchmark/questions_chat_dados.json"] = "0" * 64
    target = tmp_path / "manifest.json"
    target.write_text(json.dumps(manifest))
    monkeypatch.setattr(chat, "MANIFEST", target)
    with pytest.raises(ValueError, match="Manifesto divergente"):
        chat.validate()


def test_oracle_rejects_handwritten_value(tmp_path, monkeypatch):
    questions = json.loads(chat.QUESTIONS.read_text())
    questions[0]["expected"][0]["value"] += 1
    target = tmp_path / "questions.json"
    target.write_text(json.dumps(questions))
    monkeypatch.setattr(chat, "QUESTIONS", target)
    with pytest.raises(ValueError, match="Gabarito divergente: C01"):
        chat.validate()


def test_repeat_run_refused(tmp_path):
    runner.reserve_run("ensaio", tmp_path)
    with pytest.raises(FileExistsError):
        runner.reserve_run("ensaio", tmp_path)
    with pytest.raises(ValueError):
        runner.reserve_run("../escape", tmp_path)


@pytest.mark.parametrize(
    "text,correct",
    [
        ("R$ 1.234,56", True),
        ("1234.56 BRL", True),
        ("-1234.56 BRL", False),
        ("1234.56 USD", False),
        ("1234.56%", False),
    ],
)
def test_numeric_units_and_sign(text, correct):
    assert runner.contains_value(text, {"value": 1234.56}) is correct


class SafeProvider:
    async def generate(self, prompt, **kwargs):
        response = __import__("app.models.llm_provider", fromlist=["LLMResponse"])
        return response.LLMResponse(content="Consulta aos dados importados.", model="teste")


@pytest.mark.parametrize("question", json.loads(chat.QUESTIONS.read_text()), ids=lambda q: q["id"])
def test_real_path_without_network(question):
    async def execute():
        provider = runner.RecordingProvider(SafeProvider())
        validation = runner.RecordingValidation()
        orchestrator = runner.Orchestrator(
            research=runner.ResearchAgent(),
            analysis=runner.AnalysisAgent(),
            communication=runner.CommunicationAgent(llm_provider=provider),
            validation=validation,
        )
        response = await runner.AgentQueryService(orchestrator).run(
            question["question"],
            library=chat.load_library(),
            filters=runner.FinancialFilters(**question["filters"]),
        )
        metrics = runner.evaluate(question, response, provider.calls, validation.contexts)
        if question["behavior"] == "answer":
            assert metrics["numeric_case_correct"], response.model_dump()
        else:
            assert metrics["abstention_correct"], response.model_dump()
        assert not metrics["technical_failure"]
        assert metrics["final_invented_numbers"] == 0

    asyncio.run(execute())


def test_rejected_is_not_numeric_success():
    question = {
        "expected": [{"key": "total_expenses", "value": 100, "unit": "BRL"}],
        "behavior": "answer",
    }
    response = models.MultiAgentResponse(
        query="teste",
        status="rejected",
        answer="100 BRL",
        calculations=[
            models.CalculationResult(
                key="total_expenses", label="Gasto", value=100, unit="BRL", source="teste"
            )
        ],
    )
    metrics = runner.evaluate(question, response, [], [])
    assert metrics["numeric_correct"] == 0


def test_raw_model_invention_is_not_hidden_by_fallback():
    response = models.MultiAgentResponse(
        query="teste",
        status="answered",
        answer="100 BRL",
        calculations=[
            models.CalculationResult(
                key="total_expenses", label="Gasto", value=100, unit="BRL", source="teste"
            )
        ],
    )
    metrics = runner.evaluate(
        {"expected": [], "behavior": "answer"},
        response,
        [{"content": "Gasto de R$ 999,00"}],
        [{"notes": [], "issues": [], "step": {"status": "ok"}}],
    )
    assert metrics["raw_model_invented_numbers"] == 1
    assert metrics["final_invented_numbers"] == 0
