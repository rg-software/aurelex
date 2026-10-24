# Spec Delta

## Purpose

Bilingual translation cards carry the headword's pronunciation
transcription, reused verbatim from the kaikki stage.

## ADDED Requirements

### Requirement: Headword pronunciation

Each translation card SHALL show the headword's pronunciation transcription
as a `[t]` line directly under the headword, whenever the source-language
kaikki snapshot holds one for that headword. The transcription is the most
common value across the headword's kaikki records (first-seen wins ties),
picked with the kaikki notation discipline (IPA unlabeled, other notations
labeled, mismatched-notation sounds skipped). The line is present whether
or not the card carries audio recordings.

#### Scenario: Transcription under the headword

- **WHEN** the kaikki snapshot holds a transcription for the headword
- **THEN** the article shows it as a `[t]` line between the headword and
  the rest of the card

#### Scenario: No transcription, no line

- **WHEN** no kaikki record for the headword carries a transcription
- **THEN** the card carries no `[t]` line (and no placeholder)

#### Scenario: Disagreement collapses to most common

- **WHEN** the headword's records carry different transcriptions
- **THEN** the article shows the most common one, first-seen winning ties
