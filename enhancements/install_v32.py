from pathlib import Path

source = Path("enhancements/OfflineDownloads.kt")
target = Path("app/src/main/java/com/sonsplayer/app/OfflineDownloads.kt")
target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

main_path = Path("app/src/main/java/com/sonsplayer/app/MainActivity.kt")
main = main_path.read_text(encoding="utf-8")

def replace_once(old, new):
    global main
    if old not in main:
        raise RuntimeError("Trecho da activity nao encontrado: " + old[:90])
    main = main.replace(old, new, 1)

replace_once(
    '    private var currentTab = Tab.ALL',
    '    private val offline by lazy { OfflineDownloads(this) }\n    private var currentTab = Tab.ALL'
)

replace_once(
    'val options = arrayOf("Importar arquivo MP3 / áudio", "Adicionar URL HTTPS de áudio", "Atualizar músicas do celular")',
    'val options = arrayOf("Importar arquivo MP3 / áudio", "Adicionar URL HTTPS de áudio", "Baixar arquivo de áudio para offline", "Verificar downloads pendentes", "Atualizar músicas do celular")'
)
replace_once(
    '                2 -> { scanLibrary(); toast("Atualizando biblioteca...") }',
    '                2 -> showOfflineDownloadDialog()\n                3 -> checkOfflineDownloads(true)\n                4 -> { scanLibrary(); toast("Atualizando biblioteca...") }'
)
replace_once(
    '        PopupMenu(this, anchor).apply {\n            val add = menu.add("Adicionar a uma playlist")',
    '        PopupMenu(this, anchor).apply {\n            val download = if (track.source == "stream") menu.add("Baixar para ouvir offline") else null\n            val add = menu.add("Adicionar a uma playlist")'
)
replace_once(
    '                when (item) {\n                    add -> choosePlaylist(track)',
    '                when (item) {\n                    download -> startDownload(track.uri, track.title)\n                    add -> choosePlaylist(track)'
)

insert_before = '    private fun showTrackOptions(anchor: View, track: Track) {'
new_methods = '''
    private fun showOfflineDownloadDialog() {
        val input = EditText(this).apply {
            hint = "https://site-autorizado.com/musica.mp3"
            inputType = android.text.InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
            setPadding(38, 20, 38, 20)
        }
        AlertDialog.Builder(this)
            .setTitle("Download offline")
            .setMessage("Cole um link HTTPS direto de MP3, M4A, AAC, OGG, OPUS, FLAC ou WAV que permita download. Links de videos YouTube nao funcionam aqui.")
            .setView(input)
            .setNegativeButton("Cancelar", null)
            .setPositiveButton("Baixar") { _, _ ->
                val url = input.text.toString().trim()
                val title = Uri.parse(url).lastPathSegment?.substringBeforeLast('.')
                    ?.take(70).orEmpty().ifBlank { "Musica offline" }
                startDownload(url, title)
            }.show()
    }

    private fun startDownload(url: String, title: String) {
        try {
            offline.enqueue(url, title)
            toast("Download iniciado. Confira a notificacao e volte ao SonsPlayer.")
        } catch (error: Exception) {
            toast(error.message ?: "Nao foi possivel iniciar o download.")
        }
    }

    private fun checkOfflineDownloads(showStatus: Boolean) {
        try {
            val result = offline.reconcile(libraryStore)
            if (result.completed > 0) {
                scanLibrary()
                toast("Downloads concluidos: " + result.completed + ". Disponiveis offline!")
            } else if (result.failed > 0) {
                toast("Falharam " + result.failed + " downloads. Confira se os links oferecem audio direto.")
            } else if (showStatus) {
                toast(if (result.waiting > 0) "Downloads em andamento: " + result.waiting else "Nenhum download pendente.")
            }
        } catch (_: Exception) {
            if (showStatus) toast("Nao foi possivel consultar os downloads.")
        }
    }

    override fun onResume() {
        super.onResume()
        if (::libraryStore.isInitialized) checkOfflineDownloads(false)
    }

'''
replace_once(insert_before, new_methods + insert_before)
main_path.write_text(main, encoding="utf-8")

gradle_path = Path("app/build.gradle.kts")
gradle = gradle_path.read_text(encoding="utf-8")
if 'versionCode = 5' not in gradle:
    raise RuntimeError("Codigo da versao Samsung nao encontrado")
gradle = gradle.replace('versionCode = 5', 'versionCode = 6')
gradle = gradle.replace('versionName = "3.1.1"', 'versionName = "3.2.0"')
gradle = gradle.replace('applicationId = "com.sonsplayer.app.samsung"', 'applicationId = "com.sonsplayer.app.samsung.v32"')
gradle_path.write_text(gradle, encoding="utf-8")

manifest_path = Path("app/src/main/AndroidManifest.xml")
manifest = manifest_path.read_text(encoding="utf-8")
manifest = manifest.replace('android:label="SonsPlayer V3.1"', 'android:label="SonsPlayer V3.2"')
manifest_path.write_text(manifest, encoding="utf-8")

print("SonsPlayer V3.2 com audio HTTPS offline, player Media3, EQ e YouTube integrado preparado")
