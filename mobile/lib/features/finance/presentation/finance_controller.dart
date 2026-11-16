import 'dart:async';

import 'package:flutter/widgets.dart';

import '../../../core/network/api_client.dart';
import '../data/finance_repository.dart';
import '../domain/finance_models.dart';

enum FinanceStatus { idle, loading, ready, error }

/// Falha de importação com mensagem pronta para mostrar ao usuário.
class ImportFailure implements Exception {
  const ImportFailure(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Estado do resumo financeiro e dos extratos importados.
class FinanceController extends ChangeNotifier {
  FinanceController(this._repository);

  final FinanceRepository _repository;

  FinanceStatus _status = FinanceStatus.idle;
  FinancialSummary? _summary;
  List<ImportedFile> _files = const [];
  bool _importing = false;
  bool _disposed = false;
  Future<void>? _loading;

  FinanceStatus get status => _status;
  FinancialSummary? get summary => _summary;
  List<ImportedFile> get files => List.unmodifiable(_files);
  bool get importing => _importing;

  /// Carrega resumo e arquivos. Chamadas simultâneas compartilham a mesma
  /// requisição. Falhas viram [FinanceStatus.error]; nunca lançam.
  Future<void> load() => _loading ??= _load().whenComplete(() {
    _loading = null;
  });

  Future<void> _load() async {
    _status = FinanceStatus.loading;
    _notify();
    try {
      final results = await Future.wait<Object>([
        _repository.fetchSummary(),
        _repository.fetchImportedFiles(),
      ]);
      _summary = results[0] as FinancialSummary;
      _files = results[1] as List<ImportedFile>;
      _status = FinanceStatus.ready;
    } on Object {
      _status = FinanceStatus.error;
    }
    _notify();
  }

  /// Envia um extrato OFX ou PDF e recarrega o resumo. Lança [ImportFailure]
  /// com a mensagem a exibir quando algo dá errado.
  Future<ImportResult> importStatement(
    String name,
    Future<List<int>> Function() readBytes,
  ) async {
    final lower = name.toLowerCase();
    if (!lower.endsWith('.ofx') && !lower.endsWith('.pdf')) {
      throw const ImportFailure(
        'Formato não suportado. Escolha um arquivo .ofx ou .pdf.',
      );
    }
    _importing = true;
    _notify();
    try {
      final result = await _repository.uploadStatement(name, await readBytes());
      await load();
      return result;
    } on ApiException catch (e) {
      throw ImportFailure(
        e.detail ?? 'A API recusou o arquivo (erro ${e.statusCode}).',
      );
    } on TimeoutException {
      throw const ImportFailure(
        'A API demorou demais para processar o arquivo.',
      );
    } on Object {
      throw const ImportFailure(
        'Não foi possível enviar o arquivo à API local. '
        'Confira o endereço em Ajustes.',
      );
    } finally {
      _importing = false;
      _notify();
    }
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}

/// Disponibiliza o [FinanceController] para toda a árvore de widgets.
class FinanceScope extends InheritedNotifier<FinanceController> {
  const FinanceScope({
    super.key,
    required FinanceController controller,
    required super.child,
  }) : super(notifier: controller);

  /// Sem registrar dependência (para ações, como recarregar após uma mudança).
  static FinanceController? read(BuildContext context) =>
      context.getInheritedWidgetOfExactType<FinanceScope>()?.notifier;

  static FinanceController of(BuildContext context) {
    final controller = context
        .dependOnInheritedWidgetOfExactType<FinanceScope>()
        ?.notifier;
    assert(controller != null, 'FinanceScope ausente na árvore de widgets.');
    return controller!;
  }
}
