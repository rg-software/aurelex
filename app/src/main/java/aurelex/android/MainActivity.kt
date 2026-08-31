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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
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

    /** Routes an incoming share/VIEW intent into a lookup (task 1.1). */
    private fun handleLookupIntent(intent: Intent?) {
        if (intent == null) return
        val word = when (intent.action) {
            Intent.ACTION_SEND -> {
                (intent.getStringExtra(Intent.EXTRA_TEXT) ?: intent.getStringExtra(Intent.EXTRA_SUBJECT))?.trim()
            }
            Intent.ACTION_VIEW -> {
                // aurelex://lookup?word=<word> or /lookup/<word>
                intent.data?.let { uri ->
                    uri.getQueryParameter("word")
                        ?: uri.path?.trimStart('/')?.trim()
                } ?: ""
            }
            else -> return
        }
        if (word?.isNotBlank() == true) {
            mainViewModel.lookup(word)
        }
    }
}

@Composable
fun AurelexApp(viewModel: MainViewModel) {
    val backStack by viewModel.backStack.collectAsState()
    val darkMode by viewModel.darkMode.collectAsState()
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
                }
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

    LaunchedEffect(query) {
            viewModel.suggest(query)
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
                .padding(horizontal = 16.dp),
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
            modifier = Modifier.padding(horizontal = 16.dp),
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
        }

        LazyColumn(modifier = Modifier.fillMaxSize()) {
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
    var editing by remember { mutableStateOf<Int?>(null) }
    val g = editing
    if (g == null) {
        GroupsList(viewModel, onBack = onBack, onEdit = { editing = it })
    } else {
        GroupDetailScreen(viewModel, groupId = g, onBack = { editing = null })
    }
}

@Composable
private fun GroupsList(viewModel: MainViewModel, onBack: () -> Unit, onEdit: (Int) -> Unit) {
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
                    TextButton(onClick = { onEdit(grp.id) }) { Text("Edit") }
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
    var members by remember(groupId) { mutableStateOf<List<Int>?>(null) }
    LaunchedEffect(groupId) {
        members = try { viewModel.groupDicts(groupId).get() } catch (e: Exception) { emptyList() }
    }
    val memberSet = (members ?: emptyList()).toSet()

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
                            val m = members ?: emptyList()
                            members = if (on) (m + idx).distinct() else m.filter { it != idx }
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
                    }
                }
            }
        }
    }
}