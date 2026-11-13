import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Marca do Trokim: uma moeda e o "troquinho" dourado que sai dela.
/// Trokim vem de troquinho, que vem de troco.
class TrokimMark extends StatelessWidget {
  const TrokimMark({super.key, this.size = 40, this.onDark = false});

  final double size;

  /// Versão com a moeda branca, para aplicar sobre cores escuras.
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
    // A moeda grande e o "troquinho" dourado que sai dela.
    canvas.drawCircle(
      const Offset(26, 30),
      20,
      Paint()..color = onDark ? Colors.white : AppTheme.emerald,
    );
    canvas.drawCircle(
      const Offset(50, 50),
      8,
      Paint()..color = AppTheme.coin,
    );
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
