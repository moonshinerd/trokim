import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Preferências do usuário, salvas no aparelho (nada sai dele).
class SettingsController extends ChangeNotifier {
  SettingsController._(this._prefs)
      : _themeMode = _decodeMode(_prefs?.getString(_kTheme)),
        _reduceMotion = _prefs?.getBool(_kReduce) ?? false,
        _showSplash = _prefs?.getBool(_kSplash) ?? true;

  /// Sem persistência (testes).
  SettingsController.memory()
      : _prefs = null,
        _themeMode = ThemeMode.system,
        _reduceMotion = false,
        _showSplash = true;

  static const _kTheme = 'theme_mode';
  static const _kReduce = 'reduce_motion';
  static const _kSplash = 'show_splash';

  final SharedPreferences? _prefs;
  ThemeMode _themeMode;
  bool _reduceMotion;
  bool _showSplash;

  static Future<SettingsController> load() async =>
      SettingsController._(await SharedPreferences.getInstance());

  /// Sistema por padrão: o app segue o claro/escuro do aparelho.
  ThemeMode get themeMode => _themeMode;
  bool get reduceMotion => _reduceMotion;
  bool get showSplash => _showSplash;

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

  void setShowSplash(bool value) {
    if (value == _showSplash) return;
    _showSplash = value;
    _prefs?.setBool(_kSplash, value);
    notifyListeners();
  }

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

  static SettingsController of(BuildContext context) =>
      maybeOf(context) ?? SettingsController.memory();
}
