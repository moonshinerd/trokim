"""Ajuste de categoria pelo usuário e regras aprendidas por estabelecimento (#80, RF09)."""

import pytest

from tests.helpers_api import cliente, enviar
from tests.nubank_samples import CONTA_PF, extrato_conta, fatura_cartao, lancamento

D = lancamento


def _fatura(fitid_extra: str = "c3", inicio: str = "20261103", fim: str = "20261110") -> bytes:
    return fatura_cartao(
        [
            D("DEBIT", "20261104", "-55.00", f"{fitid_extra}a", "Eletro Exemplo"),
            D("DEBIT", "20261105", "-20.00", f"{fitid_extra}b", "Eletro Exemplo - Parcela 1/3"),
            D("DEBIT", "20261106", "-12.00", f"{fitid_extra}c", "Bazar Exemplo"),
        ],
        inicio=inicio,
        fim=fim,
    )


async def _uid(c, nome: str) -> str:
    txs = (await c.get("/v1/transactions")).json()
    return next(t["uid"] for t in txs if t["merchant"] == nome)


@pytest.mark.asyncio
async def test_corrigir_categoria_vale_para_todo_o_estabelecimento():
    async with cliente() as c:
        await enviar(c, _fatura(), "fatura.ofx", "pessoal")
        uid = await _uid(c, "Eletro Exemplo")
        r = await c.patch(f"/v1/transactions/{uid}/category", json={"category": "moradia"})
        assert r.status_code == 200
        corpo = r.json()
        txs = (await c.get("/v1/transactions")).json()
        resumo = (await c.get("/v1/transactions/summary")).json()
    assert corpo == {"updated": 2, "merchant": "Eletro Exemplo", "rule": True}
    eletro = [t["category"] for t in txs if t["merchant"] == "Eletro Exemplo"]
    assert eletro == ["moradia", "moradia"]
    bazar = next(t for t in txs if t["merchant"] == "Bazar Exemplo")
    assert bazar["category"] == "outros"
    assert resumo["expenses_by_category"]["moradia"] == 75.0


@pytest.mark.asyncio
async def test_regra_aprendida_vale_para_o_proximo_arquivo():
    async with cliente() as c:
        await enviar(c, _fatura(), "fatura_nov.ofx", "pessoal")
        uid = await _uid(c, "Bazar Exemplo")
        await c.patch(f"/v1/transactions/{uid}/category", json={"category": "educacao"})
        corpo = (
            await enviar(
                c,
                _fatura("d", inicio="20261203", fim="20261210"),
                "fatura_dez.ofx",
                "pessoal",
            )
        ).json()
        txs = (await c.get("/v1/transactions")).json()
        regras = (await c.get("/v1/transactions/category-rules")).json()
    assert [t["category"] for t in txs if t["merchant"] == "Bazar Exemplo"] == [
        "educacao",
        "educacao",
    ]
    # o arquivo novo traz 2 lançamentos do Eletro sem regra; o bazar já vem categorizado
    assert corpo["uncategorized_count"] == 2
    assert regras == [{"merchant": "bazar exemplo", "category": "educacao"}]


@pytest.mark.asyncio
async def test_so_este_lancamento_nao_cria_regra():
    async with cliente() as c:
        await enviar(c, _fatura(), "fatura.ofx", "pessoal")
        uid = await _uid(c, "Eletro Exemplo")
        r = await c.patch(
            f"/v1/transactions/{uid}/category",
            json={"category": "lazer", "apply_to_merchant": False},
        )
        txs = (await c.get("/v1/transactions")).json()
        regras = (await c.get("/v1/transactions/category-rules")).json()
    assert r.json() == {"updated": 1, "merchant": None, "rule": False}
    assert sorted(t["category"] for t in txs if t["merchant"] == "Eletro Exemplo") == [
        "lazer",
        "outros",
    ]
    assert regras == []


@pytest.mark.asyncio
async def test_remover_regra_mantem_o_que_ja_mudou_e_para_de_aplicar():
    async with cliente() as c:
        await enviar(c, _fatura(), "fatura_nov.ofx", "pessoal")
        uid = await _uid(c, "Bazar Exemplo")
        await c.patch(f"/v1/transactions/{uid}/category", json={"category": "educacao"})
        r = await c.delete("/v1/transactions/category-rules/Bazar Exemplo")
        assert r.status_code == 200
        await enviar(c, _fatura("d", "20261203", "20261210"), "fatura_dez.ofx", "pessoal")
        txs = (await c.get("/v1/transactions")).json()
        assert (await c.delete("/v1/transactions/category-rules/nada")).status_code == 404
    assert sorted(t["category"] for t in txs if t["merchant"] == "Bazar Exemplo") == [
        "educacao",
        "outros",
    ]


@pytest.mark.asyncio
async def test_movimentacao_interna_e_gasto_como_renda_sao_recusados():
    conta = extrato_conta(
        [
            D("DEBIT", "20261005", "-250.00", "p1", "Pagamento de fatura"),
            D("DEBIT", "20261006", "-30.00", "p2", "Compra no débito - LOJA EXEMPLO"),
        ],
        acct=CONTA_PF,
    )
    async with cliente() as c:
        await enviar(c, conta, "conta.ofx", "pessoal")
        txs = (await c.get("/v1/transactions")).json()
        fatura = next(t["uid"] for t in txs if t["nature"] == "pagamento_fatura")
        compra = next(t["uid"] for t in txs if t["nature"] == "compra")
        r1 = await c.patch(f"/v1/transactions/{fatura}/category", json={"category": "lazer"})
        r2 = await c.patch(f"/v1/transactions/{compra}/category", json={"category": "renda"})
        r3 = await c.patch("/v1/transactions/nada/category", json={"category": "lazer"})
        r4 = await c.patch(f"/v1/transactions/{compra}/category", json={"category": "xyz"})
    assert r1.status_code == 400
    assert r2.status_code == 400
    assert r3.status_code == 404
    assert r4.status_code == 422


@pytest.mark.asyncio
async def test_limpar_extratos_apaga_as_regras():
    async with cliente() as c:
        await enviar(c, _fatura(), "fatura.ofx", "pessoal")
        uid = await _uid(c, "Bazar Exemplo")
        await c.patch(f"/v1/transactions/{uid}/category", json={"category": "educacao"})
        await c.delete("/v1/transactions/clear")
        assert (await c.get("/v1/transactions/category-rules")).json() == []
