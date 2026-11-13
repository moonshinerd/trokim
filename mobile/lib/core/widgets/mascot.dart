import 'package:flutter/material.dart';

/// Mascote do Trokim: a onça-pintada (a da nota de R\$ 50), simplificada e de
/// olhar sério. A pelagem dourada combina com a moeda.
class Mascot {
  Mascot._();

  /// Espaço de desenho: centrado em (0, 0), cabe num círculo de raio ~150.
  static const double extent = 150;

  static void paint(Canvas canvas) {
    for (final p in _prims) {
      p.paint(canvas);
    }
  }
}

// Marcadores de degradê dourado (um por elemento, como no SVG).
const Color _G1 = Color(0x01FFE08A);
const Color _G2 = Color(0x02F2B42E);

class _P {
  const _P(this.kind, this.a, this.b, this.c, this.d, this.w, this.color);
  const _P.circle(double x, double y, double r, Color color)
      : this(0, x, y, r, 0, 0, color);
  const _P.ellipse(double x, double y, double rx, double ry, Color color)
      : this(1, x, y, rx, ry, 0, color);
  const _P.rect(double x, double y, double w, double h, Color color)
      : this(2, x, y, w, h, 0, color);
  const _P.line(
      double x1, double y1, double x2, double y2, double width, Color color)
      : this(3, x1, y1, x2, y2, width, color);

  final int kind;
  final double a, b, c, d, w;
  final Color color;

  Paint _fill(Rect bounds) {
    final p = Paint()..isAntiAlias = true;
    if (color == _G1) {
      p.shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFFF6DB82), Color(0xFFDAA520), Color(0xFFB07C12)],
        stops: [0, 0.5, 1],
      ).createShader(bounds);
    } else if (color == _G2) {
      p.shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFFE2B032), Color(0xFFA06F0E)],
      ).createShader(bounds);
    } else {
      p.color = color;
    }
    return p;
  }

  void paint(Canvas canvas) {
    switch (kind) {
      case 0:
        final r = Rect.fromCircle(center: Offset(a, b), radius: c);
        canvas.drawCircle(Offset(a, b), c, _fill(r));
      case 1:
        final r =
            Rect.fromCenter(center: Offset(a, b), width: 2 * c, height: 2 * d);
        canvas.drawOval(r, _fill(r));
      case 2:
        final r = Rect.fromLTWH(a, b, c, d);
        canvas.drawRect(r, _fill(r));
      default:
        canvas.drawLine(
          Offset(a, b),
          Offset(c, d),
          Paint()
            ..color = color
            ..strokeWidth = w
            ..strokeCap = StrokeCap.round,
        );
    }
  }
}

const List<_P> _prims = [
  _P.circle(-84.0, -92.0, 31, Color(0xFFDAA520)),
  _P.circle(-84.0, -90.0, 15, Color(0xFF1B1210)),
  _P.circle(84.0, -92.0, 31, Color(0xFFDAA520)),
  _P.circle(84.0, -90.0, 15, Color(0xFF1B1210)),
  _P.ellipse(0.0, 12.0, 118, 104, Color(0xFFDAA520)),
  _P.circle(-62.0, -62.0, 10, Color(0xFF1B1210)),
  _P.circle(-62.0, -62.0, 4.2, Color(0xFFDAA520)),
  _P.circle(0.0, -78.0, 10, Color(0xFF1B1210)),
  _P.circle(0.0, -78.0, 4.2, Color(0xFFDAA520)),
  _P.circle(62.0, -62.0, 10, Color(0xFF1B1210)),
  _P.circle(62.0, -62.0, 4.2, Color(0xFFDAA520)),
  _P.circle(-100.0, -4.0, 10, Color(0xFF1B1210)),
  _P.circle(-100.0, -4.0, 4.2, Color(0xFFDAA520)),
  _P.circle(100.0, -4.0, 10, Color(0xFF1B1210)),
  _P.circle(100.0, -4.0, 4.2, Color(0xFFDAA520)),
  _P.circle(-88.0, 64.0, 10, Color(0xFF1B1210)),
  _P.circle(-88.0, 64.0, 4.2, Color(0xFFDAA520)),
  _P.circle(88.0, 64.0, 10, Color(0xFF1B1210)),
  _P.circle(88.0, 64.0, 4.2, Color(0xFFDAA520)),
  _P.ellipse(0.0, 56.0, 48, 34, Color(0xFFFBEBC8)),
  _P.ellipse(-38.0, -4.0, 10.5, 13, Color(0xFF1B1210)),
  _P.circle(-35.0, -8.0, 3, Color(0xFFFBEBC8)),
  _P.line(-58, -28, -22, -22, 6, Color(0xFF1B1210)),
  _P.ellipse(38.0, -4.0, 10.5, 13, Color(0xFF1B1210)),
  _P.circle(35.0, -8.0, 3, Color(0xFFFBEBC8)),
  _P.line(58, -28, 22, -22, 6, Color(0xFF1B1210)),
  _P.ellipse(0.0, 38.0, 15, 10, Color(0xFF1B1210)),
  _P.line(0, 46, 0, 58, 4.5, Color(0xFF1B1210)),
  _P.line(0, 58, -14, 66, 4.5, Color(0xFF1B1210)),
  _P.line(0, 58, 14, 66, 4.5, Color(0xFF1B1210)),
];
