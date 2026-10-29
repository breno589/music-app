package com.sonsplayer.app

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import org.json.JSONObject
import java.io.File
import java.util.Locale
import java.util.UUID

/**
 * Downloads de arquivos de audio HTTPS diretos e autorizados.
 * Nao converte links de video ou playlist YouTube em audio.
 */
class OfflineDownloads(private val context: Context) {
    private val prefs = context.getSharedPreferences("sons_offline_v32", Context.MODE_PRIVATE)
    private val manager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager

    data class Result(val completed: Int, val failed: Int, val waiting: Int)

    fun enqueue(rawUrl: String, title: String): Long {
        val uri = Uri.parse(rawUrl.trim())
        val host = uri.host?.lowercase(Locale.US).orEmpty()
        require(uri.scheme.equals("https", true) && host.isNotBlank()) { "Informe um link HTTPS válido." }
        require(host != "youtube.com" && !host.endsWith(".youtube.com") && host != "youtu.be" &&
                host != "music.youtube.com") { "Links do YouTube não são arquivos de áudio diretos." }

        val ext = uri.lastPathSegment?.substringAfterLast('.', "")?.lowercase(Locale.US).orEmpty()
        require(ext in setOf("mp3", "m4a", "aac", "ogg", "opus", "flac", "wav")) {
            "Use um link direto para arquivo MP3, M4A, AAC, OGG, OPUS, FLAC ou WAV."
        }
        val cleanTitle = title.trim().take(90).ifBlank { "Áudio offline" }
        val filename = "sons_" + UUID.randomUUID().toString() + "." + ext
        val request = DownloadManager.Request(uri)
            .setTitle(cleanTitle)
            .setDescription("SonsPlayer • Áudio autorizado")
            .setAllowedOverRoaming(false)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_MUSIC, filename)
        val id = manager.enqueue(request)
        val obj = pending()
        obj.put(id.toString(), JSONObject().put("file", filename).put("title", cleanTitle))
        prefs.edit().putString("pending", obj.toString()).apply()
        return id
    }

    fun reconcile(store: LibraryStore): Result {
        val obj = pending()
        val keys = mutableListOf<String>()
        val iterator = obj.keys()
        while (iterator.hasNext()) keys.add(iterator.next())
        var imported = 0
        var failed = 0
        var waiting = 0
        for (key in keys) {
            val id = key.toLongOrNull() ?: continue
            val item = obj.optJSONObject(key) ?: continue
            val cursor = try { manager.query(DownloadManager.Query().setFilterById(id)) } catch (_: Exception) { null }
            var status = -1
            cursor?.use {
                if (it.moveToFirst()) {
                    status = it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                }
            }
            if (status == DownloadManager.STATUS_SUCCESSFUL) {
                val file = File(context.getExternalFilesDir(Environment.DIRECTORY_MUSIC), item.optString("file"))
                if (file.isFile && file.length() > 0L) {
                    store.addImported(Track(Uri.fromFile(file).toString(),
                        item.optString("title", "Áudio offline"), "Baixado • disponível sem internet", "download"))
                    imported++
                } else failed++
                obj.remove(key)
            } else if (status == DownloadManager.STATUS_FAILED || status == -1) {
                failed++
                obj.remove(key)
            } else waiting++
        }
        prefs.edit().putString("pending", obj.toString()).apply()
        return Result(imported, failed, waiting)
    }

    private fun pending(): JSONObject =
        try { JSONObject(prefs.getString("pending", "{}") ?: "{}") }
        catch (_: Exception) { JSONObject() }
}
