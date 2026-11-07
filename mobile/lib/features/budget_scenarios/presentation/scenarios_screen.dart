import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

class ScenariosScreen extends StatelessWidget {
  const ScenariosScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Comparador de Cenários'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Simulação de Orçamento Mensal',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          const Text(
            'Compare duas estratégias sem comprometer seu bem-estar ou despesas essenciais.',
            style: TextStyle(color: Colors.grey, fontSize: 13),
          ),
          const SizedBox(height: 16),
          _buildScenarioCard(
            title: 'Cenário A: Padrão Atual',
            income: 'R\$ 6.000,00',
            fixed: 'R\$ 3.000,00',
            variable: 'R\$ 1.800,00',
            savings: 'R\$ 800,00',
            margin: 'R\$ 400,00',
            color: Colors.blueGrey,
          ),
          const SizedBox(height: 16),
          _buildScenarioCard(
            title: 'Cenário B: Otimizado (Meta Reserva)',
            income: 'R\$ 6.000,00',
            fixed: 'R\$ 3.000,00',
            variable: 'R\$ 1.400,00',
            savings: 'R\$ 1.200,00',
            margin: 'R\$ 400,00',
            color: AppTheme.primaryBlue,
            highlight: true,
          ),
        ],
      ),
    );
  }

  Widget _buildScenarioCard({
    required String title,
    required String income,
    required String fixed,
    required String variable,
    required String savings,
    required String margin,
    required Color color,
    bool highlight = false,
  }) {
    return Card(
      elevation: highlight ? 3 : 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: highlight
            ? const BorderSide(color: AppTheme.primaryBlue, width: 2)
            : BorderSide.none,
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
                if (highlight)
                  const Chip(
                    label: Text(
                      'Sugerido',
                      style: TextStyle(fontSize: 11, color: Colors.white),
                    ),
                    backgroundColor: AppTheme.primaryBlue,
                  ),
              ],
            ),
            const Divider(),
            _buildRow('Renda Mensal:', income),
            _buildRow('Despesas Fixas:', fixed),
            _buildRow('Despesas Variáveis:', variable),
            _buildRow('Aporte na Reserva:', savings, isPositive: true),
            _buildRow('Margem Operacional:', margin),
          ],
        ),
      ),
    );
  }

  Widget _buildRow(String label, String value, {bool isPositive = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.w600,
              color: isPositive ? AppTheme.successGreen : AppTheme.textDark,
            ),
          ),
        ],
      ),
    );
  }
}
