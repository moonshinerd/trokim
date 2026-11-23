import 'package:material_ui/material_ui.dart';

/// Tipo de arquivo que o usuário quer importar.
enum NubankStatementKind { card, account }

/// Banco que o usuário escolheu na importação guiada.
enum GuideBank { nubank, bb, picpay, mercadopago, inter, c6, itau, other }

/// Nível de validação do suporte ao banco no Trokim.
enum BankSupportLevel { validated, experimental }

extension BankSupportLevelX on BankSupportLevel {
  String get label => switch (this) {
    BankSupportLevel.validated => 'Validado',
    BankSupportLevel.experimental => 'Experimental',
  };
}

/// Metadados e status de um banco suportado.
class SupportedBankInfo {
  const SupportedBankInfo({
    required this.bank,
    required this.name,
    required this.supportLevel,
    required this.acceptedFormats,
    required this.description,
    this.experimentalNotice,
    required this.icon,
  });

  final GuideBank bank;
  final String name;
  final BankSupportLevel supportLevel;
  final String acceptedFormats;
  final String description;
  final String? experimentalNotice;
  final IconData icon;

  bool get isValidated => supportLevel == BankSupportLevel.validated;
  bool get isExperimental => supportLevel == BankSupportLevel.experimental;
}

/// Catálogo de bancos com suporte no aplicativo Trokim.
const List<SupportedBankInfo> supportedBanks = [
  SupportedBankInfo(
    bank: GuideBank.nubank,
    name: 'Nubank',
    supportLevel: BankSupportLevel.validated,
    acceptedFormats: 'OFX (conta e cartão)',
    description: 'Conta e cartão de crédito, pessoa física ou Nubank Empresas',
    icon: Icons.account_balance_rounded,
  ),
  SupportedBankInfo(
    bank: GuideBank.bb,
    name: 'Banco do Brasil',
    supportLevel: BankSupportLevel.validated,
    acceptedFormats: 'PDF (cartão Ourocard) e OFX (conta)',
    description: 'Fatura Ourocard (PDF) e extrato da conta corrente (OFX)',
    icon: Icons.account_balance_rounded,
  ),
  SupportedBankInfo(
    bank: GuideBank.picpay,
    name: 'PicPay',
    supportLevel: BankSupportLevel.experimental,
    acceptedFormats: 'PDF (extrato da conta)',
    description:
        'Extrato da conta do PicPay em PDF (fatura do cartão ainda não)',
    experimentalNotice: 'Suporte experimental: leitor baseado em formato público do PicPay, ainda não testado em conta real.',
    icon: Icons.account_balance_wallet_rounded,
  ),
  SupportedBankInfo(
    bank: GuideBank.mercadopago,
    name: 'Mercado Pago',
    supportLevel: BankSupportLevel.experimental,
    acceptedFormats: 'PDF (extrato da conta)',
    description: 'Extrato de movimentações da conta Mercado Pago (fatura do cartão ainda não)',
    experimentalNotice: 'Suporte experimental: leitor baseado em formato público do Mercado Pago, ainda não testado em conta real.',
    icon: Icons.storefront_rounded,
  ),
  SupportedBankInfo(
    bank: GuideBank.inter,
    name: 'Banco Inter',
    supportLevel: BankSupportLevel.experimental,
    acceptedFormats: 'OFX (conta) e PDF (fatura)',
    description: 'Extrato da conta em OFX e fatura do cartão Inter em PDF',
    experimentalNotice: 'Suporte experimental: passos baseados na ajuda oficial do Banco Inter, ainda não testados em conta real.',
    icon: Icons.account_balance_rounded,
  ),
  SupportedBankInfo(
    bank: GuideBank.c6,
    name: 'C6 Bank',
    supportLevel: BankSupportLevel.experimental,
    acceptedFormats: 'OFX (conta) e CSV (fatura do cartão)',
    description: 'Extrato da conta do C6 em OFX e fatura do cartão em CSV',
    experimentalNotice: 'Suporte experimental: passos baseados na ajuda oficial do C6 Bank, ainda não testados em conta real.',
    icon: Icons.account_balance_rounded,
  ),
  SupportedBankInfo(
    bank: GuideBank.itau,
    name: 'Itaú',
    supportLevel: BankSupportLevel.experimental,
    acceptedFormats: 'OFX (conta) e PDF (fatura)',
    description:
        'Extrato da conta corrente em OFX e fatura do cartão Itaú em PDF',
    experimentalNotice: 'Suporte experimental: passos baseados na ajuda oficial do Itaú, ainda não testados em conta real.',
    icon: Icons.account_balance_rounded,
  ),
];

/// Obtém os metadados do banco cadastrado.
SupportedBankInfo? getSupportedBankInfo(GuideBank bank) {
  for (final info in supportedBanks) {
    if (info.bank == bank) return info;
  }
  return null;
}

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

/// Retorna os passos do tutorial de exportação para qualquer banco cadastrado.
List<GuideStep> getGuideForBank(
  GuideBank bank,
  NubankStatementKind kind, {
  bool business = false,
}) => switch (bank) {
  GuideBank.nubank => nubankGuide(kind, business: business),
  GuideBank.bb => bbGuide(kind),
  GuideBank.picpay => picpayGuide(kind),
  GuideBank.mercadopago => mercadopagoGuide(kind),
  GuideBank.inter => interGuide(kind),
  GuideBank.c6 => c6Guide(kind),
  GuideBank.itau => itauGuide(kind),
  GuideBank.other => const [],
};

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

/// Passo a passo validado do PicPay: fatura do PicPay Card (PDF) e extrato da conta (PDF).
List<GuideStep> picpayGuide(NubankStatementKind kind) => switch (kind) {
  NubankStatementKind.card => const [
    GuideStep(
      icon: Icons.credit_card_rounded,
      title: 'Abra o PicPay Card',
      description: 'No app do PicPay, toque na aba Carteira ou no atalho Cartões e escolha o PicPay Card.',
    ),
    GuideStep(
      icon: Icons.receipt_long_rounded,
      title: 'Acesse a fatura fechada',
      description: 'Toque em Faturas e escolha o mês fechado que deseja importar. Faturas fechadas garantem a conciliação completa.',
    ),
    GuideStep(
      icon: Icons.ios_share_rounded,
      title: 'Exporte em PDF',
      description: 'Toque no ícone de exportar ou compartilhar fatura e selecione o arquivo em formato PDF.',
    ),
    GuideStep(
      icon: Icons.share_rounded,
      title: 'Compartilhe com o Trokim',
      description: 'Na lista de aplicativos, escolha o Trokim para importar direto, ou salve o arquivo PDF neste aparelho.',
    ),
  ],
  NubankStatementKind.account => const [
    GuideStep(
      icon: Icons.account_balance_wallet_rounded,
      title: 'Abra o extrato da conta',
      description: 'Na tela inicial do PicPay, toque sobre o seu saldo ou acesse a opção Extrato.',
    ),
    GuideStep(
      icon: Icons.ios_share_rounded,
      title: 'Exporte o extrato',
      description: 'Toque no ícone de exportar ou compartilhar no topo da tela do extrato.',
    ),
    GuideStep(
      icon: Icons.calendar_month_rounded,
      title: 'Escolha o período em PDF',
      description:
          'Selecione o mês desejado e exporte o arquivo em formato PDF.',
    ),
    GuideStep(
      icon: Icons.share_rounded,
      title: 'Envie para o Trokim',
      description: 'Compartilhe o arquivo diretamente com o Trokim ou salve na pasta de downloads do aparelho.',
    ),
  ],
};

/// Passo a passo validado do Mercado Pago: fatura do cartão (PDF) e extrato da conta (PDF).
List<GuideStep> mercadopagoGuide(NubankStatementKind kind) => switch (kind) {
  NubankStatementKind.card => const [
    GuideStep(
      icon: Icons.credit_card_rounded,
      title: 'Acesse a área de cartões',
      description: 'No app do Mercado Pago, vá até a seção Cartões e selecione o Cartão de Crédito Mercado Pago.',
    ),
    GuideStep(
      icon: Icons.receipt_long_rounded,
      title: 'Escolha a fatura fechada',
      description: 'Toque em Faturas e selecione a fatura do mês fechado.',
    ),
    GuideStep(
      icon: Icons.download_rounded,
      title: 'Baixe a fatura em PDF',
      description: 'Toque em Baixar fatura ou no ícone de compartilhar e selecione o formato PDF.',
    ),
    GuideStep(
      icon: Icons.share_rounded,
      title: 'Compartilhe com o Trokim',
      description: 'Escolha o Trokim na lista de compartilhamento ou salve o PDF no celular.',
    ),
  ],
  NubankStatementKind.account => const [
    GuideStep(
      icon: Icons.account_balance_wallet_rounded,
      title: 'Acesse seu extrato',
      description: 'Na tela inicial do Mercado Pago, toque em Extrato ou Ver extrato completo.',
    ),
    GuideStep(
      icon: Icons.download_rounded,
      title: 'Toque em baixar/exportar',
      description:
          'Toque no ícone de download/exportar no canto superior direito.',
    ),
    GuideStep(
      icon: Icons.calendar_month_rounded,
      title: 'Defina o período',
      description: 'Escolha o mês ou intervalo de datas fechado para exportar o relatório de movimentações em PDF.',
    ),
    GuideStep(
      icon: Icons.share_rounded,
      title: 'Importe no Trokim',
      description: 'Compartilhe o arquivo PDF com o Trokim ou salve no armazenamento deste aparelho.',
    ),
  ],
};

/// Passo a passo experimental do Banco Inter: extrato da conta (OFX) e fatura do cartão (PDF).
///
/// Baseado na central de ajuda oficial do Banco Inter. Não testado em conta real.
List<GuideStep> interGuide(NubankStatementKind kind) => switch (kind) {
  NubankStatementKind.card => const [
    GuideStep(
      icon: Icons.credit_card_rounded,
      title: 'Acesse a área de cartões',
      description:
          'No app do Banco Inter, acesse a opção Cartões na tela inicial.',
    ),
    GuideStep(
      icon: Icons.receipt_long_rounded,
      title: 'Selecione a fatura fechada',
      description:
          'Toque na fatura do cartão e selecione o mês fechado desejado.',
    ),
    GuideStep(
      icon: Icons.download_rounded,
      title: 'Baixe a fatura em PDF',
      description: 'Toque no botão de baixar ou compartilhar fatura e escolha o formato PDF.',
    ),
    GuideStep(
      icon: Icons.share_rounded,
      title: 'Envie para o Trokim',
      description:
          'Salve o PDF neste aparelho ou compartilhe diretamente com o Trokim.',
    ),
  ],
  NubankStatementKind.account => const [
    GuideStep(
      icon: Icons.account_balance_wallet_rounded,
      title: 'Abra o extrato da conta',
      description: 'Na tela inicial do Inter, toque na opção Extrato.',
    ),
    GuideStep(
      icon: Icons.ios_share_rounded,
      title: 'Toque em exportar',
      description:
          'Toque no ícone de exportação no canto superior da tela do extrato.',
    ),
    GuideStep(
      icon: Icons.calendar_month_rounded,
      title: 'Escolha período e formato OFX',
      description: 'Selecione o período desejado e marque o formato OFX. O Trokim lê arquivos OFX com maior precisão.',
    ),
    GuideStep(
      icon: Icons.save_alt_rounded,
      title: 'Salve o arquivo OFX',
      description:
          'Baixe o arquivo OFX no aparelho e escolha-o no passo seguinte.',
    ),
  ],
};

/// Passo a passo experimental do C6 Bank: extrato da conta (OFX) e fatura do cartão (CSV).
///
/// Baseado na central de ajuda oficial do C6 Bank. Não testado em conta real.
List<GuideStep> c6Guide(NubankStatementKind kind) => switch (kind) {
  NubankStatementKind.card => const [
    GuideStep(
      icon: Icons.credit_card_rounded,
      title: 'Abra a área de cartões',
      description: 'Na tela inicial do app C6 Bank, toque em Cartão.',
    ),
    GuideStep(
      icon: Icons.receipt_long_rounded,
      title: 'Acesse a fatura fechada',
      description: 'Selecione o mês da fatura fechada que deseja importar.',
    ),
    GuideStep(
      icon: Icons.download_rounded,
      title: 'Baixe a fatura em CSV',
      description: 'Toque em Baixar fatura e escolha o formato CSV (planilha).',
    ),
    GuideStep(
      icon: Icons.share_rounded,
      title: 'Importe no Trokim',
      description:
          'Salve o arquivo CSV no aparelho ou compartilhe com o Trokim.',
    ),
  ],
  NubankStatementKind.account => const [
    GuideStep(
      icon: Icons.account_balance_wallet_rounded,
      title: 'Acesse o extrato',
      description: 'Na tela inicial do C6 Bank, toque em Extrato.',
    ),
    GuideStep(
      icon: Icons.ios_share_rounded,
      title: 'Exporte o extrato',
      description:
          'Toque no ícone de compartilhar/exportar no canto superior direito.',
    ),
    GuideStep(
      icon: Icons.description_rounded,
      title: 'Selecione o formato OFX',
      description: 'Escolha o período desejado e selecione o formato OFX.',
    ),
    GuideStep(
      icon: Icons.save_alt_rounded,
      title: 'Salve o arquivo OFX',
      description: 'Salve o arquivo OFX neste aparelho e avance para escolher o arquivo.',
    ),
  ],
};

/// Passo a passo experimental do Itaú: extrato da conta (OFX) e fatura do cartão (PDF).
///
/// Baseado na central de ajuda oficial do Itaú. Não testado em conta real.
List<GuideStep> itauGuide(NubankStatementKind kind) => switch (kind) {
  NubankStatementKind.card => const [
    GuideStep(
      icon: Icons.credit_card_rounded,
      title: 'Acesse as faturas',
      description:
          'No app Itaú ou Itaú Cartões, toque em Cartões e depois em Faturas.',
    ),
    GuideStep(
      icon: Icons.receipt_long_rounded,
      title: 'Escolha a fatura fechada',
      description: 'Selecione o mês da fatura já fechada que quer analisar.',
    ),
    GuideStep(
      icon: Icons.ios_share_rounded,
      title: 'Visualize e baixe em PDF',
      description:
          'Toque em Ver fatura ou Compartilhar e selecione o arquivo PDF.',
    ),
    GuideStep(
      icon: Icons.share_rounded,
      title: 'Importe no Trokim',
      description: 'Compartilhe o PDF com o Trokim ou salve no armazenamento do aparelho.',
    ),
  ],
  NubankStatementKind.account => const [
    GuideStep(
      icon: Icons.account_balance_wallet_rounded,
      title: 'Abra o extrato da conta',
      description: 'Na tela inicial do app Itaú, toque em Extrato.',
    ),
    GuideStep(
      icon: Icons.download_rounded,
      title: 'Selecione exportar extrato',
      description: 'Toque no botão de exportar ou salvar extrato.',
    ),
    GuideStep(
      icon: Icons.description_rounded,
      title: 'Escolha o formato OFX',
      description: 'Defina o período e selecione o formato OFX (Money 2000+).',
    ),
    GuideStep(
      icon: Icons.save_alt_rounded,
      title: 'Salve o arquivo OFX',
      description: 'Baixe o arquivo OFX no aparelho para selecionar no Trokim.',
    ),
  ],
};
