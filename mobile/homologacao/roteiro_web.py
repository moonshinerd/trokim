"""Roteiro de homologação da Semana 5 no Chrome emulando um Pixel 7 (#100).

Pré-requisitos: o app web servido na porta 8091 (`preparar_web.sh`), o Ollama com
`qwen2.5:1.5b` em 127.0.0.1:11434 e o Playwright (`uv run --with playwright`).
A API sobe sozinha na porta 8010 com um banco temporário, só com dados sintéticos.

Uso: uv run --with playwright python mobile/homologacao/roteiro_web.py <pasta-dos-prints> [--visao]
`--visao` também testa o modelo remoto (OpenRouter); a chave vem de OPENROUTER_API_KEY.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
DADOS = ROOT / "research" / "synthetic_data"
UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36"
)
OUT = Path(sys.argv[1])
VISAO = "--visao" in sys.argv
LOG = []


def subir_api(visao=False):
    subprocess.run("fuser -k 8010/tcp", shell=True, capture_output=True)
    time.sleep(2)
    env = dict(
        os.environ,
        DATABASE_URL=f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/homologacao.db",
        LLM_API_BASE="http://127.0.0.1:11434",
        LLM_MODEL="ollama/qwen2.5:1.5b",
    )
    if visao:
        env.update(
            VISION_PROVIDER="litellm",
            VISION_MODEL="openrouter/google/gemini-2.5-flash-lite",
            VISION_API_KEY=os.environ["OPENROUTER_API_KEY"],
        )
    cmd = "uv run --frozen --extra documents --extra ocr uvicorn app.main:app --port 8010"
    subprocess.Popen(
        cmd,
        shell=True,
        cwd=ROOT / "api",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    for _ in range(90):
        try:
            urllib.request.urlopen("http://localhost:8010/v1/accounts", timeout=1)
            return
        except OSError:
            time.sleep(1)
    raise SystemExit("A API não subiu.")


async def abrir(p):
    b = await p.chromium.launch(
        channel="chrome",
        headless=True,
        args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
    )
    ctx = await b.new_context(
        viewport={"width": 412, "height": 915},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        user_agent=UA,
        locale="pt-BR",
    )
    page = await ctx.new_page()
    page.on("pageerror", lambda e: print("ERRO NA PÁGINA", e.message[:200]))
    await page.goto("http://localhost:8091/")
    await page.wait_for_timeout(9000)
    return b, page


async def rolar(page, dy):
    cdp = await page.context.new_cdp_session(page)
    await cdp.send(
        "Input.synthesizeScrollGesture",
        {"x": 206, "y": 450, "yDistance": -int(dy), "gestureSourceType": "touch", "speed": 1500},
    )
    await page.wait_for_timeout(900)


async def _achar(page, texto, nth):
    achados = []
    for e in await page.query_selector_all("flt-semantics"):
        rotulo = (await e.get_attribute("aria-label")) or ""
        txt = await e.evaluate(
            "e => [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('')"
        )
        if texto in rotulo or texto in txt:
            box = await e.bounding_box()
            if box and box["width"] > 0 and box["height"] > 0:
                achados.append(box)
    return achados[nth] if len(achados) > nth else None


async def tocar(page, texto, nth=0):
    for _ in range(6):
        box = await _achar(page, texto, nth)
        if box is None:
            raise SystemExit(f"Não achei {texto!r} na tela.")
        cy = box["y"] + box["height"] / 2
        if 60 <= cy <= 820:
            break
        await rolar(page, cy - 450)
    await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    await page.wait_for_timeout(1200)


async def escolher(page, botao, caminho):
    async with page.expect_file_chooser(timeout=15000) as fc:
        await tocar(page, botao)
    await (await fc.value).set_files(str(caminho))
    await page.wait_for_timeout(1500)


async def foto(page, nome, nota):
    await page.screenshot(path=OUT / f"{nome}.png")
    LOG.append({"print": nome, "nota": nota})
    print("PRINT", nome, "-", nota, flush=True)


async def perguntar(page, pergunta, nome, nota):
    await page.mouse.click(180, 795)
    await page.keyboard.type(pergunta, delay=15)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(40000)
    await foto(page, nome, nota)


async def esperar(page, texto, ms=60000):
    for _ in range(ms // 1000):
        if await _achar(page, texto, 0):
            return
        await page.wait_for_timeout(1000)
    raise SystemExit(f"{texto!r} não apareceu em {ms // 1000} s.")


async def importar_fatura(page, abrir=True):
    if abrir:
        await tocar(page, "Importar extrato")
        await page.wait_for_timeout(1200)
    await escolher(page, "Já tenho o arquivo", DADOS / "fatura_nubank_aberta_pessoal.ofx")
    await page.wait_for_timeout(2000)
    await tocar(page, "Importar como Conta pessoal")
    await page.wait_for_timeout(5000)


async def documentos_e_chat(p):
    subir_api()
    b, page = await abrir(p)
    await foto(page, "01-resumo-vazio", "App aberto sem dados (emulação Pixel 7, 412 px)")
    await tocar(page, "Extratos")
    await tocar(page, "Fotografar ou escolher documento")
    await escolher(page, "Escolher imagem", DADOS / "document_images" / "D02.png")
    await foto(page, "02-previa-documento", "Prévia do comprovante D02 antes da leitura")
    await tocar(page, "Ler documento")
    await esperar(page, "Confirmar")
    await foto(
        page, "03-revisao-ocr", "OCR local leu banco, valor, data e favorecido (nome colado)"
    )
    await page.mouse.click(206, 630)  # campo Favorecido
    await page.keyboard.press("Control+A")
    await page.keyboard.type("Pessoa Exemplo Alfa", delay=15)
    await foto(page, "04-favorecido-corrigido", "Favorecido corrigido antes de confirmar")
    await tocar(page, "Confirmar")
    await page.wait_for_timeout(3000)
    await foto(page, "05-confirmado", "Lançamento criado com o selo Documento")
    await tocar(page, "Fotografar ou escolher documento")
    await escolher(page, "Escolher imagem", DADOS / "document_images" / "D32.png")
    await tocar(page, "Ler documento")
    await page.wait_for_timeout(8000)
    await foto(page, "06-ilegivel", "Foto ilegível D32: nenhum campo, pede nova foto")
    await tocar(page, "Back")
    await page.wait_for_timeout(1500)
    await tocar(page, "Fotografar ou escolher documento")
    await escolher(page, "Escolher PDF", DADOS / "document_images" / "D05.pdf")
    await tocar(page, "Ler documento")
    await esperar(page, "Descartar")
    await foto(
        page, "07-pdf-fatura", "PDF de fatura D05: a data obrigatória bloqueia a confirmação"
    )
    await tocar(page, "Descartar")
    await page.wait_for_timeout(1500)
    await tocar(page, "Importar extrato")
    await page.wait_for_timeout(1200)
    await foto(page, "08-bancos-suportados", "Bancos com selos Validado e Experimental")
    await importar_fatura(page, abrir=False)
    await foto(page, "09-extrato-importado", "Fatura aberta sintética importada como conta pessoal")
    await tocar(page, "Ainda está aberta")
    await tocar(page, "Concluir")
    await page.wait_for_timeout(2500)
    await foto(page, "09b-extratos-lista", "Extratos: documento confirmado e fatura importada")
    await tocar(page, "Ajustes")
    await tocar(page, "Modo multiagente")
    await foto(page, "10-multiagente-ligado", "Modo multiagente ligado em Ajustes")
    await tocar(page, "Assistente")
    await page.wait_for_timeout(2000)
    await foto(page, "11-chat-seletores", "Seletores de conta e período e perguntas sugeridas")
    await perguntar(
        page,
        "Quanto gastei na Pessoa Exemplo Alfa?",
        "12-chat-documento",
        "A resposta usa o lançamento confirmado da foto",
    )
    await perguntar(
        page,
        "Quais parcelas ainda tenho a pagar?",
        "13-chat-parcelas",
        "Parcelas a pagar calculadas por código",
    )
    await tocar(page, "Período")
    await tocar(page, "Fatura aberta")  # o primeiro é o item do menu
    await perguntar(
        page,
        "Quanto gastei?",
        "14-chat-fatura-aberta",
        "Período na fatura aberta: resposta retida, card do cálculo mantido",
    )
    await b.close()


async def banco_e_sugestao(p):
    subir_api()
    b, page = await abrir(p)
    await tocar(page, "Extratos")
    await tocar(page, "Importar extrato")
    await page.wait_for_timeout(1000)
    await tocar(page, "Ver como exportar", nth=2)  # PicPay
    await foto(page, "15-tutorial-picpay", "Tutorial do PicPay, banco experimental")
    await b.close()
    b, page = await abrir(p)
    await tocar(page, "Extratos")
    await importar_fatura(page)
    await tocar(page, "Ainda está aberta")
    await tocar(page, "Concluir")
    await tocar(page, "Ajustes")
    await tocar(page, "Modo multiagente")
    await tocar(page, "Assistente")
    await page.wait_for_timeout(1500)
    await tocar(page, "Gastos de nov/2026")
    await page.wait_for_timeout(40000)
    await foto(page, "16-sugestao-mes", "Sugestão do último mês com lançamentos (nov/2026)")
    await b.close()


async def chat_generativo(p):
    """Cenários do roteiro da Semana 3 (VALIDACAO_CHAT_GENERATIVO.md), modo de agente único."""
    subir_api()
    b, page = await abrir(p)
    await tocar(page, "Assistente")
    await page.wait_for_timeout(1500)
    await perguntar(
        page,
        "Como montar uma reserva de emergência?",
        "21-chat-fundamentado",
        "Resposta fundamentada com cartões de fonte oficial",
    )
    await page.mouse.click(382, 28)  # interruptor Auditoria pedagógica
    await page.wait_for_timeout(1500)
    await foto(page, "22-auditoria", "Auditoria pedagógica ligada")
    await perguntar(
        page,
        "Escreva um poema sobre futebol",
        "23-abstencao",
        "Fora do escopo: abstenção com perguntas rápidas",
    )
    subprocess.run("fuser -k 8010/tcp", shell=True, capture_output=True)
    await page.wait_for_timeout(3000)
    await perguntar(
        page,
        "Como organizar o orçamento?",
        "24-api-fora",
        "API desligada: erro amigável e Tentar novamente",
    )
    subir_api()
    await tocar(page, "Tentar novamente")
    await page.wait_for_timeout(40000)
    await foto(page, "25-nova-tentativa", "API de volta: resposta sem duplicar a pergunta")
    await b.close()


async def visao_remota(p):
    subir_api(visao=True)
    b, page = await abrir(p)
    await tocar(page, "Ajustes")
    for _ in range(3):
        await rolar(page, 700)
    await foto(page, "26-ajustes-motores", "OCR local e modelo de visão remoto disponíveis")
    await tocar(page, "Modelo de visão remoto")
    await foto(page, "27-dialogo-consentimento", "O app pede consentimento antes de qualquer envio")
    await tocar(page, "Concordo com o envio")
    await foto(page, "28-consentimento-ligado", "Visão remota escolhida, com consentimento salvo")
    await tocar(page, "Extratos")
    await tocar(page, "Fotografar ou escolher documento")
    await escolher(page, "Escolher imagem", DADOS / "document_images" / "D12.jpg")
    await tocar(page, "Ler documento")
    await page.wait_for_timeout(30000)
    await foto(page, "29-leitura-com-visao", "Fatura D12 lida com OCR e visão remota")
    await b.close()


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        await documentos_e_chat(p)
        await banco_e_sugestao(p)
        await chat_generativo(p)
        if VISAO:
            await visao_remota(p)
    (OUT / "roteiro.json").write_text(json.dumps(LOG, ensure_ascii=False, indent=1))
    subprocess.run("fuser -k 8010/tcp", shell=True, capture_output=True)


if __name__ == "__main__":
    asyncio.run(main())
