import 'package:flutter/material.dart';

import '../widgets/app_motion.dart';

/// Identidade visual do Trokim: verde-esmeralda profundo, papel quente e
/// um toque dourado de "moeda". Tipografia Plus Jakarta Sans.
class AppTheme {
  AppTheme._();

  // Marca
  static const Color ink = Color(0xFF0E1F1A);
  static const Color forest = Color(0xFF0B3D2E);
  static const Color emerald = Color(0xFF0F8F6B);
  static const Color mint = Color(0xFFDDF1E8);
  static const Color coin = Color(0xFFE9B44C);

  // Superfícies
  static const Color paper = Color(0xFFF5F3EE);
  static const Color surface = Colors.white;
  static const Color line = Color(0xFFE6E2D8);
  static const Color muted = Color(0xFF6B7A74);

  // Semânticas
  static const Color positive = Color(0xFF0F8F6B);
  static const Color negative = Color(0xFFD9573F);
  static const Color info = Color(0xFF2F6FB0);

  // Aliases mantidos para compatibilidade com telas existentes.
  static const Color primaryBlue = emerald;
  static const Color accentTeal = emerald;
  static const Color backgroundLight = paper;
  static const Color cardLight = surface;
  static const Color textDark = ink;
  static const Color successGreen = positive;
  static const Color dangerRed = negative;

  static const double radius = 20;
  static const String fontFamily = 'PlusJakartaSans';

  static List<BoxShadow> get softShadow => [
        BoxShadow(
          color: forest.withValues(alpha: 0.07),
          blurRadius: 24,
          offset: const Offset(0, 8),
        ),
      ];

  static ThemeData get lightTheme {
    final scheme = ColorScheme.fromSeed(
      seedColor: emerald,
      brightness: Brightness.light,
    ).copyWith(
      primary: emerald,
      onPrimary: Colors.white,
      secondary: coin,
      surface: surface,
      onSurface: ink,
      outlineVariant: line,
    );

    const base = TextStyle(fontFamily: fontFamily, color: ink);

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      fontFamily: fontFamily,
      scaffoldBackgroundColor: paper,
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
      ).apply(bodyColor: ink, displayColor: ink),
      appBarTheme: const AppBarTheme(
        backgroundColor: paper,
        foregroundColor: ink,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          fontFamily: fontFamily,
          fontSize: 20,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.3,
          color: ink,
        ),
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radius),
          side: const BorderSide(color: line),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: mint,
        side: BorderSide.none,
        labelStyle: base.copyWith(fontSize: 12, fontWeight: FontWeight.w600),
        shape: const StadiumBorder(),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? Colors.white : muted),
        trackColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? emerald : line),
        trackOutlineColor: const WidgetStatePropertyAll(Colors.transparent),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        border: InputBorder.none,
        hintStyle: TextStyle(color: muted),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: ink,
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
