# Spec Delta

## ADDED Requirements

### Requirement: Charset conversion during scan never terminates the process

The system SHALL convert dictionary text through platform charset facilities that are safe on every supported Android API level (28+), so a dictionary whose text converts cleanly MUST load on all of them rather than crashing the scan on some OS versions.

#### Scenario: Scan a UTF-8 DSL dictionary on Android 10

- **WHEN** the scan loads a UTF-8 DSL dictionary on an Android 10 device
- **THEN** the scan completes, the dictionary is listed, and its headwords resolve

#### Scenario: Genuine conversion failure stays a reported failure

- **WHEN** a dictionary's text cannot be converted at all
- **THEN** that dictionary is reported as a failed load and the remaining dictionaries still load
