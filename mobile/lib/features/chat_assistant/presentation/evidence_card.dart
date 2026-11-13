import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../domain/chat_models.dart';

/// Cartão isolado para exibir e abrir uma evidência retornada pelo RAG.
///
/// Quem tem a chave de [EvidenceCardState] pode chamar [EvidenceCardState.reveal]
/// para abrir o cartão, rolar até ele e destacá-lo (usado pelos marcadores
/// [1], [2]… do texto da resposta).
class EvidenceCard extends StatefulWidget {
  const EvidenceCard({super.key, required this.evidence, this.number});

  /// Posição da fonte na resposta, igual ao marcador [n] do texto.
  final int? number;

  final Evidence evidence;

  @override
  State<EvidenceCard> createState() => EvidenceCardState();
}

class EvidenceCardState extends State<EvidenceCard>
    with SingleTickerProviderStateMixin {
  final ExpansibleController _expansion = ExpansibleController();
  late final AnimationController _flash = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  );

  Evidence get evidence => widget.evidence;
  int? get number => widget.number;

  @override
  void dispose() {
    _flash.dispose();
    super.dispose();
  }

  /// Abre o cartão, rola até ele e o destaca por um instante.
  void reveal() {
    _expansion.expand();
    _flash.forward(from: 0);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      Scrollable.ensureVisible(
        context,
        duration: Motion.reduced(context)
            ? Duration.zero
            : const Duration(milliseconds: 380),
        curve: Motion.emphasized,
        alignment: 0.15,
      );
    });
  }

  String get _institution {
    final name = evidence.sourceName.toLowerCase();
    if (name.contains('banco central') || name.contains('bcb')) return 'BCB';
    if (name.contains('cvm')) return 'CVM';
    if (name.contains('cfpb')) return 'CFPB';
    return evidence.sourceName;
  }

  Future<void> _openSource(BuildContext context) async {
    final uri = Uri.tryParse(evidence.sourceUrl ?? '');
    if (uri == null || !{'http', 'https'}.contains(uri.scheme)) return;
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Não foi possível abrir o link da fonte.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Uri.tryParse(evidence.sourceUrl ?? '')?.scheme;
    final hasLink = scheme == 'http' || scheme == 'https';
    final score = (evidence.score * 100).clamp(0, 100).round();
    final c = context.colors;
    return AnimatedBuilder(
      animation: _flash,
      builder: (context, child) {
        // brilho dourado que some: 1 -> 0 ao longo da animação
        final glow = (1 - _flash.value) * (_flash.isAnimating ? 1 : 0);
        return DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppTheme.radius),
            boxShadow: [
              if (glow > 0)
                BoxShadow(
                  color: AppTheme.gold.withValues(alpha: 0.55 * glow),
                  blurRadius: 16 * glow,
                  spreadRadius: 2 * glow,
                ),
            ],
            border: Border.all(
              color:
                  Color.lerp(Colors.transparent, AppTheme.gold, glow) ?? c.line,
              width: 1.5,
            ),
          ),
          child: child,
        );
      },
      child: Card(
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        child: ExpansionTile(
          controller: _expansion,
          tilePadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          leading: CircleAvatar(
            radius: 17,
            backgroundColor: AppTheme.positive.withValues(alpha: 0.16),
            child: const Icon(Icons.verified_outlined,
                size: 19, color: AppTheme.positive),
          ),
          title: Text('${evidence.sourceName} • ${evidence.documentTitle}',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style:
                  const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 5),
            child: Wrap(spacing: 6, runSpacing: 4, children: [
              if (number != null) _Tag(label: '[$number]'),
              _Tag(label: _institution),
              _Tag(label: 'Relevância $score%'),
            ]),
          ),
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Text(evidence.section,
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 12)),
            ),
            const SizedBox(height: 6),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(evidence.content,
                  style: const TextStyle(fontSize: 13, height: 1.45)),
            ),
            if (hasLink) ...[
              const SizedBox(height: 8),
              SelectableText(
                evidence.sourceUrl!,
                style: TextStyle(color: context.colors.accent, fontSize: 11),
              ),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => _openSource(context),
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: const Text('Abrir documento oficial'),
                  style: TextButton.styleFrom(
                      foregroundColor: context.colors.accent),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
        decoration: BoxDecoration(
          color: context.colors.tint,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(label,
            style: TextStyle(color: context.colors.accent, fontSize: 10)),
      );
}
