import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Marca do Trokim: um "T" cuja barra superior é uma troca (⇄) entre duas
/// setas, e cuja haste termina numa moeda. "Trokim" vem de trocar/troco:
/// converter dispersão de contas em decisões claras.
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
    final s = size.width / 64;
    canvas.scale(s);

    if (!onDark) {
      final bg = RRect.fromRectAndRadius(
        const Rect.fromLTWH(0, 0, 64, 64),
        const Radius.circular(18),
      );
      canvas.drawRRect(
        bg,
        Paint()
          ..shader = const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [AppTheme.emerald, AppTheme.forest],
          ).createShader(const Rect.fromLTWH(0, 0, 64, 64)),
      );
    }

    final stroke = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5.5
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    // Barra de troca ⇄ (duas setas opostas).
    final top = Path()
      ..moveTo(16, 21)
      ..lineTo(46, 21)
      ..moveTo(40, 15)
      ..lineTo(46, 21)
      ..lineTo(40, 27);
    final bottom = Path()
      ..moveTo(48, 33)
      ..lineTo(18, 33)
      ..moveTo(24, 27)
      ..lineTo(18, 33)
      ..lineTo(24, 39);
    // Haste do T.
    final stem = Path()
      ..moveTo(32, 33)
      ..lineTo(32, 44);

    canvas.drawPath(top, stroke);
    canvas.drawPath(bottom, stroke);
    canvas.drawPath(stem, stroke);

    // Moeda no pé da haste.
    canvas.drawCircle(const Offset(32, 51), 5, Paint()..color = AppTheme.coin);
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
