import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'core/theme/app_theme.dart';
import 'core/widgets/app_motion.dart';
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
      builder: (context, child) => AnnotatedRegion<SystemUiOverlayStyle>(
        value: const SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.dark,
          systemNavigationBarColor: AppTheme.paper,
          systemNavigationBarIconBrightness: Brightness.dark,
        ),
        child: child!,
      ),
      home: const MainNavigationScreen(),
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
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(26),
            border: Border.all(color: AppTheme.line),
            boxShadow: AppTheme.softShadow,
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
                    color: AppTheme.mint,
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
    final color = selected ? AppTheme.forest : AppTheme.muted;
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
