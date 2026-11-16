/// Resumo financeiro calculado pela API (`/transactions/summary`).
///
/// O app só exibe estes números: somas, saldo e taxa de poupança são
/// computados no backend (`calculation_service.py`), nunca no aparelho.
class FinancialSummary {
  const FinancialSummary({
    required this.totalIncome,
    required this.totalExpenses,
    required this.netBalance,
    required this.savingsRatePercent,
    required this.expensesByCategory,
    required this.transactionCount,
  });

  final double totalIncome;
  final double totalExpenses;
  final double netBalance;

  /// Taxa de poupança em percentual, como vem da API (ex.: 56,99).
  final double savingsRatePercent;

  /// Despesas por categoria (`moradia`, `alimentacao`, ...), em reais.
  final Map<String, double> expensesByCategory;
  final int transactionCount;

  bool get isEmpty => transactionCount == 0;

  /// Taxa de poupança como fração de 0 a 1, para a barra de progresso.
  double get savingsFraction => (savingsRatePercent / 100).clamp(0.0, 1.0);

  factory FinancialSummary.fromJson(Map<String, dynamic> json) {
    final categories = json['expenses_by_category'];
    if (categories is! Map) {
      throw const FormatException('Resumo inválido: categorias ausentes.');
    }
    final byCategory = <String, double>{};
    for (final entry in categories.entries) {
      final key = entry.key;
      final value = entry.value;
      if (key is! String || value is! num) {
        throw const FormatException('Resumo inválido: categoria.');
      }
      byCategory[key] = value.toDouble();
    }
    return FinancialSummary(
      totalIncome: _number(json, 'total_income'),
      totalExpenses: _number(json, 'total_expenses'),
      netBalance: _number(json, 'net_balance'),
      savingsRatePercent: _number(json, 'savings_rate'),
      expensesByCategory: byCategory,
      transactionCount: _count(json, 'transaction_count'),
    );
  }
}

/// Arquivo importado, reconstruído a partir de `source_file` das transações
/// guardadas na API.
class ImportedFile {
  const ImportedFile({
    required this.name,
    required this.imported,
    required this.duplicates,
  });

  final String name;

  /// Transações contabilizadas.
  final int imported;

  /// Transações descartadas por já existirem (mesma data, descrição e valor).
  final int duplicates;

  String get kind => name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'OFX';

  /// Agrupa por arquivo, na ordem em que cada um apareceu pela primeira vez.
  static List<ImportedFile> fromTransactions(
    List<Map<String, dynamic>> transactions,
  ) {
    final imported = <String, int>{};
    final duplicates = <String, int>{};
    for (final tx in transactions) {
      final source = tx['source_file'];
      final name = source is String && source.isNotEmpty
          ? source
          : 'arquivo desconhecido';
      imported.putIfAbsent(name, () => 0);
      duplicates.putIfAbsent(name, () => 0);
      if (tx['is_duplicate'] == true) {
        duplicates[name] = duplicates[name]! + 1;
      } else {
        imported[name] = imported[name]! + 1;
      }
    }
    return [
      for (final name in imported.keys)
        ImportedFile(
          name: name,
          imported: imported[name]!,
          duplicates: duplicates[name]!,
        ),
    ];
  }
}

/// Resposta de `POST /transactions/upload`.
class ImportResult {
  const ImportResult({required this.filename, required this.importedCount});

  final String filename;
  final int importedCount;

  factory ImportResult.fromJson(Map<String, dynamic> json) {
    final filename = json['filename'];
    if (filename is! String) {
      throw const FormatException('Resposta de importação inválida.');
    }
    return ImportResult(
      filename: filename,
      importedCount: _count(json, 'imported_count'),
    );
  }
}

double _number(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! num) {
    throw FormatException('Resumo inválido: "$key".');
  }
  return value.toDouble();
}

int _count(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! int || value < 0) {
    throw FormatException('Resposta inválida: "$key".');
  }
  return value;
}
