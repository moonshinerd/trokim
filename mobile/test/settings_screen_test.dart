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

/// A lista é preguiçosa: rola até o texto existir na árvore.
Future<void> _scrollTo(WidgetTester tester, String text) async {
  await tester.scrollUntilVisible(
    find.text(text),
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('segue o sistema por padrão e permite fixar o tema escuro', (
    tester,
  ) async {
    final settings = await openSettings(tester);
    expect(settings.themeMode, ThemeMode.system);
    expect(find.text('Segue o claro/escuro do seu aparelho.'), findsOneWidget);

    await tester.tap(find.text('Escuro'));
    await tester.pumpAndSettle();
    expect(settings.themeMode, ThemeMode.dark);
    expect(find.text('Fixo no tema escuro.'), findsOneWidget);
  });

  testWidgets('a IA generativa vem ligada e pode ser desligada', (
    tester,
  ) async {
    final settings = await openSettings(tester);
    expect(settings.generativeChat, isTrue);
    await _scrollTo(tester, 'Respostas com IA (LLM local)');
    await tester.tap(find.text('Respostas com IA (LLM local)'));
    await tester.pumpAndSettle();
    expect(settings.generativeChat, isFalse);
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
      client: MockClient(
        (_) async => http.Response('{"status":"healthy"}', 200),
      ),
    );
    await _scrollTo(tester, 'Testar conexão');
    expect(find.text('Não testado'), findsOneWidget);
    await tester.tap(find.text('Testar conexão'));
    await tester.pumpAndSettle();
    expect(find.text('Conectado'), findsOneWidget);
  });

  testWidgets('avisa quando a API está fora do ar', (tester) async {
    await openSettings(
      tester,
      client: MockClient((_) async => throw Exception('offline')),
    );
    await _scrollTo(tester, 'Testar conexão');
    await tester.tap(find.text('Testar conexão'));
    await tester.pumpAndSettle();
    expect(find.text('Sem conexão com a API'), findsOneWidget);
  });
}
