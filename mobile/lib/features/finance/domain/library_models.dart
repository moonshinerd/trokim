/// Contas, arquivos importados, parcelamentos e transferências, como a API calcula.
///
/// O app só exibe estes dados: períodos, situação da fatura, parcelas e transferências próprias
/// são decididos no backend (ADR 0017 e ADR 0018).
library;

import 'finance_models.dart' show institutionName;

DateTime? _date(Object? value) {
  if (value is! String) return null;
  return DateTime.tryParse(value);
}

String _string(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String) {
    throw FormatException('Campo inválido: "$key".');
  }
  return value;
}

double _double(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! num) {
    throw FormatException('Campo inválido: "$key".');
  }
  return value.toDouble();
}

int _int(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! int) {
    throw FormatException('Campo inválido: "$key".');
  }
  return value;
}

/// Dono da conta: o OFX não diz se é pessoal ou Empresas, então o app pergunta uma vez.
enum AccountOwner {
  personal('pessoal', 'Conta pessoal'),
  business('empresa', 'Nubank Empresas');

  const AccountOwner(this.api, this.label);

  final String api;
  final String label;

  static AccountOwner? fromApi(Object? value) {
    for (final owner in values) {
      if (owner.api == value) return owner;
    }
    return null;
  }
}

class AccountInfo {
  const AccountInfo({
    required this.id,
    required this.displayLabel,
    required this.needsOwner,
    this.owner,
    this.kind,
  });

  final String id;
  final String displayLabel;
  final AccountOwner? owner;

  /// `conta` ou `cartao`.
  final String? kind;
  final bool needsOwner;

  bool get isCard => kind == 'cartao';

  factory AccountInfo.fromJson(Map<String, dynamic> json) => AccountInfo(
    id: _string(json, 'id'),
    displayLabel: json['display_label'] is String
        ? json['display_label'] as String
        : _string(json, 'id'),
    owner: AccountOwner.fromApi(json['owner']),
    kind: json['kind'] as String?,
    needsOwner: json['needs_owner'] == true,
  );
}

/// Situação do período de um arquivo.
enum StatementStatus {
  closed('fechada'),
  open('aberta'),
  partial('parcial'),
  unknown('desconhecida');

  const StatementStatus(this.api);

  final String api;

  static StatementStatus fromApi(Object? value) {
    for (final status in values) {
      if (status.api == value) return status;
    }
    return StatementStatus.unknown;
  }

  bool get isIncomplete => this == open || this == partial;
}

class StatementInfo {
  const StatementInfo({
    required this.id,
    required this.accountId,
    required this.filename,
    required this.status,
    required this.userConfirmed,
    required this.importedCount,
    this.kind,
    this.periodStart,
    this.periodEnd,
    this.generatedAt,
    this.coveredUntil,
    this.closesOn,
  });

  final String id;
  final String accountId;
  final String filename;
  final String? kind;
  final DateTime? periodStart;
  final DateTime? periodEnd;
  final DateTime? generatedAt;
  final StatementStatus status;
  final DateTime? coveredUntil;
  final DateTime? closesOn;
  final bool userConfirmed;
  final int importedCount;

  bool get isCard => kind == 'cartao';

  factory StatementInfo.fromJson(Map<String, dynamic> json) => StatementInfo(
    id: _string(json, 'id'),
    accountId: _string(json, 'account_id'),
    filename: _string(json, 'filename'),
    kind: json['kind'] as String?,
    periodStart: _date(json['period_start']),
    periodEnd: _date(json['period_end']),
    generatedAt: _date(json['generated_at']),
    status: StatementStatus.fromApi(json['status']),
    coveredUntil: _date(json['covered_until']),
    closesOn: _date(json['closes_on']),
    userConfirmed: json['user_confirmed'] == true,
    importedCount: json['imported_count'] is int
        ? json['imported_count'] as int
        : 0,
  );
}

class DateGap {
  const DateGap(this.from, this.to);

  final DateTime from;
  final DateTime to;
}

class AccountCoverage {
  const AccountCoverage({
    required this.label,
    required this.gaps,
    required this.hasOpen,
  });

  final String label;
  final List<DateGap> gaps;
  final bool hasOpen;
}

class StatementsData {
  const StatementsData({required this.statements, required this.coverage});

  const StatementsData.empty() : statements = const [], coverage = const {};

  final List<StatementInfo> statements;
  final Map<String, AccountCoverage> coverage;

  StatementInfo? byFilename(String name) {
    for (final item in statements) {
      if (item.filename == name) return item;
    }
    return null;
  }

  factory StatementsData.fromJson(Map<String, dynamic> json) {
    final rawStatements = json['statements'];
    final rawCoverage = json['coverage'];
    if (rawStatements is! List || rawCoverage is! Map) {
      throw const FormatException('Resposta inválida: arquivos.');
    }
    final coverage = <String, AccountCoverage>{};
    for (final entry in rawCoverage.entries) {
      final value = entry.value;
      if (entry.key is! String || value is! Map<String, dynamic>) continue;
      final gaps = <DateGap>[];
      final rawGaps = value['gaps'];
      if (rawGaps is List) {
        for (final gap in rawGaps) {
          if (gap is! Map) continue;
          final from = _date(gap['from']);
          final to = _date(gap['to']);
          if (from != null && to != null) gaps.add(DateGap(from, to));
        }
      }
      coverage[entry.key as String] = AccountCoverage(
        label: value['label'] is String
            ? value['label'] as String
            : entry.key as String,
        gaps: gaps,
        hasOpen: value['has_open'] == true,
      );
    }
    return StatementsData(
      statements: [
        for (final item in rawStatements)
          if (item is Map<String, dynamic>) StatementInfo.fromJson(item),
      ],
      coverage: coverage,
    );
  }
}

class InspectionWarning {
  const InspectionWarning({
    required this.code,
    required this.severity,
    required this.message,
  });

  final String code;

  /// `conflito` (bloqueia até o usuário confirmar), `atencao` ou `info`.
  final String severity;
  final String message;

  bool get isConflict => severity == 'conflito';
  bool get isAttention => severity == 'atencao';
}

/// Análise de um arquivo antes de importar (`POST /transactions/inspect`).
class Inspection {
  const Inspection({
    required this.warnings,
    required this.hasConflict,
    required this.needsOwner,
    this.institution,
    this.kind,
    this.detectedOwner,
    this.confidence,
    this.knownOwner,
    this.signals = const [],
    this.statusLabel,
    this.closesOn,
    this.periodStart,
    this.periodEnd,
    this.transactionCount = 0,
  });

  final String? institution;
  final String? kind;
  final AccountOwner? detectedOwner;
  final String? confidence;
  final AccountOwner? knownOwner;
  final List<String> signals;
  final List<InspectionWarning> warnings;
  final bool hasConflict;
  final bool needsOwner;
  final StatementStatus? statusLabel;
  final DateTime? closesOn;
  final DateTime? periodStart;
  final DateTime? periodEnd;
  final int transactionCount;

  List<InspectionWarning> get attention =>
      warnings.where((w) => w.isConflict || w.isAttention).toList();

  /// Há algo que o usuário precisa decidir antes de importar.
  bool get needsDecision => hasConflict || needsOwner || attention.isNotEmpty;

  String? get institutionLabel => institutionName(institution);

  String? get kindLabel => switch (kind) {
    'cartao' => 'fatura do cartão',
    'conta' => 'extrato da conta',
    _ => null,
  };

  factory Inspection.fromJson(Map<String, dynamic> json) {
    final rawWarnings = json['warnings'];
    final period = json['period'];
    return Inspection(
      institution: json['institution'] as String?,
      kind: json['kind'] as String?,
      detectedOwner: AccountOwner.fromApi(json['detected_owner']),
      confidence: json['confidence'] as String?,
      knownOwner: AccountOwner.fromApi(json['known_owner']),
      signals: [
        if (json['signals'] is List)
          for (final item in json['signals'] as List)
            if (item is Map && item['label'] is String) item['label'] as String,
      ],
      warnings: [
        if (rawWarnings is List)
          for (final item in rawWarnings)
            if (item is Map<String, dynamic>)
              InspectionWarning(
                code: _string(item, 'code'),
                severity: _string(item, 'severity'),
                message: _string(item, 'message'),
              ),
      ],
      hasConflict: json['has_conflict'] == true,
      needsOwner: json['needs_owner'] == true,
      statusLabel: period is Map
          ? StatementStatus.fromApi(period['status'])
          : null,
      closesOn: period is Map ? _date(period['closes_on']) : null,
      periodStart: period is Map ? _date(period['start']) : null,
      periodEnd: period is Map ? _date(period['end']) : null,
      transactionCount: json['transaction_count'] is int
          ? json['transaction_count'] as int
          : 0,
    );
  }
}

/// Possível transferência entre duas contas do usuário, aguardando confirmação.
class TransferSuggestion {
  const TransferSuggestion({
    required this.id,
    required this.debitUid,
    required this.creditUid,
    required this.amount,
    required this.debitDate,
    required this.creditDate,
    required this.fromLabel,
    required this.toLabel,
    required this.confidence,
    required this.reason,
    this.kind = 'transferencia',
  });

  final String id;

  /// `transferencia` (entre contas suas) ou `pagamento_fatura` (a saída paga o cartão de
  /// outro banco).
  final String kind;
  final String debitUid;
  final String creditUid;
  final double amount;
  final DateTime debitDate;
  final DateTime creditDate;
  final String fromLabel;
  final String toLabel;

  /// `alta` ou `media`.
  final String confidence;
  final String reason;

  bool get isHigh => confidence == 'alta';
  bool get isCardPayment => kind == 'pagamento_fatura';

  factory TransferSuggestion.fromJson(Map<String, dynamic> json) {
    final debit = _date(json['debit_date']);
    final credit = _date(json['credit_date']);
    if (debit == null || credit == null) {
      throw const FormatException('Transferência inválida: datas.');
    }
    return TransferSuggestion(
      id: _string(json, 'id'),
      kind: json['kind'] is String ? json['kind'] as String : 'transferencia',
      debitUid: _string(json, 'debit_uid'),
      creditUid: _string(json, 'credit_uid'),
      amount: _double(json, 'amount'),
      debitDate: debit,
      creditDate: credit,
      fromLabel: json['from_label'] is String
          ? json['from_label'] as String
          : _string(json, 'from_account'),
      toLabel: json['to_label'] is String
          ? json['to_label'] as String
          : _string(json, 'to_account'),
      confidence: _string(json, 'confidence'),
      reason: json['reason'] is String ? json['reason'] as String : '',
    );
  }
}

/// Transferência entre contas próprias já tratada: confirmada pelo usuário ou
/// reconhecida sozinha pela conta de destino.
class OwnTransfer {
  const OwnTransfer({
    required this.id,
    required this.automatic,
    required this.amount,
    required this.date,
    required this.fromLabel,
    required this.toLabel,
    this.cardPayment = false,
  });

  /// Pagamento de fatura de cartão (e não transferência entre contas).
  final bool cardPayment;

  /// Para as automáticas é o identificador do lançamento; para as confirmadas, do par.
  final String id;
  final bool automatic;
  final double amount;
  final DateTime date;
  final String fromLabel;
  final String toLabel;

  factory OwnTransfer.fromJson(Map<String, dynamic> json) {
    final date = _date(json['date'] ?? json['debit_date']);
    if (date == null) {
      throw const FormatException('Transferência inválida: data.');
    }
    return OwnTransfer(
      id: _string(json, 'id'),
      automatic: json['kind'] == 'automatica',
      cardPayment: json['transfer_kind'] == 'pagamento_fatura',
      amount: _double(json, 'amount'),
      date: date,
      fromLabel: json['from_label'] is String
          ? json['from_label'] as String
          : _string(json, 'from_account'),
      toLabel: json['to_label'] is String
          ? json['to_label'] as String
          : _string(json, 'to_account'),
    );
  }
}

class InstallmentPlan {
  const InstallmentPlan({
    required this.accountLabel,
    required this.merchant,
    required this.amount,
    required this.total,
    required this.current,
    required this.remaining,
    required this.remainingAmount,
    required this.endsOnMonth,
    required this.finished,
  });

  final String accountLabel;
  final String merchant;
  final double amount;
  final int total;
  final int current;
  final int remaining;
  final double remainingAmount;

  /// `AAAA-MM` previsto para a última parcela.
  final String endsOnMonth;
  final bool finished;

  double get progress => total <= 0 ? 0 : (current / total).clamp(0.0, 1.0);

  factory InstallmentPlan.fromJson(Map<String, dynamic> json) {
    final total = _int(json, 'total');
    final current = _int(json, 'current');
    if (total < 1 || current < 1 || current > total) {
      throw const FormatException('Parcelamento inválido.');
    }
    return InstallmentPlan(
      accountLabel: json['account_label'] is String
          ? json['account_label'] as String
          : '',
      merchant: _string(json, 'merchant'),
      amount: _double(json, 'amount'),
      total: total,
      current: current,
      remaining: _int(json, 'remaining'),
      remainingAmount: _double(json, 'remaining_amount'),
      endsOnMonth: _string(json, 'ends_on_month'),
      finished: json['finished'] == true,
    );
  }
}

class MonthTotal {
  const MonthTotal(this.month, this.total);

  /// `AAAA-MM`.
  final String month;
  final double total;
}

class InstallmentsData {
  const InstallmentsData({
    required this.plans,
    required this.activeCount,
    required this.finishedCount,
    required this.totalRemaining,
    required this.projection,
  });

  const InstallmentsData.empty()
    : plans = const [],
      activeCount = 0,
      finishedCount = 0,
      totalRemaining = 0,
      projection = const [];

  final List<InstallmentPlan> plans;
  final int activeCount;
  final int finishedCount;
  final double totalRemaining;
  final List<MonthTotal> projection;

  bool get isEmpty => plans.isEmpty;

  factory InstallmentsData.fromJson(Map<String, dynamic> json) {
    final rawPlans = json['plans'];
    final rawProjection = json['monthly_projection'];
    if (rawPlans is! List || rawProjection is! List) {
      throw const FormatException('Resposta inválida: parcelamentos.');
    }
    return InstallmentsData(
      plans: [
        for (final item in rawPlans)
          if (item is Map<String, dynamic>) InstallmentPlan.fromJson(item),
      ],
      activeCount: _int(json, 'active_count'),
      finishedCount: _int(json, 'finished_count'),
      totalRemaining: _double(json, 'total_remaining'),
      projection: [
        for (final item in rawProjection)
          if (item is Map<String, dynamic>)
            MonthTotal(_string(item, 'month'), _double(item, 'total')),
      ],
    );
  }
}
