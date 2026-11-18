import 'package:flutter/material.dart';

/// Tipo de arquivo que o usuário quer importar do Nubank.
enum NubankStatementKind { card, account }

/// Um passo do tutorial de exportação.
class GuideStep {
  const GuideStep({
    required this.icon,
    required this.title,
    required this.description,
  });

  final IconData icon;
  final String title;
  final String description;
}

/// Passo a passo para baixar o OFX no app do Nubank.
///
/// O OFX é sempre o formato pedido: a fatura aberta não tem PDF, e o e-mail do
/// extrato traz OFX, PDF e CSV.
List<GuideStep> nubankGuide(NubankStatementKind kind) => switch (kind) {
  NubankStatementKind.card => const [
    GuideStep(
      icon: Icons.credit_card_rounded,
      title: 'Abra a área do cartão',
      description: 'No app do Nubank, toque em Cartão de crédito.',
    ),
    GuideStep(
      icon: Icons.receipt_long_rounded,
      title: 'Acesse a fatura',
      description:
          'Toque em Acessar fatura. A fatura aberta é a do mês atual; para '
          'meses anteriores, escolha o mês na própria tela.',
    ),
    GuideStep(
      icon: Icons.ios_share_rounded,
      title: 'Toque em compartilhar',
      description: 'É o botão com uma seta para cima saindo de uma caixinha.',
    ),
    GuideStep(
      icon: Icons.description_rounded,
      title: 'Escolha o formato OFX',
      description:
          'Selecione OFX. O PDF só existe depois que a fatura fecha, por isso '
          'peça sempre o OFX.',
    ),
    GuideStep(
      icon: Icons.mail_rounded,
      title: 'Baixe o arquivo do e-mail',
      description:
          'O Nubank avisa que vai enviar por e-mail. Abra a mensagem e salve '
          'o arquivo OFX neste aparelho.',
    ),
  ],
  NubankStatementKind.account => const [
    GuideStep(
      icon: Icons.account_balance_wallet_rounded,
      title: 'Abra o saldo da conta',
      description: 'Na tela inicial do Nubank, toque em Saldo em conta.',
    ),
    GuideStep(
      icon: Icons.receipt_long_rounded,
      title: 'Peça o extrato',
      description: 'Toque nos três pontinhos e em Pedir extrato.',
    ),
    GuideStep(
      icon: Icons.calendar_month_rounded,
      title: 'Escolha o mês e o ano',
      description: 'Selecione o período que você quer importar.',
    ),
    GuideStep(
      icon: Icons.mail_rounded,
      title: 'Baixe o OFX do e-mail',
      description:
          'O e-mail traz 3 arquivos (OFX, PDF e CSV). Salve o OFX neste '
          'aparelho.',
    ),
  ],
};
