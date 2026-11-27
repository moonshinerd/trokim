// Ponto de entrada só da homologação web: igual ao lib/main.dart, mas guarda a
// biblioteca na memória, porque o path_provider não tem implementação web.
import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/core/sharing/shared_file_receiver.dart';
import 'package:trokim/core/storage/library_sync.dart';
import 'package:trokim/core/storage/local_library_store.dart';
import 'package:trokim/core/widgets/mascot.dart';
import 'package:trokim/features/finance/data/finance_repository.dart';
import 'package:trokim/features/finance/presentation/finance_controller.dart';
import 'package:trokim/main.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Árvore de acessibilidade sempre ligada: o teste clica pelos rótulos.
  SemanticsBinding.instance.ensureSemantics();
  final settings = await SettingsController.load();
  await Mascot.load();
  ApiClient newClient() =>
      ApiClient(baseUrlProvider: () => settings.apiBaseUrl);
  final sync = LibrarySync(MemoryLibraryStore(), newClient);
  final finance = FinanceController(FinanceRepository(newClient, sync: sync));
  final firstLoad = () async {
    await sync.hydrate();
    await finance.load();
  }();
  runApp(
    SettingsScope(
      controller: settings,
      child: FinanceScope(
        controller: finance,
        child: TrokimApp(
          firstLoad: firstLoad,
          sharedFiles: SharedFileReceiver(),
        ),
      ),
    ),
  );
}
