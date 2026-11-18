import 'package:flutter/material.dart';
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
      _apiBaseUrl = _decodeUrl(_prefs?.getString(_kApiUrl));

  /// Sem persistência (testes).
  SettingsController.memory()
    : _prefs = null,
      _themeMode = ThemeMode.system,
      _reduceMotion = false,
      _showSplash = true,
      _generativeChat = true,
      _multiAgent = false,
      _apiBaseUrl = ApiConstants.defaultBaseUrl;

  static const _kTheme = 'theme_mode';
  static const _kReduce = 'reduce_motion';
  static const _kSplash = 'show_splash';
  static const _kGenerative = 'generative_chat';
  static const _kMultiAgent = 'multi_agent';
  static const _kApiUrl = 'api_base_url';

  final SharedPreferences? _prefs;
  ThemeMode _themeMode;
  bool _reduceMotion;
  bool _showSplash;
  bool _generativeChat;
  bool _multiAgent;
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
