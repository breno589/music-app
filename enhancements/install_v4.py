from pathlib import Path

base = Path("app/src/main")
src = base / "java/com/sonsplayer/app"
src.mkdir(parents=True, exist_ok=True)

(src / "SonsOfflineDownloads.kt").write_text(r'''package com.sonsplayer.app

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import org.json.JSONObject
import java.io.File
import java.util.Locale

/**
 * Baixa apenas links HTTPS diretos de arquivos de áudio autorizados.
 * Não recebe links de vídeos, streams HLS, URLs do YouTube ou de suas CDNs.
 * O arquivo permanece no diretório de músicas privado do aplicativo.
 */
class SonsOfflineDownloads(private val context: Context) {
    private val manager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
    private val prefs = context.getSharedPreferences("sons_offline_jobs_v4", Context.MODE_PRIVATE)
    private val extensions = setOf("mp3", "m4a", "aac", "ogg", "opus", "flac", "wav")

    fun enqueue(rawUrl: String, rawTitle: String): Long {
        val uri = Uri.parse(rawUrl.trim())
        val host = uri.host?.lowercase(Locale.US) ?: ""
        val extension = uri.lastPathSegment?.substringAfterLast('.', "")?.lowercase(Locale.US) ?: ""
        val blockedHost = host == "youtube.com" || host.endsWith(".youtube.com") ||
                host == "youtu.be" || host == "googlevideo.com" ||
                host.endsWith(".googlevideo.com") || host.endsWith(".youtube-nocookie.com")
        require(uri.scheme.equals("https", true) && host.isNotBlank() && !blockedHost && extension in extensions) {
            "Use uma URL HTTPS direta para um arquivo MP3, M4A, AAC, OGG, OPUS, FLAC ou WAV autorizado."
        }
        val title = rawTitle.trim().ifBlank {
            uri.lastPathSegment?.substringBeforeLast('.')?.take(80) ?: "Minha musica"
        }.take(90)
        val safeName = title.replace(Regex("[^A-Za-z0-9 _.-]"), "_").trim().ifBlank { "audio" }
        val relative = "SonsPlayer/" + System.currentTimeMillis() + "_" + safeName + "." + extension
        val directory = File(context.getExternalFilesDir(Environment.DIRECTORY_MUSIC), "SonsPlayer")
        check(directory.exists() || directory.mkdirs()) { "Não foi possível criar a pasta offline." }

        val request = DownloadManager.Request(uri)
            .setTitle("SonsPlayer · $title")
            .setDescription("Baixando áudio autorizado para ouvir offline")
            .setMimeType(if (extension == "mp3") "audio/mpeg" else "audio/*")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setAllowedOverMetered(true)
            .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_MUSIC, relative)
        val id = manager.enqueue(request)
        prefs.edit().putString(id.toString(),
            JSONObject().put("title", title).put("file", relative).toString()).apply()
        return id
    }

    /**
     * Registra músicas concluídas na biblioteca ao reabrir ou atualizar o app.
     * Retorna quantas músicas novas foram incorporadas.
     */
    fun sync(store: LibraryStore): Int {
        var imported = 0
        for ((key, value) in prefs.all) {
            val id = key.toLongOrNull() ?: continue
            val job = try { JSONObject(value as? String ?: continue) } catch (_: Exception) { continue }
            try {
                manager.query(DownloadManager.Query().setFilterById(id))?.use { cursor ->
                    if (!cursor.moveToFirst()) return@use
                    val statusIndex = cursor.getColumnIndex(DownloadManager.COLUMN_STATUS)
                    if (statusIndex < 0) return@use
                    when (cursor.getInt(statusIndex)) {
                        DownloadManager.STATUS_SUCCESSFUL -> {
                            val relative = job.optString("file")
                            val base = context.getExternalFilesDir(Environment.DIRECTORY_MUSIC) ?: return@use
                            val file = File(base, relative).canonicalFile
                            if (file.path.startsWith(base.canonicalPath + File.separator) &&
                                file.isFile && file.length() > 0L) {
                                val uri = Uri.fromFile(file).toString()
                                store.addImported(Track(uri, job.optString("title", file.name),
                                    "Offline · SonsPlayer", "downloaded"))
                                imported++
                            }
                            prefs.edit().remove(key).apply()
                        }
                        DownloadManager.STATUS_FAILED -> prefs.edit().remove(key).apply()
                    }
                }
            } catch (_: Exception) {
                // Não comprometer a abertura da biblioteca se o download falhar.
            }
        }
        return imported
    }
}
''', encoding="utf-8")

main = src / "MainActivity.kt"
s = main.read_text(encoding="utf-8")
needle = '    private lateinit var libraryStore: LibraryStore'
assert needle in s
s = s.replace(needle, needle + '\n    private lateinit var offlineDownloads: SonsOfflineDownloads', 1)
needle = '        libraryStore = LibraryStore(this)'
assert needle in s
s = s.replace(needle, needle + '\n        offlineDownloads = SonsOfflineDownloads(this)', 1)
needle = '        findViewById<View>(R.id.btnAdd).setOnClickListener { addAudioOptions() }'
assert needle in s
s = s.replace(needle, needle + '\n        findViewById<View>(R.id.btnOffline).setOnClickListener { showOfflineDownload() }', 1)
needle = '        val options = arrayOf("Importar arquivo MP3 / áudio", "Adicionar URL HTTPS de áudio", "Atualizar músicas do celular")'
assert needle in s
s = s.replace(needle,
'''        val options = arrayOf(
            "Importar arquivo MP3 / áudio",
            "Adicionar URL HTTPS de áudio",
            "Atualizar músicas do celular",
            "Baixar arquivo de áudio autorizado para ouvir offline"
        )''', 1)
needle = '                2 -> { scanLibrary(); toast("Atualizando biblioteca...") }'
assert needle in s
s = s.replace(needle,
'''                2 -> { checkOfflineDownloads(); scanLibrary(); toast("Atualizando biblioteca...") }
                3 -> showOfflineDownload()''',1)
needle = '    private fun showTrackOptions(anchor: View, track: Track) {'
assert needle in s
s = s.replace(needle,
'''    private fun showOfflineDownload() {
        val outer = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(40, 8, 40, 8)
        }
        val urlInput = EditText(this).apply {
            hint = "https://seusite.com/minha-musica.mp3"
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
        }
        val titleInput = EditText(this).apply {
            hint = "Nome da música (opcional)"
            setSingleLine(true)
        }
        outer.addView(urlInput)
        outer.addView(titleInput)
        AlertDialog.Builder(this)
            .setTitle("Baixar áudio para ouvir offline")
            .setMessage("Somente link HTTPS direto de um arquivo de áudio que você pode baixar. Não aceita links de vídeos do YouTube.")
            .setView(outer)
            .setNegativeButton("Cancelar", null)
            .setPositiveButton("Baixar") { _, _ ->
                try {
                    offlineDownloads.enqueue(urlInput.text.toString(), titleInput.text.toString())
                    toast("Download iniciado. Toque em Atualizar músicas ao concluir.")
                } catch (error: Exception) {
                    toast(error.message ?: "Não foi possível iniciar o download.")
                }
            }.show()
    }

    private fun checkOfflineDownloads() {
        val added = offlineDownloads.sync(libraryStore)
        if (added > 0) toast("$added música(s) pronta(s) para ouvir offline!")
    }

''' + needle, 1)
needle = '    override fun onStart() {\n        super.onStart()'
assert needle in s
s = s.replace(needle, '    override fun onStart() {\n        super.onStart()\n        checkOfflineDownloads()\n        scanLibrary()', 1)
main.write_text(s, encoding="utf-8")

layout = base / "res/layout/activity_main.xml"
s = layout.read_text(encoding="utf-8")
needle = '    <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="24dp"'
assert needle in s
s = s.replace(needle, '''    <TextView android:id="@+id/btnOffline"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:layout_marginTop="12dp" android:padding="12dp"
        android:gravity="center_vertical" android:background="@drawable/bg_card"
        android:text="↓  BAIXAR ÁUDIO OFFLINE   •   Links diretos autorizados"
        android:textColor="@color/accent" android:textSize="12sp"
        android:contentDescription="Baixar arquivos MP3 e outros áudios autorizados para ouvir sem internet"/>
''' + needle, 1)
s = s.replace('android:text="Sua música. Seu ritmo."','android:text="Sua música, do seu jeito."')
layout.write_text(s, encoding="utf-8")

print("SonsPlayer V4: download offline de audio autorizado e interface adicionados")
