import 'package:intl/intl.dart';

final NumberFormat brl = NumberFormat.currency(locale: 'pt_BR', symbol: r'R$');

const _months = [
  'jan',
  'fev',
  'mar',
  'abr',
  'mai',
  'jun',
  'jul',
  'ago',
  'set',
  'out',
  'nov',
  'dez',
];

/// `2026-11-03` → `03/11/2026`.
String fullDate(DateTime day) =>
    '${day.day.toString().padLeft(2, '0')}/'
    '${day.month.toString().padLeft(2, '0')}/${day.year}';

/// `2026-11-03` → `03/11`.
String shortDate(DateTime day) =>
    '${day.day.toString().padLeft(2, '0')}/${day.month.toString().padLeft(2, '0')}';

/// `2026-12` → `dez/2026`. Valor inesperado volta como veio.
String monthLabel(String yearMonth) {
  final parts = yearMonth.split('-');
  if (parts.length != 2) return yearMonth;
  final month = int.tryParse(parts[1]);
  if (month == null || month < 1 || month > 12) return yearMonth;
  return '${_months[month - 1]}/${parts[0]}';
}
