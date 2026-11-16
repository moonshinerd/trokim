import '../../../core/network/api_client.dart';
import '../domain/finance_models.dart';

/// Acesso às transações e ao resumo da API local.
class FinanceRepository {
  /// [newClient] cria um cliente por operação, que é fechado ao final; assim
  /// o endereço da API editado em Ajustes vale na chamada seguinte.
  FinanceRepository(this._newClient);

  final ApiClient Function() _newClient;

  Future<T> _run<T>(Future<T> Function(ApiClient client) action) async {
    final client = _newClient();
    try {
      return await action(client);
    } finally {
      client.close();
    }
  }

  Future<FinancialSummary> fetchSummary() => _run(
    (client) async => FinancialSummary.fromJson(await client.getSummary()),
  );

  Future<List<ImportedFile>> fetchImportedFiles() => _run(
    (client) async =>
        ImportedFile.fromTransactions(await client.getTransactions()),
  );

  Future<ImportResult> uploadStatement(String filename, List<int> bytes) =>
      _run(
        (client) async => ImportResult.fromJson(
          await client.uploadStatement(filename, bytes),
        ),
      );
}
