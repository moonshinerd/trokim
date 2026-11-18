import '../../chat_assistant/domain/chat_models.dart';

enum MultiAgentStatus { answered, abstained, rejected }

enum AgentName { research, analysis, communication, validation }

enum AgentStepStatus { ok, abstained, skipped, failed }

enum ValidationSeverity { blocker, warning }

String _text(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('Campo obrigatório inválido: $key.');
  }
  return value;
}

T _enumValue<T extends Enum>(List<T> values, Object? value, String name) =>
    values.firstWhere(
      (item) => item.name == value,
      orElse: () => throw FormatException('Valor inválido: $name.'),
    );

final class AgentStep {
  final AgentName agent;
  final AgentStepStatus status;
  final String summary;
  final int durationMs;
  AgentStep.fromJson(Map<String, dynamic> json)
    : agent = _enumValue(AgentName.values, json['agent'], 'agent'),
      status = _enumValue(AgentStepStatus.values, json['status'], 'status'),
      summary = _text(json, 'summary'),
      durationMs =
          json['duration_ms'] is int && (json['duration_ms'] as int) >= 0
          ? json['duration_ms'] as int
          : (throw const FormatException('Duração inválida.'));
}

final class CalculationResult {
  final String key, label, source;
  final Object value;
  final String? unit;
  CalculationResult.fromJson(Map<String, dynamic> json)
    : key = _text(json, 'key'),
      label = _text(json, 'label'),
      source = _text(json, 'source'),
      value = json['value'] is num || json['value'] is String
          ? json['value'] as Object
          : (throw const FormatException('Resultado de cálculo inválido.')),
      unit = json['unit'] as String?;
}

final class ValidationIssue {
  final String code, message;
  final ValidationSeverity severity;
  ValidationIssue.fromJson(Map<String, dynamic> json)
    : code = _text(json, 'code'),
      message = _text(json, 'message'),
      severity = _enumValue(
        ValidationSeverity.values,
        json['severity'],
        'severity',
      );
}

final class MultiAgentResponse {
  final String query, answer;
  final MultiAgentStatus status;
  final String? model;
  final List<Evidence> evidences;
  final List<AgentStep> steps;
  final List<CalculationResult> calculations;
  final List<ValidationIssue> validationIssues;
  final int totalMs;
  MultiAgentResponse._({
    required this.query,
    required this.answer,
    required this.status,
    required this.model,
    required this.evidences,
    required this.steps,
    required this.calculations,
    required this.validationIssues,
    required this.totalMs,
  });

  factory MultiAgentResponse.fromJson(Map<String, dynamic> json) {
    List<T> list<T>(String key, T Function(Map<String, dynamic>) parse) {
      final raw = json[key];
      if (raw is! List) throw FormatException('Lista inválida: $key.');
      return List.unmodifiable(
        raw.map((v) {
          if (v is! Map<String, dynamic>) {
            throw FormatException('Item inválido: $key.');
          }
          return parse(v);
        }),
      );
    }

    final status = _enumValue(
      MultiAgentStatus.values,
      json['status'],
      'status',
    );
    final evidences = list('evidences', Evidence.fromJson);
    final steps = list('steps', AgentStep.fromJson);
    final calculations = list('calculations', CalculationResult.fromJson);
    final validationIssues = list(
      'validation_issues',
      ValidationIssue.fromJson,
    );
    final duration = json['total_ms'];
    if (json['answered'] != null &&
        json['answered'] != (status == MultiAgentStatus.answered)) {
      throw const FormatException('Status e resposta divergentes.');
    }
    if (status == MultiAgentStatus.answered &&
        evidences.isEmpty &&
        calculations.isEmpty) {
      throw const FormatException(
        'Resposta aprovada sem evidências nem cálculos.',
      );
    }
    if (status == MultiAgentStatus.answered &&
        (!steps.any(
              (step) =>
                  step.agent == AgentName.validation &&
                  step.status == AgentStepStatus.ok,
            ) ||
            validationIssues.any(
              (issue) => issue.severity == ValidationSeverity.blocker,
            ))) {
      throw const FormatException('Resposta sem validação aprovada.');
    }
    if (duration is! int || duration < 0 || steps.isEmpty) {
      throw const FormatException('Trilha multiagente inconsistente.');
    }
    return MultiAgentResponse._(
      query: _text(json, 'query'),
      answer: _text(json, 'answer'),
      status: status,
      model: json['model'] as String?,
      evidences: evidences,
      steps: steps,
      calculations: calculations,
      validationIssues: validationIssues,
      totalMs: duration,
    );
  }
}
