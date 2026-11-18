/// Respostas da API no cenário sintético completo (Nubank pessoal e Empresas, Banco do Brasil).
///
/// Copiadas da API local com `research/synthetic_data/generate_nubank_datasets.py`: dados
/// 100% fictícios.
library;

const accountsJson = <Map<String, Object?>>[
  {
    'id': 'nubank:cartao-pf',
    'display_label': 'Nubank · cartão',
    'owner': 'pessoal',
    'kind': 'cartao',
    'needs_owner': false,
  },
  {
    'id': 'nubank:0000000-0',
    'display_label': 'Nubank · conta',
    'owner': 'pessoal',
    'kind': 'conta',
    'needs_owner': false,
  },
  {
    'id': 'nubank:1111111-1',
    'display_label': 'Nubank Empresas · conta',
    'owner': 'empresa',
    'kind': 'conta',
    'needs_owner': false,
  },
  {
    'id': 'bb:70182-3',
    'display_label': 'Banco do Brasil · conta',
    'owner': null,
    'kind': 'conta',
    'needs_owner': true,
  },
];

const statementsJson = <String, Object?>{
  'statements': [
    {
      'id': 's-aberta',
      'account_id': 'nubank:cartao-pf',
      'filename': 'fatura_nubank_aberta_pessoal.ofx',
      'kind': 'cartao',
      'period_start': '2026-11-03',
      'period_end': '2026-12-03',
      'generated_at': '2026-11-18',
      'status': 'aberta',
      'covered_until': '2026-11-14',
      'closes_on': '2026-12-03',
      'user_confirmed': false,
      'imported_count': 6,
    },
    {
      'id': 's-pj',
      'account_id': 'nubank:1111111-1',
      'filename': 'extrato_empresas.ofx',
      'kind': 'conta',
      'period_start': '2026-10-01',
      'period_end': '2026-10-31',
      'generated_at': '2026-11-18',
      'status': 'fechada',
      'covered_until': '2026-10-31',
      'closes_on': null,
      'user_confirmed': false,
      'imported_count': 4,
    },
  ],
  'coverage': {
    'nubank:cartao-pf': {
      'gaps': [],
      'label': 'Nubank · cartão',
      'has_open': true,
    },
    'nubank:1111111-1': {
      'gaps': [
        {'from': '2026-08-01', 'to': '2026-08-31'},
      ],
      'label': 'Nubank Empresas · conta',
      'has_open': false,
    },
  },
};

/// Lançamentos mínimos para os arquivos acima aparecerem em "Importados".
const libraryTransactionsJson = <Map<String, Object?>>[
  {'source_file': 'fatura_nubank_aberta_pessoal.ofx', 'is_duplicate': false},
  {'source_file': 'extrato_empresas.ofx', 'is_duplicate': false},
];

const installmentsJson = <String, Object?>{
  'plans': [
    {
      'account_id': 'nubank:cartao-pf',
      'merchant': 'Eletro Exemplo',
      'amount': 271.61,
      'total': 8,
      'current': 4,
      'paid': 1,
      'remaining': 4,
      'remaining_amount': 1086.44,
      'ends_on_month': '2027-03',
      'finished': false,
      'account_label': 'Nubank · cartão',
    },
    {
      'account_id': 'nubank:cartao-pf',
      'merchant': 'Curso Exemplo',
      'amount': 50.0,
      'total': 3,
      'current': 3,
      'paid': 3,
      'remaining': 0,
      'remaining_amount': 0,
      'ends_on_month': '2026-11',
      'finished': true,
      'account_label': 'Nubank · cartão',
    },
  ],
  'active_count': 1,
  'finished_count': 1,
  'total_remaining': 1086.44,
  'monthly_projection': [
    {'month': '2026-12', 'total': 271.61},
    {'month': '2027-01', 'total': 271.61},
  ],
};

const suggestionsJson = <Map<String, Object?>>[
  {
    'id': 'sug-1',
    'kind': 'pagamento_fatura',
    'debit_uid': 'd1',
    'credit_uid': 'c1',
    'amount': 750.0,
    'debit_date': '2026-10-13',
    'credit_date': '2026-10-13',
    'from_account': 'nubank:0000000-0',
    'to_account': 'bb:ourocard-1234',
    'confidence': 'alta',
    'reason': 'O valor bate com o pagamento da fatura do cartão.',
    'from_label': 'Nubank · conta',
    'to_label': 'Banco do Brasil · cartão final 1234',
  },
];

const transfersJson = <Map<String, Object?>>[
  {
    'id': 'auto-1',
    'kind': 'automatica',
    'amount': 308.76,
    'date': '2026-10-05',
    'both_sides': true,
    'from_label': 'Nubank · conta',
    'to_label': 'Nubank Empresas · conta',
  },
  {
    'id': 'par-1',
    'kind': 'confirmada',
    'transfer_kind': 'transferencia',
    'amount': 120.0,
    'debit_date': '2026-10-10',
    'credit_date': '2026-10-11',
    'from_label': 'Nubank · conta',
    'to_label': 'Banco do Brasil · conta',
  },
];

Map<String, Object?> summaryWithAccounts({
  String owner = 'todas',
  String view = 'competencia',
}) => {
  'total_income': owner == 'empresa' ? 308.76 : 3162.33,
  'total_expenses': owner == 'empresa' ? 414.9 : 2258.45,
  'net_balance': owner == 'empresa' ? -106.14 : 903.88,
  'savings_rate': owner == 'empresa' ? 0.0 : 28.58,
  'expenses_by_category': {'alimentacao': 425.9, 'outros': 1623.85},
  'transaction_count': 29,
  'excluded_count': 10,
  'view': view,
  'owner': owner,
  'by_account': [
    {
      'account_id': 'nubank:0000000-0',
      'income': 2500.0,
      'expenses': 810.0,
      'count': 3,
      'label': 'Nubank · conta',
      'owner': 'pessoal',
      'kind': 'conta',
    },
    {
      'account_id': 'nubank:1111111-1',
      'income': 0.0,
      'expenses': 150.0,
      'count': 1,
      'label': 'Nubank Empresas · conta',
      'owner': 'empresa',
      'kind': 'conta',
    },
  ],
  'top_merchants': <Object>[],
};
