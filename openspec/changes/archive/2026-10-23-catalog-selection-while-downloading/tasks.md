# Tasks

## 1. Guard the tap handler (app/main.qml)

- [x] 1.1 `_toggleCatalogSelect` returns early while `engine.downloadActive`,
      with the installed-entry comment extended; row visuals unchanged
- [x] 1.2 Change validates; main spec scenario added on archive

## 2. Verification

- [x] 2.1 Change validates; no other `catalogSelected` writers bypass the guard
      (only the delegate's `onClicked` calls it)
- [x] 2.2 No QML unit harness covers the pane; verify by reading the handler
      and its callers
