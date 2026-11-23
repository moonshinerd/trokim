import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:trokim/core/constants/api_constants.dart';
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
  test('modo multiagente começa desligado e persiste no aparelho', () async {
    SharedPreferences.setMockInitialValues({});
    final settings = await SettingsController.load();
    expect(settings.multiAgent, isFalse);
    settings.setMultiAgent(true);
    settings.dispose();

    final restored = await SettingsController.load();
    expect(restored.multiAgent, isTrue);
    restored.dispose();
  });

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

  testWidgets('o tutorial de importação vem ligado e pode ser desligado', (
    tester,
  ) async {
    final settings = await openSettings(tester);
    expect(settings.showImportTutorial, isTrue);
    await _scrollTo(tester, 'Tutorial ao importar extratos');
    await tester.tap(find.text('Tutorial ao importar extratos'));
    await tester.pumpAndSettle();
    expect(settings.showImportTutorial, isFalse);
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

  group('endereço da API', () {
    testWidgets('começa no padrão e salva um endereço novo normalizado', (
      tester,
    ) async {
      final settings = await openSettings(tester);
      expect(settings.apiBaseUrl, ApiConstants.defaultBaseUrl);
      await _scrollTo(tester, 'Salvar endereço');

      await tester.enterText(
        find.byType(TextField).first,
        '  http://192.168.0.10:8000/v1/  ',
      );
      await tester.tap(find.text('Salvar endereço'));
      await tester.pumpAndSettle();

      expect(settings.apiBaseUrl, 'http://192.168.0.10:8000/v1');
      expect(find.text('http://192.168.0.10:8000/v1'), findsOneWidget);
    });

    testWidgets('endereço inválido mostra erro e não altera o salvo', (
      tester,
    ) async {
      final settings = await openSettings(tester);
      await _scrollTo(tester, 'Salvar endereço');

      await tester.enterText(
        find.byType(TextField).first,
        'localhost sem esquema',
      );
      await tester.tap(find.text('Salvar endereço'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Use um endereço http://'), findsOneWidget);
      expect(settings.apiBaseUrl, ApiConstants.defaultBaseUrl);
    });

    testWidgets('"Restaurar padrão" volta ao endereço original', (
      tester,
    ) async {
      final settings = await openSettings(tester);
      settings.setApiBaseUrl('http://10.1.1.1:9000/v1');
      await tester.pumpAndSettle();
      await _scrollTo(tester, 'Restaurar padrão');

      await tester.tap(find.text('Restaurar padrão'));
      await tester.pumpAndSettle();

      expect(settings.apiBaseUrl, ApiConstants.defaultBaseUrl);
      expect(find.text(ApiConstants.defaultBaseUrl), findsOneWidget);
    });

    testWidgets('o teste de conexão usa o endereço salvo', (tester) async {
      final urls = <Uri>[];
      final settings = await openSettings(
        tester,
        client: MockClient((request) async {
          urls.add(request.url);
          return http.Response('{"status":"healthy"}', 200);
        }),
      );
      settings.setApiBaseUrl('http://192.168.0.10:8000/v1');
      await tester.pumpAndSettle();
      await _scrollTo(tester, 'Testar conexão');

      await tester.tap(find.text('Testar conexão'));
      await tester.pumpAndSettle();

      expect(urls.single.toString(), 'http://192.168.0.10:8000/v1/health');
    });

    test(
      'é guardado no aparelho e um valor corrompido volta ao padrão',
      () async {
        SharedPreferences.setMockInitialValues({
          'api_base_url': 'http://10.0.0.5:8000/v1',
        });
        final saved = await SettingsController.load();
        expect(saved.apiBaseUrl, 'http://10.0.0.5:8000/v1');

        saved.setApiBaseUrl('https://trokim.exemplo.local/v1');
        final reopened = await SettingsController.load();
        expect(reopened.apiBaseUrl, 'https://trokim.exemplo.local/v1');

        SharedPreferences.setMockInitialValues({'api_base_url': 'lixo'});
        final broken = await SettingsController.load();
        expect(broken.apiBaseUrl, ApiConstants.defaultBaseUrl);
      },
    );

    test('normalizeBaseUrl aceita só http(s) com servidor', () {
      expect(
        ApiConstants.normalizeBaseUrl('http://10.0.2.2:8000/v1///'),
        'http://10.0.2.2:8000/v1',
      );
      expect(
        ApiConstants.normalizeBaseUrl('https://api.exemplo.com'),
        'https://api.exemplo.com',
      );
      for (final bad in [
        '',
        'abc',
        'http://',
        'ftp://servidor/v1',
        'http://x/v1?a=1',
        'http://x/v1#topo',
      ]) {
        expect(ApiConstants.normalizeBaseUrl(bad), isNull, reason: bad);
      }
    });
  });
}
