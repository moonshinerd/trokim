import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;

/// Mascote do Trokim: a onça-pintada (a da nota de R\$ 50), em dourado com as
/// manchas vazadas. A arte vem de `assets/brand/` (ver o `LEIA-ME.md` de lá).
class Mascot {
  Mascot._();

  /// Corpo inteiro (moeda e site) e cabeça (tamanhos pequenos).
  static ui.Image? body;
  static ui.Image? head;

  static Future<void> load() async {
    body = await _decode('assets/brand/mascot_body.png');
    head = await _decode('assets/brand/mascot_head.png');
  }

  static Future<ui.Image?> _decode(String asset) async {
    try {
      final data = await rootBundle.load(asset);
      final codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
      return (await codec.getNextFrame()).image;
    } on Object {
      return null;
    }
  }

  static final Paint _paint = Paint()
    ..filterQuality = FilterQuality.high
    ..isAntiAlias = true;

  /// Desenha o corpo inteiro centrado em (0, 0) com a [width] dada.
  static void paintBody(Canvas canvas, {double width = 330}) {
    final img = body;
    if (img == null) {
      _fallback(canvas, width / 2);
      return;
    }
    final h = width * img.height / img.width;
    canvas.drawImageRect(
      img,
      Rect.fromLTWH(0, 0, img.width.toDouble(), img.height.toDouble()),
      Rect.fromCenter(center: Offset.zero, width: width, height: h),
      _paint,
    );
  }

  /// Desenha a cabeça centrada em (0, 0), cabendo num quadrado de [side].
  static void paintHead(Canvas canvas, {double side = 300}) {
    final img = head;
    if (img == null) {
      _fallback(canvas, side / 2);
      return;
    }
    canvas.drawImageRect(
      img,
      Rect.fromLTWH(0, 0, img.width.toDouble(), img.height.toDouble()),
      Rect.fromCenter(center: Offset.zero, width: side, height: side),
      _paint,
    );
  }

  // Sem arte carregada (ex.: testes): disco dourado.
  static void _fallback(Canvas canvas, double r) {
    canvas.drawCircle(
        Offset.zero, r * 0.6, Paint()..color = const Color(0xFFDAA520));
  }
}
