package br.com.trokim.trokim

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Recebe extratos enviados por "Compartilhar" (ou "Abrir com") de outro app, como o app do banco
 * ou o e-mail, e entrega o arquivo ao Flutter pelo canal [CHANNEL].
 *
 * O arquivo é lido aqui e só os bytes e o nome seguem para o app: nada sai do aparelho.
 */
class MainActivity : FlutterActivity() {
    private var channel: MethodChannel? = null

    // Arquivo que abriu o app, guardado até o Flutter pedir (a tela inicial ainda está carregando).
    private var pending: Map<String, Any>? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        pending = readSharedFile(intent)
        channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).apply {
            setMethodCallHandler { call, result ->
                when (call.method) {
                    "takeInitialFile" -> {
                        result.success(pending)
                        pending = null
                    }
                    else -> result.notImplemented()
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        val file = readSharedFile(intent) ?: return
        channel?.invokeMethod("fileShared", file)
    }

    private fun readSharedFile(intent: Intent?): Map<String, Any>? {
        val uri = when (intent?.action) {
            Intent.ACTION_SEND -> streamExtra(intent)
            Intent.ACTION_VIEW -> intent.data
            else -> null
        } ?: return null
        return try {
            val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return null
            if (bytes.isEmpty() || bytes.size > MAX_BYTES) return null
            mapOf("name" to displayName(uri), "bytes" to bytes)
        } catch (e: Exception) {
            // Sem permissão ou arquivo indisponível: o app abre normalmente, sem o arquivo.
            null
        }
    }

    private fun streamExtra(intent: Intent): Uri? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(Intent.EXTRA_STREAM)
        }

    private fun displayName(uri: Uri): String {
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            ?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val name = cursor.getString(0)
                    if (!name.isNullOrBlank()) return name
                }
            }
        return uri.lastPathSegment?.substringAfterLast('/') ?: "arquivo"
    }

    companion object {
        const val CHANNEL = "br.com.trokim/shared_file"

        // Extratos e faturas têm poucos KB; o limite evita travar o app com um arquivo errado.
        const val MAX_BYTES = 20 * 1024 * 1024
    }
}
