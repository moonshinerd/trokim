import 'package:material_ui/material_ui.dart';

import '../../../core/theme/app_theme.dart';

/// Nome, ícone e cor de uma categoria devolvida pela API.
class CategoryInfo {
  const CategoryInfo(this.key, this.name, this.icon, this.color);

  /// Identificador usado pela API (`alimentacao`, `outros`...).
  final String key;
  final String name;
  final IconData icon;
  final Color color;
}

const _other = CategoryInfo(
  'outros',
  'Outros',
  Icons.category_rounded,
  Color(0xFF8A8F98),
);

/// Categorias de gasto que o usuário pode escolher, na ordem em que aparecem.
const expenseCategories = <CategoryInfo>[
  CategoryInfo(
    'alimentacao',
    'Alimentação',
    Icons.restaurant_rounded,
    Color(0xFFE9892F),
  ),
  CategoryInfo('moradia', 'Moradia', Icons.home_rounded, Color(0xFF2F6FB0)),
  CategoryInfo(
    'transporte',
    'Transporte',
    Icons.directions_car_rounded,
    AppTheme.positive,
  ),
  CategoryInfo('saude', 'Saúde', Icons.favorite_rounded, Color(0xFFD64F6B)),
  CategoryInfo('educacao', 'Educação', Icons.school_rounded, Color(0xFF0E8F8F)),
  CategoryInfo(
    'lazer',
    'Lazer e bem-estar',
    Icons.spa_rounded,
    Color(0xFF8B5CF6),
  ),
  CategoryInfo(
    'servicos',
    'Serviços',
    Icons.receipt_rounded,
    Color(0xFF6B7A90),
  ),
  CategoryInfo(
    'impostos',
    'Impostos e taxas',
    Icons.account_balance_rounded,
    Color(0xFFB0712F),
  ),
  _other,
];

const _income = CategoryInfo(
  'renda',
  'Renda',
  Icons.payments_rounded,
  AppTheme.positive,
);

/// Categoria pelo identificador da API; desconhecida vira "Outros".
CategoryInfo categoryInfo(String key) {
  if (key == _income.key) return _income;
  for (final item in expenseCategories) {
    if (item.key == key) return item;
  }
  return _other;
}
