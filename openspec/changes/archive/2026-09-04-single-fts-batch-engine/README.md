# single-fts-batch-engine

Single shared full-text index batch worker: queue-based, grows when dictionaries are added mid-build (no restarts / double work), tracks per-dict + overall progress.
