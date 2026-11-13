import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Marca do Trokim: um "T" sólido e um ponto dourado, o "troco".
class TrokimMark extends StatelessWidget {
  const TrokimMark({super.key, this.size = 40, this.onDark = false});

  final double size;

  /// Usa versão sem fundo (traço claro) para aplicar sobre cores escuras.
  final bool onDark;

  @override
  Widget build(BuildContext context) => Semantics(
        label: 'Trokim',
        image: true,
        child: SizedBox(
          width: size,
          height: size,
          child: CustomPaint(painter: _MarkPainter(onDark: onDark)),
        ),
      );
}

class _MarkPainter extends CustomPainter {
  _MarkPainter({required this.onDark});
  final bool onDark;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.scale(size.width / 64);

    if (!onDark) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          const Rect.fromLTWH(0, 0, 64, 64),
          const Radius.circular(18),
        ),
        Paint()..color = AppTheme.forest,
      );
    }

    final white = Paint()..color = Colors.white;
    // "T" geométrico: barra e haste sólidas.
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(16, 17, 32, 9),
        const Radius.circular(4.5),
      ),
      white,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(24, 17, 9, 31),
        const Radius.circular(4.5),
      ),
      white,
    );
    // O "troco": um ponto dourado.
    canvas.drawCircle(
        const Offset(42, 43.5), 4.5, Paint()..color = AppTheme.coin);
  }

  @override
  bool shouldRepaint(covariant _MarkPainter old) => old.onDark != onDark;
}

/// Logo horizontal: símbolo + nome.
class TrokimLogo extends StatelessWidget {
  const TrokimLogo({super.key, this.size = 36, this.color = AppTheme.ink});

  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          TrokimMark(size: size),
          SizedBox(width: size * 0.3),
          ExcludeSemantics(
            child: Text(
              'trokim',
              style: TextStyle(
                fontFamily: AppTheme.fontFamily,
                fontSize: size * 0.62,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.8,
                color: color,
              ),
            ),
          ),
        ],
      );
}
