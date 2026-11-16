import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'app_motion.dart';
import 'mascot.dart';

/// Moeda 3D do Trokim desenhada em tempo real.
///
/// [angle] é a rotação em torno do eixo vertical (radianos). Em 0 a face com
/// o "T" aparece de frente; em pi aparece o verso. A espessura e a borda
/// serrilhada surgem conforme a moeda gira.
class CoinPainter extends CustomPainter {
  CoinPainter({
    this.angle = 0,
    this.tilt = -0.14,
    this.compact = false,
    this.sparkle = 0,
  });

  final double angle;

  /// Inclinação da moeda no plano (radianos).
  final double tilt;

  /// Versão simples para tamanhos pequenos: sem texto nem borda.
  final bool compact;

  /// 0..1: intensidade do brilho em estrela na borda.
  final double sparkle;

  @override
  void paint(Canvas canvas, Size size) {
    final r = size.shortestSide * (compact ? 0.48 : 0.40);
    canvas.translate(size.width / 2, size.height / 2);
    canvas.rotate(tilt);

    final cosA = math.cos(angle);
    final sinA = math.sin(angle);
    final sx = cosA.abs().clamp(0.015, 1.0);
    final frontFacing = cosA >= 0;
    final depth = compact ? 0.0 : r * 0.13;

    // Sombra no chão.
    if (!compact) {
      canvas.save();
      canvas.translate(0, r * 1.08);
      canvas.drawOval(
        Rect.fromCenter(
          center: Offset.zero,
          width: r * 1.5 * (0.5 + 0.5 * sx),
          height: r * 0.2,
        ),
        Paint()
          ..color = Colors.black.withValues(alpha: 0.45)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, r * 0.12),
      );
      canvas.restore();
    }

    // Camadas da espessura, de trás para a frente.
    const layers = 26;
    for (var i = 0; i < layers; i++) {
      final t = frontFacing ? -1 + 2 * i / layers : 1 - 2 * i / layers;
      final x = t * depth * 0.5 * sinA;
      final milled = i.isEven;
      final shade = (t.abs());
      final color = Color.lerp(
        milled ? const Color(0xFFF0CD6A) : const Color(0xFFB8860B),
        const Color(0xFF6B4A06),
        shade * 0.6,
      )!;
      canvas.drawOval(
        Rect.fromCenter(center: Offset(x, 0), width: 2 * r * sx, height: 2 * r),
        Paint()..color = color,
      );
    }

    // Face visível.
    final faceX = (frontFacing ? 1 : -1) * depth * 0.5 * sinA;
    canvas.save();
    canvas.translate(faceX, 0);
    canvas.scale(sx, 1);
    _face(canvas, r, frontFacing);
    canvas.restore();

    if (sparkle > 0 && !compact) {
      _star(
        canvas,
        Offset(r * 0.74 * sx, r * 0.62),
        r * 0.2 * sparkle,
        sparkle,
      );
      _star(
        canvas,
        Offset(-r * 0.78 * sx, -r * 0.34),
        r * 0.11 * sparkle,
        sparkle * 0.8,
      );
    }
  }

  void _face(Canvas canvas, double r, bool front) {
    final circle = Rect.fromCircle(center: Offset.zero, radius: r);
    canvas.drawCircle(
      Offset.zero,
      r,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment(-0.9, -1),
          end: Alignment(0.9, 1),
          colors: [
            Color(0xFF7FA8A5),
            Color(0xFF4A7573),
            Color(0xFF2F4F4F),
            Color(0xFF142828),
          ],
          stops: [0, 0.3, 0.62, 1],
        ).createShader(circle),
    );

    // Brilho metálico que varre a face conforme gira.
    final sweep = ((angle / math.pi) % 2) * 2.4 - 1.2;
    canvas.save();
    canvas.clipPath(Path()..addOval(circle));
    canvas.drawRect(
      circle,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment(-1.4 + sweep, 1),
          end: Alignment(0.2 + sweep, -1),
          colors: [
            Colors.white.withValues(alpha: 0),
            Colors.white.withValues(alpha: 0.38),
            Colors.white.withValues(alpha: 0),
          ],
        ).createShader(circle),
    );
    canvas.restore();

    // Brilho luminoso no aro.
    if (!compact) {
      canvas.drawCircle(
        Offset.zero,
        r - 2 * (r / 250),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 10 * (r / 250)
          ..color = const Color(0xFFE9B44C).withValues(alpha: 0.35)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, r * 0.05),
      );
    }

    // Aros.
    final scale = r / 250;
    canvas.drawCircle(
      Offset.zero,
      r - 2 * scale,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 6 * scale
        ..color = const Color(0xFFF0CD6A),
    );
    if (!compact) {
      canvas.drawCircle(
        Offset.zero,
        r - 16 * scale,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5 * scale
          ..color = const Color(0xFF0E1B1B).withValues(alpha: 0.6),
      );
      canvas.drawCircle(
        Offset.zero,
        r - 20 * scale,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2 * scale
          ..color = const Color(0xFFDAA520).withValues(alpha: 0.8),
      );
    }

    // Texto gravado em anel.
    if (!compact) {
      final top = front ? 'DE TROCO NASCE O TROKIM' : 'TROQUINHO  ·  TROCO';
      _arcText(canvas, top, r * 0.80, r * 0.075, top: true);
      _arcText(
        canvas,
        front ? 'EST. 2026' : 'R\$ 0,01',
        r * 0.80,
        r * 0.075,
        top: false,
      );
    }

    // Marca em relevo.
    canvas.save();
    canvas.scale(scale);
    if (front) {
      _mark(canvas);
    } else {
      _glyph(canvas, 'R\$');
    }
    canvas.restore();
  }

  void _mark(Canvas canvas) {
    // sombra suave do relevo
    canvas.save();
    canvas.translate(4, 8);
    canvas.drawOval(
      Rect.fromCenter(center: const Offset(0, 6), width: 300, height: 170),
      Paint()
        ..color = Colors.black.withValues(alpha: 0.28)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 12),
    );
    canvas.restore();
    Mascot.paintBody(canvas, width: 330);
  }

  void _glyph(Canvas canvas, String text) {
    TextPainter make(Color c) => TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          fontFamily: AppTheme.fontFamily,
          fontSize: 210,
          fontWeight: FontWeight.w800,
          letterSpacing: -6,
          color: c,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final shadow = make(const Color(0xFF3D2706));
    final face = make(const Color(0xFFF6D27A));
    final off = Offset(-face.width / 2, -face.height / 2);
    for (var i = 10; i > 0; i--) {
      shadow.paint(canvas, off + Offset(-i * 0.7, i * 0.9));
    }
    face.paint(canvas, off);
  }

  void _arcText(
    Canvas canvas,
    String text,
    double radius,
    double fontSize, {
    required bool top,
  }) {
    final chars = text.split('');
    final painters = [
      for (final ch in chars)
        TextPainter(
          text: TextSpan(
            text: ch,
            style: TextStyle(
              fontFamily: AppTheme.fontFamily,
              fontSize: fontSize,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
              color: const Color(0xFFF0CD6A).withValues(alpha: 0.95),
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout(),
    ];
    final gap = fontSize * 0.22;
    final total = painters.fold<double>(0, (s, p) => s + p.width + gap) - gap;
    var cursor = -total / 2;
    for (final p in painters) {
      final mid = cursor + p.width / 2;
      final theta = mid / radius;
      canvas.save();
      if (top) {
        canvas.rotate(theta);
        canvas.translate(0, -radius);
      } else {
        canvas.rotate(-theta);
        canvas.translate(0, radius);
        canvas.rotate(math.pi);
      }
      // gravado: sombra escura deslocada + luz.
      final shade = TextPainter(
        text: TextSpan(
          text: p.text!.toPlainText(),
          style: (p.text! as TextSpan).style!.copyWith(
            color: const Color(0xFF0A1414).withValues(alpha: 0.8),
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      shade.paint(canvas, Offset(-p.width / 2 + 0.8, -p.height / 2 + 0.8));
      p.paint(canvas, Offset(-p.width / 2, -p.height / 2));
      canvas.restore();
      cursor += p.width + gap;
    }
  }

  void _star(Canvas canvas, Offset c, double size, double a) {
    final glow = Paint()
      ..color = Colors.white.withValues(alpha: 0.9 * a)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, size * 0.3);
    canvas.drawCircle(c, size * 0.3, glow);
    final p = Path()
      ..moveTo(c.dx, c.dy - size)
      ..lineTo(c.dx + size * 0.08, c.dy - size * 0.08)
      ..lineTo(c.dx + size, c.dy)
      ..lineTo(c.dx + size * 0.08, c.dy + size * 0.08)
      ..lineTo(c.dx, c.dy + size)
      ..lineTo(c.dx - size * 0.08, c.dy + size * 0.08)
      ..lineTo(c.dx - size, c.dy)
      ..lineTo(c.dx - size * 0.08, c.dy - size * 0.08)
      ..close();
    canvas.drawPath(p, Paint()..color = Colors.white.withValues(alpha: a));
  }

  @override
  bool shouldRepaint(covariant CoinPainter old) =>
      old.angle != angle || old.tilt != tilt || old.sparkle != sparkle;
}

/// Moeda que gira [turns] voltas ao aparecer e termina de frente, brilhando.
class SpinningCoin extends StatefulWidget {
  const SpinningCoin({
    super.key,
    this.size = 120,
    this.turns = 1,
    this.duration = const Duration(milliseconds: 1400),
    this.compact = false,
    this.onProgress,
  });

  final double size;
  final double turns;
  final Duration duration;
  final bool compact;

  /// Recebe o progresso 0..1 da animação (usado pelo splash).
  final ValueChanged<double>? onProgress;

  @override
  State<SpinningCoin> createState() => _SpinningCoinState();
}

class _SpinningCoinState extends State<SpinningCoin>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: widget.duration,
  );

  @override
  void initState() {
    super.initState();
    if (widget.onProgress != null) {
      _c.addListener(() => widget.onProgress!(_c.value));
    }
    _c.forward();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduced = Motion.reduced(context);
    if (reduced) {
      return SizedBox.square(
        dimension: widget.size,
        child: CustomPaint(painter: CoinPainter(compact: widget.compact)),
      );
    }
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) {
        final t = _c.value;
        final angle =
            2 * math.pi * widget.turns * Curves.easeOutCubic.transform(t);
        final pop = Curves.easeOutBack.transform((t / 0.4).clamp(0.0, 1.0));
        final sparkle = t > 0.7
            ? math.sin(((t - 0.7) / 0.3) * math.pi).clamp(0.0, 1.0)
            : 0.0;
        return Transform.scale(
          scale: 0.6 + 0.4 * pop,
          child: Opacity(
            opacity: (t / 0.15).clamp(0.0, 1.0),
            child: SizedBox.square(
              dimension: widget.size,
              child: CustomPaint(
                painter: CoinPainter(
                  angle: angle,
                  compact: widget.compact,
                  sparkle: widget.compact ? 0 : sparkle,
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Poeira luminosa que flutua e cintila ao fundo (como partículas de luz).
class DustField extends StatefulWidget {
  const DustField({super.key, this.count = 46});
  final int count;

  @override
  State<DustField> createState() => _DustFieldState();
}

class _DustFieldState extends State<DustField>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 12),
  )..repeat();
  late final List<_Mote> _motes = () {
    final rnd = math.Random(7);
    return List.generate(
      widget.count,
      (_) => _Mote(
        rnd.nextDouble(),
        rnd.nextDouble(),
        0.8 + rnd.nextDouble() * 2.2,
        rnd.nextDouble(),
        0.4 + rnd.nextDouble() * 0.9,
        rnd.nextBool(),
      ),
    );
  }();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => IgnorePointer(
    child: RepaintBoundary(
      child: AnimatedBuilder(
        animation: _c,
        builder: (_, __) => CustomPaint(
          size: Size.infinite,
          painter: _DustPainter(_motes, _c.value),
        ),
      ),
    ),
  );
}

class _Mote {
  _Mote(this.x, this.y, this.r, this.phase, this.speed, this.lime);
  final double x, y, r, phase, speed;
  final bool lime;
}

class _DustPainter extends CustomPainter {
  _DustPainter(this.motes, this.t);
  final List<_Mote> motes;
  final double t;

  @override
  void paint(Canvas canvas, Size size) {
    for (final m in motes) {
      final y = (m.y - t * m.speed * 0.35) % 1.0;
      final x = m.x + math.sin((t + m.phase) * 2 * math.pi) * 0.012;
      final tw = 0.5 + 0.5 * math.sin((t * 3 + m.phase) * 2 * math.pi);
      final color = (m.lime ? const Color(0xFFF0CD6A) : const Color(0xFFB9D6CF))
          .withValues(alpha: 0.15 + 0.6 * tw);
      canvas.drawCircle(
        Offset(x * size.width, y * size.height),
        m.r,
        Paint()
          ..color = color
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, m.r * 0.6),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _DustPainter old) => old.t != t;
}
