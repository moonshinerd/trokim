import 'dart:async';

import 'package:flutter/material.dart';

import '../../features/import_guide/presentation/import_flow_screen.dart';
import '../../features/transactions/presentation/transactions_screen.dart';
import 'shared_file_receiver.dart';

/// Abre o fluxo de importação já com o arquivo quando um extrato é compartilhado com o app.
///
/// Atende o arquivo que abriu o app e os que chegam depois. [onFile] é chamado antes de abrir o
/// fluxo (a navegação principal usa para mostrar a aba Extratos por baixo).
class SharedFileListener extends StatefulWidget {
  const SharedFileListener({
    super.key,
    required this.receiver,
    required this.child,
    this.onFile,
  });

  final SharedFileReceiver receiver;
  final Widget child;
  final VoidCallback? onFile;

  @override
  State<SharedFileListener> createState() => _SharedFileListenerState();
}

class _SharedFileListenerState extends State<SharedFileListener> {
  StreamSubscription<PickedStatement>? _subscription;

  @override
  void initState() {
    super.initState();
    _subscription = widget.receiver.files.listen(_open);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final initial = await widget.receiver.takeInitialFile();
      if (initial != null) _open(initial);
    });
  }

  void _open(PickedStatement file) {
    if (!mounted) return;
    widget.onFile?.call();
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ImportFlowScreen(initialFile: file),
      ),
    );
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
