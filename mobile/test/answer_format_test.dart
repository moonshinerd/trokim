import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/features/chat_assistant/domain/answer_format.dart';

void main() {
  group('AnswerFormat.clean', () {
    test('remove o bloco de fontes e mantém a resposta', () {
      const raw =
          'A reserva cobre 3 a 6 meses [1].\n\n'
          '**Fontes:**\n'
          '[1] CVM, Documento: Reserva, SEÇÃO 1.\n'
          '[2] BCB, Documento: Orçamento.';
      expect(AnswerFormat.clean(raw), 'A reserva cobre 3 a 6 meses [1].');
    });

    test('remove URLs soltas e parênteses vazios', () {
      const raw =
          'Veja a norma (https://www.bcb.gov.br/x) e também https://cvm.gov.br/y fim.';
      expect(AnswerFormat.clean(raw), 'Veja a norma e também fim.');
    });

    test('não corta quando "Fontes" é a primeira linha', () {
      expect(
        AnswerFormat.clean('Fontes: o BCB define.'),
        'Fontes: o BCB define.',
      );
    });

    test('mantém texto sem fontes intacto e colapsa linhas em branco', () {
      expect(
        AnswerFormat.clean('Linha um.\n\n\n\nLinha dois.  '),
        'Linha um.\n\nLinha dois.',
      );
    });
  });

  test('spans: negrito e marcadores de citação viram spans estilizados', () {
    final spans = AnswerFormat.spans(
      'Use **liquidez diária** [1] sempre.',
      const TextStyle(fontSize: 14),
      citationColor: Colors.amber,
    ).cast<TextSpan>();
    expect(spans.map((s) => s.text).toList(), [
      'Use ',
      'liquidez diária',
      ' ',
      '[1]',
      ' sempre.',
    ]);
    expect(spans[1].style?.fontWeight, FontWeight.w800);
    expect(spans[3].style?.color, Colors.amber);
  });
}
