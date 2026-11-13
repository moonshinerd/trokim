# 0011 — Mascote onça-pintada e arte de marca com licença livre e arquivos trocáveis

- **Status:** Aceita
- **Data:** 13/11/2026
- **Requisitos / GQs:** RNF11; GQ01, GQ03
- **Issues:** #40, #42

## Contexto

"Trokim" vem de "troquinho", que vem de "troco". O time quis uma logo com
sentido, um mascote com presença (a onça-pintada, ilustrada na nota de R$ 50) e
um visual de moeda premium. Tentativas de desenhar a onça à mão, em código, não
atingiram a qualidade de marca esperada. Usar arte de terceiros sem licença
adequada traria risco jurídico.

## Decisão

- Partir do vetor *Jaguar SVG* de Jordan Irwin (AntumDeluge), em
  [OpenGameArt](https://opengameart.org/node/98089) sob **CC0 (domínio
  público)**. Removemos o cenário, recolorimos em quatro tons dourados com as
  manchas vazadas e geramos duas versões: corpo inteiro e cabeça.
- A arte fica em `mobile/assets/brand/` (`mascot_body.png` e `mascot_head.png`) e
  é carregada em tempo de execução. **Trocar a arte exige apenas substituir os
  dois arquivos**, sem alterar código. Instruções no `LEIA-ME.md` da pasta.
- A moeda 3D da abertura é desenhada em código (`CoinPainter`); a onça é uma
  imagem aplicada sobre a face.
- Créditos registrados em `docs/referencias.md` e no `LEIA-ME.md`, mesmo sem
  obrigatoriedade.
- Qualquer arte nova deve ser própria ou ter licença que permita uso comercial
  (CC0, domínio público ou licença paga), com a origem registrada no PR.

## Consequências

Marca com qualidade profissional e sem risco de licença. A arte pode ser
refinada por um designer sem tocar no código. A abertura depende de dois PNGs de
cerca de 1 MB no pacote do app.
