package aurelex.android

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
        }, 1500)    }
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
                }
            }
        }
    }
}

@Composable
fun SearchScreen(viewModel: MainViewModel) {
    var query by remember { mutableStateOf("") }
    val suggestions by viewModel.suggestions.collectAsState()

    LaunchedEffect(query) {
            viewModel.suggest(query)
        }

    Column(modifier = Modifier.fillMaxSize()) {
            Text(
            text = "Aurelex",
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(16.dp)
        )
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
    var audioNotice by remember { mutableStateOf<String?>(null) }

    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(end = 8.dp),
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            TextButton(onClick = onBack) { Text("← Search") }
            TextButton(onClick = { viewModel.toggleDarkMode(article?.word) }) {
                Text(if (darkMode) "Light mode" else "Dark mode")
            }
        }
        audioNotice?.let {
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