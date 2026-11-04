import 'package:flutter/material.dart';

class TransactionsScreen extends StatelessWidget {
  const TransactionsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Extratos & Faturas'),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Seletor de arquivos OFX/PDF em execução local.'),
            ),
          );
        },
        icon: const Icon(Icons.file_upload_outlined),
        label: const Text('Importar Extrato'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const [
          ListTile(
            leading: Icon(Icons.check_circle, color: Colors.green),
            title: Text('extrato_novembro_sintetico.ofx'),
            subtitle: Text('3 transações importadas • Sem duplicatas'),
            trailing: Text('OFX', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
          Divider(),
          ListTile(
            leading: Icon(Icons.picture_as_pdf, color: Colors.red),
            title: Text('fatura_cartao_sintetica.pdf'),
            subtitle: Text('4 transações importadas • 1 duplicata evitada'),
            trailing: Text('PDF', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }
}
