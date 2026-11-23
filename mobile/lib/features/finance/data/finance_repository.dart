import '../../../core/network/api_client.dart';
import '../../../core/storage/library_sync.dart';
import '../../categories/domain/ledger_entry.dart';
import '../domain/finance_models.dart';
import '../domain/library_models.dart';

/// Acesso às transações, arquivos, parcelamentos e transferências da API local.
class FinanceRepository {
  /// [newClient] cria um cliente por operação, que é fechado ao final; assim
  /// o endereço da API editado em Ajustes vale na chamada seguinte.
  FinanceRepository(this._newClient, {LibrarySync? sync}) : _sync = sync;

  final ApiClient Function() _newClient;

  /// Guarda no aparelho o retrato da biblioteca depois de cada alteração (ADR 0025).
  final LibrarySync? _sync;

  Future<T> _run<T>(Future<T> Function(ApiClient client) action) async {
    final client = _newClient();
    try {
      return await action(client);
    } finally {
      client.close();
    }
  }

  /// Como [_run], mas grava o retrato no aparelho quando a alteração dá certo.
  Future<T> _mutate<T>(Future<T> Function(ApiClient client) action) async {
    final result = await _run(action);
    await _sync?.saveFromApi();
    return result;
  }

  /// Grava o retrato atual no aparelho (depois de restaurar um backup).
  Future<void> saveToDevice() async => _sync?.saveFromApi();

  Future<FinancialSummary> fetchSummary({
    String owner = 'todas',
    String view = 'competencia',
  }) => _run(
    (client) async => FinancialSummary.fromJson(
      await client.getSummary(owner: owner, view: view),
    ),
  );

  Future<List<ImportedFile>> fetchImportedFiles() => _run(
    (client) async =>
        ImportedFile.fromTransactions(await client.getTransactions()),
  );

  Future<List<LedgerEntry>> fetchEntries() => _run(
    (client) async => LedgerEntry.listFromJson(await client.getTransactions()),
  );

  Future<CategoryChange> setCategory(
    String uid,
    String category, {
    bool applyToMerchant = true,
  }) => _mutate(
    (client) async => CategoryChange.fromJson(
      await client.setTransactionCategory(
        uid,
        category,
        applyToMerchant: applyToMerchant,
      ),
    ),
  );

  Future<StatementsData> fetchStatements() => _run(
    (client) async => StatementsData.fromJson(await client.getStatements()),
  );

  Future<InstallmentsData> fetchInstallments() => _run(
    (client) async => InstallmentsData.fromJson(await client.getInstallments()),
  );

  Future<List<AccountInfo>> fetchAccounts() => _run(
    (client) async => [
      for (final item in await client.getAccounts()) AccountInfo.fromJson(item),
    ],
  );

  Future<List<TransferSuggestion>> fetchTransferSuggestions() => _run(
    (client) async => [
      for (final item in await client.getTransferSuggestions())
        TransferSuggestion.fromJson(item),
    ],
  );

  Future<List<OwnTransfer>> fetchTransfers() => _run(
    (client) async => [
      for (final item in await client.getTransfers())
        OwnTransfer.fromJson(item),
    ],
  );

  Future<ImportResult> uploadStatement(
    String filename,
    List<int> bytes, {
    AccountOwner? owner,
    String? expectKind,
    bool confirmed = false,
  }) => _mutate(
    (client) async => ImportResult.fromJson(
      await client.uploadStatement(
        filename,
        bytes,
        owner: owner?.api,
        expectKind: expectKind,
        confirmed: confirmed,
      ),
    ),
  );

  Future<Inspection> inspectStatement(
    String filename,
    List<int> bytes, {
    AccountOwner? owner,
    String? expectKind,
  }) => _run(
    (client) async => Inspection.fromJson(
      await client.inspectStatement(
        filename,
        bytes,
        owner: owner?.api,
        expectKind: expectKind,
      ),
    ),
  );

  Future<AccountInfo> setAccountOwner(String id, AccountOwner owner) => _mutate(
    (client) async =>
        AccountInfo.fromJson(await client.patchAccount(id, owner: owner.api)),
  );

  Future<StatementInfo> patchStatement(
    String id, {
    bool? closed,
    DateTime? periodStart,
    DateTime? periodEnd,
  }) => _mutate(
    (client) async => StatementInfo.fromJson(
      await client.patchStatement(
        id,
        closed: closed,
        periodStart: periodStart,
        periodEnd: periodEnd,
      ),
    ),
  );

  Future<void> confirmTransfer(TransferSuggestion item) => _mutate(
    (client) => client.confirmTransfer(item.debitUid, item.creditUid),
  );

  Future<void> rejectTransfer(TransferSuggestion item) =>
      _mutate((client) => client.rejectTransfer(item.debitUid, item.creditUid));

  Future<void> undoTransfer(OwnTransfer item) => _mutate(
    (client) => item.automatic
        ? client.unmarkTransfer(item.id)
        : client.undoTransfer(item.id),
  );
}
