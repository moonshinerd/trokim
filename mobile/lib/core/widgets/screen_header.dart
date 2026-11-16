import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'trokim_logo.dart';

/// Cabeçalho editorial das telas: marca discreta, título grande e subtítulo.
class ScreenHeader extends StatelessWidget {
  const ScreenHeader({super.key, required this.title, this.subtitle});

  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const TrokimLogo(size: 30),
        const SizedBox(height: 22),
        Semantics(
          header: true,
          child: Text(title, style: Theme.of(context).textTheme.headlineMedium),
        ),
        if (subtitle != null) ...[
          const SizedBox(height: 6),
          Text(
            subtitle!,
            style: TextStyle(
              color: context.colors.muted,
              fontSize: 14,
              height: 1.4,
            ),
          ),
        ],
      ],
    ),
  );
}
