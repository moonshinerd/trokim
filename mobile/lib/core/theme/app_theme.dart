import 'package:flutter/material.dart';

import '../widgets/app_motion.dart';

/// Cores que mudam entre o tema claro e o escuro.
@immutable
class AppColors extends ThemeExtension<AppColors> {
  const AppColors({
    required this.bg,
    required this.surface,
    required this.line,
    required this.muted,
    required this.ink,
    required this.tint,
    required this.accent,
  });

  /// Fundo das telas.
  final Color bg;

  /// Cartões e barras.
  final Color surface;

  /// Contornos sutis.
  final Color line;

  /// Texto secundário.
  final Color muted;

  /// Texto principal.
  final Color ink;

  /// Realce suave (indicadores, avisos).
  final Color tint;

  /// Violeta legível sobre o fundo atual (ícones, links).
  final Color accent;

  static const light = AppColors(
    bg: Color(0xFFF6F5FA),
    surface: Colors.white,
    line: Color(0xFFE6E3F0),
    muted: Color(0xFF6E6A82),
    ink: Color(0xFF14141A),
    tint: Color(0xFFEDE6FF),
    accent: Color(0xFF5B22D6),
  );

  static const dark = AppColors(
    bg: Color(0xFF111116),
    surface: Color(0xFF1B1B23),
    line: Color(0xFF2B2B37),
    muted: Color(0xFF9C9AB0),
    ink: Color(0xFFF3F2F8),
    tint: Color(0xFF2A2145),
    accent: Color(0xFFB79BFF),
  );

  @override
  AppColors copyWith() => this;

  @override
  AppColors lerp(ThemeExtension<AppColors>? other, double t) {
    if (other is! AppColors) return this;
    return AppColors(
      bg: Color.lerp(bg, other.bg, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      line: Color.lerp(line, other.line, t)!,
      muted: Color.lerp(muted, other.muted, t)!,
      ink: Color.lerp(ink, other.ink, t)!,
      tint: Color.lerp(tint, other.tint, t)!,
      accent: Color.lerp(accent, other.accent, t)!,
    );
  }
}

extension AppColorsContext on BuildContext {
  /// Paleta atual (cai no tema claro se não houver tema do Trokim, ex.: testes).
  AppColors get colors =>
      Theme.of(this).extension<AppColors>() ?? AppColors.light;
}

/// Identidade visual do Trokim: carvão profundo, violeta elétrico e verde-limão
/// ácido. Tema escuro como referência; segue a configuração do sistema.
class AppTheme {
  AppTheme._();

  // Marca (iguais nos dois temas)
  static const Color charcoal = Color(0xFF14141A);
  static const Color violet = Color(0xFF7B3FF2);
  static const Color violetDeep = Color(0xFF2A1470);
  static const Color lime = Color(0xFFC6F135);

  // Semânticas
  static const Color positive = Color(0xFF2BD98B);
  static const Color negative = Color(0xFFFF5C7A);
  static const Color info = Color(0xFF5AA9FF);

  static const double radius = 20;
  static const String fontFamily = 'PlusJakartaSans';

  /// Degradê dos cartões de destaque.
  static const LinearGradient hero = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF8E5BFF), Color(0xFF5B22D6), Color(0xFF1E0F57)],
    stops: [0.0, 0.55, 1.0],
  );

  static List<BoxShadow> softShadow(BuildContext context) => [
        BoxShadow(
          color: Colors.black.withValues(
            alpha:
                Theme.of(context).brightness == Brightness.dark ? 0.35 : 0.08,
          ),
          blurRadius: 24,
          offset: const Offset(0, 8),
        ),
      ];

  static ThemeData get lightTheme => _build(Brightness.light, AppColors.light);
  static ThemeData get darkTheme => _build(Brightness.dark, AppColors.dark);

  static ThemeData _build(Brightness brightness, AppColors c) {
    final isDark = brightness == Brightness.dark;
    final scheme = ColorScheme.fromSeed(
      seedColor: violet,
      brightness: brightness,
    ).copyWith(
      primary: isDark ? const Color(0xFF9B6BFF) : violet,
      onPrimary: Colors.white,
      secondary: lime,
      onSecondary: charcoal,
      surface: c.surface,
      onSurface: c.ink,
      outlineVariant: c.line,
    );

    final base = TextStyle(fontFamily: fontFamily, color: c.ink);

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      fontFamily: fontFamily,
      scaffoldBackgroundColor: c.bg,
      extensions: [c],
      splashFactory: InkSparkle.splashFactory,
      textTheme: const TextTheme(
        headlineMedium: TextStyle(
            fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: -0.6),
        titleLarge: TextStyle(
            fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.3),
        titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
        bodyLarge: TextStyle(fontSize: 15, height: 1.5),
        bodyMedium: TextStyle(fontSize: 14, height: 1.45),
        labelLarge: TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
      ).apply(bodyColor: c.ink, displayColor: c.ink),
      appBarTheme: AppBarTheme(
        backgroundColor: c.bg,
        foregroundColor: c.ink,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          fontFamily: fontFamily,
          fontSize: 20,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.3,
          color: c.ink,
        ),
      ),
      cardTheme: CardThemeData(
        color: c.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radius),
          side: BorderSide(color: c.line),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: c.tint,
        side: BorderSide.none,
        labelStyle: base.copyWith(fontSize: 12, fontWeight: FontWeight.w600),
        shape: const StadiumBorder(),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? charcoal : c.muted),
        trackColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? lime : c.line),
        trackOutlineColor: const WidgetStatePropertyAll(Colors.transparent),
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: InputBorder.none,
        hintStyle: TextStyle(color: c.muted),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: isDark ? c.tint : charcoal,
        contentTextStyle:
            base.copyWith(color: Colors.white, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      pageTransitionsTheme: const PageTransitionsTheme(builders: {
        TargetPlatform.android: SoftPageTransitionsBuilder(),
        TargetPlatform.iOS: SoftPageTransitionsBuilder(),
      }),
    );
  }
}
