import 'library_models.dart';

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
    this.excludedCount = 0,
    this.topMerchants = const [],
    this.view = 'competencia',
    this.owner = 'todas',
    this.byAccount = const [],
  });

  final double totalIncome;
  final double totalExpenses;
  final double netBalance;

  /// Taxa de poupança em percentual, como vem da API (ex.: 56,99).
  final double savingsRatePercent;

  /// Despesas por categoria (`moradia`, `alimentacao`, ...), em reais.
  final Map<String, double> expensesByCategory;
  final int transactionCount;

  /// Movimentações fora dos totais (pagamento de fatura, resgates e
  /// transferências próprias), para não contar o mesmo dinheiro duas vezes.
  final int excludedCount;

  /// Estabelecimentos com mais gastos, do maior para o menor.
  final List<MerchantTotal> topMerchants;

  /// `competencia` (gastos quando acontecem) ou `caixa` (o que passou pelas contas).
  final String view;

  /// `todas`, `pessoal` ou `empresa`.
  final String owner;
  final List<AccountTotals> byAccount;

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
      excludedCount: json['excluded_count'] is int
          ? json['excluded_count'] as int
          : 0,
      topMerchants: _merchants(json['top_merchants']),
      view: json['view'] is String ? json['view'] as String : 'competencia',
      owner: json['owner'] is String ? json['owner'] as String : 'todas',
      byAccount: _accounts(json['by_account']),
    );
  }
}

/// Receitas e despesas de uma conta ou cartão (calculadas pela API).
class AccountTotals {
  const AccountTotals({
    required this.label,
    required this.income,
    required this.expenses,
    required this.count,
    this.owner,
    this.kind,
  });

  final String label;
  final AccountOwner? owner;
  final String? kind;
  final double income;
  final double expenses;
  final int count;

  bool get isCard => kind == 'cartao';
}

List<AccountTotals> _accounts(Object? raw) {
  if (raw is! List) return const [];
  return [
    for (final item in raw)
      if (item is Map && item['income'] is num && item['expenses'] is num)
        AccountTotals(
          label: item['label'] is String
              ? item['label'] as String
              : '${item['account_id']}',
          owner: AccountOwner.fromApi(item['owner']),
          kind: item['kind'] as String?,
          income: (item['income'] as num).toDouble(),
          expenses: (item['expenses'] as num).toDouble(),
          count: item['count'] is int ? item['count'] as int : 0,
        ),
  ];
}

/// Total gasto em um estabelecimento (calculado pela API).
class MerchantTotal {
  const MerchantTotal(this.merchant, this.total);

  final String merchant;
  final double total;
}

List<MerchantTotal> _merchants(Object? raw) {
  if (raw is! List) return const [];
  return [
    for (final item in raw)
      if (item is Map && item['merchant'] is String && item['total'] is num)
        MerchantTotal(
          item['merchant'] as String,
          (item['total'] as num).toDouble(),
        ),
  ];
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
  const ImportResult({
    required this.filename,
    required this.importedCount,
    this.duplicateCount = 0,
    this.institution,
    this.kind,
    this.uncategorizedCount = 0,
    this.excludedCount = 0,
    this.outcome = 'novo',
    this.delta = 0,
    this.account,
    this.statement,
    this.autoTransfers = 0,
    this.transferSuggestions = 0,
  });

  final String filename;
  final int importedCount;
  final int duplicateCount;

  /// Banco detectado pelo conteúdo do arquivo (ex.: `nubank`), se reconhecido.
  final String? institution;

  /// `cartao` ou `conta`, quando o banco foi reconhecido.
  final String? kind;
  final int uncategorizedCount;

  /// Movimentações fora dos totais neste arquivo.
  final int excludedCount;

  /// `novo`, `atualizado` (mesmo período, conteúdo diferente) ou `repetido`.
  final String outcome;

  /// Quantos lançamentos a atualização acrescentou (ou tirou).
  final int delta;
  final AccountInfo? account;
  final StatementInfo? statement;

  /// Transferências entre contas suas reconhecidas sozinhas neste arquivo.
  final int autoTransfers;

  /// Possíveis transferências entre contas que aguardam confirmação.
  final int transferSuggestions;

  String? get institutionLabel => switch (institution) {
    'nubank' => 'Nubank',
    final other? => other,
    null => null,
  };

  String? get kindLabel => switch (kind) {
    'cartao' => 'fatura do cartão',
    'conta' => 'extrato da conta',
    _ => null,
  };

  factory ImportResult.fromJson(Map<String, dynamic> json) {
    final filename = json['filename'];
    if (filename is! String) {
      throw const FormatException('Resposta de importação inválida.');
    }
    final byNature = json['by_nature'];
    var excluded = 0;
    if (byNature is Map) {
      for (final key in const [
        'pagamento_fatura',
        'resgate_investimento',
        'aplicacao_investimento',
        'transferencia_propria',
      ]) {
        final value = byNature[key];
        if (value is int) excluded += value;
      }
    }
    return ImportResult(
      filename: filename,
      importedCount: _count(json, 'imported_count'),
      duplicateCount: json['duplicate_count'] is int
          ? json['duplicate_count'] as int
          : 0,
      institution: json['institution'] as String?,
      kind: json['kind'] as String?,
      uncategorizedCount: json['uncategorized_count'] is int
          ? json['uncategorized_count'] as int
          : 0,
      excludedCount: excluded,
      outcome: json['outcome'] is String ? json['outcome'] as String : 'novo',
      delta: json['delta'] is int ? json['delta'] as int : 0,
      account: json['account'] is Map<String, dynamic>
          ? AccountInfo.fromJson(json['account'] as Map<String, dynamic>)
          : null,
      statement: json['statement'] is Map<String, dynamic>
          ? StatementInfo.fromJson(json['statement'] as Map<String, dynamic>)
          : null,
      autoTransfers: json['auto_transfers'] is int
          ? json['auto_transfers'] as int
          : 0,
      transferSuggestions: json['transfer_suggestions'] is int
          ? json['transfer_suggestions'] as int
          : 0,
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
