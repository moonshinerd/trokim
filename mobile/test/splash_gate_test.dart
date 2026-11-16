import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/main.dart';

int _inits = 0;

class _Probe extends StatefulWidget {
  const _Probe();

  @override
  State<_Probe> createState() => _ProbeState();
}

class _ProbeState extends State<_Probe> {
  @override
  void initState() {
    super.initState();
    _inits++;
  }

  @override
  Widget build(BuildContext context) => const Text('app em uso');
}

void main() {
  testWidgets(
    'mudar opções em Ajustes não recria o app em uso (preserva o estado)',
    (tester) async {
      _inits = 0;
      final settings = SettingsController.memory();
      addTearDown(settings.dispose);
      await tester.pumpWidget(
        SettingsScope(
          controller: settings,
          child: const MaterialApp(home: SplashGate(child: _Probe())),
        ),
      );
      // Abertura animada visível; o app ainda não entrou.
      expect(find.text('trokim'), findsOneWidget);
      expect(find.text('app em uso'), findsNothing);

      await tester.pump(const Duration(seconds: 4));
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('app em uso'), findsOneWidget);
      expect(_inits, 1);

      settings.setShowSplash(false);
      await tester.pump();
      settings.setReduceMotion(true);
      await tester.pump(const Duration(seconds: 1));

      expect(find.text('app em uso'), findsOneWidget);
      expect(_inits, 1, reason: 'o app não pode ser recriado');
    },
  );

  testWidgets('com a abertura desligada o app entra direto', (tester) async {
    final settings = SettingsController.memory()..setShowSplash(false);
    addTearDown(settings.dispose);
    await tester.pumpWidget(
      SettingsScope(
        controller: settings,
        child: const MaterialApp(home: SplashGate(child: _Probe())),
      ),
    );
    await tester.pump();
    expect(find.text('app em uso'), findsOneWidget);
    expect(find.text('trokim'), findsNothing);
    await tester.pump(const Duration(seconds: 4));
  });

  group('carregamento real', () {
    Future<void> openWith(WidgetTester tester, Future<void> ready) async {
      final settings = SettingsController.memory();
      addTearDown(settings.dispose);
      await tester.pumpWidget(
        SettingsScope(
          controller: settings,
          child: MaterialApp(
            home: SplashGate(ready: ready, child: const _Probe()),
          ),
        ),
      );
    }

    double barValue(WidgetTester tester) => tester
        .widget<LinearProgressIndicator>(find.byType(LinearProgressIndicator))
        .value!;

    testWidgets('espera o carregamento mesmo depois da animação acabar', (
      tester,
    ) async {
      final done = Completer<void>();
      await openWith(tester, done.future);

      await tester.pump(const Duration(seconds: 4));
      expect(find.text('app em uso'), findsNothing, reason: 'ainda carregando');
      expect(barValue(tester), closeTo(0.9, 1e-9), reason: 'não chega a 100%');

      done.complete();
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('app em uso'), findsOneWidget);
    });

    testWidgets('com carregamento rápido a barra completa junto da moeda', (
      tester,
    ) async {
      await openWith(tester, Future<void>.value());

      await tester.pump(const Duration(milliseconds: 2700));
      expect(barValue(tester), closeTo(1, 1e-9));
      expect(find.text('app em uso'), findsNothing, reason: 'moeda ainda gira');

      // Deixa a abertura terminar (nenhum timer pode sobrar ao fim do teste).
      await tester.pump(const Duration(seconds: 1));
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('app em uso'), findsOneWidget);
    });

    testWidgets('sem resposta da API, abre depois do tempo máximo', (
      tester,
    ) async {
      await openWith(tester, Completer<void>().future);

      await tester.pump(const Duration(seconds: 7));
      expect(find.text('app em uso'), findsNothing);

      await tester.pump(const Duration(seconds: 2));
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('app em uso'), findsOneWidget);
    });

    testWidgets('falha no carregamento não trava a abertura', (tester) async {
      // O erro só ocorre depois do primeiro build, quando a abertura já ouve.
      await openWith(
        tester,
        Future<void>.delayed(
          const Duration(milliseconds: 10),
          () => throw StateError('API fora'),
        ),
      );

      await tester.pump(const Duration(seconds: 4));
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('app em uso'), findsOneWidget);
    });
  });
}
