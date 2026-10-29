from pathlib import Path

base = Path("app/src/main")
src = base / "java/com/sonsplayer/app"
src.mkdir(parents=True, exist_ok=True)

(src / "SonsAudioEffects.kt").write_text(r'''package com.sonsplayer.app

import android.content.Context
import android.content.SharedPreferences
import android.media.audiofx.Equalizer
import kotlin.math.abs
import kotlin.math.ln

/**
 * Equalizador somente da sessao de audio do Media3/ExoPlayer.
 * Nao altera o som reproduzido por WebView/YouTube.
 */
class SonsAudioEffects(context: Context) : SharedPreferences.OnSharedPreferenceChangeListener {
    private val prefs = context.getSharedPreferences("sons_equalizer", Context.MODE_PRIVATE)
    private var effect: Equalizer? = null
    private var sessionId = -1
    private val anchors = intArrayOf(60, 230, 910, 3600, 14000)

    init {
        prefs.registerOnSharedPreferenceChangeListener(this)
    }

    fun attach(newSessionId: Int) {
        if (newSessionId <= 0 || newSessionId == sessionId) return
        try {
            effect?.release()
            effect = Equalizer(0, newSessionId)
            sessionId = newSessionId
            apply()
        } catch (_: Exception) {
            effect = null
            sessionId = -1
        }
    }

    override fun onSharedPreferenceChanged(sharedPreferences: SharedPreferences, key: String?) {
        if (key == "enabled" || key?.startsWith("band_") == true) apply()
    }

    private fun apply() {
        val eq = effect ?: return
        try {
            val enabled = prefs.getBoolean("enabled", false)
            eq.enabled = enabled
            if (!enabled) return
            val range = eq.bandLevelRange
            val count = eq.numberOfBands.toInt()
            for (i in 0 until count) {
                val hz = eq.getCenterFreq(i.toShort()) / 1000.0
                val band = anchors.indices.minByOrNull {
                    abs(ln(hz.coerceAtLeast(1.0) / anchors[it]))
                } ?: 0
                val progress = prefs.getInt("band_" + band, 50).coerceIn(0, 100)
                val value = range[0].toInt() + (range[1].toInt() - range[0].toInt()) * progress / 100
                eq.setBandLevel(i.toShort(), value.toShort())
            }
        } catch (_: Exception) {
            // Alguns fabricantes nao oferecem equalizador de hardware.
        }
    }

    fun close() {
        prefs.unregisterOnSharedPreferenceChangeListener(this)
        effect?.release()
        effect = null
        sessionId = -1
    }
}
''', encoding="utf-8")

(src / "EqualizerActivity.kt").write_text(r'''package com.sonsplayer.app

import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat

class EqualizerActivity : AppCompatActivity() {
    private val accent = Color.rgb(155, 128, 255)
    private val white = Color.rgb(246, 244, 255)
    private val muted = Color.rgb(166, 162, 185)
    private val names = arrayOf("60 Hz · Subgrave", "230 Hz · Graves", "910 Hz · Medios", "3,6 kHz · Presenca", "14 kHz · Brilho")
    private val bars = mutableListOf<SeekBar>()
    private val values = mutableListOf<TextView>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("sons_equalizer", Context.MODE_PRIVATE)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 20, 20, 24)
            setBackgroundColor(Color.rgb(10, 11, 18))
        }
        val scroll = ScrollView(this).apply { fillViewport = true }
        scroll.addView(root)
        setContentView(scroll)

        fun text(value: String, size: Float, color: Int = white): TextView =
            TextView(this).apply {
                this.text = value
                textSize = size
                setTextColor(color)
                setPadding(4, 10, 4, 10)
            }

        val back = text("‹  Voltar ao SonsPlayer", 16f, accent)
        back.setOnClickListener { finish() }
        root.addView(back)
        root.addView(text("EQUALIZADOR", 27f))
        root.addView(text("Ajuste o som das musicas da sua biblioteca.", 14f, muted))

        val toggle = SwitchCompat(this).apply {
            this.text = "Ativar equalizador"
            setTextColor(white)
            thumbTintList = android.content.res.ColorStateList.valueOf(accent)
            isChecked = prefs.getBoolean("enabled", false)
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putBoolean("enabled", checked).apply()
            }
        }
        root.addView(toggle)

        for (i in names.indices) {
            val heading = text(names[i], 14f, white)
            root.addView(heading)
            val valueText = text("", 13f, accent).apply {
                gravity = Gravity.END
            }
            values.add(valueText)
            val bar = SeekBar(this).apply {
                max = 100
                progress = prefs.getInt("band_" + i, 50)
                progressTintList = android.content.res.ColorStateList.valueOf(accent)
                thumbTintList = android.content.res.ColorStateList.valueOf(accent)
                setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                    override fun onProgressChanged(seekBar: SeekBar, progress: Int, fromUser: Boolean) {
                        valueText.text = (progress - 50).toString() + " / 50"
                        if (fromUser) prefs.edit().putInt("band_" + i, progress).apply()
                    }
                    override fun onStartTrackingTouch(seekBar: SeekBar) = Unit
                    override fun onStopTrackingTouch(seekBar: SeekBar) = Unit
                })
            }
            bars.add(bar)
            root.addView(bar, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 45.dp))
            root.addView(valueText)
            valueText.text = (bar.progress - 50).toString() + " / 50"
        }

        root.addView(text("PERFIS DE SOM", 16f, accent))
        val presets = linkedMapOf(
            "Padrao" to intArrayOf(50, 50, 50, 50, 50),
            "Graves" to intArrayOf(85, 80, 55, 45, 50),
            "Rock" to intArrayOf(78, 65, 46, 70, 78),
            "Voz" to intArrayOf(45, 45, 70, 80, 62),
            "Brilho" to intArrayOf(50, 46, 50, 74, 90)
        )
        presets.forEach { (name, levels) ->
            val button = text("▶  " + name, 16f)
            button.setOnClickListener {
                val editor = prefs.edit()
                levels.forEachIndexed { index, amount ->
                    editor.putInt("band_" + index, amount)
                    bars[index].progress = amount
                }
                editor.putBoolean("enabled", true).apply()
                toggle.isChecked = true
            }
            root.addView(button)
        }
        root.addView(text("O equalizador atua apenas nas musicas reproduzidas pelo SonsPlayer, nao no audio de videos YouTube.", 12f, muted))
    }

    private val Int.dp: Int get() = (this * resources.displayMetrics.density).toInt()
}
''', encoding="utf-8")

(src / "YouTubeBrowserActivity.kt").write_text(r'''package com.sonsplayer.app

import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import java.net.URLEncoder

/** Pesquisa e assiste no player de video do proprio YouTube, sem chave da Data API. */
class YouTubeBrowserActivity : AppCompatActivity() {
    private lateinit var browser: WebView
    private val youtube = "https://m.youtube.com/"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(10, 11, 18))
        }
        val top = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(14, 12, 14, 12)
        }
        fun button(value: String, action: () -> Unit) = TextView(this).apply {
            text = value
            textSize = 15f
            setTextColor(Color.WHITE)
            setPadding(12, 14, 12, 14)
            setOnClickListener { action() }
        }
        top.addView(button("‹ Voltar") { if (browser.canGoBack()) browser.goBack() else finish() })
        top.addView(button("Inicio") { browser.loadUrl(youtube) })
        top.addView(button("YouTube ↗") {
            val url = browser.url?.takeIf { it.startsWith("https://") } ?: youtube
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        })
        root.addView(top)
        val searchRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(14, 6, 14, 10)
        }
        val input = EditText(this).apply {
            hint = "Pesquisar musicas e artistas"
            setHintTextColor(Color.LTGRAY)
            setTextColor(Color.WHITE)
            textSize = 15f
            isSingleLine = true
            imeOptions = EditorInfo.IME_ACTION_SEARCH
        }
        fun search() {
            val q = input.text.toString().trim()
            if (q.isNotEmpty()) {
                browser.loadUrl(youtube + "results?search_query=" + URLEncoder.encode(q, "UTF-8"))
                (getSystemService(INPUT_METHOD_SERVICE) as? android.view.inputmethod.InputMethodManager)
                    ?.hideSoftInputFromWindow(input.windowToken, 0)
            }
        }
        input.setOnEditorActionListener { _, _, _ -> search(); true }
        searchRow.addView(input, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        searchRow.addView(button("Buscar") { search() })
        root.addView(searchRow)
        val info = TextView(this).apply {
            text = "Videos com tela visivel • Login e recursos Premium no app oficial."
            textSize = 12f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER
            setPadding(8, 3, 8, 12)
        }
        root.addView(info)
        browser = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = true
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    val uri = request.url
                    if (uri.scheme != "https" && uri.scheme != "http") return true
                    val host = uri.host.orEmpty().lowercase()
                    if (host == "youtube.com" || host.endsWith(".youtube.com") || host == "youtu.be") return false
                    startActivity(Intent(Intent.ACTION_VIEW, uri))
                    return true
                }
            }
        }
        root.addView(browser, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(root)
        browser.loadUrl(youtube)
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (browser.canGoBack()) browser.goBack() else finish()
            }
        })
    }

    override fun onStop() {
        if (::browser.isInitialized) browser.onPause()
        super.onStop()
    }
    override fun onStart() {
        super.onStart()
        if (::browser.isInitialized) browser.onResume()
    }
    override fun onDestroy() {
        if (::browser.isInitialized) {
            browser.stopLoading()
            browser.destroy()
        }
        super.onDestroy()
    }
}
''', encoding="utf-8")

manifest = base / "AndroidManifest.xml"
xml = manifest.read_text(encoding="utf-8")
xml = xml.replace('<uses-permission android:name="android.permission.WAKE_LOCK" />',
                  '<uses-permission android:name="android.permission.WAKE_LOCK" />\n    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />')
xml = xml.replace('<activity\n            android:name=".YouTubePlaylistActivity"',
                  '<activity android:name=".YouTubeBrowserActivity" android:exported="false" />\n        <activity android:name=".EqualizerActivity" android:exported="false" />\n        <activity\n            android:name=".YouTubePlaylistActivity"')
manifest.write_text(xml, encoding="utf-8")

main = src / "MainActivity.kt"
s = main.read_text(encoding="utf-8")
s = s.replace('Intent(this, YouTubePlaylistActivity::class.java)', 'Intent(this, YouTubeBrowserActivity::class.java)')
needle = '        newPlaylist.setOnClickListener {'
replacement = '''        findViewById<View>(R.id.btnEqualizer).setOnClickListener {
            startActivity(Intent(this, EqualizerActivity::class.java))
        }
''' + needle
assert needle in s
s = s.replace(needle, replacement, 1)
main.write_text(s, encoding="utf-8")

layout = base / "res/layout/activity_main.xml"
s = layout.read_text(encoding="utf-8")
needle = 'android:contentDescription="Abrir playlists do YouTube"/>'
assert needle in s
s = s.replace(needle, '''android:contentDescription="Pesquisar e assistir YouTube"/>
        <TextView android:id="@+id/btnEqualizer" android:layout_width="wrap_content" android:layout_height="48dp"
            android:layout_marginStart="8dp" android:gravity="center" android:paddingHorizontal="12dp"
            android:background="@drawable/bg_track" android:text="EQ ♪"
            android:textColor="@color/accent" android:textSize="14sp"
            android:contentDescription="Abrir equalizador de cinco bandas"/>''', 1)
layout.write_text(s, encoding="utf-8")

service = src / "MusicPlaybackService.kt"
s = service.read_text(encoding="utf-8")
s = s.replace('import androidx.media3.common.C',
'''import androidx.media3.common.C
import androidx.media3.common.Player
import androidx.annotation.OptIn
import androidx.media3.common.util.UnstableApi''')
s = s.replace('    private var session: MediaSession? = null',
'''    private var session: MediaSession? = null
    private var effects: SonsAudioEffects? = null''')
needle = '        session = MediaSession.Builder(this, player).build()'
assert needle in s
s = s.replace(needle, '''        effects = SonsAudioEffects(this)
        player.addListener(object : Player.Listener {
            @OptIn(UnstableApi::class)
            override fun onAudioSessionIdChanged(audioSessionId: Int) {
                effects?.attach(audioSessionId)
            }
        })
''' + needle, 1)
s = s.replace('    override fun onDestroy() {\n        session?.let',
'''    override fun onDestroy() {
        effects?.close()
        effects = null
        session?.let''')
service.write_text(s, encoding="utf-8")

gradle = Path("app/build.gradle.kts")
s = gradle.read_text(encoding="utf-8")
s = s.replace('versionCode = 3', 'versionCode = 4').replace('versionName = "3.0.0"', 'versionName = "3.1.0"')
gradle.write_text(s, encoding="utf-8")
print("SonsPlayer V3.1: YouTube integrado + equalizador aplicados")
