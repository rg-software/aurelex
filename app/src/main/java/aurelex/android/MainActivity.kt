package aurelex.android

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.activity.viewModels

class MainActivity : ComponentActivity() {
    private val mainViewModel: MainViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        mainViewModel.loadPreferences(PreferencesStore(applicationContext))
        setContent {
            AurelexApp(mainViewModel)
        }
        // Re-scan the previously staged dictionaries after an engine-process
        // restart so lookups work without re-picking the folder.
        AurelexApp.onEngineDied = { ctx ->
            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                mainViewModel.resumeScan(ctx)
            }, 1500)
        }
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            mainViewModel.resumeScan(applicationContext)
        }, 1500)
        // Handle an intent that launched the activity directly (cold start).
        handleLookupIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleLookupIntent(intent)
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        // A clipboard read requires the window to have input focus, so a
        // clipboard lookup received while the activity is still gaining focus
        // is deferred until focus is granted (design D1).
        if (hasFocus && clipboardLookupPending) {
            clipboardLookupPending = false
            performClipboardLookup(0)
        }
    }

    @Volatile
    private var clipboardLookupPending = false

    /**
     * Routes an incoming external intent into a lookup. Share/VIEW keep their
     * existing behavior; the launcher shortcuts (Quick Settings tile and
     * home-screen widget) land here via the QuickLookup actions. Every branch
     * funnels non-blank text into [MainViewModel.lookup] so the article /
     * not-found / active-group / history handling is reused (tasks 4.1-4.3),
     * and blank text opens the search screen.
     */
    private fun handleLookupIntent(intent: Intent?) {
        if (intent == null) return
        when (intent.action) {
            Intent.ACTION_SEND -> {
                val word = (intent.getStringExtra(Intent.EXTRA_TEXT)
                    ?: intent.getStringExtra(Intent.EXTRA_SUBJECT))?.trim()
                if (word?.isNotBlank() == true) mainViewModel.lookup(word)
            }
            Intent.ACTION_VIEW -> {
                // aurelex://lookup?word=<word> or /lookup/<word>
                val word = intent.data?.let { uri ->
                    uri.getQueryParameter("word")
                        ?: uri.path?.trimStart('/')?.trim()
                } ?: ""
                if (word.isNotBlank()) mainViewModel.lookup(word)
            }
            Intent.ACTION_PROCESS_TEXT -> {
                // "Look up in Aurelex" on selected text (long-press selection
                // toolbar in other apps).
                val word = intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)
                    ?.toString()?.trim()
                if (word?.isNotBlank() == true) mainViewModel.lookup(word)
            }
            QuickLookup.ACTION_LOOKUP_CLIPBOARD -> {
                // The clipboard is only readable while the window has input
                // focus, so if it hasn't yet, defer until onWindowFocusChanged
                // fires (design D1).
                if (hasWindowFocus()) performClipboardLookup(0)
                else clipboardLookupPending = true
            }
            QuickLookup.ACTION_SEARCH -> {
                // Field text lands in EXTRA_TEXT on launchers that deliver it;
                // blank means "open the search screen with focus" (design D2).
                val word = intent.getStringExtra(QuickLookup.EXTRA_TEXT)?.trim()
                if (word.isNullOrBlank()) mainViewModel.openSearch()
                else mainViewModel.lookup(word)
                refreshWidget()
            }
        }
    }

    /** Reads the clipboard and routes it to a lookup or the search screen. */
    private fun performClipboardLookup(attempt: Int) {
        val clip = mainViewModel.clipboardText(applicationContext)?.trim()
        when {
            !clip.isNullOrBlank() -> mainViewModel.lookup(clip)
            attempt == 0 -> {
                // The clipboard may only become readable once the window is fully
                // focused; retry once shortly after before giving up.
                android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                    performClipboardLookup(1)
                }, 250L)
            }
            else -> mainViewModel.openSearch()
        }
    }

    /** Re-wires the widget's RemoteViews after a submit handled it (task 3.2). */
    private fun refreshWidget() {
        sendBroadcast(Intent(this, AurelexSearchWidget::class.java).apply {
            action = QuickLookup.ACTION_REFRESH_WIDGET
        })
    }
}

@Composable
fun AurelexApp(viewModel: MainViewModel) {
    val backStack by viewModel.backStack.collectAsState()
    val darkMode by viewModel.darkMode.collectAsState()
    val onboarded by viewModel.onboarded.collectAsState()
    val current = backStack.lastOrNull() ?: Dest.SEARCH

    BackHandler(enabled = backStack.size > 1) { viewModel.pop() }

    AurelexTheme(darkTheme = darkMode) {
        Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
            Column(modifier = Modifier.padding(innerPadding)) {
                when (current) {
                    Dest.SEARCH -> SearchScreen(viewModel)
                    Dest.ARTICLE -> ArticleScreen(viewModel, onBack = { viewModel.pop() })
                    Dest.DICTIONARIES -> DictionariesScreen(viewModel, onBack = { viewModel.pop() })
                    Dest.HISTORY -> HistoryScreen(viewModel, onBack = { viewModel.pop() })
                    Dest.FAVORITES -> FavoritesScreen(viewModel, onBack = { viewModel.pop() })
                    Dest.GROUPS -> GroupsScreen(viewModel, onBack = { viewModel.pop() })
                    Dest.GROUP_DETAIL -> GroupDetailScreen(viewModel, groupId = viewModel.detailGroupId, onBack = { viewModel.pop() })
                    Dest.FTS -> FtsScreen(viewModel, onBack = { viewModel.pop() })
                }
            }
        }
    }

    // First-run onboarding overlays everything until dismissed (design D5).
    if (!onboarded) {
        OnboardingScreen(onDone = { viewModel.markOnboarded() })
    }
}

@Composable
fun OnboardingScreen(onDone: () -> Unit) {
    androidx.compose.material3.Surface(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                text = "Welcome to Aurelex",
                style = MaterialTheme.typography.headlineMedium
            )
            Text(
                text = "Your offline dictionary. Add dictionary files (mdict, DSL, StarDict) from any folder, then look words up — including full-text search inside article bodies.",
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(top = 12.dp)
            )
            Text(
                text = "1.  Dictionaries → Add dictionaries… and pick a folder.",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 16.dp)
            )
            Text(
                text = "2.  Type a word on the search screen, or use Full text to search inside articles.",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 6.dp)
            )
            Button(
                onClick = onDone,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 28.dp)
            ) {
                Text("Get started")
            }
        }
    }
}

@Composable
fun SearchScreen(viewModel: MainViewModel) {
    var query by remember { mutableStateOf("") }
    val suggestions by viewModel.suggestions.collectAsState()
    val groups by viewModel.groups.collectAsState()
    val activeGroup by viewModel.activeGroupId.collectAsState()
    val context = LocalContext.current
    val activeName = groups.firstOrNull { it.id == activeGroup }?.name ?: "All"
    val focusRequest by viewModel.searchFocusRequest.collectAsState()
    val focusRequester = remember { FocusRequester() }
    val dictCount by viewModel.dictCount.collectAsState()

    LaunchedEffect(query) {
            viewModel.suggest(query)
        }

    // Request keyboard focus when the launcher shortcuts drop the user here
    // without a word to look up (spec "Widget opens search screen").
    LaunchedEffect(focusRequest) {
        if (focusRequest > 0) focusRequester.requestFocus()
    }

    Column(modifier = Modifier.fillMaxSize()) {
            Text(
            text = "Aurelex",
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(16.dp)
        )
            TextButton(onClick = { viewModel.push(Dest.GROUPS) }) {
                Text("Group: $activeName")
            }
            TextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .focusRequester(focusRequester),
            placeholder = { Text("Search dictionaries") },
            singleLine = true
        )
        Row(
            modifier = Modifier.padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            TextButton(onClick = {
                if (query.isNotBlank()) viewModel.lookup(query)
            }) { Text("Look up") }
            TextButton(onClick = { viewModel.push(Dest.DICTIONARIES) }) { Text("Dictionaries") }
        }
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            TextButton(onClick = { viewModel.push(Dest.HISTORY) }) { Text("History") }
            TextButton(onClick = { viewModel.push(Dest.FAVORITES) }) { Text("Favorites") }
            // Task 1.2: clipboard lookup
            TextButton(onClick = {
                val cm = viewModel.clipboardText(context.applicationContext)
                if (cm != null && cm.isNotBlank()) viewModel.lookup(cm)
            }) { Text("Clipboard") }
            TextButton(onClick = { viewModel.push(Dest.GROUPS) }) { Text("Groups") }
            TextButton(onClick = { viewModel.push(Dest.FTS) }) { Text("Full text") }
        }

        LazyColumn(modifier = Modifier.fillMaxSize()) {
            if (dictCount == 0 && suggestions.isEmpty()) {
                item {
                    // Empty state (spec "First-run onboarding"/"Empty search state"):
                    // with no dictionaries there is nothing to search.
                    Column(modifier = Modifier.padding(24.dp)) {
                        Text(
                            text = "No dictionaries yet",
                            style = MaterialTheme.typography.titleMedium
                        )
                        Text(
                            text = "Add a folder of dictionary files (mdict, DSL, StarDict) to start searching.",
                            modifier = Modifier.padding(top = 8.dp)
                        )
                        TextButton(onClick = { viewModel.push(Dest.DICTIONARIES) }) {
                            Text("Add dictionaries…")
                        }
                    }
                }
            }
            items(suggestions) { w ->
                TextButton(onClick = { viewModel.lookup(w) }) {
                    Text(w)
                }
            }
        }
        }
}

@Composable
fun ArticleScreen(viewModel: MainViewModel, onBack: () -> Unit) {
    val article by viewModel.article.collectAsState()
    val darkMode by viewModel.darkMode.collectAsState()
    val ttsEnabled by viewModel.ttsEnabled.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    var audioNotice by remember { mutableStateOf<String?>(null) }
    var ttsNotice by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val ttsHelper = remember { TtsHelper(context, onUnavailable = { ttsNotice = it }) }
    DisposableEffect(Unit) {
        onDispose { ttsHelper.shutdown() }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(end = 8.dp),
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            TextButton(onClick = onBack) { Text("← Search") }
            Row {
                // Task 3.3: save/remove favorite reflecting current state
                article?.word?.let { word ->
                    val fav = favorites.contains(word)
                    TextButton(onClick = { viewModel.toggleFavorite(word) }) {
                        Text(if (fav) "★" else "☆")
                    }
                    // Task 4.2: pronounce gated by TTS toggle
                    if (ttsEnabled) {
                        TextButton(onClick = { ttsHelper.speak(word) }) { Text("🔊") }
                    }
                }
                TextButton(onClick = { viewModel.toggleDarkMode(article?.word) }) {
                    Text(if (darkMode) "Light mode" else "Dark mode")
                }
            }
        }
        audioNotice?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 16.dp)
            )
        }
        ttsNotice?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 16.dp)
            )
        }
        val a = article
        Box(modifier = Modifier.fillMaxSize()) {
            if (a == null) {
                // Task 5.7: not-found UX — explain and offer a way back to search.
                Column(modifier = Modifier.padding(24.dp)) {
                    Text(
                        text = "Word not found",
                        style = MaterialTheme.typography.titleLarge
                    )
                    Text(
                        text = "No dictionary contains that headword. Check the spelling, or try the Suggestions in Search.",
                        modifier = Modifier.padding(top = 8.dp)
                    )
                    TextButton(onClick = onBack) { Text("Back to search") }
                }
            } else {
                ArticleView(
                    word = a.word,
                    html = a.html,
                    onLookup = { word -> viewModel.lookup(word) },
                    onAudioResult = { audioNotice = it },
                    modifier = Modifier.fillMaxSize()
                )
            }
        }
    }
}

@Composable
fun HistoryScreen(viewModel: MainViewModel, onBack: () -> Unit) {
    val history by viewModel.history.collectAsState()
    Column(modifier = Modifier.fillMaxSize()) {
        TextButton(onClick = onBack) { Text("← Back") }
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("History", style = MaterialTheme.typography.titleMedium)
            if (history.isNotEmpty()) {
                TextButton(onClick = { viewModel.clearHistory() }) { Text("Clear") }
            }
        }
        if (history.isEmpty()) {
            Text("No lookups yet.", modifier = Modifier.padding(16.dp))
        }
        LazyColumn(modifier = Modifier.fillMaxSize()) {
            items(history) { word ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    TextButton(onClick = { viewModel.lookup(word) }) { Text(word) }
                    TextButton(onClick = { viewModel.removeHistory(word) }) { Text("✕") }
                }
            }
        }
    }
}

@Composable
fun FavoritesScreen(viewModel: MainViewModel, onBack: () -> Unit) {
    val favorites by viewModel.favorites.collectAsState()
    Column(modifier = Modifier.fillMaxSize()) {
        TextButton(onClick = onBack) { Text("← Back") }
        Text("Favorites", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(16.dp))
        if (favorites.isEmpty()) {
            Text("No favorites yet.", modifier = Modifier.padding(16.dp))
        }
        LazyColumn(modifier = Modifier.fillMaxSize()) {
            items(favorites) { word ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    TextButton(onClick = { viewModel.lookup(word) }) { Text(word) }
                    TextButton(onClick = { viewModel.removeFavorite(word) }) { Text("✕") }
                }
            }
        }
    }
}

@Composable
fun GroupsScreen(viewModel: MainViewModel, onBack: () -> Unit) {
    val groups by viewModel.groups.collectAsState()
    val active by viewModel.activeGroupId.collectAsState()
    var showCreate by remember { mutableStateOf(false) }

    Column(modifier = Modifier.fillMaxSize()) {
        TextButton(onClick = onBack) { Text("← Back") }
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("Groups", style = MaterialTheme.typography.titleMedium)
            TextButton(onClick = { showCreate = true }) { Text("+ New") }
        }
        if (groups.isEmpty()) {
            Text("No groups yet. 'All' is the default.", modifier = Modifier.padding(16.dp))
        }
        LazyColumn(modifier = Modifier.fillMaxSize()) {
            items(groups) { grp ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        TextButton(onClick = { viewModel.applyActiveGroup(grp.id) }) {
                            Text(if (active == grp.id) "● ${grp.name} (${grp.dictCount})" else "${grp.name} (${grp.dictCount})")
                        }
                    }
                    TextButton(onClick = {
                        viewModel.detailGroupId = grp.id
                        viewModel.push(Dest.GROUP_DETAIL)
                    }) { Text("Edit") }
                    if (grp.id != 0) {
                        TextButton(onClick = { viewModel.deleteGroup(grp.id) }) { Text("✕") }
                    }
                }
            }
        }
    }
    if (showCreate) {
        var newName by remember { mutableStateOf("") }
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { showCreate = false },
            title = { Text("New group") },
            text = { TextField(value = newName, onValueChange = { newName = it }, placeholder = { Text("Name") }) },
            confirmButton = {
                TextButton(onClick = {
                    if (newName.isNotBlank()) viewModel.createGroup(newName.trim())
                    showCreate = false
                }) { Text("Create") }
            },
            dismissButton = { TextButton(onClick = { showCreate = false }) { Text("Cancel") } }
        )
    }
}

@Composable
fun GroupDetailScreen(viewModel: MainViewModel, groupId: Int, onBack: () -> Unit) {
    val dictionaries by viewModel.dictionaries.collectAsState()
    val memberships by viewModel.groupMembers.collectAsState()
    val members = memberships[groupId] ?: emptyList()
    LaunchedEffect(groupId) {
        if (!memberships.containsKey(groupId)) viewModel.loadGroupMembers(groupId)
    }
    val memberSet = members.toSet()

    Column(modifier = Modifier.fillMaxSize()) {
        TextButton(onClick = onBack) { Text("← Back") }
        Text("Membership", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(16.dp))
        if (dictionaries.isEmpty()) {
            Text("No dictionaries loaded.", modifier = Modifier.padding(16.dp))
        }
        LazyColumn(modifier = Modifier.fillMaxSize()) {
            items(dictionaries) { entry ->
                val idx = dictionaries.indexOf(entry)
                val checked = memberSet.contains(idx)
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically
                ) {
                    androidx.compose.material3.Checkbox(
                        checked = checked,
                        onCheckedChange = { on ->
                            if (on) viewModel.groupAddDict(groupId, idx)
                            else viewModel.groupRemoveDict(groupId, idx)
                            val m = members
                            viewModel.setGroupMembers(groupId, if (on) (m + idx).distinct() else m.filter { it != idx })
                        }
                    )
                    Text(entry.name, modifier = Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
fun DictionariesScreen(viewModel: MainViewModel, onBack: () -> Unit) {
    val dictCount by viewModel.dictCount.collectAsState()
    val dictionaries by viewModel.dictionaries.collectAsState()
    val isIndexing by viewModel.isIndexing.collectAsState()
    val indexMessage by viewModel.indexMessage.collectAsState()
    val context = LocalContext.current
    var message by remember { mutableStateOf<String?>(null) }
    var pendingRemove by remember { mutableStateOf<Int?>(null) }
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocumentTree()
    ) { uri: Uri? ->
        if (uri != null) {
            viewModel.pickAndScan(context, uri) { n ->
                message = if (n <= 0) {
                    "No supported dictionaries found (mdx/mdd, dsl/dz, ifo)."
                } else {
                    "$n dictionary(ies) loaded."
                }
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        TextButton(onClick = onBack) { Text("← Back") }
        Text(
            text = "Dictionaries ($dictCount loaded)",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(16.dp)
        )
        Button(
            onClick = { launcher.launch(null) },
            modifier = Modifier.padding(horizontal = 16.dp),
            enabled = !isIndexing
        ) {
            Text(if (isIndexing) "Scanning…" else "Add dictionaries…")
        }
        if (isIndexing) {
            androidx.compose.material3.LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        }
        indexMessage?.let {
            Text(text = it, modifier = Modifier.padding(16.dp))
        }
        message?.let {
            Text(text = it, modifier = Modifier.padding(16.dp))
        }

        LazyColumn(modifier = Modifier.fillMaxSize()) {
            itemsIndexed(dictionaries) { index, entry ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 4.dp),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(entry.name, style = MaterialTheme.typography.bodyLarge)
                        Text(
                            text = entry.file,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    Row {
                        TextButton(
                            onClick = { viewModel.moveDict(index, index - 1) },
                            enabled = index > 0
                        ) { Text("↑") }
                        TextButton(
                            onClick = { viewModel.moveDict(index, index + 1) },
                            enabled = index < dictionaries.lastIndex
                        ) { Text("↓") }
                        TextButton(onClick = { pendingRemove = index }) { Text("Remove") }
                    }
                }
            }
        }
    }

    // Confirmation before the destructive removal (design D4 / spec).
    val toRemove = pendingRemove
    if (toRemove != null) {
        val entry = dictionaries.getOrNull(toRemove)
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { pendingRemove = null },
            title = { Text("Remove dictionary") },
            text = { Text("Remove \"${entry?.name ?: "dictionary"}\" from the loaded set? This does not delete the files.") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.removeDict(toRemove)
                    pendingRemove = null
                }) { Text("Remove") }
            },
            dismissButton = {
                TextButton(onClick = { pendingRemove = null }) { Text("Cancel") }
            }
        )
    }
}

@Composable
fun FtsScreen(viewModel: MainViewModel, onBack: () -> Unit) {
    val queryState by viewModel.ftsQuery.collectAsState()
    val results by viewModel.ftsResults.collectAsState()
    val dictionaries by viewModel.dictionaries.collectAsState()
    val indexStates by viewModel.ftsIndexStates.collectAsState()
    val building by viewModel.ftsBuilding.collectAsState()
    val activeGroup by viewModel.activeGroupId.collectAsState()
    val groups by viewModel.groups.collectAsState()
    val activeName = groups.firstOrNull { it.id == activeGroup }?.name ?: "All"

    LaunchedEffect(Unit) {
        if (indexStates.isEmpty()) viewModel.refreshFtsStates()
    }

    Column(modifier = Modifier.fillMaxSize()) {
        TextButton(onClick = onBack) { Text("← Back") }
        Text(
            text = "Full-text search ($activeName)",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(16.dp)
        )
        TextField(
            value = queryState,
            onValueChange = { viewModel.setFtsQuery(it) },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            placeholder = { Text("Search article bodies… (ends with *)") },
            singleLine = true
        )
        Row(
            modifier = Modifier.padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Button(
                onClick = { viewModel.ftsSearch(queryState) },
                enabled = queryState.isNotBlank()
            ) { Text("Search") }
        }
        Text(
            text = "Tip: append * to match word prefixes, e.g. read*",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(horizontal = 16.dp)
        )

        // Per-dictionary index state (spec: built / building / missing).
        LazyColumn(modifier = Modifier.weight(1f)) {
            item {
                Text(
                    text = "Indexes",
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                )
            }
            itemsIndexed(dictionaries) { index, entry ->
                val state = indexStates[index]
                val label = when {
                    building.contains(index) -> "building…"
                    state == 0 -> "built"
                    state == 1 -> "missing"
                    state == null -> ""
                    else -> "not supported"
                }
                val showBuild = state == 1 && !building.contains(index)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 2.dp),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(entry.name, style = MaterialTheme.typography.bodyLarge)
                        Text(label, style = MaterialTheme.typography.bodySmall)
                    }
                    if (showBuild) {
                        TextButton(onClick = { viewModel.ftsIndex(index) }) { Text("Build") }
                    }
                }
            }
        }

        // Results → reuse the normal article flow (spec "Results lead to
        // articles": a tap runs the standard active-group lookup).
        Text(
            text = "Results (${results.size})",
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
        )
        LazyColumn(modifier = Modifier.weight(1f)) {
            if (results.isEmpty()) {
                item { Text("No results.", modifier = Modifier.padding(16.dp)) }
            }
            items(results) { r ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically
                ) {
                    TextButton(onClick = { viewModel.lookup(r.headword) }) {
                        Text(r.headword)
                    }
                    Text(
                        text = r.dictName,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }
    }
}