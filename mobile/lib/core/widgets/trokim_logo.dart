import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Marca do Trokim: uma moeda dourada com um "T" cunhado.
/// Trokim vem de troquinho, que vem de troco.
class TrokimMark extends StatelessWidget {
  const TrokimMark({super.key, this.size = 40});

  final double size;

  @override
  Widget build(BuildContext context) => Semantics(
        label: 'Trokim',
        image: true,
        child: SizedBox(
          width: size,
          height: size,
          child: CustomPaint(painter: _MarkPainter()),
        ),
      );
}

class _MarkPainter extends CustomPainter {
  _MarkPainter();

  static const Color _rim = Color(0xFFC98F1F);
  static const Color _milled = Color(0xFFB87F14);

  @override
  void paint(Canvas canvas, Size size) {
    canvas.scale(size.width / 64);
    const c = Offset(32, 32);

    // Moeda dourada com aro.
    canvas.drawCircle(c, 30, Paint()..color = AppTheme.coin);
    canvas.drawCircle(
      c,
      30,
      Paint()
        ..color = _rim
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );
    // Borda serrilhada: pontos ao redor.
    final dot = Paint()..color = _milled;
    for (var i = 0; i < 28; i++) {
      final a = i * 2 * math.pi / 28;
      canvas.drawCircle(
        c + Offset(math.cos(a), math.sin(a)) * 23.5,
        0.95,
        dot,
      );
    }
    // "T" cunhado.
    final ink = Paint()..color = AppTheme.forest;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(19, 18, 26, 8),
        const Radius.circular(3),
      ),
      ink,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(28, 18, 8, 28),
        const Radius.circular(3),
      ),
      ink,
    );
  }

  @override
  bool shouldRepaint(covariant _MarkPainter old) => false;
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
