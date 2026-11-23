import 'package:material_ui/material_ui.dart';

/// Tipo de arquivo que o usuário quer importar.
enum NubankStatementKind { card, account }

/// Banco que o usuário escolheu na importação guiada.
enum GuideBank { nubank, bb, other }

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

/// Passo a passo para baixar o OFX no app do Nubank (pessoal ou Empresas).
///
/// O OFX é sempre o formato pedido: a fatura aberta não tem PDF, e o e-mail do
/// extrato traz OFX, PDF e CSV. No Nubank Empresas, o arquivo que baixa direto no
/// celular é sempre PDF: o OFX só vem pelo e-mail.
List<GuideStep> nubankGuide(
  NubankStatementKind kind, {
  bool business = false,
}) => business ? _nubankBusinessGuide(kind) : _nubankPersonalGuide(kind);

List<GuideStep> _nubankBusinessGuide(
  NubankStatementKind kind,
) => switch (kind) {
  NubankStatementKind.card => const [
    GuideStep(
      icon: Icons.credit_card_rounded,
      title: 'Abra a área do cartão',
      description:
          'Na tela inicial do Nubank Empresas, toque em Cartão de crédito.',
    ),
    GuideStep(
      icon: Icons.receipt_long_rounded,
      title: 'Acesse a fatura',
      description:
          'Toque em Acessar fatura e escolha o mês. Faturas fechadas aparecem '
          'nos meses anteriores.',
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
      title: 'Abra o saldo',
      description: 'Na tela inicial do Nubank Empresas, toque em Saldo.',
    ),
    GuideStep(
      icon: Icons.ios_share_rounded,
      title: 'Exporte o extrato',
      description: 'Toque em Exportar extrato e depois em Exportar agora.',
    ),
    GuideStep(
      icon: Icons.account_balance_rounded,
      title: 'Escolha a conta e o período',
      description:
          'Selecione Extrato da conta Nu Empresas e toque em Outro período.',
    ),
    GuideStep(
      icon: Icons.calendar_month_rounded,
      title: 'Marque as datas',
      description:
          'Marque do primeiro ao último dia que você quer (por exemplo, de '
          '01/10 a 31/10) e toque em Continuar.',
    ),
    GuideStep(
      icon: Icons.mail_rounded,
      title: 'Envie por e-mail',
      description:
          'Selecione enviar por e-mail (se quiser, marque também salvar no '
          'celular), informe o e-mail e toque em Exportar.',
    ),
    GuideStep(
      icon: Icons.warning_amber_rounded,
      title: 'Use o OFX que chega por e-mail',
      description:
          'O arquivo que baixa direto no celular é sempre PDF. O OFX só vem '
          'pelo e-mail: abra a mensagem e salve o arquivo OFX neste aparelho.',
    ),
  ],
};

/// Passo a passo do Banco do Brasil: fatura do cartão Ourocard (PDF, app do cartão) e extrato da
/// conta corrente (OFX "Money 2000+", app do banco).
///
/// A fatura do BB só existe em PDF. Nos dois casos dá para compartilhar o arquivo direto com o
/// Trokim pela lista de aplicativos.
List<GuideStep> bbGuide(NubankStatementKind kind) => switch (kind) {
  NubankStatementKind.card => const [
    GuideStep(
      icon: Icons.credit_card_rounded,
      title: 'Abra as faturas',
      description: 'No app Ourocard, na página inicial, toque em Ver faturas.',
    ),
    GuideStep(
      icon: Icons.receipt_long_rounded,
      title: 'Escolha a fatura',
      description:
          'Selecione o mês. Dá para usar faturas fechadas, inclusive as já '
          'pagas.',
    ),
    GuideStep(
      icon: Icons.ios_share_rounded,
      title: 'Salve ou compartilhe',
      description:
          'Toque em Salvar ou Compartilhar. A fatura do cartão sai sempre em '
          'PDF (não existe OFX).',
    ),
    GuideStep(
      icon: Icons.share_rounded,
      title: 'Compartilhe direto com o Trokim',
      description:
          'Na lista de aplicativos, escolha o Trokim: o arquivo chega aqui sem '
          'procurar na pasta de downloads. Se preferir, salve o PDF e escolha '
          'o arquivo no passo seguinte.',
    ),
  ],
  NubankStatementKind.account => const [
    GuideStep(
      icon: Icons.account_balance_rounded,
      title: 'Abra o extrato',
      description: 'No app do BB, na página inicial, toque em Extrato.',
    ),
    GuideStep(
      icon: Icons.download_rounded,
      title: 'Baixe o extrato',
      description: 'Toque em Download extrato.',
    ),
    GuideStep(
      icon: Icons.calendar_month_rounded,
      title: 'Escolha o mês e o ano',
      description: 'Selecione o período que você quer importar e avance.',
    ),
    GuideStep(
      icon: Icons.description_rounded,
      title: 'Escolha o tipo OFX',
      description:
          'Selecione o tipo OFX (Money 2000+) e avance. O PDF não serve para o '
          'Trokim ler a conta.',
    ),
    GuideStep(
      icon: Icons.share_rounded,
      title: 'Compartilhe com o Trokim',
      description:
          'O BB oferece enviar o arquivo para um aplicativo: escolha o Trokim. '
          'Se preferir, salve no dispositivo e escolha o arquivo no passo '
          'seguinte.',
    ),
  ],
};

List<GuideStep> _nubankPersonalGuide(
  NubankStatementKind kind,
) => switch (kind) {
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
