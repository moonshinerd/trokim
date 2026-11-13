import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'mascot.dart';

/// Marca do Trokim: a onça-pintada, de pelagem dourada como uma moeda.
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
          child: CustomPaint(painter: _MascotPainter(simple: size < 56)),
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
  _MascotPainter({required this.simple});
  final bool simple;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.translate(size.width / 2, size.height / 2);
    canvas.scale(size.shortestSide / (Mascot.extent * 2.05));
    Mascot.paint(canvas, simple: simple);
  }

  @override
  bool shouldRepaint(covariant _MascotPainter old) => old.simple != simple;
}
