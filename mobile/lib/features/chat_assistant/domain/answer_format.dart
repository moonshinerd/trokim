import 'package:material_ui/material_ui.dart';

/// Prepara o texto de uma resposta do LLM para exibir no chat.
///
/// O modelo costuma citar fontes em formato markdown com link e nome da fonte,
/// por exemplo `[Banco Central do Brasil](url)` ou marcadores `[1]`.
/// As URLs soltas redundantes e blocos de fim de texto saem; os links com o nome
/// da fonte e marcadores viram spans clicáveis com o nome da fonte.
class AnswerFormat {
  AnswerFormat._();

  static final _sourcesBlock = RegExp(
    r'\n[ \t]*(?:\*\*|__)?[ \t]*(?:Fontes?|Refer[eê]ncias?)[ \t]*:?[ \t]*(?:\*\*|__)?[ \t]*:?[ \t]*(?:\n|$)[\s\S]*$',
    caseSensitive: false,
  );
  static final _token = RegExp(
    r'\[([^\]]+)\]\((https?://[^\)]+)\)|\*\*(.+?)\*\*|\[(\d{1,2})\]',
  );

  /// Remove o bloco de fontes redundante ao final e URLs soltas que não façam parte de links markdown.
  static String clean(String raw) {
    var text = raw.replaceAll('\r\n', '\n');
    final block = _sourcesBlock.firstMatch(text);
    // Só corta se houver resposta antes do bloco de fontes.
    if (block != null && block.start > 0) text = text.substring(0, block.start);
    // Remove apenas URLs soltas que NÃO estejam dentro de parênteses de markdown [label](url)
    text = text
        .replaceAll(RegExp(r'(?<!\]\()[ \t]*https?://[^\s)>\]]+[)>\]]?'), '')
        .replaceAll(RegExp(r'\(\s*\)'), '')
        .replaceAll(RegExp(r'[ \t]+\n'), '\n')
        .replaceAll(RegExp(r'\n{3,}'), '\n\n');
    return text.trim();
  }

  /// Converte markdown links [nome](url), **negrito** e marcadores [n] em spans estilizados.
  static List<InlineSpan> spans(
    String cleaned,
    TextStyle base, {
    required Color citationColor,
    InlineSpan Function(int number)? citation,
    InlineSpan Function(String label, String url)? link,
  }) {
    final out = <InlineSpan>[];
    var pos = 0;
    for (final m in _token.allMatches(cleaned)) {
      if (m.start > pos) {
        out.add(TextSpan(text: cleaned.substring(pos, m.start)));
      }
      if (m.group(1) != null && m.group(2) != null) {
        // Link em formato markdown [Nome da Fonte](url)
        final label = m.group(1)!;
        final url = m.group(2)!;
        if (link != null) {
          out.add(link(label, url));
        } else {
          out.add(
            TextSpan(
              text: label,
              style: TextStyle(
                color: citationColor,
                fontWeight: FontWeight.w700,
                decoration: TextDecoration.underline,
                decorationColor: citationColor.withValues(alpha: 0.5),
              ),
            ),
          );
        }
      } else if (m.group(3) != null) {
        // Negrito **texto**
        out.add(
          TextSpan(
            text: m.group(3),
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
        );
      } else if (m.group(4) != null) {
        // Marcador numérico legado [1]
        final num = int.parse(m.group(4)!);
        if (citation != null) {
          out.add(citation(num));
        } else {
          out.add(
            TextSpan(
              text: '[$num]',
              style: TextStyle(
                color: citationColor,
                fontWeight: FontWeight.w800,
                fontSize: (base.fontSize ?? 14) * 0.82,
              ),
            ),
          );
        }
      }
      pos = m.end;
    }
    if (pos < cleaned.length) out.add(TextSpan(text: cleaned.substring(pos)));
    return out;
  }
}
