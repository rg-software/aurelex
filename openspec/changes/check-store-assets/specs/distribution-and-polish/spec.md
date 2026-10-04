## ADDED Requirements

### Requirement: Store listing assets are validated before publication

The system SHALL validate the versioned store listing assets — the listing icon,
the feature graphic and the phone screenshots — against the constraints the target
store enforces, and SHALL fail the check when any of them is violated, so that a
malformed or duplicated asset set is caught by the repository rather than by the
store rejecting an upload.

The validation SHALL cover, for the phone-screenshot gallery: that it is within
the store's per-language screenshot limit; that every screenshot is within the
store's minimum and maximum pixel bounds on each side; that every screenshot has
an aspect ratio the store accepts; that no two screenshots share identical
content; and that the gallery's ordering prefixes are unique and contiguous from
one, so the published order is the order the filenames declare. For the listing
icon and the feature graphic it SHALL check that each is present at the
dimensions the store requires.

The check SHALL NOT require the assets to be regenerated in order to run, so that
it is usable on a machine without the image tooling the converter needs. It SHALL
report every violation it finds rather than only the first.

The store listing copy SHALL state the same constraints in prose, so the numbers
a maintainer needs to respect by hand are the numbers the check enforces.

#### Scenario: A gallery within the store's limits passes

- **WHEN** the check runs against a gallery whose screenshot count is within the
  store's limit and whose files satisfy every dimension, ratio, uniqueness and
  ordering rule
- **THEN** the check succeeds

#### Scenario: Too many screenshots fails

- **WHEN** the gallery contains more screenshots than the store accepts for one
  language
- **THEN** the check fails and names the limit and the actual count

#### Scenario: A wrongly sized screenshot fails

- **WHEN** a screenshot falls outside the store's minimum or maximum pixel bounds
  on either side, or has an aspect ratio the store does not accept
- **THEN** the check fails and names the file, its dimensions and the bound or
  ratio that was violated

#### Scenario: Duplicate screenshot content fails

- **WHEN** two screenshots in the gallery have identical bytes, as happens when a
  renamed capture leaves the previous file behind
- **THEN** the check fails and names both files, so the stale one can be removed

#### Scenario: Ambiguous gallery order fails

- **WHEN** two screenshots share an ordering prefix, or the prefixes are not
  contiguous from one
- **THEN** the check fails, because the published gallery order would not be the
  order the filenames claim

#### Scenario: A missing or wrongly sized listing icon fails

- **WHEN** the listing icon or the feature graphic is absent, or is not at the
  dimensions the store requires
- **THEN** the check fails and names the missing or wrongly sized asset

#### Scenario: Every violation is reported at once

- **WHEN** the gallery violates more than one rule
- **THEN** the check reports each violation, not only the first one found

#### Scenario: The documented constraints match the enforced ones

- **WHEN** a maintainer reads the constraints stated beside the listing copy
- **THEN** the limits, bounds and ratios stated there are the ones the check
  enforces, so hand-made assets and checked assets are held to the same rule