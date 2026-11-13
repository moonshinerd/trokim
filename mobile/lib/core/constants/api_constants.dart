class ApiConstants {
  // Para emulador Android padrão, 10.0.2.2 aponta para o localhost da máquina host
  static const String defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/v1',
  );

  static const String healthEndpoint = '/health';
  static const String transactionsEndpoint = '/transactions';
  static const String transactionsSummaryEndpoint = '/transactions/summary';
  static const String transactionsUploadEndpoint = '/transactions/upload';
  static const String chatAskEndpoint = '/chat/ask';

  static const int chatGenerateTimeoutSeconds = int.fromEnvironment(
    'CHAT_GENERATE_TIMEOUT_SECONDS',
    defaultValue: 90,
  );

  /// Endpoint de síntese fundamentada com o modelo local.
  static const String chatGenerateEndpoint = '/chat/generate';
  static const String budgetsCompareEndpoint = '/budgets/compare';
}
