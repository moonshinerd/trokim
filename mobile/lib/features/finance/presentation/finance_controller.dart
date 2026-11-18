import 'dart:async';

import 'package:flutter/widgets.dart';

import '../../../core/network/api_client.dart';
import '../data/finance_repository.dart';
import '../domain/finance_models.dart';
import '../domain/library_models.dart';

enum FinanceStatus { idle, loading, ready, error }

/// Falha de importação com mensagem pronta para mostrar ao usuário.
class ImportFailure implements Exception {
  const ImportFailure(this.message, {this.conflict = false});

  final String message;

  /// A API barrou o arquivo (HTTP 409) por um conflito que o usuário pode confirmar.
  final bool conflict;

  @override
  String toString() => message;
}

/// Estado do resumo financeiro, dos arquivos, dos parcelamentos e das transferências.
class FinanceController extends ChangeNotifier {
  FinanceController(this._repository);

  final FinanceRepository _repository;

  FinanceStatus _status = FinanceStatus.idle;
  FinancialSummary? _summary;
  List<ImportedFile> _files = const [];
  StatementsData _statements = const StatementsData.empty();
  InstallmentsData _installments = const InstallmentsData.empty();
  List<TransferSuggestion> _suggestions = const [];
  List<OwnTransfer> _transfers = const [];
  List<AccountInfo> _accounts = const [];
  String _owner = 'todas';
  String _view = 'competencia';
  bool _importing = false;
  bool _disposed = false;
  Future<void>? _loading;

  FinanceStatus get status => _status;
  FinancialSummary? get summary => _summary;
  List<ImportedFile> get files => List.unmodifiable(_files);
  StatementsData get statements => _statements;
  InstallmentsData get installments => _installments;
  List<TransferSuggestion> get suggestions => List.unmodifiable(_suggestions);
  List<OwnTransfer> get transfers => List.unmodifiable(_transfers);
  List<AccountInfo> get accounts => List.unmodifiable(_accounts);

  /// Filtro do Resumo: `todas`, `pessoal` ou `empresa`.
  String get ownerFilter => _owner;

  /// Visão do Resumo: `competencia` ou `caixa`.
  String get view => _view;
  bool get importing => _importing;

  /// Há mais de um dono entre as contas: só então o filtro pessoal/empresa faz sentido.
  bool get hasSeveralOwners =>
      _accounts
          .where((a) => a.owner != null)
          .map((a) => a.owner)
          .toSet()
          .length >
      1;

  /// Arquivos ainda abertos (fatura que não fechou ou extrato parcial).
  List<StatementInfo> get incompleteStatements =>
      _statements.statements.where((s) => s.status.isIncomplete).toList();

  /// Carrega resumo e arquivos. Chamadas simultâneas compartilham a mesma
  /// requisição. Falhas viram [FinanceStatus.error]; nunca lançam.
  Future<void> load() => _loading ??= _load().whenComplete(() {
    _loading = null;
  });

  Future<T> _optional<T>(Future<T> Function() action, T fallback) async {
    try {
      return await action();
    } on Object {
      // Uma API mais antiga pode não ter estes recursos: o essencial continua.
      return fallback;
    }
  }

  Future<void> _load() async {
    _status = FinanceStatus.loading;
    _notify();
    try {
      final results = await Future.wait<Object>([
        _repository.fetchSummary(owner: _owner, view: _view),
        _repository.fetchImportedFiles(),
      ]);
      _summary = results[0] as FinancialSummary;
      _files = results[1] as List<ImportedFile>;
      final extras = await Future.wait<Object>([
        _optional(_repository.fetchStatements, const StatementsData.empty()),
        _optional(
          _repository.fetchInstallments,
          const InstallmentsData.empty(),
        ),
        _optional(_repository.fetchTransferSuggestions, <TransferSuggestion>[]),
        _optional(_repository.fetchTransfers, <OwnTransfer>[]),
        _optional(_repository.fetchAccounts, <AccountInfo>[]),
      ]);
      _statements = extras[0] as StatementsData;
      _installments = extras[1] as InstallmentsData;
      _suggestions = extras[2] as List<TransferSuggestion>;
      _transfers = extras[3] as List<OwnTransfer>;
      _accounts = extras[4] as List<AccountInfo>;
      _status = FinanceStatus.ready;
    } on Object {
      _status = FinanceStatus.error;
    }
    _notify();
  }

  Future<void> setOwnerFilter(String owner) {
    if (owner == _owner) return Future.value();
    _owner = owner;
    return _reloadSummary();
  }

  Future<void> setView(String view) {
    if (view == _view) return Future.value();
    _view = view;
    return _reloadSummary();
  }

  Future<void> _reloadSummary() async {
    try {
      _summary = await _repository.fetchSummary(owner: _owner, view: _view);
      _status = FinanceStatus.ready;
    } on Object {
      _status = FinanceStatus.error;
    }
    _notify();
  }

  ImportFailure _failure(Object error) {
    if (error is ImportFailure) return error;
    if (error is ApiException) {
      return ImportFailure(
        error.detail ?? 'A API recusou o arquivo (erro ${error.statusCode}).',
        conflict: error.statusCode == 409,
      );
    }
    if (error is TimeoutException) {
      return const ImportFailure(
        'A API demorou demais para processar o arquivo.',
      );
    }
    return const ImportFailure(
      'Não foi possível enviar o arquivo à API local. '
      'Confira o endereço em Ajustes.',
    );
  }

  void _checkExtension(String name) {
    final lower = name.toLowerCase();
    if (!lower.endsWith('.ofx') && !lower.endsWith('.pdf')) {
      throw const ImportFailure(
        'Formato não suportado. Escolha um arquivo .ofx ou .pdf.',
      );
    }
  }

  /// Analisa o arquivo sem importar (banco, tipo, dono provável e avisos). Para PDF, devolve
  /// uma análise vazia: o detector só lê OFX.
  Future<Inspection> inspect(
    String name,
    Future<List<int>> Function() readBytes, {
    AccountOwner? owner,
    String? expectKind,
  }) async {
    _checkExtension(name);
    try {
      return await _repository.inspectStatement(
        name,
        await readBytes(),
        owner: owner,
        expectKind: expectKind,
      );
    } on Object catch (e) {
      throw _failure(e);
    }
  }

  /// Envia um extrato OFX ou PDF e recarrega o resumo. Lança [ImportFailure]
  /// com a mensagem a exibir quando algo dá errado.
  Future<ImportResult> importStatement(
    String name,
    Future<List<int>> Function() readBytes, {
    AccountOwner? owner,
    String? expectKind,
    bool confirmed = false,
  }) async {
    _checkExtension(name);
    _importing = true;
    _notify();
    try {
      final result = await _repository.uploadStatement(
        name,
        await readBytes(),
        owner: owner,
        expectKind: expectKind,
        confirmed: confirmed,
      );
      await load();
      return result;
    } on Object catch (e) {
      throw _failure(e);
    } finally {
      _importing = false;
      _notify();
    }
  }

  Future<StatementInfo> confirmStatementClosed(
    StatementInfo statement, {
    required bool closed,
  }) async {
    final updated = await _repository.patchStatement(
      statement.id,
      closed: closed,
    );
    await load();
    return updated;
  }

  Future<StatementInfo> setStatementPeriod(
    StatementInfo statement,
    DateTime start,
    DateTime end,
  ) async {
    final updated = await _repository.patchStatement(
      statement.id,
      periodStart: start,
      periodEnd: end,
    );
    await load();
    return updated;
  }

  Future<void> setAccountOwner(String accountId, AccountOwner owner) async {
    await _repository.setAccountOwner(accountId, owner);
    await load();
  }

  Future<void> confirmTransfer(TransferSuggestion item) async {
    await _repository.confirmTransfer(item);
    await load();
  }

  Future<void> rejectTransfer(TransferSuggestion item) async {
    await _repository.rejectTransfer(item);
    await load();
  }

  Future<void> undoTransfer(OwnTransfer item) async {
    await _repository.undoTransfer(item);
    await load();
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
