import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'app_motion.dart';

/// Marca do Trokim: uma moeda que se parte em três. Os cortes desenham um
/// "T" no espaço negativo e o pedaço dourado, o "troquinho", desliza para
/// fora. Trokim vem de troquinho, que vem de troco.
class TrokimMark extends StatelessWidget {
  const TrokimMark({
    super.key,
    this.size = 40,
    this.onDark = false,
    this.assemble = 1,
  });

  final double size;

  /// Versão para fundos escuros (pedaço superior branco, verde-menta).
  final bool onDark;

  /// 0 = peças espalhadas, 1 = moeda montada.
  final double assemble;

  /// Moeda que se monta sozinha ao aparecer.
  static Widget animated({
    Key? key,
    double size = 40,
    bool onDark = false,
    Duration duration = const Duration(milliseconds: 1100),
  }) =>
      _AssemblingMark(key: key, size: size, onDark: onDark, duration: duration);

  @override
  Widget build(BuildContext context) => Semantics(
        label: 'Trokim',
        image: true,
        child: SizedBox(
          width: size,
          height: size,
          child: CustomPaint(
            painter: _MarkPainter(onDark: onDark, assemble: assemble),
          ),
        ),
      );
}

class _AssemblingMark extends StatelessWidget {
  const _AssemblingMark({
    super.key,
    required this.size,
    required this.onDark,
    required this.duration,
  });

  final double size;
  final bool onDark;
  final Duration duration;

  @override
  Widget build(BuildContext context) {
    if (Motion.reduced(context)) {
      return TrokimMark(size: size, onDark: onDark);
    }
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: duration,
      curve: Curves.easeOutBack,
      builder: (_, t, __) =>
          TrokimMark(size: size, onDark: onDark, assemble: t),
    );
  }
}

class _MarkPainter extends CustomPainter {
  _MarkPainter({required this.onDark, required this.assemble});

  final bool onDark;
  final double assemble;

  static const Offset _slide = Offset(1.4, 2.2);

  @override
  void paint(Canvas canvas, Size size) {
    canvas.scale(size.width / 64);
    final coin = Path()
      ..addOval(Rect.fromCircle(center: const Offset(32, 32), radius: 29));
    final e = 1 - assemble;
    final alpha = assemble.clamp(0.0, 1.0);

    void piece(RRect rect, Color color, Offset shift) {
      final path = Path.combine(
        PathOperation.intersect,
        coin,
        Path()..addRRect(rect),
      ).shift(shift);
      canvas.drawPath(
        path,
        Paint()..color = color.withValues(alpha: color.a * alpha),
      );
    }

    const r = Radius.circular(3);
    piece(
      RRect.fromLTRBR(-2, -6, 66, 24.2, r),
      onDark ? Colors.white : AppTheme.forest,
      Offset(0, -18 * e),
    );
    piece(
      RRect.fromLTRBR(-2, 27.8, 30.2, 68, r),
      onDark ? const Color(0xFF4FD1A5) : AppTheme.emerald,
      Offset(-16 * e, 10 * e),
    );
    piece(
      RRect.fromLTRBR(33.8, 27.8, 66, 68, r),
      AppTheme.coin,
      _slide + Offset(16 * e, 14 * e),
    );
  }

  @override
  bool shouldRepaint(covariant _MarkPainter old) =>
      old.onDark != onDark || old.assemble != assemble;
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
