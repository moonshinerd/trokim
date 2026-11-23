import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../../../core/network/api_client.dart';
import '../../../core/settings/settings_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../finance/presentation/finance_controller.dart';

/// Arquivo de backup escolhido pelo usuário.
class PickedBackup {
  const PickedBackup(this.name, this.readBytes);
  final String name;
  final Future<Uint8List> Function() readBytes;
}

typedef BackupSaver = Future<bool> Function(String fileName, List<int> bytes);
typedef BackupPicker = Future<PickedBackup?> Function();

/// Salva o backup pelo seletor do sistema. Devolve `false` se o usuário cancelar.
Future<bool> saveBackupFile(String fileName, List<int> bytes) async {
  final target = await FilePicker.saveFile(
    dialogTitle: 'Salvar backup do Trokim',
    fileName: fileName,
    bytes: Uint8List.fromList(bytes),
  );
  // Na web o navegador baixa o arquivo e não devolve um destino.
  return kIsWeb || target != null;
}

/// Abre o seletor de arquivos. Não filtra por extensão: o Android não conhece `.trokim`.
Future<PickedBackup?> pickBackupFile() async {
  final file = await FilePicker.pickFile(
    dialogTitle: 'Escolha o backup (.trokim)',
  );
  if (file == null) return null;
  return PickedBackup(file.name, file.readAsBytes);
}

/// Cartão de Ajustes para exportar e restaurar a biblioteca em um arquivo
/// `.trokim` criptografado com a senha do usuário (ADR 0024).
class BackupCard extends StatefulWidget {
  const BackupCard({super.key, this.client, this.saveBackup, this.pickBackup});

  final http.Client? client;
  final BackupSaver? saveBackup;
  final BackupPicker? pickBackup;

  @override
  State<BackupCard> createState() => _BackupCardState();
}

class _BackupCardState extends State<BackupCard> {
  static const int minPassphrase = 8;

  final _passphrase = TextEditingController();
  bool _replace = false;
  bool _busy = false;
  String? _message;
  bool _failed = false;

  @override
  void dispose() {
    _passphrase.dispose();
    super.dispose();
  }

  ApiClient _client(SettingsController settings) => ApiClient(
    baseUrlProvider: () => settings.apiBaseUrl,
    client: widget.client,
  );

  bool _validPassphrase() {
    if (_passphrase.text.length >= minPassphrase) return true;
    _show('Use uma senha com pelo menos $minPassphrase caracteres.', true);
    return false;
  }

  void _show(String text, bool failed) {
    if (!mounted) return;
    setState(() {
      _message = text;
      _failed = failed;
      _busy = false;
    });
  }

  String _errorText(Object error) {
    if (error is ApiException) {
      return error.detail ?? 'A API recusou o pedido (${error.statusCode}).';
    }
    return 'Sem conexão com a API. Confira o endereço em Conexão.';
  }

  String _fileName() {
    final now = DateTime.now();
    String two(int n) => n.toString().padLeft(2, '0');
    return 'trokim-${now.year}${two(now.month)}${two(now.day)}.trokim';
  }

  Future<void> _export() async {
    if (_busy || !_validPassphrase()) return;
    final settings = SettingsScope.of(context);
    setState(() {
      _busy = true;
      _message = null;
    });
    final client = _client(settings);
    try {
      final bytes = await client.exportBackup(_passphrase.text);
      final saved = await (widget.saveBackup ?? saveBackupFile)(
        _fileName(),
        bytes,
      );
      _show(
        saved
            ? 'Backup criptografado salvo. Guarde a senha: sem ela ele não abre.'
            : 'Exportação cancelada.',
        false,
      );
    } on Object catch (error) {
      _show(_errorText(error), true);
    } finally {
      client.close();
    }
  }

  Future<bool> _confirmReplace() async =>
      await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Substituir tudo?'),
          content: const Text(
            'Os lançamentos e decisões que existem neste aparelho serão '
            'apagados e trocados pelos do backup.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Substituir'),
            ),
          ],
        ),
      ) ??
      false;

  Future<void> _import() async {
    if (_busy || !_validPassphrase()) return;
    final settings = SettingsScope.of(context);
    final finance = FinanceScope.read(context);
    if (_replace && !await _confirmReplace()) return;
    final picked = await (widget.pickBackup ?? pickBackupFile)();
    if (picked == null) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    final client = _client(settings);
    try {
      final result = await client.importBackup(
        picked.name,
        await picked.readBytes(),
        passphrase: _passphrase.text,
        mode: _replace ? 'substituir' : 'mesclar',
      );
      final added = (result['added'] as Map?)?['transactions'] ?? 0;
      final total = result['transactions_total'] ?? 0;
      await finance?.load();
      _show(
        'Backup restaurado: $added lançamentos novos, $total no total.',
        false,
      );
    } on Object catch (error) {
      _show(_errorText(error), true);
    } finally {
      client.close();
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Leve seus dados para outro aparelho em um arquivo protegido por '
            'senha. Ninguém lê o arquivo sem ela, e ela não é guardada: se '
            'você esquecer, não há como recuperar.',
            style: TextStyle(color: c.muted, height: 1.4),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _passphrase,
            obscureText: true,
            enableSuggestions: false,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: 'Senha do backup',
              helperText: 'Pelo menos 8 caracteres',
            ),
          ),
          const SizedBox(height: 8),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Substituir o que existe'),
            subtitle: const Text(
              'Desligado, o backup só acrescenta o que falta, sem duplicar.',
            ),
            value: _replace,
            onChanged: _busy ? null : (v) => setState(() => _replace = v),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: [
              FilledButton.icon(
                onPressed: _busy ? null : _export,
                icon: const Icon(Icons.upload_file_rounded),
                label: const Text('Exportar backup'),
              ),
              OutlinedButton.icon(
                onPressed: _busy ? null : _import,
                icon: const Icon(Icons.download_rounded),
                label: const Text('Restaurar backup'),
              ),
            ],
          ),
          if (_busy)
            const Padding(
              padding: EdgeInsets.only(top: 12),
              child: LinearProgressIndicator(),
            ),
          if (_message != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                _message!,
                key: const Key('backup-message'),
                style: TextStyle(
                  color: _failed ? AppTheme.negative : AppTheme.positive,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
