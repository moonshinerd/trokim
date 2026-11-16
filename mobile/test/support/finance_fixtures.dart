import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/features/finance/data/finance_repository.dart';
import 'package:trokim/features/finance/presentation/finance_controller.dart';

/// Resumo fictício, no formato devolvido por `/transactions/summary`.
const summaryJson = <String, Object?>{
  'total_income': 5000.0,
  'total_expenses': 2150.5,
  'net_balance': 2849.5,
  'savings_rate': 56.99,
  'expenses_by_category': {
    'moradia': 1500.0,
    'alimentacao': 650.5,
    'outros': 0.0,
  },
  'transaction_count': 5,
};

const emptySummaryJson = <String, Object?>{
  'total_income': 0.0,
  'total_expenses': 0.0,
  'net_balance': 0.0,
  'savings_rate': 0.0,
  'expenses_by_category': <String, Object?>{},
  'transaction_count': 0,
};

/// Lançamentos fictícios de dois arquivos, com uma duplicata evitada.
const transactionsJson = <Map<String, Object?>>[
  {'source_file': 'extrato_novembro.ofx', 'is_duplicate': false},
  {'source_file': 'extrato_novembro.ofx', 'is_duplicate': false},
  {'source_file': 'fatura_cartao.pdf', 'is_duplicate': false},
  {'source_file': 'fatura_cartao.pdf', 'is_duplicate': true},
];

http.Response jsonResponse(Object? body, [int status = 200]) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

/// API falsa de transações. Registra as requisições recebidas.
class FakeFinanceApi {
  FakeFinanceApi({
    this.summary = summaryJson,
    this.transactions = transactionsJson,
  });

  Object? summary;
  Object? transactions;

  /// Se definido, responde ao envio de arquivo (padrão: sucesso).
  http.Response Function(http.Request request)? onUpload;

  /// Se verdadeiro, qualquer chamada falha como se a API estivesse fora.
  bool offline = false;

  final requests = <http.Request>[];

  int count(String method, String pathEnd) => requests
      .where((r) => r.method == method && r.url.path.endsWith(pathEnd))
      .length;

  MockClient get client => MockClient((request) async {
    requests.add(request);
    if (offline) throw http.ClientException('sem conexão');
    final path = request.url.path;
    if (request.method == 'GET' && path.endsWith('/transactions/summary')) {
      return jsonResponse(summary);
    }
    if (request.method == 'GET' && path.endsWith('/transactions')) {
      return jsonResponse(transactions);
    }
    if (request.method == 'POST' && path.endsWith('/transactions/upload')) {
      return onUpload?.call(request) ??
          jsonResponse({
            'filename': 'novo.ofx',
            'imported_count': 2,
            'duplicate_count': 0,
          });
    }
    return http.Response('não encontrado', 404);
  });

  FinanceController controller() =>
      FinanceController(FinanceRepository(() => ApiClient(client: client)));
}
