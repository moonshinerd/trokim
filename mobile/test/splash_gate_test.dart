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
  });

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
}
