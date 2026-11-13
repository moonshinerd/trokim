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

  /// Endpoint preparado para a integração ponta a ponta do chat.
  static const String chatGenerateEndpoint = '/chat/generate';
  static const String budgetsCompareEndpoint = '/budgets/compare';
}
