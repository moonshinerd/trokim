import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/features/chat_assistant/domain/chat_models.dart';

void main() {
  Map<String, dynamic> evidence() => {
        'id': 'cvm_reserva_1',
        'source_name': 'CVM',
        'document_title': 'Reserva',
        'section': 'Planejamento',
        'content': 'Priorize liquidez e baixo risco.',
        'score': 0.8,
      };

  Map<String, dynamic> reply({bool abstained = false}) => {
        'query': 'Reserva?',
        'mode': 'grounded',
        'model': 'qwen2.5',
        'status': abstained ? 'abstained' : 'grounded',
        'answered': !abstained,
        'answer': abstained ? 'Sem evidências.' : 'Monte uma reserva.',
        'evidences': abstained ? [] : [evidence()],
      };

  for (final abstained in [false, true]) {
    test('status é a origem do estado de abstenção: $abstained', () {
      final result = AssistantReply.fromJson(reply(abstained: abstained));
      expect(result.isAbstained, abstained);
      expect(result.answered, !abstained);
      final message = ChatMessage(
        isUser: false,
        text: result.answer,
        status: result.status,
        evidences: result.evidences,
      );
      expect(message.isAbstained, result.isAbstained);
      expect(() => result.evidences.clear(), throwsUnsupportedError);
    });
  }

  for (final field in ['id', 'source_name', 'document_title', 'section', 'content']) {
    test('Evidence rejeita campo vazio diretamente: $field', () {
      final json = evidence()..[field] = '   ';
      expect(() => Evidence.fromJson(json), throwsFormatException);
    });
  }

  for (final score in [double.nan, double.infinity, double.negativeInfinity]) {
    test('Evidence rejeita relevância não finita: $score', () {
      final json = evidence()..['score'] = score;
      expect(() => Evidence.fromJson(json), throwsFormatException);
    });
  }
}
