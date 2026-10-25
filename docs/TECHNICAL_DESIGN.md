# Technical Design: THE UNSEEN INDIA

## Design principle
The dataset is the source of truth. Rules decide what is relevant. The LLM only explains records that rules already retrieved. If the LLM is off, everything except the written explanations still works.

## Components

| File | Responsibility | Uses LLM? |
|---|---|---|
| `utils/validators.py` | Record validation, URL checks, input cleaning, gap helpers | No |
| `utils/data_loader.py` | Reads `data/opportunities.json`, normalises records, skips bad ones with a reported reason | No |
| `services/discovery_engine.py` | Builds a profile from form fields and free text, scores and ranks records, keyword search, retrieval for the assistant | No |
| `services/knowledge_connections.py` | Connects records by shared attributes | No |
| `services/knowledge_gap_detector.py` | Reports gaps per record and per question | No |
| `services/groq_service.py` | Groq SDK access, grounded prompt, error classification, connectivity test | Yes |
| `utils/ui.py` | CSS and escaped HTML components | No |
| `app.py` | Streamlit tabs wiring everything together | Calls the above |
| `scripts/check_groq.py` | Command-line connectivity test | Lists models only |

## Data model
Each record has: `id, name, record_type, category, description, target_audience, education_levels, state_or_location, skills_or_interests, eligibility, benefits, deadline, required_documents, official_source_url, source_name, verification_status, verified_fields, last_verified, verification_note, missing_information`.

* `verification_status` is `verified`, `partially_verified` or `unverified`.
* `verified_fields` lists exactly which fields were checked against the source. A value outside that list counts as unverified.
* `last_verified` may only be set when a check really happened. The validator rejects an unverified record that has one.
* `record_type` is `portal_reference` (a directory or portal, not a specific scheme) or `programme`.
* `education_levels` and `skills_or_interests` are curator labels used for matching. They are not official eligibility rules.

## Discovery (Opportunity Radar)
1. `build_profile` merges typed fields with what regular expressions find in the free text (state, education level, and plain-language concepts such as "limited income" mapped to dataset tags). Typed fields win.
2. `score_record` adds rule points: state match 3.0, all-India 1.0, education level 2.5, category 2.0, shared interest tags 1.5 each (capped at 4.5), words in the record text 0.5 each (capped at 2.0), audience overlap 1.0. A record listed only for a different state is excluded.
3. Every point produces a plain-language reason that the UI shows under "Why it matched".
4. Ties are broken by verification status, then by name. Scores are rule points, not probabilities.

Limits: the rules are keyword and label based. A synonym that is not in the concept table or dataset tags will be missed.

## Knowledge connections
Method: for each attribute, Jaccard similarity of the two records' value sets times a fixed weight (skills 3.0, audience 2.0, education 2.0, location 1.5, category 1.0, documents 1.0), summed and divided by the total weight. This is set arithmetic, not machine learning, and the UI says so.

## Knowledge gaps
Three situations are kept apart:
1. **Absent from the dataset**: the field is empty.
2. **Unverified**: a value exists but the field is not in `verified_fields`.
3. **Does not exist**: never claimed. Every "absent" finding carries the note that only an official source can show that something does not exist.

For a question, the detector finds related records with the discovery engine, works out which fields the question asks about (deadline, eligibility, documents, benefits, location), and reports for each how many related records have a value and how many are verified. It also reports when no record is specific to a requested state.

## Assistant and Groq handling
* Retrieval first (`retrieve_for_question`), then one chat request with the system rules and a RECORDS block. If nothing was retrieved, no request is made.
* The model ID comes from `GROQ_MODEL`; the fallback in `config.py` is `openai/gpt-oss-20b`, which the official Groq models page listed as a production model on 2026-10-25. Access for your key is not guaranteed; `scripts/check_groq.py` lists what your key can use.
* The official `groq` SDK builds the URL. We do not set a base URL.
* `max_retries=1` and a 30 second timeout. There is no retry loop in our code.
* Errors are classified by HTTP status or exception name: 401 auth, 403 permission, 404 model or endpoint (the message tells them apart by whether it mentions the model), 429 rate limit, 400 bad request, 5xx server, timeout, network. Messages are redacted for anything that looks like a key.
* After the answer, URLs that are not in the retrieved records are flagged, and the visible source list is built from the dataset, not from the model's text.

## What is implemented
| Feature | Status |
|---|---|
| Radar ranking, connections, gap detection, comparison, dataset validation | Implemented, rule-based |
| Assistant answers, Radar "explain" button | Implemented, uses the LLM |
| Connectivity test (sidebar and script) | Implemented |
| Live web retrieval, automatic deadline checking, semantic search, accounts | Not built |

## Extending the dataset
Add an object to `data/opportunities.json` with the fields above. Fill `verified_fields` and `last_verified` only after opening the official page and confirming those values. Run the tests: the dataset tests fail if a record has a bad URL, a duplicate id, or a verification date it should not have.
