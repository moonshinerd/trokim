import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'coin.dart';

/// Marca do Trokim: uma moeda violeta com o "T" em verde-limão.
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
          child: CustomPaint(painter: CoinPainter(compact: true, tilt: 0)),
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
