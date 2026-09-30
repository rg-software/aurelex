// Minimal repro for the Material TextField floating-label glitch.
//
// The app's Search field drew its "floating" placeholder label straight through
// the box border instead of above it. Two independent triggers were found, both
// reproduced in this file:
//
// 1. FONT SIZE. Material's MaterialTextContainer positions the floating label
//    from the placeholder's largestHeight, and font.pixelSize: 18 exceeds what
//    the style budgets for, so the label is drawn at the unfloated y.
//    Field A below is the fixed version; uncomment its font.pixelSize line to
//    see it.
//
// 2. FOCUS STEALING. A Button next to the field takes keyboard focus on press,
//    which repaints the field's frame grey while the label keeps its position.
//    Restoring focus repaints only the frame, leaving it drawn through the
//    label. Fixed in the app with focusPolicy: Qt.NoFocus on the neighbouring
//    buttons; tap "B" here (a focusable Button) to see the effect.
//
// Run:  C:\Qt\6.6.3\msvc2019_64\bin\qmlscene.exe docs\repro\labelglitch.qml
//   A (top)    - the app's field settings; correct as written.
//   B (bottom) - default font size; always correct. The control.
import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts

ApplicationWindow {
    id: win
    width: 900
    height: 360
    visible: true
    title: "TextField label repro"

    Material.theme: Material.Light
    Material.accent: "#6200ee"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 16

        // A: the app's Search field. Passes now that the font-size override is
        // gone. Uncomment the font.pixelSize line to reproduce the original
        // glitch: the label drops onto the box border and overlaps the text.
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            TextField {
                id: appField
                Layout.fillWidth: true
                Component.onCompleted: { forceActiveFocus(); text = "Mire" }
                Layout.preferredWidth: 7
                placeholderText: "Search dictionaries"
                // font.pixelSize: 18   // <-- reintroduces the glitch
            }
            Button {
                text: "B"
                highlighted: true
                onClicked: appField.forceActiveFocus()
            }
        }

        // B: default font size, otherwise identical — the control.
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            TextField {
                id: ctlField
                Layout.fillWidth: true
                Layout.preferredWidth: 7
                placeholderText: "Search dictionaries"
            }
            Button {
                text: "B"
                highlighted: true
                onClicked: ctlField.forceActiveFocus()
            }
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: "Tap into A (px 18) and B (default). Compare where the label sits."
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                text: "Set both text"
                onClicked: { appField.text = "Mire"; ctlField.text = "Mire" }
            }
            Button {
                text: "Clear both"
                onClicked: { appField.text = ""; ctlField.text = "" }
            }
            Button {
                text: "Blur both"
                onClicked: { appField.focus = false; ctlField.focus = false }
            }
        }
    }
}
