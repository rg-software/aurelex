# Spec Delta

## Purpose

Dictionary headers must name the build direction's languages.

## MODIFIED Requirements

### Requirement: Import-ready deterministic packaging

The output SHALL be a dictzip `.dsl.dz` plus a sibling resource bundle that the
existing folder import resolves, byte-identical across rebuilds from the same
inputs. The output SHALL introduce no app, engine, or boundary change. The
`#INDEX_LANGUAGE` / `#CONTENTS_LANGUAGE` headers SHALL name the build
direction's source and target languages.

#### Scenario: Existing import consumes the output

- **WHEN** the produced pair is placed in an import folder
- **THEN** the app indexes and renders it with no code change

#### Scenario: Deterministic rebuild

- **WHEN** the tool runs twice on the same inputs
- **THEN** the two outputs are byte-identical

#### Scenario: Headers name the direction languages

- **WHEN** a dictionary is built in either direction
- **THEN** `#INDEX_LANGUAGE` names the source language and
  `#CONTENTS_LANGUAGE` names the target language, so the app classifies
  the dictionary under the correct pair
