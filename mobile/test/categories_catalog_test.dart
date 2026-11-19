import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/features/categories/domain/categories.dart';

void main() {
  test('o catálogo tem todas as categorias de gasto da API, com impostos', () {
    final keys = expenseCategories.map((c) => c.key).toList();
    expect(keys, [
      'alimentacao',
      'moradia',
      'transporte',
      'saude',
      'educacao',
      'lazer',
      'servicos',
      'impostos',
      'outros',
    ]);
    expect(categoryInfo('impostos').name, 'Impostos e taxas');
  });

  test('categoria desconhecida vira Outros e renda tem nome próprio', () {
    expect(categoryInfo('inexistente').key, 'outros');
    expect(categoryInfo('renda').name, 'Renda');
  });
}
