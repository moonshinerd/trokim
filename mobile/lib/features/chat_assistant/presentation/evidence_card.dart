import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/theme/app_theme.dart';
import '../domain/chat_models.dart';

/// Cartão isolado para exibir e abrir uma evidência retornada pelo RAG.
class EvidenceCard extends StatelessWidget {
  const EvidenceCard({super.key, required this.evidence});

  final Evidence evidence;

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
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        leading: const CircleAvatar(
          radius: 17,
          backgroundColor: Color(0xFFE8F5E9),
          child:
              Icon(Icons.verified_outlined, size: 19, color: Color(0xFF168447)),
        ),
        title: Text('${evidence.sourceName} • ${evidence.documentTitle}',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 5),
          child: Wrap(spacing: 6, runSpacing: 4, children: [
            _Tag(label: _institution),
            _Tag(label: 'Relevância $score%'),
          ]),
        ),
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: Text(evidence.section,
                style:
                    const TextStyle(fontWeight: FontWeight.w600, fontSize: 12)),
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
              style: const TextStyle(color: AppTheme.primaryBlue, fontSize: 11),
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () => _openSource(context),
                icon: const Icon(Icons.open_in_new, size: 16),
                label: const Text('Abrir documento oficial'),
                style:
                    TextButton.styleFrom(foregroundColor: AppTheme.primaryBlue),
              ),
            ),
          ],
        ],
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
          color: const Color(0xFFEFF6FF),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(label,
            style: const TextStyle(color: AppTheme.primaryBlue, fontSize: 10)),
      );
}
