import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;

/// Mascote do Trokim: a onça-pintada (a da nota de R\$ 50) de perfil, num disco
/// dourado, desenhada em espaço negativo. Gerado a partir de `docs/assets/logo.svg`.
class Mascot {
  Mascot._();

  /// Espaço de desenho: centrado em (0, 0), cabe num círculo de raio ~155.
  static const double extent = 155;

  /// [simple] omite os detalhes finos e engrossa os traços (tamanhos pequenos).
  /// Arte final do mascote (assets/brand/mascot.png), carregada na abertura.
  /// Se ainda não estiver carregada (ex.: testes), usa o desenho vetorial.
  static ui.Image? image;

  static Future<void> load() async {
    try {
      final data = await rootBundle.load('assets/brand/mascot.png');
      final codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
      image = (await codec.getNextFrame()).image;
    } on Object {
      image = null;
    }
  }

  static void paint(Canvas canvas, {bool simple = false}) {
    final img = image;
    if (img != null) {
      canvas.drawImageRect(
        img,
        Rect.fromLTWH(0, 0, img.width.toDouble(), img.height.toDouble()),
        const Rect.fromLTRB(-160, -160, 160, 160),
        Paint()
          ..filterQuality = FilterQuality.high
          ..isAntiAlias = true,
      );
      return;
    }
    final k = simple ? 1.7 : 1.0;
    final gold = Paint()
      ..isAntiAlias = true
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFFF6DB82), Color(0xFFDAA520), Color(0xFFB07C12)],
        stops: [0, 0.5, 1],
      ).createShader(const Rect.fromLTRB(-140, -140, 140, 140));
    final dark = Paint()
      ..isAntiAlias = true
      ..color = const Color(0xFF1B3232);
    canvas.drawCircle(Offset.zero, 140, gold);
    final head = Path()
      ..moveTo(-152, 10)
      ..cubicTo(-152, -2, -146, -10, -138, -14)
      ..lineTo(-102, -34)
      ..cubicTo(-92, -40, -86, -52, -78, -66)
      ..cubicTo(-62, -86, -36, -100, -10, -104)
      ..lineTo(18, -112)
      ..lineTo(42, -150)
      ..lineTo(78, -102)
      ..cubicTo(88, -78, 86, -44, 76, -18)
      ..cubicTo(68, 4, 68, 30, 56, 54)
      ..cubicTo(46, 74, 26, 88, 0, 94)
      ..cubicTo(-28, 100, -56, 98, -80, 90)
      ..lineTo(-120, 82)
      ..cubicTo(-136, 78, -148, 66, -152, 50)
      ..close();
    canvas.drawPath(head, dark);
    canvas.drawPath(
      head,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4
        ..strokeJoin = StrokeJoin.round
        ..color = const Color(0xFF1B3232),
    );
    canvas.drawPath(
        Path()
          ..moveTo(34, -118)
          ..lineTo(44, -138)
          ..lineTo(62, -110)
          ..close(),
        gold);
    canvas.drawPath(
        Path()
          ..moveTo(-88, -36)
          ..cubicTo(-68, -62, -34, -62, -8, -42)
          ..cubicTo(-36, -48, -64, -44, -88, -36)
          ..close(),
        gold);
    final stroke = Paint()
      ..isAntiAlias = true
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..shader = gold.shader;
    stroke.strokeWidth = 10;
    canvas.drawPath(
        Path()
          ..moveTo(-60, -12)
          ..cubicTo(-26, 8, 14, 28, 38, 62),
        stroke);
    stroke.strokeWidth = 9;
    canvas.drawPath(
        Path()
          ..moveTo(-72, 14)
          ..cubicTo(-44, 38, -14, 56, 2, 84),
        stroke);
    stroke.strokeWidth = 8;
    canvas.drawPath(
        Path()
          ..moveTo(-34, -70)
          ..cubicTo(6, -58, 46, -34, 68, 8),
        stroke);
    stroke.strokeWidth = 4;
    canvas.drawPath(
        Path()
          ..moveTo(-116, -34)
          ..cubicTo(-96, -58, -58, -74, -16, -72),
        stroke);
    stroke.strokeWidth = 5;
    canvas.drawPath(
        Path()
          ..moveTo(-130, -12)
          ..lineTo(-108, -26),
        stroke);
    stroke.strokeWidth = 5;
    canvas.drawPath(
        Path()
          ..moveTo(-150, 54)
          ..cubicTo(-130, 70, -108, 72, -90, 58),
        stroke);
    stroke.strokeWidth = 4;
    canvas.drawPath(
        Path()
          ..moveTo(-92, 58)
          ..cubicTo(-84, 48, -76, 40, -66, 36),
        stroke);
    canvas.save();
    canvas.translate(108, -54);
    canvas.rotate(-0.3491);
    canvas.drawOval(
        Rect.fromCenter(center: Offset.zero, width: 20, height: 30), dark);
    canvas.restore();
    canvas.save();
    canvas.translate(128, -4);
    canvas.rotate(-0.1745);
    canvas.drawOval(
        Rect.fromCenter(center: Offset.zero, width: 20, height: 30), dark);
    canvas.restore();
    canvas.save();
    canvas.translate(108, 38);
    canvas.rotate(-0.4363);
    canvas.drawOval(
        Rect.fromCenter(center: Offset.zero, width: 20, height: 30), dark);
    canvas.restore();
    canvas.save();
    canvas.translate(92, -92);
    canvas.rotate(-0.2618);
    canvas.drawOval(
        Rect.fromCenter(center: Offset.zero, width: 18, height: 26), dark);
    canvas.restore();
    canvas.save();
    canvas.translate(80, 74);
    canvas.rotate(-0.6109);
    canvas.drawOval(
        Rect.fromCenter(center: Offset.zero, width: 18, height: 26), dark);
    canvas.restore();
    if (!simple) {
      canvas.drawCircle(const Offset(-126, 34), 2.8, gold);
    }
    if (!simple) {
      canvas.drawCircle(const Offset(-114, 40), 2.8, gold);
    }
    if (!simple) {
      canvas.drawCircle(const Offset(-130, 46), 2.8, gold);
    }
    if (!simple) {
      canvas.drawCircle(const Offset(-140, 2), 2.8, gold);
    }
  }
}
