import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'core/network/api_client.dart';
import 'core/settings/settings_controller.dart';
import 'core/sharing/shared_file_listener.dart';
import 'core/sharing/shared_file_receiver.dart';
import 'core/storage/library_sync.dart';
import 'core/storage/local_library_store.dart';
import 'core/theme/app_theme.dart';
import 'core/widgets/app_motion.dart';
import 'core/widgets/coin.dart';
import 'core/widgets/mascot.dart';
import 'features/budget_scenarios/presentation/scenarios_screen.dart';
import 'features/chat_assistant/presentation/chat_screen.dart';
import 'features/dashboard/presentation/dashboard_screen.dart';
import 'features/finance/data/finance_repository.dart';
import 'features/finance/presentation/finance_controller.dart';
import 'features/settings/presentation/settings_screen.dart';
import 'features/transactions/presentation/transactions_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final settings = await SettingsController.load();
  await Mascot.load();
  // O aparelho guarda a biblioteca cifrada; a API só a mantém em memória (ADR 0025).
  ApiClient newClient() =>
      ApiClient(baseUrlProvider: () => settings.apiBaseUrl);
  final sync = LibrarySync(await EncryptedFileLibraryStore.open(), newClient);
  final finance = FinanceController(FinanceRepository(newClient, sync: sync));
  // A abertura espera o retrato do aparelho voltar à API e só então carrega o
  // resumo, já pronto.
  final firstLoad = () async {
    await sync.hydrate();
    await finance.load();
  }();
  runApp(
    SettingsScope(
      controller: settings,
      child: FinanceScope(
        controller: finance,
        child: TrokimApp(
          firstLoad: firstLoad,
          sharedFiles: SharedFileReceiver(),
        ),
      ),
    ),
  );
}

class TrokimApp extends StatelessWidget {
  const TrokimApp({super.key, this.firstLoad, this.sharedFiles});

  /// Carregamento inicial dos dados; a abertura só termina quando ele acaba
  /// (ou depois de um tempo máximo, se a API não responder).
  final Future<void>? firstLoad;

  /// Extratos recebidos por "Compartilhar" (Android).
  final SharedFileReceiver? sharedFiles;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Trokim',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: SettingsScope.of(context).themeMode,
      scrollBehavior: const NoStretchScrollBehavior(),
      builder: (context, child) {
        final dark = Theme.of(context).brightness == Brightness.dark;
        final c = context.colors;
        return AnnotatedRegion<SystemUiOverlayStyle>(
          value: SystemUiOverlayStyle(
            statusBarColor: Colors.transparent,
            statusBarIconBrightness: dark ? Brightness.light : Brightness.dark,
            systemNavigationBarColor: c.bg,
            systemNavigationBarIconBrightness: dark
                ? Brightness.light
                : Brightness.dark,
          ),
          child: child!,
        );
      },
      home: SplashGate(
        ready: firstLoad,
        child: MainNavigationScreen(sharedFiles: sharedFiles),
      ),
    );
  }
}

class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key, this.sharedFiles});

  /// Com um receptor, um extrato compartilhado abre a aba Extratos e o fluxo de importação.
  final SharedFileReceiver? sharedFiles;

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
    _Destination(
      'Resumo',
      Icons.space_dashboard_outlined,
      Icons.space_dashboard_rounded,
    ),
    _Destination(
      'Extratos',
      Icons.receipt_long_outlined,
      Icons.receipt_long_rounded,
    ),
    _Destination(
      'Assistente',
      Icons.chat_bubble_outline_rounded,
      Icons.chat_bubble_rounded,
    ),
    _Destination(
      'Cenários',
      Icons.swap_horiz_rounded,
      Icons.swap_horiz_rounded,
    ),
    _Destination('Ajustes', Icons.tune_rounded, Icons.tune_rounded),
  ];

  // Mantidas vivas no IndexedStack para preservar estado (ex.: conversa).
  final List<Widget> _screens = const [
    DashboardScreen(),
    TransactionsScreen(),
    ChatScreen(),
    ScenariosScreen(),
    SettingsScreen(),
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
    final curved = CurvedAnimation(
      parent: _transition,
      curve: Motion.emphasized,
    );
    final scaffold = Scaffold(
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
    final receiver = widget.sharedFiles;
    if (receiver == null) return scaffold;
    return SharedFileListener(
      receiver: receiver,
      onFile: () => _select(1),
      child: scaffold,
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
          child: LayoutBuilder(
            builder: (context, c) {
              final w = c.maxWidth / destinations.length;
              return Stack(
                children: [
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
                  Row(
                    children: [
                      for (var i = 0; i < destinations.length; i++)
                        Expanded(
                          child: _NavItem(
                            destination: destinations[i],
                            selected: i == index,
                            onTap: () => onSelected(i),
                          ),
                        ),
                    ],
                  ),
                ],
              );
            },
          ),
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
  const SplashGate({super.key, required this.child, this.ready});
  final Widget child;

  /// Carregamento real que a barra de progresso acompanha. Sem ele, a
  /// abertura dura só o tempo da animação.
  final Future<void>? ready;

  @override
  State<SplashGate> createState() => _SplashGateState();
}

class _SplashGateState extends State<SplashGate> {
  /// Tempo máximo esperando [SplashGate.ready]: sem resposta da API, o app
  /// abre mesmo assim e a tela de resumo mostra o erro.
  static const _maxWait = Duration(seconds: 8);

  bool _timerDone = false;
  bool _loaded = false;

  /// Decidido uma única vez, na abertura: mudar essa opção em Ajustes vale
  /// para a próxima abertura e nunca recria o app em uso (o que apagaria a
  /// conversa do chat e a aba atual).
  bool? _skip;

  @override
  void initState() {
    super.initState();
    Future<void>.delayed(const Duration(milliseconds: 3000), () {
      if (mounted) setState(() => _timerDone = true);
    });
    final ready = widget.ready;
    if (ready == null) {
      _loaded = true;
    } else {
      ready.timeout(_maxWait).catchError((Object _) {}).whenComplete(() {
        if (mounted) setState(() => _loaded = true);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    _skip ??= Motion.reduced(context) || !SettingsScope.of(context).showSplash;
    final showApp = _skip! || (_timerDone && _loaded);
    return AnimatedSwitcher(
      duration: _skip! ? Duration.zero : const Duration(milliseconds: 600),
      switchInCurve: Motion.emphasized,
      switchOutCurve: Curves.easeIn,
      child: showApp
          ? KeyedSubtree(key: const ValueKey('app'), child: widget.child)
          : _Splash(key: const ValueKey('splash'), loaded: _loaded),
    );
  }
}

class _Splash extends StatefulWidget {
  const _Splash({super.key, required this.loaded});

  /// O carregamento real terminou. A barra só chega a 100% quando isso
  /// acontece, mesmo que a animação da moeda já tenha acabado.
  final bool loaded;

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
      body: Stack(
        children: [
          const Positioned.fill(child: DustField()),
          // Brilho dourado atrás da moeda.
          Center(
            child: Container(
              width: 360,
              height: 360,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    AppTheme.gold.withValues(alpha: 0.16),
                    AppTheme.gold.withValues(alpha: 0),
                  ],
                ),
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
                      0,
                      (1 - ((_t - 0.45) / 0.35).clamp(0.0, 1.0)) * 10,
                    ),
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
                      value: _t * 0.9 + (widget.loaded ? 0.1 : 0),
                      backgroundColor: c.line,
                      valueColor: const AlwaysStoppedAnimation(AppTheme.gold),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Rolagem firme: sem o efeito de esticar (Android 12+) nem brilho nas bordas.
class NoStretchScrollBehavior extends MaterialScrollBehavior {
  const NoStretchScrollBehavior();

  @override
  Widget buildOverscrollIndicator(
    BuildContext context,
    Widget child,
    ScrollableDetails details,
  ) => child;

  @override
  ScrollPhysics getScrollPhysics(BuildContext context) =>
      const ClampingScrollPhysics();
}
