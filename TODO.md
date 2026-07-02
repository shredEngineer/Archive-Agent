# TODO

- Add new MCP tool `get_answer_rag_profile` accepting the profile to use for this call (instead of the currently configured one)
  - Note (2026-07-03): the `collection` parameter on `get_answer_rag`/`get_search_result` already covers cross-collection READS; a zone-leak bug was fixed the same day (cross-collection `get_answer_rag` wrote its auto-JSON answer into the ACTIVE profile's answers dir — now skipped with a log note). `get_answer_rag_profile` remains the full solution: per-call profile context incl. the CORRECT answers directory for that profile.
