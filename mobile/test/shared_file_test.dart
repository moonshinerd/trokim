import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/core/sharing/shared_file_listener.dart';
import 'package:trokim/core/sharing/shared_file_receiver.dart';

import 'support/finance_fixtures.dart';
import 'support/flow_harness.dart';

const _channel = MethodChannel(SharedFileReceiver.channelName);

void _mockNative(Object? initial) {
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(_channel, (call) async {
        if (call.method == 'takeInitialFile') return initial;
        return null;
      });
  addTearDown(
    () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_channel, null),
  );
}

/// Simula o Android avisando que um arquivo chegou com o app aberto.
Future<void> _shareFromNative(Map<String, Object?> file) async {
  final data = const StandardMethodCodec().encodeMethodCall(
    MethodCall('fileShared', file),
  );
  await TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .handlePlatformMessage(SharedFileReceiver.channelName, data, (_) {});
}

Map<String, Object?> _file(String name) => {
  'name': name,
  'bytes': Uint8List.fromList([60, 79, 70, 88]),
};

void main() {
  group('SharedFileReceiver', () {
    test('converte o mapa do canal no arquivo do fluxo', () async {
      final file = SharedFileReceiver.parse(_file('fatura.pdf'))!;
      expect(file.name, 'fatura.pdf');
      expect(await file.readBytes(), [60, 79, 70, 88]);
    });

    test('ignora dados incompletos', () {
      expect(SharedFileReceiver.parse(null), isNull);
      expect(SharedFileReceiver.parse({'name': 'a.ofx'}), isNull);
      expect(
        SharedFileReceiver.parse({'name': '', 'bytes': Uint8List(3)}),
        isNull,
      );
      expect(
        SharedFileReceiver.parse({'name': 'a.ofx', 'bytes': Uint8List(0)}),
        isNull,
      );
    });

    testWidgets('entrega o arquivo que abriu o app uma vez', (tester) async {
      _mockNative(_file('Nubank_2026-12-10.ofx'));
      final receiver = SharedFileReceiver();
      addTearDown(receiver.dispose);
      final file = await receiver.takeInitialFile();
      expect(file!.name, 'Nubank_2026-12-10.ofx');
    });

    testWidgets('sem o canal nativo (web, testes) não há arquivo', (
      tester,
    ) async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
            _channel,
            (_) async => throw MissingPluginException(),
          );
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(_channel, null),
      );
      final receiver = SharedFileReceiver();
      addTearDown(receiver.dispose);
      expect(await receiver.takeInitialFile(), isNull);
    });

    testWidgets('arquivo compartilhado com o app aberto sai no stream', (
      tester,
    ) async {
      _mockNative(null);
      final receiver = SharedFileReceiver();
      addTearDown(receiver.dispose);
      final received = <String>[];
      final sub = receiver.files.listen((f) => received.add(f.name));
      addTearDown(sub.cancel);
      await _shareFromNative(_file('extrato.ofx'));
      await tester.pump();
      expect(received, ['extrato.ofx']);
    });
  });

  group('SharedFileListener', () {
    Future<(FlowHarness, List<int>)> open(
      WidgetTester tester,
      SharedFileReceiver receiver,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) =>
          jsonResponse(uploadJson(filename: 'Nubank_2026-12-10.ofx'));
      final calls = <int>[];
      await h.open(
        tester,
        home: SharedFileListener(
          receiver: receiver,
          onFile: () => calls.add(1),
          child: const Scaffold(body: Text('início')),
        ),
      );
      return (h, calls);
    }

    testWidgets('arquivo que abriu o app vai direto para a leitura', (
      tester,
    ) async {
      _mockNative(_file('Nubank_2026-12-10.ofx'));
      final receiver = SharedFileReceiver();
      addTearDown(receiver.dispose);
      final (h, calls) = await open(tester, receiver);
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 200)),
      );
      await tester.pumpAndSettle();
      expect(calls, [1]);
      expect(find.text('De qual banco é o arquivo?'), findsNothing);
      expect(find.text('Pronto!'), findsOneWidget);
      expect(h.api.count('POST', '/transactions/upload'), 1);
    });

    testWidgets('arquivo que chega depois também abre o fluxo', (tester) async {
      _mockNative(null);
      final receiver = SharedFileReceiver();
      addTearDown(receiver.dispose);
      final (h, calls) = await open(tester, receiver);
      expect(find.text('início'), findsOneWidget);
      expect(calls, isEmpty);
      await tester.runAsync(() async {
        await _shareFromNative(_file('Nubank_2026-12-10.ofx'));
        await Future<void>.delayed(const Duration(milliseconds: 200));
      });
      await tester.pumpAndSettle();
      expect(calls, [1]);
      expect(find.text('Pronto!'), findsOneWidget);
      expect(h.api.count('POST', '/transactions/upload'), 1);
    });
  });
}
