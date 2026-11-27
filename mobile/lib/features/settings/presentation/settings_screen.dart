import 'dart:async';

import 'package:material_ui/material_ui.dart';
import 'package:http/http.dart' as http;

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/settings/settings_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/screen_header.dart';
import '../../../core/widgets/trokim_logo.dart';
import '../../backup/presentation/backup_card.dart';
import '../../finance/presentation/finance_controller.dart';

const String appVersion = '0.1.0';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({
    super.key,
    this.controller,
    this.client,
    this.documentClient,
    this.saveBackup,
    this.pickBackup,
  });

  /// Injetáveis para teste; em produção usa o escopo do app.
  final SettingsController? controller;
  final http.Client? client;
  final http.Client? documentClient;
  final BackupSaver? saveBackup;
  final BackupPicker? pickBackup;

  @override
  Widget build(BuildContext context) {
    final settings = controller ?? SettingsScope.of(context);
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListenableBuilder(
          listenable: settings,
          builder: (context, _) => ListView(
            padding: const EdgeInsets.only(bottom: 24),
            children: [
              const Reveal(
                child: ScreenHeader(
                  title: 'Ajustes',
                  subtitle:
                      'Aparência, animações, conexão, backup e privacidade.',
                ),
              ),
              _Section(
                index: 1,
                title: 'Aparência',
                child: _ThemePicker(settings: settings),
              ),
              _Section(
                index: 2,
                title: 'Animações',
                child: Column(
                  children: [
                    _SwitchRow(
                      title: 'Reduzir animações',
                      subtitle:
                          'Menos movimento nas transições e nos gráficos.',
                      value: settings.reduceMotion,
                      onChanged: settings.setReduceMotion,
                    ),
                    Divider(height: 1, color: context.colors.line),
                    _SwitchRow(
                      title: 'Abertura animada',
                      subtitle: 'A moeda do Trokim girando ao abrir o app.',
                      value: settings.showSplash,
                      onChanged: settings.setShowSplash,
                    ),
                  ],
                ),
              ),
              _Section(
                index: 3,
                title: 'Assistente',
                child: Column(
                  children: [
                    _SwitchRow(
                      title: 'Respostas com IA (LLM local)',
                      subtitle: 'O modelo de linguagem redige a resposta com base nas fontes oficiais. Desligado, o assistente só recupera os trechos, de forma mais rápida.',
                      value: settings.generativeChat,
                      onChanged: settings.setGenerativeChat,
                    ),
                    Divider(height: 1, color: context.colors.line),
                    _SwitchRow(
                      title: 'Modo multiagente (experimental)',
                      subtitle: 'Mostra as etapas, cálculos e evidências usados em cada resposta.',
                      value: settings.multiAgent,
                      onChanged: settings.setMultiAgent,
                    ),
                    Divider(height: 1, color: context.colors.line),
                    _SwitchRow(
                      title: 'Tutorial ao importar extratos',
                      subtitle: 'Mostra o passo a passo para baixar o arquivo do seu banco. Desligado, o app abre direto o seletor de arquivos.',
                      value: settings.showImportTutorial,
                      onChanged: settings.setShowImportTutorial,
                    ),
                  ],
                ),
              ),
              _Section(
                index: 4,
                title: 'Conexão',
                child: _ConnectionCard(client: client),
              ),
              _Section(
                index: 5,
                title: 'Backup',
                child: BackupCard(
                  client: client,
                  saveBackup: saveBackup,
                  pickBackup: pickBackup,
                ),
              ),
              _Section(
                index: 6,
                title: 'Leitura de documentos',
                child: _DocumentEngineCard(client: documentClient),
              ),
              const _Section(
                index: 7,
                title: 'Privacidade',
                child: _InfoRow(
                  icon: Icons.lock_rounded,
                  text:
                      'Seus extratos são lidos e guardados só neste '
                      'aparelho. Os números são calculados por código; a IA '
                      'apenas explica, com base em fontes oficiais.',
                ),
              ),
              const Reveal(index: 8, child: _About()),
            ],
          ),
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.index,
    required this.title,
    required this.child,
  });
  final int index;
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
    child: Reveal(
      index: index,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 4, bottom: 8),
            child: Semantics(
              header: true,
              child: Text(
                title.toUpperCase(),
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.1,
                  color: context.colors.muted,
                ),
              ),
            ),
          ),
          Material(
            color: context.colors.surface,
            clipBehavior: Clip.antiAlias,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(AppTheme.radius),
              side: BorderSide(color: context.colors.line),
            ),
            child: child,
          ),
        ],
      ),
    ),
  );
}

class _ThemePicker extends StatelessWidget {
  const _ThemePicker({required this.settings});
  final SettingsController settings;

  static const _options = [
    (ThemeMode.system, 'Sistema', Icons.brightness_auto_rounded),
    (ThemeMode.light, 'Claro', Icons.light_mode_rounded),
    (ThemeMode.dark, 'Escuro', Icons.dark_mode_rounded),
  ];

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              for (final o in _options)
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    child: _ThemeChip(
                      label: o.$2,
                      icon: o.$3,
                      selected: settings.themeMode == o.$1,
                      onTap: () => settings.setThemeMode(o.$1),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            settings.themeMode == ThemeMode.system
                ? 'Segue o claro/escuro do seu aparelho.'
                : 'Fixo no tema ${settings.themeMode == ThemeMode.dark ? 'escuro' : 'claro'}.',
            style: TextStyle(fontSize: 12.5, color: c.muted),
          ),
        ],
      ),
    );
  }
}

class _ThemeChip extends StatelessWidget {
  const _ThemeChip({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      button: true,
      selected: selected,
      label: 'Tema $label',
      child: ExcludeSemantics(
        child: Pressable(
          onTap: onTap,
          child: AnimatedContainer(
            duration: Motion.base,
            curve: Motion.emphasized,
            padding: const EdgeInsets.symmetric(vertical: 14),
            decoration: BoxDecoration(
              color: selected ? AppTheme.gold : c.bg,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: selected ? AppTheme.gold : c.line),
            ),
            child: Column(
              children: [
                Icon(
                  icon,
                  size: 22,
                  color: selected ? AppTheme.forest : c.muted,
                ),
                const SizedBox(height: 6),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w800,
                    color: selected ? AppTheme.forest : c.ink,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SwitchRow extends StatelessWidget {
  const _SwitchRow({
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) => MergeSemantics(
    child: ListTile(
      contentPadding: const EdgeInsets.fromLTRB(16, 4, 12, 4),
      title: Text(
        title,
        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
      ),
      subtitle: Text(
        subtitle,
        style: TextStyle(fontSize: 12.5, color: context.colors.muted),
      ),
      trailing: Switch(value: value, onChanged: onChanged),
      onTap: () => onChanged(!value),
    ),
  );
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(16),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 22, color: context.colors.accent),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            text,
            style: TextStyle(
              fontSize: 13.5,
              height: 1.45,
              color: context.colors.ink,
            ),
          ),
        ),
      ],
    ),
  );
}

class _VisionEngine {
  const _VisionEngine({required this.model, required this.remote});
  final String model;
  final bool remote;
}

class _DocumentEngineCard extends StatefulWidget {
  const _DocumentEngineCard({this.client});
  final http.Client? client;

  @override
  State<_DocumentEngineCard> createState() => _DocumentEngineCardState();
}

class _DocumentEngineCardState extends State<_DocumentEngineCard> {
  bool _loading = true;
  bool _failed = false;
  String _ocr = 'OCR local';
  _VisionEngine? _vision;
  String? _loadedFrom;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final url = SettingsScope.of(context).apiBaseUrl;
    if (url != _loadedFrom) {
      _loadedFrom = url;
      _loading = true;
      _failed = false;
      _fetch();
    }
  }

  void _load() {
    setState(() {
      _loading = true;
      _failed = false;
    });
    _fetch();
  }

  Future<void> _fetch() async {
    final settings = SettingsScope.read(context) ?? SettingsController.memory();
    final api = ApiClient(
      baseUrlProvider: () => settings.apiBaseUrl,
      client: widget.client,
    );
    try {
      final engines = await api.getDocumentEngines();
      if (!mounted) return;
      final vision = engines['vision'];
      setState(() {
        _loading = false;
        _ocr = engines['ocr']?.toString() ?? 'OCR local';
        _vision = vision is Map
            ? _VisionEngine(
                model: vision['model']?.toString() ?? 'modelo de visão',
                remote: vision['remote'] == true,
              )
            : null;
      });
      if (_vision == null &&
          settings.documentEngine == SettingsController.visionEngine) {
        settings.setDocumentEngine(SettingsController.ocrEngine);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _loading = false;
          _failed = true;
          _vision = null;
        });
      }
    } finally {
      if (widget.client == null) api.close();
    }
  }

  Future<bool> _askConsent(String model) async {
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Enviar documentos a um provedor remoto?'),
        content: Text(
          'Com o modelo de visão remoto ($model), a imagem do documento sai '
          'do aparelho e do computador da API e é enviada a um serviço de '
          'terceiros para leitura. Ela pode conter nomes, valores e dados '
          'bancários. O OCR local continua disponível sem esse envio, e você '
          'pode retirar o consentimento aqui a qualquer momento.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Concordo com o envio'),
          ),
        ],
      ),
    );
    return accepted ?? false;
  }

  Future<void> _choose(SettingsController settings, String engine) async {
    final vision = _vision;
    if (engine == SettingsController.visionEngine) {
      if (vision == null) return;
      if (vision.remote && !settings.remoteConsent) {
        if (!await _askConsent(vision.model)) return;
        settings.setRemoteConsent(true);
      }
    }
    settings.setDocumentEngine(engine);
  }

  Future<void> _setConsent(SettingsController settings, bool value) async {
    if (!value) {
      settings.setRemoteConsent(false);
      if (_vision?.remote ?? true) {
        settings.setDocumentEngine(SettingsController.ocrEngine);
      }
      return;
    }
    if (await _askConsent(_vision?.model ?? 'modelo de visão')) {
      settings.setRemoteConsent(true);
    }
  }

  Widget _option(
    SettingsController settings, {
    required String engine,
    required String title,
    required String subtitle,
  }) {
    final selected = settings.documentEngine == engine;
    return ListTile(
      contentPadding: const EdgeInsets.fromLTRB(16, 4, 12, 4),
      leading: Icon(
        selected ? Icons.radio_button_checked : Icons.radio_button_off,
        color: selected ? context.colors.accent : context.colors.muted,
      ),
      title: Text(
        title,
        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
      ),
      subtitle: Text(
        subtitle,
        style: TextStyle(fontSize: 12.5, color: context.colors.muted),
      ),
      selected: selected,
      onTap: () => _choose(settings, engine),
    );
  }

  @override
  Widget build(BuildContext context) {
    final settings = SettingsScope.of(context);
    final vision = _vision;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _option(
          settings,
          engine: SettingsController.ocrEngine,
          title: 'OCR local (padrão)',
          subtitle:
              'Lê fotos e PDFs no computador da API ($_ocr), sem enviar a '
              'imagem a terceiros.',
        ),
        if (vision != null) ...[
          Divider(height: 1, color: context.colors.line),
          _option(
            settings,
            engine: SettingsController.visionEngine,
            title: vision.remote
                ? 'Modelo de visão remoto'
                : 'Modelo de visão local',
            subtitle: vision.remote
                ? '${vision.model}. A imagem sai do aparelho e vai para um '
                      'provedor remoto; exige seu consentimento.'
                : '${vision.model}. Roda no computador da API, sem provedor '
                      'remoto.',
          ),
          if (vision.remote) ...[
            Divider(height: 1, color: context.colors.line),
            _SwitchRow(
              title: 'Permitir envio a provedor remoto',
              subtitle: settings.remoteConsent
                  ? 'Consentimento salvo neste aparelho. Desligue para '
                        'voltar a ler só com o OCR local.'
                  : 'Sem consentimento salvo, nenhuma imagem é enviada a '
                        'provedor remoto.',
              value: settings.remoteConsent,
              onChanged: (value) => _setConsent(settings, value),
            ),
          ],
        ],
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 14),
          child: _loading
              ? Text(
                  'Consultando os motores disponíveis…',
                  style: TextStyle(fontSize: 12.5, color: context.colors.muted),
                )
              : _failed
              ? Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Não foi possível consultar os motores na API; o OCR '
                        'local continua como padrão.',
                        style: TextStyle(
                          fontSize: 12.5,
                          color: context.colors.muted,
                        ),
                      ),
                    ),
                    TextButton(
                      onPressed: _load,
                      child: const Text('Tentar de novo'),
                    ),
                  ],
                )
              : vision == null
              ? Text(
                  'Só o OCR local está disponível nesta API.',
                  style: TextStyle(fontSize: 12.5, color: context.colors.muted),
                )
              : const SizedBox.shrink(),
        ),
      ],
    );
  }
}

enum _Probe { idle, loading, ok, fail }

class _ConnectionCard extends StatefulWidget {
  const _ConnectionCard({this.client});
  final http.Client? client;

  @override
  State<_ConnectionCard> createState() => _ConnectionCardState();
}

class _ConnectionCardState extends State<_ConnectionCard> {
  _Probe _state = _Probe.idle;
  TextEditingController? _address;
  String? _addressError;

  @override
  void dispose() {
    _address?.dispose();
    super.dispose();
  }

  /// O campo nasce com o endereço salvo, lido uma única vez.
  TextEditingController _field(SettingsController settings) =>
      _address ??= TextEditingController(text: settings.apiBaseUrl);

  void _changed(SettingsController settings) {
    _state = _Probe.idle;
    // O resumo e os extratos vêm da API: recarrega com o endereço novo.
    FinanceScope.read(context)?.load();
    _field(settings).text = settings.apiBaseUrl;
  }

  void _save(SettingsController settings) {
    final ok = settings.setApiBaseUrl(_field(settings).text);
    setState(() {
      if (ok) {
        _addressError = null;
        _changed(settings);
      } else {
        _addressError =
            'Use um endereço http:// ou https://, como '
            '${ApiConstants.defaultBaseUrl}';
      }
    });
  }

  void _restoreDefault(SettingsController settings) {
    settings.resetApiBaseUrl();
    setState(() {
      _addressError = null;
      _changed(settings);
    });
  }

  Future<void> _test(SettingsController settings) async {
    setState(() => _state = _Probe.loading);
    final client = widget.client ?? http.Client();
    try {
      final res = await client
          .get(
            Uri.parse('${settings.apiBaseUrl}${ApiConstants.healthEndpoint}'),
          )
          .timeout(const Duration(seconds: 4));
      if (mounted) {
        setState(
          () => _state = res.statusCode == 200 ? _Probe.ok : _Probe.fail,
        );
      }
    } on Object {
      if (mounted) setState(() => _state = _Probe.fail);
    } finally {
      if (widget.client == null) client.close();
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final settings = SettingsScope.of(context);
    final (label, color) = switch (_state) {
      _Probe.idle => ('Não testado', c.muted),
      _Probe.loading => ('Testando…', c.muted),
      _Probe.ok => ('Conectado', AppTheme.positive),
      _Probe.fail => ('Sem conexão com a API', AppTheme.negative),
    };
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Endereço da API',
            style: TextStyle(fontSize: 12.5, color: c.muted),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _field(settings),
            keyboardType: TextInputType.url,
            autocorrect: false,
            enableSuggestions: false,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _save(settings),
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5),
            decoration: InputDecoration(
              isDense: true,
              errorText: _addressError,
              errorMaxLines: 3,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              FilledButton(
                onPressed: () => _save(settings),
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.gold,
                  foregroundColor: AppTheme.forest,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                child: const Text(
                  'Salvar endereço',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
              const SizedBox(width: 8),
              TextButton(
                onPressed: () => _restoreDefault(settings),
                child: const Text('Restaurar padrão'),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: Semantics(
                  liveRegion: true,
                  child: Row(
                    children: [
                      Container(
                        width: 9,
                        height: 9,
                        decoration: BoxDecoration(
                          color: color,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Flexible(
                        child: Text(
                          label,
                          style: TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w700,
                            color: color,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              FilledButton(
                onPressed: _state == _Probe.loading
                    ? null
                    : () => _test(settings),
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.gold,
                  foregroundColor: AppTheme.forest,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                child: const Text(
                  'Testar conexão',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _About extends StatelessWidget {
  const _About();

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 32, 20, 0),
    child: Column(
      children: [
        const TrokimMark(size: 64),
        const SizedBox(height: 10),
        const Text(
          'Trokim',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 2),
        Text(
          'Versão $appVersion · Challenge 2 · TIC-IA 2026',
          style: TextStyle(fontSize: 12.5, color: context.colors.muted),
        ),
      ],
    ),
  );
}
