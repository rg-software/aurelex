## Purpose

Keeps the app's own content readable and tappable on devices that reserve screen
area for system UI — the status bar, the navigation bar, and a camera cutout — by
laying content out inside the area the system reports as safe on each edge, in
every orientation, while the window itself stays edge-to-edge behind that UI.

## ADDED Requirements

### Requirement: App content stays clear of the system bars and camera cutout

The system SHALL lay out the app's own content — text, lists, and interactive
controls — inside the area the platform reports as safe on each of the four
window edges, in every orientation and at every window size. Where the platform
reports both a system-bar inset and a display-cutout inset for an edge, the
system SHALL use the larger of the two. No article text, no search field, and no
tab or button SHALL be placed where a system bar or a camera cutout occupies the
display.

#### Scenario: A top-mounted camera does not cover content in portrait
- **WHEN** the device has a camera cutout at the top of the screen and the app is used in portrait
- **THEN** the cutout's area is covered by the app's non-interactive status strip, and no text or interactive control lies under it

#### Scenario: A side-mounted camera does not cover content in landscape
- **WHEN** the device is rotated so the camera cutout occupies a side edge of the screen
- **THEN** content on that side is inset by the cutout's width, so the article text and the search controls on that side remain fully visible and tappable

#### Scenario: The app's background still fills the area behind the cutout
- **WHEN** content is inset to avoid a camera cutout or a system bar
- **THEN** the area that was inset is filled with the app's own background, so no unthemed gap or black band appears at that edge

#### Scenario: A device with no camera cutout is unaffected
- **WHEN** the device reports no display-cutout inset on any edge
- **THEN** content is laid out edge to edge as it would be on a device without one, and the layout is unchanged

#### Scenario: Content stays clear of the navigation bar area
- **WHEN** the device shows a gesture or button navigation bar
- **THEN** the bottom navigation dock's tabs and the theme control sit above that bar, and the area the bar occupies is filled with the app's background

### Requirement: The window renders edge to edge behind the system UI

The window SHALL occupy the full display area the platform grants it, including
the areas covered by the status bar, the navigation bar, and any camera cutout,
and SHALL paint its own background there. The system icons and the camera area
SHALL therefore sit on the app's background rather than on a system-drawn band.

#### Scenario: No letterbox in portrait
- **WHEN** the app is launched in portrait on a device with a camera cutout
- **THEN** the app's background runs to the physical top and bottom edges of the display, with no system-drawn black band between the app and either edge

#### Scenario: No letterbox in landscape
- **WHEN** the device is rotated to landscape
- **THEN** the app's background continues to the left and right edges of the display, including behind the camera cutout

### Requirement: Safe-area clearance follows the current orientation

The system SHALL re-read the platform's system-bar and display-cutout insets
whenever the window's geometry changes, so that the clearance on each edge
matches the current orientation. The cutout moves to a different edge on
rotation, so the inset previously applied to one edge SHALL stop being applied
and the inset for the newly occupied edge SHALL be applied instead, without the
user switching tabs or re-opening content.

#### Scenario: Rotating moves the clearance to the edge that now has the camera
- **WHEN** the device is rotated from portrait to landscape while an article is displayed
- **THEN** content is clear of the camera on the side it now occupies, and the top and bottom clearances match the status bar and navigation bar for that orientation

#### Scenario: Rotating back restores the previous clearance
- **WHEN** the device is rotated back to portrait
- **THEN** content is again clear of the status bar and the top-mounted camera, with no leftover inset on either side

#### Scenario: Clearance updates when the window is resized without rotating
- **WHEN** the window is resized by the system, for example by the soft keyboard opening or by a multi-window resize
- **THEN** the insets in effect after the resize are used for the laid-out content
