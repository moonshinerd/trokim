import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'core/theme/app_theme.dart';
import 'core/widgets/app_motion.dart';
import 'core/widgets/coin.dart';
import 'features/budget_scenarios/presentation/scenarios_screen.dart';
import 'features/chat_assistant/presentation/chat_screen.dart';
import 'features/dashboard/presentation/dashboard_screen.dart';
import 'features/transactions/presentation/transactions_screen.dart';

void main() {
  runApp(const TrokimApp());
}

class TrokimApp extends StatelessWidget {
  const TrokimApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Trokim',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.system,
      scrollBehavior: const NoStretchScrollBehavior(),
      builder: (context, child) {
        final dark = Theme.of(context).brightness == Brightness.dark;
        final c = context.colors;
        return AnnotatedRegion<SystemUiOverlayStyle>(
          value: SystemUiOverlayStyle(
            statusBarColor: Colors.transparent,
            statusBarIconBrightness: dark ? Brightness.light : Brightness.dark,
            systemNavigationBarColor: c.bg,
            systemNavigationBarIconBrightness:
                dark ? Brightness.light : Brightness.dark,
          ),
          child: child!,
        );
      },
      home: const SplashGate(child: MainNavigationScreen()),
    );
  }
}

class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen>
    with SingleTickerProviderStateMixin {
  int _currentIndex = 0;
  int _direction = 1;
  late final AnimationController _transition = AnimationController(
    vsync: this,
    duration: Motion.base,
    value: 1,
  );

  static const _destinations = [
    _Destination('Resumo', Icons.space_dashboard_outlined,
        Icons.space_dashboard_rounded),
    _Destination(
        'Extratos', Icons.receipt_long_outlined, Icons.receipt_long_rounded),
    _Destination('Assistente', Icons.chat_bubble_outline_rounded,
        Icons.chat_bubble_rounded),
    _Destination(
        'Cenários', Icons.swap_horiz_rounded, Icons.swap_horiz_rounded),
  ];

  // Mantidas vivas no IndexedStack para preservar estado (ex.: conversa).
  final List<Widget> _screens = const [
    DashboardScreen(),
    TransactionsScreen(),
    ChatScreen(),
    ScenariosScreen(),
  ];

  void _select(int index) {
    if (index == _currentIndex) return;
    setState(() {
      _direction = index > _currentIndex ? 1 : -1;
      _currentIndex = index;
    });
    _transition.forward(from: 0);
  }

  @override
  void dispose() {
    _transition.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final curved =
        CurvedAnimation(parent: _transition, curve: Motion.emphasized);
    return Scaffold(
      body: FadeTransition(
        opacity: curved,
        child: SlideTransition(
          position: Tween<Offset>(
            begin: Offset(0.06 * _direction, 0),
            end: Offset.zero,
          ).animate(curved),
          child: IndexedStack(index: _currentIndex, children: _screens),
        ),
      ),
      bottomNavigationBar: _FloatingNavBar(
        index: _currentIndex,
        destinations: _destinations,
        onSelected: _select,
      ),
    );
  }
}

class _Destination {
  const _Destination(this.label, this.icon, this.selectedIcon);
  final String label;
  final IconData icon;
  final IconData selectedIcon;
}

class _FloatingNavBar extends StatelessWidget {
  const _FloatingNavBar({
    required this.index,
    required this.destinations,
    required this.onSelected,
  });

  final int index;
  final List<_Destination> destinations;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
        child: Container(
          height: 68,
          decoration: BoxDecoration(
            color: context.colors.surface,
            borderRadius: BorderRadius.circular(26),
            border: Border.all(color: context.colors.line),
            boxShadow: AppTheme.softShadow(context),
          ),
          child: LayoutBuilder(builder: (context, c) {
            final w = c.maxWidth / destinations.length;
            return Stack(children: [
              AnimatedPositioned(
                duration: Motion.base,
                curve: Motion.emphasized,
                left: w * index + 6,
                top: 8,
                width: w - 12,
                height: 52,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: context.colors.tint,
                    borderRadius: BorderRadius.circular(18),
                  ),
                ),
              ),
              Row(children: [
                for (var i = 0; i < destinations.length; i++)
                  Expanded(
                    child: _NavItem(
                      destination: destinations[i],
                      selected: i == index,
                      onTap: () => onSelected(i),
                    ),
                  ),
              ]),
            ]);
          }),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.destination,
    required this.selected,
    required this.onTap,
  });

  final _Destination destination;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? context.colors.accent : context.colors.muted;
    return Semantics(
      button: true,
      selected: selected,
      label: destination.label,
      child: ExcludeSemantics(
        child: InkResponse(
          onTap: onTap,
          radius: 36,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              AnimatedSwitcher(
                duration: Motion.fast,
                child: Icon(
                  selected ? destination.selectedIcon : destination.icon,
                  key: ValueKey(selected),
                  size: 23,
                  color: color,
                ),
              ),
              const SizedBox(height: 3),
              AnimatedDefaultTextStyle(
                duration: Motion.fast,
                style: TextStyle(
                  fontFamily: AppTheme.fontFamily,
                  fontSize: 11,
                  fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                  color: color,
                ),
                child: Text(destination.label),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Abertura: a moeda gira em 3D enquanto o app carrega e depois a tela
/// entra suavemente.
class SplashGate extends StatefulWidget {
  const SplashGate({super.key, required this.child});
  final Widget child;

  @override
  State<SplashGate> createState() => _SplashGateState();
}

class _SplashGateState extends State<SplashGate> {
  bool _done = false;

  @override
  void initState() {
    super.initState();
    Future<void>.delayed(const Duration(milliseconds: 3000), () {
      if (mounted) setState(() => _done = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (Motion.reduced(context)) return widget.child;
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 600),
      switchInCurve: Motion.emphasized,
      switchOutCurve: Curves.easeIn,
      child: _done
          ? KeyedSubtree(key: const ValueKey('app'), child: widget.child)
          : const _Splash(key: ValueKey('splash')),
    );
  }
}

class _Splash extends StatefulWidget {
  const _Splash({super.key});

  @override
  State<_Splash> createState() => _SplashState();
}

class _SplashState extends State<_Splash> {
  double _t = 0;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Scaffold(
      backgroundColor: c.bg,
      body: Stack(children: [
        const Positioned.fill(child: DustField()),
        // Brilho violeta atrás da moeda.
        Center(
          child: Container(
            width: 360,
            height: 360,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(colors: [
                AppTheme.violet.withValues(alpha: 0.32),
                AppTheme.violet.withValues(alpha: 0),
              ]),
            ),
          ),
        ),
        Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SpinningCoin(
                size: 320,
                turns: 2,
                duration: const Duration(milliseconds: 2600),
                onProgress: (v) => setState(() => _t = v),
              ),
              const SizedBox(height: 4),
              Opacity(
                opacity: ((_t - 0.45) / 0.35).clamp(0.0, 1.0),
                child: Transform.translate(
                  offset: Offset(
                      0, (1 - ((_t - 0.45) / 0.35).clamp(0.0, 1.0)) * 10),
                  child: Text(
                    'trokim',
                    style: TextStyle(
                      fontFamily: AppTheme.fontFamily,
                      fontSize: 38,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -1.4,
                      color: c.ink,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 28),
              // Barra de carregamento em verde-limão.
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: SizedBox(
                  width: 120,
                  height: 4,
                  child: LinearProgressIndicator(
                    value: _t,
                    backgroundColor: c.line,
                    valueColor: const AlwaysStoppedAnimation(AppTheme.lime),
                  ),
                ),
              ),
            ],
          ),
        ),
      ]),
    );
  }
}

/// Rolagem firme: sem o efeito de esticar (Android 12+) nem brilho nas bordas.
class NoStretchScrollBehavior extends MaterialScrollBehavior {
  const NoStretchScrollBehavior();

  @override
  Widget buildOverscrollIndicator(
          BuildContext context, Widget child, ScrollableDetails details) =>
      child;

  @override
  ScrollPhysics getScrollPhysics(BuildContext context) =>
      const ClampingScrollPhysics();
}
