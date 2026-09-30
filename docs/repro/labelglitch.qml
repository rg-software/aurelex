// Minimal repro for the Material TextField floating-label glitch.
//
// The app's Search field rendered its "floating" placeholder label ON the box
// border instead of above it, on two Android devices. This file strips
// everything else away: stock Material style, one TextField with the app's
// settings, plus a default-sized control field.
//
// Cause: `font.pixelSize: 18`. Material's MaterialTextContainer positions the
// floating label from the placeholder's largestHeight, and at 18px that exceeds
// what the style budgets for, so the label is drawn at the unfloated y.
//
// Run:  C:\Qt\6.6.3\msvc2019_64\bin\qmlscene.exe docs\repro\labelglitch.qml
//   A (top)    - the app's field; correct now that font.pixelSize is gone.
//                Uncomment the font.pixelSize line in field A to see the glitch:
//                the label drops onto the border and overlaps the text.
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
