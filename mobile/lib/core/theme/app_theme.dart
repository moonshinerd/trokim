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

  /// Cor de destaque legível sobre o fundo atual (ícones e links): Tidewater no
  /// claro e dourado no escuro.
  final Color accent;

  /// Champagne sobre Tidewater Green: o bege é o fundo, o verde é a tinta.
  static const light = AppColors(
    bg: Color(0xFFFAEBD7),
    surface: Color(0xFFFFF8EE),
    line: Color(0xFFE6D2B3),
    muted: Color(0xFF6B7F7A),
    ink: Color(0xFF1F3A3A),
    tint: Color(0xFFF0DCBC),
    accent: Color(0xFF2F4F4F),
  );

  /// No escuro o verde assume o fundo e o bege escurece, virando texto suave.
  static const dark = AppColors(
    bg: Color(0xFF0F1D1D),
    surface: Color(0xFF172929),
    line: Color(0xFF284141),
    muted: Color(0xFF9FB0A8),
    ink: Color(0xFFEBDCC4),
    tint: Color(0xFF223B3B),
    accent: Color(0xFFDAA520),
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

/// Identidade visual do Trokim: verde-esmeralda profundo e dourado de moeda,
/// com o mico-leão-dourado como mascote. Segue a configuração do sistema
/// (claro ou escuro).
class AppTheme {
  AppTheme._();

  // Marca (iguais nos dois temas)
  static const Color forest = Color(0xFF1B3232);
  static const Color emerald = Color(0xFF2F4F4F);
  static const Color gold = Color(0xFFDAA520);

  // Semânticas
  static const Color positive = Color(0xFF2FBF8A);
  static const Color negative = Color(0xFFE5604D);
  static const Color info = Color(0xFF5AA9FF);

  static const double radius = 20;
  static const String fontFamily = 'PlusJakartaSans';

  /// Degradê dos cartões de destaque.
  static const LinearGradient hero = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF3F6666), Color(0xFF2F4F4F), Color(0xFF1B3232)],
    stops: [0.0, 0.5, 1.0],
  );

  static List<BoxShadow> softShadow(BuildContext context) => [
    BoxShadow(
      color: Colors.black.withValues(
        alpha: Theme.of(context).brightness == Brightness.dark ? 0.35 : 0.08,
      ),
      blurRadius: 24,
      offset: const Offset(0, 8),
    ),
  ];

  static ThemeData get lightTheme => _build(Brightness.light, AppColors.light);
  static ThemeData get darkTheme => _build(Brightness.dark, AppColors.dark);

  static ThemeData _build(Brightness brightness, AppColors c) {
    final isDark = brightness == Brightness.dark;
    final scheme = ColorScheme.fromSeed(seedColor: gold, brightness: brightness)
        .copyWith(
          primary: isDark ? gold : emerald,
          onPrimary: Colors.white,
          secondary: gold,
          onSecondary: forest,
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
          fontSize: 28,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.6,
        ),
        titleLarge: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.3,
        ),
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
          (s) => s.contains(WidgetState.selected) ? forest : c.muted,
        ),
        trackColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? gold : c.line,
        ),
        trackOutlineColor: const WidgetStatePropertyAll(Colors.transparent),
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: InputBorder.none,
        hintStyle: TextStyle(color: c.muted),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: isDark ? c.tint : forest,
        contentTextStyle: base.copyWith(
          color: Colors.white,
          fontWeight: FontWeight.w600,
        ),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.android: SoftPageTransitionsBuilder(),
          TargetPlatform.iOS: SoftPageTransitionsBuilder(),
        },
      ),
    );
  }
}
