import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/screen_header.dart';

class TransactionsScreen extends StatelessWidget {
  const TransactionsScreen({super.key});

  void _import(BuildContext context) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        const SnackBar(
          content: Text('Seletor de arquivos OFX/PDF em execução local.'),
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: Reveal(
        index: 5,
        child: FloatingActionButton.extended(
          onPressed: () => _import(context),
          backgroundColor: AppTheme.gold,
          foregroundColor: AppTheme.forest,
          elevation: 2,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          icon: const Icon(Icons.add_rounded),
          label: const Text('Importar extrato',
              style: TextStyle(fontWeight: FontWeight.w700)),
        ),
      ),
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.only(bottom: 110),
          children: [
            const Reveal(
              child: ScreenHeader(
                title: 'Extratos e faturas',
                subtitle:
                    'Arquivos que você importou. Nada sai do seu aparelho.',
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
              child: Reveal(
                index: 1,
                child: _PrivacyBanner(onImport: () => _import(context)),
              ),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 20, 20, 10),
              child: Reveal(
                index: 2,
                child: Row(children: [
                  Text('Importados',
                      style:
                          TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                  SizedBox(width: 10),
                  _ExampleTag(),
                ]),
              ),
            ),
            Padding(
              padding: EdgeInsets.fromLTRB(20, 0, 20, 10),
              child: Reveal(
                index: 3,
                child: _FileTile(
                  icon: Icons.account_balance_rounded,
                  color: context.colors.accent,
                  name: 'extrato_novembro_sintetico.ofx',
                  detail: '3 transações importadas • sem duplicatas',
                  badge: 'OFX',
                ),
              ),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 0, 20, 10),
              child: Reveal(
                index: 4,
                child: _FileTile(
                  icon: Icons.credit_card_rounded,
                  color: AppTheme.negative,
                  name: 'fatura_cartao_sintetica.pdf',
                  detail: '4 transações importadas • 1 duplicata evitada',
                  badge: 'PDF',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ExampleTag extends StatelessWidget {
  const _ExampleTag();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: context.colors.tint,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text('dados de exemplo',
            style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: context.colors.accent)),
      );
}

class _PrivacyBanner extends StatelessWidget {
  const _PrivacyBanner({required this.onImport});
  final VoidCallback onImport;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onImport,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: context.colors.tint,
          borderRadius: BorderRadius.circular(24),
        ),
        child: Row(children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: context.colors.surface,
              borderRadius: BorderRadius.circular(18),
            ),
            child: Icon(Icons.lock_rounded,
                color: context.colors.accent, size: 26),
          ),
          const SizedBox(width: 16),
          Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Processamento 100% local',
                  style: TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 15,
                      color: context.colors.ink)),
              SizedBox(height: 4),
              Text(
                'Aceita OFX e faturas em PDF. Seus dados ficam em SQLite no aparelho.',
                style: TextStyle(
                    fontSize: 13, height: 1.4, color: context.colors.ink),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _FileTile extends StatelessWidget {
  const _FileTile({
    required this.icon,
    required this.color,
    required this.name,
    required this.detail,
    required this.badge,
  });

  final IconData icon;
  final Color color;
  final String name;
  final String detail;
  final String badge;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radius),
        border: Border.all(color: context.colors.line),
      ),
      child: Row(children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Icon(icon, color: color, size: 22),
        ),
        const SizedBox(width: 12),
        Expanded(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style:
                    const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
            const SizedBox(height: 3),
            Text(detail,
                style: TextStyle(color: context.colors.muted, fontSize: 12)),
          ]),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: context.colors.bg,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Text(badge,
              style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 11,
                  letterSpacing: 0.5)),
        ),
      ]),
    );
  }
}
