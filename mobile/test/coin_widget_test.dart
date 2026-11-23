import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/core/widgets/coin.dart';

void main() {
  group('CoinPainter', () {
    testWidgets('desenha face frontal (angle = 0) sem erros', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: SizedBox.square(
                dimension: 200,
                child: CustomPaint(
                  painter: CoinPainter(angle: 0, compact: false, sparkle: 0.5),
                ),
              ),
            ),
          ),
        ),
      );
      expect(find.byType(CustomPaint), findsWidgets);
    });

    testWidgets('desenha face posterior (angle = pi) sem erros', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: SizedBox.square(
                dimension: 200,
                child: CustomPaint(
                  painter: CoinPainter(
                    angle: math.pi,
                    compact: false,
                    sparkle: 0.0,
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      expect(find.byType(CustomPaint), findsWidgets);
    });

    testWidgets('desenha versão compacta sem erros', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: SizedBox.square(
                dimension: 60,
                child: CustomPaint(
                  painter: CoinPainter(angle: 0.5, compact: true),
                ),
              ),
            ),
          ),
        ),
      );
      expect(find.byType(CustomPaint), findsWidgets);
    });

    test('shouldRepaint detecta mudanças de ângulo, inclinação e brilho', () {
      final p1 = CoinPainter(angle: 0, tilt: -0.14, sparkle: 0);
      final p2 = CoinPainter(angle: 0.1, tilt: -0.14, sparkle: 0);
      final p3 = CoinPainter(angle: 0, tilt: 0.0, sparkle: 0);
      final p4 = CoinPainter(angle: 0, tilt: -0.14, sparkle: 0.5);
      final pSame = CoinPainter(angle: 0, tilt: -0.14, sparkle: 0);

      expect(p1.shouldRepaint(pSame), isFalse);
      expect(p1.shouldRepaint(p2), isTrue);
      expect(p1.shouldRepaint(p3), isTrue);
      expect(p1.shouldRepaint(p4), isTrue);
    });
  });

  group('SpinningCoin', () {
    testWidgets('anima e reporta progresso até o final', (tester) async {
      final progressValues = <double>[];
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: SpinningCoin(
                size: 100,
                duration: const Duration(milliseconds: 500),
                onProgress: (v) => progressValues.add(v),
              ),
            ),
          ),
        ),
      );

      await tester.pump(const Duration(milliseconds: 100));
      expect(progressValues, isNotEmpty);

      await tester.pump(const Duration(milliseconds: 500));
      expect(progressValues.last, closeTo(1.0, 0.05));
    });

    testWidgets('respeita modo de redução de movimento (Motion.reduced)', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: MediaQuery(
            data: MediaQueryData(disableAnimations: true),
            child: Scaffold(
              body: Center(child: SpinningCoin(size: 80, compact: true)),
            ),
          ),
        ),
      );

      expect(
        find.descendant(
          of: find.byType(SpinningCoin),
          matching: find.byType(CustomPaint),
        ),
        findsOneWidget,
      );
    });
  });

  group('DustField', () {
    testWidgets('renderiza campo de partículas de poeira luminosa', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: SizedBox.expand(child: DustField(count: 20))),
        ),
      );

      expect(find.byType(DustField), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 200));
    });
  });
}
