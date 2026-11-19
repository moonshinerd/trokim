/// Um lançamento importado, como a API devolve em `GET /transactions`.
class LedgerEntry {
  const LedgerEntry({
    required this.uid,
    required this.date,
    required this.amount,
    required this.isDebit,
    required this.category,
    required this.nature,
    required this.description,
    this.merchant,
    this.isDuplicate = false,
  });

  final String uid;
  final DateTime date;
  final double amount;
  final bool isDebit;
  final String category;
  final String nature;
  final String description;
  final String? merchant;
  final bool isDuplicate;

  /// Pagamento de fatura, investimento e transferência entre contas próprias não são gasto
  /// nem renda: não têm categoria para corrigir.
  static const _movements = {
    'pagamento_fatura',
    'resgate_investimento',
    'aplicacao_investimento',
    'transferencia_propria',
  };

  /// Gasto que o usuário pode recategorizar.
  bool get isEditableExpense =>
      isDebit && !isDuplicate && !_movements.contains(nature);

  /// Nome para exibir: o estabelecimento, ou a descrição do banco quando não houver.
  String get title {
    final name = merchant?.trim() ?? '';
    return name.isEmpty ? description : name;
  }

  static LedgerEntry? tryParse(Map<String, dynamic> json) {
    final uid = json['uid'];
    final date = DateTime.tryParse('${json['date']}');
    final amount = json['amount'];
    if (uid is! String || date == null || amount is! num) return null;
    final merchant = json['merchant'];
    return LedgerEntry(
      uid: uid,
      date: date,
      amount: amount.toDouble().abs(),
      isDebit: json['type'] == 'debit',
      category: json['category'] is String
          ? json['category'] as String
          : 'outros',
      nature: json['nature'] is String ? json['nature'] as String : 'outro',
      description: json['description'] is String
          ? json['description'] as String
          : '',
      merchant: merchant is String ? merchant : null,
      isDuplicate: json['is_duplicate'] == true,
    );
  }

  /// Lê a lista da API ignorando itens que não tenham o mínimo necessário.
  static List<LedgerEntry> listFromJson(List<Map<String, dynamic>> items) => [
    for (final item in items) ?tryParse(item),
  ];
}

/// Resultado da correção de categoria.
class CategoryChange {
  const CategoryChange({
    required this.updated,
    required this.rule,
    this.merchant,
  });

  /// Quantos lançamentos mudaram (o escolhido e os do mesmo estabelecimento).
  final int updated;

  /// A escolha virou regra para o estabelecimento (vale para os próximos arquivos).
  final bool rule;
  final String? merchant;

  factory CategoryChange.fromJson(Map<String, dynamic> json) => CategoryChange(
    updated: json['updated'] is int ? json['updated'] as int : 1,
    rule: json['rule'] == true,
    merchant: json['merchant'] is String ? json['merchant'] as String : null,
  );
}
