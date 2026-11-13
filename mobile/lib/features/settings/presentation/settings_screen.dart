import 'dart:async';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../../../core/constants/api_constants.dart';
import '../../../core/settings/settings_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/screen_header.dart';
import '../../../core/widgets/trokim_logo.dart';

const String appVersion = '0.1.0';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key, this.controller, this.client});

  /// Injetáveis para teste; em produção usa o escopo do app.
  final SettingsController? controller;
  final http.Client? client;

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
                  subtitle: 'Aparência, animações, conexão e privacidade.',
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
                child: Column(children: [
                  _SwitchRow(
                    title: 'Reduzir animações',
                    subtitle: 'Menos movimento nas transições e nos gráficos.',
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
                ]),
              ),
              _Section(
                index: 3,
                title: 'Assistente',
                child: _SwitchRow(
                  title: 'Respostas com IA (LLM local)',
                  subtitle:
                      'O modelo de linguagem redige a resposta com base nas fontes oficiais. Desligado, o assistente só recupera os trechos, de forma mais rápida.',
                  value: settings.generativeChat,
                  onChanged: settings.setGenerativeChat,
                ),
              ),
              _Section(
                index: 4,
                title: 'Conexão',
                child: _ConnectionCard(client: client),
              ),
              _Section(
                index: 5,
                title: 'Privacidade',
                child: const _InfoRow(
                  icon: Icons.lock_rounded,
                  text: 'Seus extratos são lidos e guardados só neste '
                      'aparelho. Os números são calculados por código; a IA '
                      'apenas explica, com base em fontes oficiais.',
                ),
              ),
              Reveal(index: 6, child: const _About()),
            ],
          ),
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section(
      {required this.index, required this.title, required this.child});
  final int index;
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
        child: Reveal(
          index: index,
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Padding(
              padding: const EdgeInsets.only(left: 4, bottom: 8),
              child: Semantics(
                header: true,
                child: Text(title.toUpperCase(),
                    style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.1,
                        color: context.colors.muted)),
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
          ]),
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
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
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
        ]),
        const SizedBox(height: 10),
        Text(
          settings.themeMode == ThemeMode.system
              ? 'Segue o claro/escuro do seu aparelho.'
              : 'Fixo no tema ${settings.themeMode == ThemeMode.dark ? 'escuro' : 'claro'}.',
          style: TextStyle(fontSize: 12.5, color: c.muted),
        ),
      ]),
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
            child: Column(children: [
              Icon(icon, size: 22, color: selected ? AppTheme.forest : c.muted),
              const SizedBox(height: 6),
              Text(label,
                  style: TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w800,
                      color: selected ? AppTheme.forest : c.ink)),
            ]),
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
          title: Text(title,
              style:
                  const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
          subtitle: Text(subtitle,
              style: TextStyle(fontSize: 12.5, color: context.colors.muted)),
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
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(icon, size: 22, color: context.colors.accent),
          const SizedBox(width: 12),
          Expanded(
            child: Text(text,
                style: TextStyle(
                    fontSize: 13.5, height: 1.45, color: context.colors.ink)),
          ),
        ]),
      );
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

  Future<void> _test() async {
    setState(() => _state = _Probe.loading);
    final client = widget.client ?? http.Client();
    try {
      final res = await client
          .get(Uri.parse(
              '${ApiConstants.defaultBaseUrl}${ApiConstants.healthEndpoint}'))
          .timeout(const Duration(seconds: 4));
      if (mounted) {
        setState(
            () => _state = res.statusCode == 200 ? _Probe.ok : _Probe.fail);
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
    final (label, color) = switch (_state) {
      _Probe.idle => ('Não testado', c.muted),
      _Probe.loading => ('Testando…', c.muted),
      _Probe.ok => ('Conectado', AppTheme.positive),
      _Probe.fail => ('Sem conexão com a API', AppTheme.negative),
    };
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Endereço da API',
            style: TextStyle(fontSize: 12.5, color: c.muted)),
        const SizedBox(height: 4),
        SelectableText(ApiConstants.defaultBaseUrl,
            style:
                const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5)),
        const SizedBox(height: 14),
        Row(children: [
          Expanded(
            child: Semantics(
              liveRegion: true,
              child: Row(children: [
                Container(
                  width: 9,
                  height: 9,
                  decoration:
                      BoxDecoration(color: color, shape: BoxShape.circle),
                ),
                const SizedBox(width: 8),
                Flexible(
                  child: Text(label,
                      style: TextStyle(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w700,
                          color: color)),
                ),
              ]),
            ),
          ),
          FilledButton(
            onPressed: _state == _Probe.loading ? null : _test,
            style: FilledButton.styleFrom(
              backgroundColor: AppTheme.gold,
              foregroundColor: AppTheme.forest,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
            child: const Text('Testar conexão',
                style: TextStyle(fontWeight: FontWeight.w800)),
          ),
        ]),
      ]),
    );
  }
}

class _About extends StatelessWidget {
  const _About();

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 32, 20, 0),
        child: Column(children: [
          const TrokimMark(size: 64),
          const SizedBox(height: 10),
          const Text('Trokim',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text('Versão $appVersion · Challenge 2 · TIC-IA 2026',
              style: TextStyle(fontSize: 12.5, color: context.colors.muted)),
        ]),
      );
}
