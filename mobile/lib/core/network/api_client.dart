import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../constants/api_constants.dart';

class ApiException implements Exception {
  final int statusCode;

  /// Mensagem de erro devolvida pela API (campo `detail`), quando houver.
  final String? detail;

  const ApiException(this.statusCode, [this.detail]);
}

class ApiClient {
  final String? _fixedBaseUrl;
  final String Function()? _baseUrlProvider;
  final http.Client _client;
  final Duration timeout;

  /// Ler e interpretar um extrato (principalmente PDF) leva mais que um GET.
  final Duration uploadTimeout;
  final Duration generationTimeout;

  /// Nomear a conversa com o LLM local não pode travar o chat.
  final Duration titleTimeout;
  final Set<Completer<void>> _generationAborts = {};

  /// [baseUrlProvider] é consultado a cada chamada, para que o endereço
  /// editado em Ajustes valha sem recriar o cliente.
  ApiClient({
    String? baseUrl,
    String Function()? baseUrlProvider,
    http.Client? client,
    this.timeout = const Duration(seconds: 15),
    this.uploadTimeout = const Duration(seconds: 60),
    this.titleTimeout = const Duration(seconds: 40),
    this.generationTimeout = const Duration(
      seconds: ApiConstants.chatGenerateTimeoutSeconds,
    ),
  }) : _fixedBaseUrl = baseUrl,
       _baseUrlProvider = baseUrlProvider,
       _client = client ?? http.Client() {
    if (generationTimeout <= Duration.zero) {
      throw ArgumentError.value(generationTimeout, 'generationTimeout');
    }
  }

  String get baseUrl =>
      _baseUrlProvider?.call() ?? _fixedBaseUrl ?? ApiConstants.defaultBaseUrl;

  /// [owner]: `todas`, `pessoal` ou `empresa`. [view]: `competencia` ou `caixa`.
  Future<Map<String, dynamic>> getSummary({
    String owner = 'todas',
    String view = 'competencia',
  }) async {
    final uri = Uri.parse('$baseUrl${ApiConstants.transactionsSummaryEndpoint}')
        .replace(queryParameters: {'owner': owner, 'view': view});
    final response = await _client.get(uri).timeout(timeout);
    return _decode(response);
  }

  Future<Map<String, dynamic>> _getMap(String endpoint) async => _decode(
    await _client.get(Uri.parse('$baseUrl$endpoint')).timeout(timeout),
  );

  Future<List<Map<String, dynamic>>> _getList(String endpoint) async {
    final decoded = _decodeJson(
      await _client.get(Uri.parse('$baseUrl$endpoint')).timeout(timeout),
    );
    if (decoded is! List) {
      throw const FormatException('Resposta inválida do servidor.');
    }
    return [
      for (final item in decoded)
        if (item is Map<String, dynamic>)
          item
        else
          throw const FormatException('Resposta inválida do servidor.'),
    ];
  }

  Future<Map<String, dynamic>> _sendJson(
    String method,
    String endpoint,
    Map<String, Object?> body,
  ) async {
    final request = http.Request(method, Uri.parse('$baseUrl$endpoint'))
      ..headers['Content-Type'] = 'application/json'
      ..body = jsonEncode(body);
    final response = await http.Response.fromStream(
      await _client.send(request).timeout(timeout),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> getStatements() =>
      _getMap(ApiConstants.statementsEndpoint);

  Future<Map<String, dynamic>> getInstallments() =>
      _getMap(ApiConstants.installmentsEndpoint);

  Future<List<Map<String, dynamic>>> getAccounts() =>
      _getList(ApiConstants.accountsEndpoint);

  Future<List<Map<String, dynamic>>> getTransferSuggestions() =>
      _getList('${ApiConstants.transfersEndpoint}/suggestions');

  Future<List<Map<String, dynamic>>> getTransfers() =>
      _getList(ApiConstants.transfersEndpoint);

  Future<Map<String, dynamic>> patchAccount(
    String id, {
    String? owner,
    String? label,
  }) => _sendJson('PATCH', '${ApiConstants.accountsEndpoint}/$id', {
    'owner': ?owner,
    'label': ?label,
  });

  Future<Map<String, dynamic>> patchStatement(
    String id, {
    bool? closed,
    DateTime? periodStart,
    DateTime? periodEnd,
  }) => _sendJson('PATCH', '${ApiConstants.statementsEndpoint}/$id', {
    'closed': ?closed,
    if (periodStart != null) 'period_start': _isoDate(periodStart),
    if (periodEnd != null) 'period_end': _isoDate(periodEnd),
  });

  Future<Map<String, dynamic>> confirmTransfer(
    String debitUid,
    String creditUid,
  ) => _sendJson('POST', '${ApiConstants.transfersEndpoint}/confirm', {
    'debit_uid': debitUid,
    'credit_uid': creditUid,
  });

  Future<Map<String, dynamic>> rejectTransfer(
    String debitUid,
    String creditUid,
  ) => _sendJson('POST', '${ApiConstants.transfersEndpoint}/reject', {
    'debit_uid': debitUid,
    'credit_uid': creditUid,
  });

  Future<Map<String, dynamic>> undoTransfer(String id) =>
      _sendJson('POST', '${ApiConstants.transfersEndpoint}/undo', {'id': id});

  Future<Map<String, dynamic>> unmarkTransfer(String uid) => _sendJson(
    'POST',
    '${ApiConstants.transfersEndpoint}/unmark',
    {'uid': uid},
  );

  /// Corrige a categoria de um lançamento. Com [applyToMerchant], a escolha vale para todos
  /// os lançamentos do mesmo estabelecimento e para os próximos arquivos.
  Future<Map<String, dynamic>> setTransactionCategory(
    String uid,
    String category, {
    bool applyToMerchant = true,
  }) => _sendJson(
    'PATCH',
    '${ApiConstants.transactionsEndpoint}/${Uri.encodeComponent(uid)}/category',
    {'category': category, 'apply_to_merchant': applyToMerchant},
  );

  static String _isoDate(DateTime day) =>
      '${day.year.toString().padLeft(4, '0')}-'
      '${day.month.toString().padLeft(2, '0')}-'
      '${day.day.toString().padLeft(2, '0')}';

  Future<List<Map<String, dynamic>>> getTransactions() async {
    final response = await _client
        .get(Uri.parse('$baseUrl${ApiConstants.transactionsEndpoint}'))
        .timeout(timeout);
    final decoded = _decodeJson(response);
    if (decoded is! List) {
      throw const FormatException('Resposta inválida do servidor.');
    }
    return [
      for (final item in decoded)
        if (item is Map<String, dynamic>)
          item
        else
          throw const FormatException('Resposta inválida do servidor.'),
    ];
  }

  /// Envia um extrato (OFX ou PDF) para a API local processar.
  ///
  /// [owner] (`pessoal` ou `empresa`) e [expectKind] (`conta` ou `cartao`) vêm do que o usuário
  /// escolheu. [confirmed] importa mesmo quando o detector avisa de um conflito (a API devolve
  /// 409 sem ele).
  Future<Map<String, dynamic>> uploadStatement(
    String filename,
    List<int> bytes, {
    String? owner,
    String? expectKind,
    bool confirmed = false,
  }) => _multipart(
    ApiConstants.transactionsUploadEndpoint,
    filename,
    bytes,
    owner: owner,
    expectKind: expectKind,
    confirmed: confirmed,
  );

  /// Analisa o arquivo sem importar: banco, tipo, período, dono provável e avisos.
  Future<Map<String, dynamic>> inspectStatement(
    String filename,
    List<int> bytes, {
    String? owner,
    String? expectKind,
  }) => _multipart(
    ApiConstants.transactionsInspectEndpoint,
    filename,
    bytes,
    owner: owner,
    expectKind: expectKind,
  );

  Future<Map<String, dynamic>> _multipart(
    String endpoint,
    String filename,
    List<int> bytes, {
    String? owner,
    String? expectKind,
    bool confirmed = false,
  }) async {
    final request =
        http.MultipartRequest('POST', Uri.parse('$baseUrl$endpoint'))
          ..files.add(
            http.MultipartFile.fromBytes('file', bytes, filename: filename),
          );
    if (owner != null) request.fields['owner'] = owner;
    if (expectKind != null) request.fields['expect_kind'] = expectKind;
    if (confirmed) request.fields['confirmed'] = 'true';
    final response = await http.Response.fromStream(
      await _client.send(request).timeout(uploadTimeout),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> askAssistant(String message) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl${ApiConstants.chatAskEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'message': message}),
        )
        .timeout(timeout);
    return _decode(response);
  }

  /// Pede ao LLM local um título curto para a conversa.
  Future<Map<String, dynamic>> generateTitle(
    String message, {
    String? answer,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl${ApiConstants.chatTitleEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'message': message,
            if (answer != null && answer.isNotEmpty) 'answer': answer,
          }),
        )
        .timeout(titleTimeout);
    return _decode(response);
  }

  Future<Map<String, dynamic>> generateAssistant(String message) async {
    return _postAbortable(ApiConstants.chatGenerateEndpoint, {
      'message': message,
      'mode': 'grounded',
    }, 'Tempo limite da geração excedido.');
  }

  Future<Map<String, dynamic>> askAgents(String message) async =>
      _postAbortable(ApiConstants.agentsAskEndpoint, {
        'message': message,
      }, 'Tempo limite dos agentes excedido.');

  Future<Map<String, dynamic>> _postAbortable(
    String endpoint,
    Map<String, Object> payload,
    String timeoutMessage,
  ) async {
    final abort = Completer<void>();
    _generationAborts.add(abort);
    final request =
        http.AbortableRequest(
            'POST',
            Uri.parse('$baseUrl$endpoint'),
            abortTrigger: abort.future,
          )
          ..headers['Content-Type'] = 'application/json'
          ..body = jsonEncode(payload);
    var timedOut = false;
    final timer = Timer(generationTimeout, () {
      timedOut = true;
      if (!abort.isCompleted) abort.complete();
    });
    try {
      final response = await http.Response.fromStream(
        await _client.send(request),
      );
      return _decode(response);
    } on http.RequestAbortedException {
      if (timedOut) {
        throw TimeoutException(timeoutMessage, generationTimeout);
      }
      rethrow;
    } finally {
      timer.cancel();
      _generationAborts.remove(abort);
    }
  }

  Object? _decodeJson(http.Response response) {
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, _detailOf(response));
    }
    return jsonDecode(utf8.decode(response.bodyBytes));
  }

  String? _detailOf(http.Response response) {
    try {
      final body = jsonDecode(utf8.decode(response.bodyBytes));
      if (body is Map && body['detail'] is String) {
        return body['detail'] as String;
      }
    } on Object {
      // Corpo que não é JSON: segue sem detalhe.
    }
    return null;
  }

  Map<String, dynamic> _decode(http.Response response) {
    final decoded = _decodeJson(response);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Resposta inválida do servidor.');
    }
    return decoded;
  }

  void close() {
    for (final abort in _generationAborts) {
      if (!abort.isCompleted) abort.complete();
    }
    _client.close();
  }
}
