import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/features/agents/domain/multi_agent_models.dart';

Map<String, dynamic> response({String status = 'answered'}) => {
  'query': 'Como organizar?',
  'status': status,
  'answer': status == 'answered'
      ? 'Organize por etapas.'
      : 'Não posso responder com segurança.',
  'model': 'ollama/qwen2.5',
  'evidences': status == 'answered'
      ? [
          {
            'id': 'bcb-1',
            'source_name': 'BCB',
            'document_title': 'Caderno',
            'section': 'Orçamento',
            'content': 'Planeje gastos.',
            'score': 0.9,
          },
        ]
      : [],
  'calculations': [
    {
      'key': 'net',
      'label': 'Saldo',
      'value': 100,
      'unit': 'BRL',
      'source': 'CalculationService',
    },
  ],
  'validation_issues': status == 'rejected'
      ? [
          {
            'code': 'UNSUPPORTED',
            'severity': 'blocker',
            'message': 'A resposta não foi aprovada.',
          },
        ]
      : [],
  'steps': [
    {
      'agent': 'research',
      'status': status == 'abstained' ? 'abstained' : 'ok',
      'summary': 'Busca concluída.',
      'duration_ms': 4,
    },
    {
      'agent': 'analysis',
      'status': 'skipped',
      'summary': 'Sem cálculo.',
      'duration_ms': 0,
    },
    {
      'agent': 'communication',
      'status': status == 'rejected' ? 'failed' : 'ok',
      'summary': 'Texto preparado.',
      'duration_ms': 7,
    },
    {
      'agent': 'validation',
      'status': status == 'rejected' ? 'failed' : 'ok',
      'summary': 'Checagem concluída.',
      'duration_ms': 1,
    },
  ],
  'total_ms': 11,
};

void main() {
  test('lê resposta aprovada, trilha, cálculo e evidência', () {
    final result = MultiAgentResponse.fromJson(response());
    expect(result.status, MultiAgentStatus.answered);
    expect(result.steps.first.agent, AgentName.research);
    expect(result.calculations.single.value, 100);
    expect(result.evidences.single.sourceName, 'BCB');
  });

  test('lê abstenção e rejeição com motivo de validação', () {
    expect(
      MultiAgentResponse.fromJson(response(status: 'abstained')).status,
      MultiAgentStatus.abstained,
    );
    final rejected = MultiAgentResponse.fromJson(response(status: 'rejected'));
    expect(rejected.status, MultiAgentStatus.rejected);
    expect(
      rejected.validationIssues.single.message,
      'A resposta não foi aprovada.',
    );
  });

  test('rejeita status, duração ou estruturas inconsistentes', () {
    expect(
      () => MultiAgentResponse.fromJson({...response(), 'status': 'unknown'}),
      throwsFormatException,
    );
    expect(
      () => MultiAgentResponse.fromJson({...response(), 'total_ms': -1}),
      throwsFormatException,
    );
    expect(
      () => MultiAgentResponse.fromJson({...response(), 'steps': []}),
      throwsFormatException,
    );
    expect(
      () => MultiAgentResponse.fromJson({...response(), 'evidences': []}),
      throwsFormatException,
    );
    expect(
      () => MultiAgentResponse.fromJson({
        ...response(),
        'steps': response()['steps']!
            .where((step) => step['agent'] != 'validation')
            .toList(),
      }),
      throwsFormatException,
    );
  });
}
