import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../constants/api_constants.dart';

/// Preferências do usuário, salvas no aparelho (nada sai dele).
class SettingsController extends ChangeNotifier {
  SettingsController._(this._prefs)
    : _themeMode = _decodeMode(_prefs?.getString(_kTheme)),
      _reduceMotion = _prefs?.getBool(_kReduce) ?? false,
      _showSplash = _prefs?.getBool(_kSplash) ?? true,
      _generativeChat = _prefs?.getBool(_kGenerative) ?? true,
      _multiAgent = _prefs?.getBool(_kMultiAgent) ?? false,
      _importTutorial = _prefs?.getBool(_kImportTutorial) ?? true,
      _documentEngine = _decodeEngine(_prefs?.getString(_kDocumentEngine)),
      _remoteConsent = _prefs?.getBool(_kRemoteConsent) ?? false,
      _apiBaseUrl = _decodeUrl(_prefs?.getString(_kApiUrl));

  /// Sem persistência (testes).
  SettingsController.memory()
    : _prefs = null,
      _themeMode = ThemeMode.system,
      _reduceMotion = false,
      _showSplash = true,
      _generativeChat = true,
      _multiAgent = false,
      _importTutorial = true,
      _documentEngine = ocrEngine,
      _remoteConsent = false,
      _apiBaseUrl = ApiConstants.defaultBaseUrl;

  static const _kTheme = 'theme_mode';
  static const _kReduce = 'reduce_motion';
  static const _kSplash = 'show_splash';
  static const _kGenerative = 'generative_chat';
  static const _kMultiAgent = 'multi_agent';
  static const _kImportTutorial = 'import_tutorial';
  static const _kApiUrl = 'api_base_url';
  static const _kDocumentEngine = 'document_engine';
  static const _kRemoteConsent = 'document_remote_consent';
  static const ocrEngine = 'ocr';
  static const visionEngine = 'vision';

  final SharedPreferences? _prefs;
  ThemeMode _themeMode;
  bool _reduceMotion;
  bool _showSplash;
  bool _generativeChat;
  bool _multiAgent;
  bool _importTutorial;
  String _documentEngine;
  bool _remoteConsent;
  String _apiBaseUrl;

  static Future<SettingsController> load() async =>
      SettingsController._(await SharedPreferences.getInstance());

  /// Sistema por padrão: o app segue o claro/escuro do aparelho.
  ThemeMode get themeMode => _themeMode;
  bool get reduceMotion => _reduceMotion;
  bool get showSplash => _showSplash;

  /// Respostas redigidas pelo LLM local (padrão). Desligado: busca extrativa.
  bool get generativeChat => _generativeChat;
  bool get multiAgent => _multiAgent;

  /// Mostra o tutorial guiado ao importar um extrato (padrão). Desligado, o
  /// app abre direto o seletor de arquivos.
  bool get showImportTutorial => _importTutorial;

  String get documentEngine => _documentEngine;
  bool get remoteConsent => _remoteConsent;
  bool get allowRemoteDocuments =>
      _documentEngine == visionEngine && _remoteConsent;

  /// Endereço da API local (já normalizado). Padrão: o do emulador Android.
  String get apiBaseUrl => _apiBaseUrl;

  void setThemeMode(ThemeMode mode) {
    if (mode == _themeMode) return;
    _themeMode = mode;
    _prefs?.setString(_kTheme, mode.name);
    notifyListeners();
  }

  void setReduceMotion(bool value) {
    if (value == _reduceMotion) return;
    _reduceMotion = value;
    _prefs?.setBool(_kReduce, value);
    notifyListeners();
  }

  void setGenerativeChat(bool value) {
    if (value == _generativeChat) return;
    _generativeChat = value;
    _prefs?.setBool(_kGenerative, value);
    notifyListeners();
  }

  void setMultiAgent(bool value) {
    if (value == _multiAgent) return;
    _multiAgent = value;
    _prefs?.setBool(_kMultiAgent, value);
    notifyListeners();
  }

  void setShowImportTutorial(bool value) {
    if (value == _importTutorial) return;
    _importTutorial = value;
    _prefs?.setBool(_kImportTutorial, value);
    notifyListeners();
  }

  void setDocumentEngine(String engine) {
    final value = _decodeEngine(engine);
    if (value == _documentEngine) return;
    _documentEngine = value;
    _prefs?.setString(_kDocumentEngine, value);
    notifyListeners();
  }

  void setRemoteConsent(bool value) {
    if (value == _remoteConsent) return;
    _remoteConsent = value;
    _prefs?.setBool(_kRemoteConsent, value);
    notifyListeners();
  }

  /// Salva o endereço da API. Devolve `false`, sem salvar, se for inválido.
  bool setApiBaseUrl(String value) {
    final normalized = ApiConstants.normalizeBaseUrl(value);
    if (normalized == null) return false;
    if (normalized != _apiBaseUrl) {
      _apiBaseUrl = normalized;
      _prefs?.setString(_kApiUrl, normalized);
      notifyListeners();
    }
    return true;
  }

  /// Volta ao endereço padrão.
  void resetApiBaseUrl() {
    if (_apiBaseUrl == ApiConstants.defaultBaseUrl) return;
    _apiBaseUrl = ApiConstants.defaultBaseUrl;
    _prefs?.remove(_kApiUrl);
    notifyListeners();
  }

  void setShowSplash(bool value) {
    if (value == _showSplash) return;
    _showSplash = value;
    _prefs?.setBool(_kSplash, value);
    notifyListeners();
  }

  static String _decodeUrl(String? stored) =>
      (stored == null ? null : ApiConstants.normalizeBaseUrl(stored)) ??
      ApiConstants.defaultBaseUrl;

  static String _decodeEngine(String? stored) =>
      stored == visionEngine ? visionEngine : ocrEngine;

  static ThemeMode _decodeMode(String? name) => ThemeMode.values.firstWhere(
    (m) => m.name == name,
    orElse: () => ThemeMode.system,
  );
}

/// Disponibiliza as preferências para toda a árvore de widgets.
class SettingsScope extends InheritedNotifier<SettingsController> {
  const SettingsScope({
    super.key,
    required SettingsController controller,
    required super.child,
  }) : super(notifier: controller);

  static SettingsController? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<SettingsScope>()?.notifier;

  /// Lê as preferências sem registrar dependência (serve em `initState`).
  static SettingsController? read(BuildContext context) =>
      context.getInheritedWidgetOfExactType<SettingsScope>()?.notifier;

  static SettingsController of(BuildContext context) =>
      maybeOf(context) ?? SettingsController.memory();
}
