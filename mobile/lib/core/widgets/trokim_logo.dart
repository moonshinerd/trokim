import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'mascot.dart';

/// Marca do Trokim: a cabeça da onça-pintada numa mini-moeda.
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
      child: CustomPaint(painter: _MascotPainter()),
    ),
  );
}

/// Logo horizontal: símbolo + nome.
class TrokimLogo extends StatelessWidget {
  const TrokimLogo({super.key, this.size = 36});

  final double size;

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
            color: context.colors.ink,
          ),
        ),
      ),
    ],
  );
}

class _MascotPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final r = size.shortestSide / 2;
    canvas.translate(size.width / 2, size.height / 2);
    final disc = Rect.fromCircle(center: Offset.zero, radius: r);
    // mini-moeda: disco Tidewater com aro dourado, para ler em qualquer fundo
    canvas.drawCircle(
      Offset.zero,
      r,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF4A7573), Color(0xFF1B3232)],
        ).createShader(disc),
    );
    canvas.drawCircle(
      Offset.zero,
      r - r * 0.035,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = r * 0.07
        ..color = const Color(0xFFF0CD6A),
    );
    canvas.save();
    canvas.translate(-r * 0.02, r * 0.06);
    Mascot.paintHead(canvas, side: r * 1.9);
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _MascotPainter old) => false;
}
