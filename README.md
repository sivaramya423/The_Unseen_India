# THE UNSEEN INDIA

**AI That Discovers What People Don't Know They're Missing.**

A hackathon prototype that helps people find scholarships, skill programmes, public services and learning resources they might never have thought to search for. It matches a person's description against a structured dataset, explains why each record matched, and states plainly what is unknown.

## Problem
Opportunities are scattered across portals, documents and announcements. Search engines need the right keyword, and many people do not know the name of what they are missing.

## Solution and what makes it different
* **Discovery, not keyword search.** You describe your situation; transparent rules rank records and list a reason for every match.
* **Evidence first.** The AI answers only from retrieved records. Source links shown to you come from the dataset, not from the AI.
* **Honest gaps.** Every record shows what is missing and whether its values were verified. The Gap Detector separates "not in our dataset" from "unverified", and never claims something does not exist.

> **Limits you should state to judges:** the prototype searches a small, hand-built dataset, not the live web. Most records are portal references, not specific schemes, and most are marked unverified because they were not opened and checked during the build.

## Features
| Feature | How it works |
|---|---|
| Opportunity Radar | Rule-based scoring (no AI) |
| Knowledge Connections | Weighted shared-attribute overlap (set arithmetic, not ML) |
| Knowledge Gap Detector | Field checks per record and per question |
| AI Assistant | Retrieval from the dataset, then Groq LLM explanation |
| Comparison | Side-by-side of stored fields (up to 3 records) |
| Transparency | Source link, verification status and date on every record |

Works without an API key: everything except the AI explanations.

## Technology
Python 3.11+, Streamlit, official `groq` SDK, python-dotenv, JSON dataset, pytest.

## Folder structure
```
the_unseen_india/
    app.py                      Streamlit interface
    config.py                   settings from .env
    requirements.txt  .env.example  .gitignore  pytest.ini  LICENSE
    .streamlit/config.toml      dark theme
    data/opportunities.json     the dataset
    services/                   discovery, connections, gaps, Groq
    utils/                      data loading, validation, UI components
    scripts/check_groq.py       safe API connectivity test
    tests/                      pytest tests (no network needed)
    docs/                       TECHNICAL_DESIGN.md, architecture.mmd
```
Additions to the requested structure: `scripts/check_groq.py`, `utils/ui.py`, `tests/test_groq_service.py`, `pytest.ini` and `.streamlit/config.toml`.

## Install on Windows (VS Code, PowerShell)
1. Install Python 3.11 or newer from python.org (tick "Add python.exe to PATH").
2. Unzip the project, open the `the_unseen_india` folder in VS Code, then open a terminal (Terminal > New Terminal).
3. Create and activate a virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
If PowerShell says scripts are disabled, allow them for this terminal window only (this does not change your system settings):
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```
Alternatively use Command Prompt and run `.venv\Scripts\activate.bat`.

## Configure the API key
1. Copy `.env.example` to a new file named `.env` in the same folder as `app.py`.
2. Put your own key after `GROQ_API_KEY=` (create one in the Groq console). No quotes, no spaces.
3. Leave `GROQ_MODEL=` empty to use the default, or set a model your key can use.
4. Check it:
```powershell
python scripts/check_groq.py
```
This prints whether a key was found (never the key), lists the models your key can see, and says whether your configured model is one of them. It sends no chat message.

## Run
```powershell
python -m streamlit run app.py
```

## Test
```powershell
python -m pytest -q
```
The tests use fake API clients. They need no key and make no network calls.

## Troubleshooting
| Symptom | Meaning and fix |
|---|---|
| **HTTP 404 from Groq, message mentions the model** | The model ID is misspelled, retired, or not available to your key. Run `python scripts/check_groq.py`, pick a chat model from the list, set `GROQ_MODEL` in `.env`, restart. |
| **HTTP 404 without a model name** | Wrong URL. Do not set a custom base URL; the SDK chooses it. Upgrade: `python -m pip install -U groq`. |
| 401 | Key rejected. Re-copy it into `.env`, check it is active in the Groq console. |
| 429 | Rate or quota limit. Wait and retry. |
| "Could not reach Groq" | Network, VPN, proxy or firewall. |
| "No Groq API key found" | `.env` missing, in the wrong folder, or the app was not restarted after editing it. |
| `ModuleNotFoundError` | The virtual environment is not active or requirements were not installed. |

Models listed on Groq's official page for chat include `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` (as of 2026-10-25; some may need a paid plan). Always trust the list your own key returns.

## Dataset limitations
* 11 records. Five portals come from the project brief; the others were written from general knowledge.
* Only **Naan Mudhalvan** is marked partly verified (description and benefits, checked 2026-10-25 against its official pages). Everything else is `unverified` with no verification date.
* Eligibility, deadlines and required documents are empty for nearly all records, which is why the Gap Detector has plenty to show. They must be filled from official sources.
* Education-level and interest labels are curator labels for matching, not official eligibility.

## Security
* The key lives only in `.env`, which `.gitignore` excludes. Never commit it or put it in screenshots.
* The app shows only "found" or "not found" for the key, and error messages are redacted.
* All dataset text is HTML-escaped before display.

## Future improvements
Live retrieval from official pages, scheduled re-verification, semantic search over descriptions, more verified records, multilingual input (Tamil, Hindi), saved profiles.

See `docs/TECHNICAL_DESIGN.md` for the design and `docs/architecture.mmd` for the diagram.
