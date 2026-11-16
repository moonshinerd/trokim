import 'package:flutter/material.dart';

/// Prepara o texto de uma resposta do LLM para exibir no chat.
///
/// O modelo costuma terminar a resposta com um bloco "**Fontes:**" com as URLs.
/// No app isso é redundante (e não é clicável): as fontes aparecem nos cartões
/// de evidência logo abaixo, com link que abre o documento oficial. Por isso o
/// bloco e as URLs soltas saem do texto; os marcadores [1], [2]… ficam e
/// correspondem à numeração dos cartões.
class AnswerFormat {
  AnswerFormat._();

  static final _sourcesBlock = RegExp(
    r'\n[ \t]*(?:\*\*|__)?[ \t]*(?:Fontes?|Refer[eê]ncias?)[ \t]*:?[ \t]*(?:\*\*|__)?[ \t]*:?[ \t]*(?:\n|$)[\s\S]*$',
    caseSensitive: false,
  );
  static final _url = RegExp(r'[ \t]*[(<\[]?https?://[^\s)>\]]+[)>\]]?');
  static final _token = RegExp(r'\*\*(.+?)\*\*|\[(\d{1,2})\]');

  /// Remove o bloco de fontes e as URLs soltas.
  static String clean(String raw) {
    var text = raw.replaceAll('\r\n', '\n');
    final block = _sourcesBlock.firstMatch(text);
    // Só corta se houver resposta antes do bloco de fontes.
    if (block != null && block.start > 0) text = text.substring(0, block.start);
    text = text
        .replaceAll(_url, '')
        .replaceAll(RegExp(r'\(\s*\)'), '')
        .replaceAll(RegExp(r'[ \t]+\n'), '\n')
        .replaceAll(RegExp(r'\n{3,}'), '\n\n');
    return text.trim();
  }

  /// Converte **negrito** e os marcadores [n] em spans estilizados.
  ///
  /// Cada marcador [n] vira o que [citation] devolver (ex.: um botão que leva
  /// ao cartão da fonte). Sem [citation], fica um texto colorido.
  static List<InlineSpan> spans(
    String cleaned,
    TextStyle base, {
    required Color citationColor,
    InlineSpan Function(int number)? citation,
  }) {
    final out = <InlineSpan>[];
    var pos = 0;
    for (final m in _token.allMatches(cleaned)) {
      if (m.start > pos) {
        out.add(TextSpan(text: cleaned.substring(pos, m.start)));
      }
      if (m.group(1) != null) {
        out.add(
          TextSpan(
            text: m.group(1),
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
        );
      } else if (citation != null) {
        out.add(citation(int.parse(m.group(2)!)));
      } else {
        out.add(
          TextSpan(
            text: '[${m.group(2)}]',
            style: TextStyle(
              color: citationColor,
              fontWeight: FontWeight.w800,
              fontSize: (base.fontSize ?? 14) * 0.82,
            ),
          ),
        );
      }
      pos = m.end;
    }
    if (pos < cleaned.length) out.add(TextSpan(text: cleaned.substring(pos)));
    return out;
  }
}
