import 'dart:convert';
import 'dart:typed_data';

import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/features/backup/presentation/backup_card.dart';
import 'package:trokim/features/settings/presentation/settings_screen.dart';

class _Saved {
  String? name;
  List<int>? bytes;
}

Future<SettingsController> _open(
  WidgetTester tester, {
  required http.Client client,
  BackupSaver? saver,
  BackupPicker? picker,
}) async {
  final settings = SettingsController.memory();
  addTearDown(settings.dispose);
  await tester.pumpWidget(
    SettingsScope(
      controller: settings,
      child: MaterialApp(
        home: SettingsScreen(
          controller: settings,
          client: client,
          saveBackup: saver,
          pickBackup: picker,
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  await tester.scrollUntilVisible(
    find.text('Exportar backup'),
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.ensureVisible(find.text('Exportar backup'));
  await tester.pumpAndSettle();
  return settings;
}

Future<void> _typePassphrase(WidgetTester tester, String text) async {
  await tester.ensureVisible(find.byType(TextField).last);
  await tester.enterText(find.byType(TextField).last, text);
  await tester.pump();
}

String _message(WidgetTester tester) =>
    tester.widget<Text>(find.byKey(const Key('backup-message'))).data!;

void main() {
  testWidgets('exporta com a senha e entrega o arquivo ao seletor', (
    tester,
  ) async {
    final saved = _Saved();
    late http.Request received;
    final client = MockClient((request) async {
      received = request;
      return http.Response.bytes([1, 2, 3, 4], 200);
    });
    await _open(
      tester,
      client: client,
      saver: (name, bytes) async {
        saved
          ..name = name
          ..bytes = bytes;
        return true;
      },
    );
    await _typePassphrase(tester, 'senha-longa-123');
    await tester.tap(find.text('Exportar backup'));
    await tester.pumpAndSettle();

    expect(received.url.path, endsWith('/backup/export'));
    expect(jsonDecode(received.body), {'passphrase': 'senha-longa-123'});
    expect(saved.name, endsWith('.trokim'));
    expect(saved.bytes, [1, 2, 3, 4]);
    expect(_message(tester), contains('Backup criptografado salvo'));
  });

  testWidgets('recusa senha curta sem chamar a API', (tester) async {
    var calls = 0;
    final client = MockClient((request) async {
      calls++;
      return http.Response('', 200);
    });
    await _open(tester, client: client);
    await _typePassphrase(tester, '123');
    await tester.tap(find.text('Exportar backup'));
    await tester.pumpAndSettle();

    expect(calls, 0);
    expect(_message(tester), contains('pelo menos 8 caracteres'));
  });

  testWidgets('restaura mesclando e mostra quantos lançamentos entraram', (
    tester,
  ) async {
    late http.BaseRequest received;
    final client = MockClient.streaming((request, body) async {
      received = request;
      final payload = jsonEncode({
        'mode': 'mesclar',
        'added': {'transactions': 2, 'accounts': 1, 'statements': 1},
        'transactions_total': 5,
      });
      return http.StreamedResponse(
        Stream.value(utf8.encode(payload)),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    await _open(
      tester,
      client: client,
      picker: () async =>
          PickedBackup('meu.trokim', () async => Uint8List.fromList([9, 9, 9])),
    );
    await _typePassphrase(tester, 'senha-longa-123');
    await tester.tap(find.text('Restaurar backup'));
    await tester.pumpAndSettle();

    expect(received.url.path, endsWith('/backup/import'));
    expect(_message(tester), contains('2 lançamentos novos, 5 no total'));
  });

  testWidgets('mostra o motivo quando a senha está errada', (tester) async {
    final client = MockClient.streaming((request, body) async {
      return http.StreamedResponse(
        Stream.value(
          utf8.encode(
            jsonEncode({'detail': 'Senha incorreta ou arquivo corrompido.'}),
          ),
        ),
        400,
        headers: {'content-type': 'application/json'},
      );
    });
    await _open(
      tester,
      client: client,
      picker: () async =>
          PickedBackup('meu.trokim', () async => Uint8List.fromList([1])),
    );
    await _typePassphrase(tester, 'senha-errada-999');
    await tester.tap(find.text('Restaurar backup'));
    await tester.pumpAndSettle();

    expect(_message(tester), 'Senha incorreta ou arquivo corrompido.');
  });

  testWidgets('substituir pede confirmação e cancelar não chama a API', (
    tester,
  ) async {
    var calls = 0;
    final client = MockClient.streaming((request, body) async {
      calls++;
      return http.StreamedResponse(const Stream.empty(), 200);
    });
    await _open(
      tester,
      client: client,
      picker: () async =>
          PickedBackup('meu.trokim', () async => Uint8List.fromList([1])),
    );
    await _typePassphrase(tester, 'senha-longa-123');
    await tester.tap(find.byType(Switch));
    await tester.pump();
    await tester.tap(find.text('Restaurar backup'));
    await tester.pumpAndSettle();

    expect(find.text('Substituir tudo?'), findsOneWidget);
    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();
    expect(calls, 0);
  });
}
