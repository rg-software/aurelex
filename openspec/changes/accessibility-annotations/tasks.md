## 1. Navigation — Bottom TabBar

- [x] 1.1 Add `Accessible.name` and `Accessible.role` to `navBar` (TabBar) — name: "Main navigation", role: `Accessible.TabBar`
- [x] 1.2 Add `Accessible.name` and `Accessible.role` to `tabBtn` (TabButton delegate) — role: `Accessible.TabButton`, name bound to `modelData.label` for each tab (Search, Dictionaries, Groups, Full-text search, History, Favorites)

## 2. Top Bar — ToolBar

- [x] 2.1 Add `Accessible.name` and `Accessible.role` to `topBar` (ToolBar) — name: "Top toolbar", role: `Accessible.ToolBar`
- [x] 2.2 Add `Accessible.name` and `Accessible.role` to dark-mode toggle ToolButton — role: `Accessible.Button`, name bound dynamically: `engine.userDarkOverride || engine.systemDark ? "Light mode" : "Dark mode"`

## 3. Search Pane

- [x] 3.1 Add `Accessible.name` and `Accessible.role` to `searchGroupCombo` (ComboBox) — name: "Search group scope", role: `Accessible.ComboBox`
- [x] 3.2 Add `Accessible.name` and `Accessible.role` to `input` (TextField) — name: "Search dictionaries", role: `Accessible.EditableText`
- [x] 3.3 Add `Accessible.name` and `Accessible.role` to clipboard Button — name: "Clipboard", role: `Accessible.Button`
- [x] 3.4 Add `Accessible.name` and `Accessible.role` to `suggestionList` (ListView) — name: "Search suggestions", role: `Accessible.List`
- [x] 3.5 Add `Accessible.role` to suggestion ItemDelegate — name bound to `modelData`, role: `Accessible.ListItem`

## 4. Dictionaries Pane

- [x] 4.1 Add `Accessible.name` and `Accessible.role` to "Add dictionaries" RoundButton — name: "Add dictionaries", role: `Accessible.Button`
- [x] 4.2 Add `Accessible.name` and `Accessible.role` to "By Pair" toggle Button — name: "By Pair", role: `Accessible.Button`
- [x] 4.3 Add `Accessible.name` and `Accessible.role` to "Remove" Button — name: "Remove", role: `Accessible.Button`
- [x] 4.4 Add `Accessible.name` and `Accessible.role` to `dictsList` (flat ListView) — name: "Dictionaries list", role: `Accessible.List`
- [x] 4.5 Add `Accessible.role` to flat `dictRow` ItemDelegate — name bound to `dictData.name`, role: `Accessible.ListItem`
- [x] 4.6 Add `Accessible.name` and `Accessible.role` to remove ToolButton in `dictRow` — name: "Remove", role: `Accessible.Button`
- [x] 4.7 Add `Accessible.name` and `Accessible.role` to `dictsListByPair` (grouped ListView) — name: "Dictionaries list by pair", role: `Accessible.List`
- [x] 4.8 Add `Accessible.role` to grouped header `bpRow` ItemDelegate — name bound to `modelData.pair`, role: `Accessible.ListItem`
- [x] 4.9 Add `Accessible.name` and `Accessible.role` to remove-pair ToolButton — name: "Remove pair", role: `Accessible.Button`
- [x] 4.10 Add `Accessible.role` to grouped dict `bpRow` ItemDelegate — name bound to `modelData.item.name`, role: `Accessible.ListItem`
- [x] 4.11 Add `Accessible.name` and `Accessible.role` to remove ToolButton in grouped dict row — name: "Remove", role: `Accessible.Button`
- [x] 4.12 Add `Accessible.name` and `Accessible.role` to `removeDialog` (Dialog) — name: "Remove dictionary confirmation", role: `Accessible.Dialog`

## 5. Groups Pane — List Mode

- [x] 5.1 Add `Accessible.name` and `Accessible.role` to `newGroupInput` (TextField) — name: "New group name", role: `Accessible.EditableText`
- [x] 5.2 Add `Accessible.name` and `Accessible.role` to "Create" Button — name: "Create", role: `Accessible.Button`
- [x] 5.3 Add `Accessible.name` and `Accessible.role` to `groupsList` (ListView) — name: "Groups list", role: `Accessible.List`
- [x] 5.4 Add `Accessible.role` to `groupRow` ItemDelegate — name bound to `groupData.name`, role: `Accessible.ListItem`
- [x] 5.5 Add `Accessible.name` and `Accessible.role` to edit-group ToolButton — name: "Edit group dictionaries", role: `Accessible.Button`
- [x] 5.6 Add `Accessible.name` and `Accessible.role` to overflow ToolButton — name: "Group options", role: `Accessible.Button`
- [x] 5.7 Add `Accessible.name` and `Accessible.role` to `groupMenu` (Menu) — name: "Group options menu", role: `Accessible.Menu`
- [x] 5.8 Add `Accessible.name` and `Accessible.role` to "Rename" MenuItem — name: "Rename", role: `Accessible.MenuItem`
- [x] 5.9 Add `Accessible.name` and `Accessible.role` to "Delete" MenuItem — name: "Delete", role: `Accessible.MenuItem`

## 6. Groups Pane — Membership Editor

- [x] 6.1 Add `Accessible.name` and `Accessible.role` to "Back" Button — name: "Back", role: `Accessible.Button`
- [x] 6.2 Add `Accessible.name` and `Accessible.role` to `memberList` (ListView) — name: "Group members", role: `Accessible.List`
- [x] 6.3 Add `Accessible.role` to `memberRow` ItemDelegate — name bound to `rowData.name`, role: `Accessible.ListItem`
- [x] 6.4 Add `Accessible.name` and `Accessible.role` to "Move up" ToolButton — name: "Move up", role: `Accessible.Button`
- [x] 6.5 Add `Accessible.name` and `Accessible.role` to "Move down" ToolButton — name: "Move down", role: `Accessible.Button`
- [x] 6.6 Add `Accessible.name` and `Accessible.role` to "Remove from group" ToolButton — name: "Remove from group", role: `Accessible.Button`
- [x] 6.7 Add `Accessible.name` and `Accessible.role` to non-members ListView — name: "Available dictionaries to add", role: `Accessible.List`
- [x] 6.8 Add `Accessible.role` to `nonMemberRow` ItemDelegate — name bound to `rowData.name`, role: `Accessible.ListItem`
- [x] 6.9 Add `Accessible.name` and `Accessible.role` to "Add to group" ToolButton — name: "Add to group", role: `Accessible.Button`

## 7. Article Pane

- [x] 7.1 Add `Accessible.name` and `Accessible.role` to "Back" ToolButton — name: "Back", role: `Accessible.Button`
- [x] 7.2 Add `Accessible.name` and `Accessible.role` to favorites star ToolButton — role: `Accessible.Button`, name bound dynamically: `engine.isFavorite(root.currentWord) ? "Remove from favorites" : "Add to favorites"`
- [x] 7.3 Add `Accessible.name` and `Accessible.role` to `articleLoader` (Loader) — name: "Article content", role: `Accessible.Group`
- [x] 7.4 Add `Accessible.name` and `Accessible.role` to `view` (WebView) — name: "Dictionary article", role: `Accessible.WebView`

## 8. FTS Pane

- [x] 8.1 Add `Accessible.name` and `Accessible.role` to `ftsInput` (TextField) — name: "Full-text search", role: `Accessible.EditableText`
- [x] 8.2 Add `Accessible.name` and `Accessible.role` to `ftsWholeWords` (CheckBox) — name: "Whole words", role: `Accessible.CheckBox`
- [x] 8.3 Add `Accessible.name` and `Accessible.role` to `ftsGroupCombo` (ComboBox) — name: "Full-text search group scope", role: `Accessible.ComboBox`
- [x] 8.4 Add `Accessible.name` and `Accessible.role` to `ftsSearchBtn` (Button) — name: "Search", role: `Accessible.Button`
- [x] 8.5 Add `Accessible.name` and `Accessible.role` to FTS results ListView — name: "Full-text search results", role: `Accessible.List`
- [x] 8.6 Add `Accessible.role` to FTS result ItemDelegate — name bound to `modelData.headword`, role: `Accessible.ListItem`

## 9. History Pane

- [x] 9.1 Add `Accessible.name` and `Accessible.role` to "Clear all" Button — name: "Clear all", role: `Accessible.Button`
- [x] 9.2 Add `Accessible.name` and `Accessible.role` to history ListView — name: "Lookup history", role: `Accessible.List`
- [x] 9.3 Add `Accessible.role` to `histRow` SwipeDelegate — name bound to `word`, role: `Accessible.ListItem`
- [x] 9.4 Add `Accessible.name` and `Accessible.role` to delete Button inside `histRow` swipe — name: "Delete", role: `Accessible.Button`

## 10. Favorites Pane

- [x] 10.1 Add `Accessible.name` and `Accessible.role` to favorites ListView — name: "Favorites", role: `Accessible.List`
- [x] 10.2 Add `Accessible.role` to `favRow` SwipeDelegate — name bound to `word`, role: `Accessible.ListItem`
- [x] 10.3 Add `Accessible.name` and `Accessible.role` to remove Button inside `favRow` swipe — name: "Remove", role: `Accessible.Button`

## 11. Onboarding Dialog

- [x] 11.1 Add `Accessible.name` and `Accessible.role` to onboarding Dialog — name: "Welcome", role: `Accessible.Dialog`
- [x] 11.2 Add `Accessible.name` and `Accessible.role` to "Get started" Button — name: "Get started", role: `Accessible.Button`

## 12. Informational Elements

- [x] 12.1 Add `Accessible.role: Accessible.ProgressBar` to both ProgressBar elements in the processing banner (lines ~508, ~518)
