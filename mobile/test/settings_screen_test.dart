import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/features/settings/presentation/settings_screen.dart';

Future<SettingsController> openSettings(
  WidgetTester tester, {
  http.Client? client,
}) async {
  final settings = SettingsController.memory();
  addTearDown(settings.dispose);
  await tester.pumpWidget(
    SettingsScope(
      controller: settings,
      child: MaterialApp(
        home: SettingsScreen(controller: settings, client: client),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return settings;
}

void main() {
  testWidgets('segue o sistema por padrão e permite fixar o tema escuro',
      (tester) async {
    final settings = await openSettings(tester);
    expect(settings.themeMode, ThemeMode.system);
    expect(find.text('Segue o claro/escuro do seu aparelho.'), findsOneWidget);

    await tester.tap(find.text('Escuro'));
    await tester.pumpAndSettle();
    expect(settings.themeMode, ThemeMode.dark);
    expect(find.text('Fixo no tema escuro.'), findsOneWidget);
  });

  testWidgets('alterna animações e abertura', (tester) async {
    final settings = await openSettings(tester);
    expect(settings.reduceMotion, isFalse);
    expect(settings.showSplash, isTrue);

    await tester.tap(find.text('Reduzir animações'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Abertura animada'));
    await tester.pumpAndSettle();

    expect(settings.reduceMotion, isTrue);
    expect(settings.showSplash, isFalse);
  });

  testWidgets('testa a conexão com a API e mostra o resultado', (tester) async {
    await openSettings(
      tester,
      client:
          MockClient((_) async => http.Response('{"status":"healthy"}', 200)),
    );
    await tester.ensureVisible(find.text('Não testado'));
    expect(find.text('Não testado'), findsOneWidget);
    await tester.ensureVisible(find.text('Testar conexão'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Testar conexão'));
    await tester.pumpAndSettle();
    expect(find.text('Conectado'), findsOneWidget);
  });

  testWidgets('avisa quando a API está fora do ar', (tester) async {
    await openSettings(
      tester,
      client: MockClient((_) async => throw Exception('offline')),
    );
    await tester.ensureVisible(find.text('Testar conexão'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Testar conexão'));
    await tester.pumpAndSettle();
    expect(find.text('Sem conexão com a API'), findsOneWidget);
  });
}
