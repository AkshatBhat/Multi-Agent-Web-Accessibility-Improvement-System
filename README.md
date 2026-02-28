# Multi-Agent Web Accessibility Improvement System

This repository contains a multi-agent pipeline for detecting, explaining, and proposing fixes for web accessibility issues.

The project was developed for **CS 568: User-Centered Machine Learning** at the **University of Illinois Urbana-Champaign (UIUC)** in **Spring 2025**.

## Team

- Akshat Bhat
- Trusha Talati
- Isha Agrawal
- Viraj Shah
- Apurv Sawant
- Shantanu Dhamdhere

## Project Motivation

The system targets a core gap in existing accessibility tooling:

- Rule-based checkers (for example Axe/Lighthouse) are useful but limited for nuanced, context-aware fixes.
- Developers need assistance that is actionable and understandable, not only a list of rule violations.
- Accessibility improvements should account for multiple user perspectives (for example screen-reader users, keyboard-only users, color-blind users).

This repository implements a workflow where specialized agents detect and summarize issues, simulation agents reason from user personas, and a final fixing agent recommends concrete code changes.

## Research Questions

The project was structured around three course research questions:

- **RQ1:** Can we generate an LLM-augmented dataset for accessibility fixes from web UI data?
- **RQ2:** Can AI agents recommend meaningful, user-centered fixes for accessibility issues?
- **RQ3:** Are AI-generated fixes perceived as useful and actionable by users?

In this repository, RQ1/RQ2 are reflected in the data + agent pipeline, and RQ3 is reflected in the evaluation app and feedback analysis workflow.

## What Is In This Repo

### Core Pipeline

- `analyze_page.py`
  - Runs Playwright on a target URL.
  - Captures HTML and screenshot.
  - Extracts semantic structure (headings, links, images, missing alt/name).
  - Computes contrast ratios.
  - Extracts image/SVG bounding boxes for captioning.
  - Runs Axe and writes a unified JSON output.

- `scripts/phase1_collect.py`
  - Builds structured per-page/per-viewport metadata from the WebUI7k source format.
  - Creates `axe_jobs.json` and an intermediate pickle.

- `scripts/run-axe-puppeteer.js`
  - Executes Axe jobs in bulk for local HTML snapshots.
  - Writes per-viewport Axe JSON and logs failures.

- `scripts/rerun_axe_failures.js`
  - Retries failed Axe runs with a more defensive loading strategy.

- `scripts/phase3_and_4.py`
  - Merges Axe results back into per-page metadata.
  - Filters to pages/viewports with real violations.
  - Writes final JSON files for agent training/use.

### Agents

- `agents/semantic_agent/agent.py`
  - T5-based model for semantics-related violation summarization/fix guidance.
- `agents/contrast_agent/agent.py`
  - T5-based model for low-contrast issue descriptions.
- `agents/axe_violations_agent/agent.py`
  - Rule-centric summarizer over Axe violations.
- `agents/image_captioning_agent/agent.py`
  - BLIP-based captioning over cropped UI regions to support alt-text recommendations.

### Multi-Agent Orchestration

- `scripts/all_agents_init.py`
  - Initializes specialist agents plus user-persona agents (visually impaired, motor impaired, color blind) and a fixing agent.

- `scripts/calling_agents.py`
  - Example end-to-end flow:
    - Loads a JSON page snapshot.
    - Gets summaries from specialist agents.
    - Runs a group chat with persona agents and final fixing agent.

### Human Evaluation App

- `webapp/accessibility_eval_app.py`
  - Streamlit UI for reviewing agent findings and fix suggestions.
  - Supports upvote/downvote feedback and aggregate stats (Supabase-backed).

- `webapp/app.py`
  - Minimal FastAPI prototype with `/analyze` and `/feedback` endpoints.

## Repository Layout

```text
Multi-Agent-Web-Accessibility-Improvement-System/
  agents/
    axe_violations_agent/
    contrast_agent/
    image_captioning_agent/
    semantic_agent/
  agent_pickles/
  scripts/
  training/
  webapp/
  test_data/
  reports_and_presentations/
  analyze_page.py
  requirements.txt
  json_structure.txt
```

## Data Format

Expected JSON shape is documented in `json_structure.txt` and follows:

- Page-level ID
- One or more viewport entries
- Per-viewport fields for:
  - `semantic`
  - `contrast`
  - `image_captioning`
  - `axe`
  - `html_path`
  - `screenshot`

`test_data/test_file.json` is a concrete sample payload you can use for local testing.

## External Dataset (WebUI-7k)

The full `WebUI-7k` dataset is intentionally **not** stored in this GitHub repository (size and portability reasons).

- Google Drive (viewer access): https://drive.google.com/drive/folders/1khjrM0XA19HHPgV8hPlEoBhAnzoMempU?usp=sharing

Example local dataset root used during development:

- `/Users/akshat/Data/UIUC/Spring 2025/Courses/CS 568 User-Centered Machine Learning/Project/WebUI-7k`

Scripts in `scripts/` are configurable via CLI flags and/or environment variables so you can point to your own local dataset location.

## Setup

### 1) Python environment (root pipeline/agents)

```bash
cd Multi-Agent-Web-Accessibility-Improvement-System
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 2) Node dependencies (Axe batch scripts)

There is no `package.json` in this repo, so install required packages manually:

```bash
npm install puppeteer axe-puppeteer
```

### 3) Streamlit evaluation app

```bash
cd webapp
pip install -r requirements.txt
streamlit run accessibility_eval_app.py
```

## Running the System

### A) Analyze a single website URL

```bash
python analyze_page.py "https://example.com" "output/example.json"
```

This produces:

- unified JSON report
- saved HTML snapshot
- full-page WebP screenshot

### B) Bulk dataset generation flow (WebUI7k-style inputs)

Set a local dataset root (replace with your own path). Example:

```bash
export WEBUI7K_ROOT="/Users/akshat/Data/UIUC/Spring 2025/Courses/CS 568 User-Centered Machine Learning/Project/WebUI-7k"
```

Run:

```bash
python scripts/phase1_collect.py --base-dir "$WEBUI7K_ROOT/train_split_web7k"
node scripts/run-axe-puppeteer.js axe_jobs.json "$WEBUI7K_ROOT/axe_failures.txt"
node scripts/rerun_axe_failures.js /path/to/failures.txt
python scripts/phase3_and_4.py --base-dir "$WEBUI7K_ROOT"
```

Path configuration support added in scripts:

- `scripts/phase1_collect.py`
  - `--base-dir`, `--viewports`, `--intermediate-dir`, `--jobs-file`
  - env: `WEBUI7K_TRAIN_DIR` or `WEBUI7K_ROOT`
- `scripts/phase3_and_4.py`
  - `--base-dir`, `--train-dir`, `--pkl-path`, `--output-dir`
  - env: `WEBUI7K_ROOT`, `WEBUI7K_TRAIN_DIR`, `WEBUI7K_PKL_PATH`, `WEBUI7K_OUTPUT_DIR`
- `scripts/run-axe-puppeteer.js`
  - args: `<axe_jobs.json> [failure_log_path]`
  - env fallback: `AXE_FAILURE_LOG`

### C) Run multi-agent orchestration example

```bash
python scripts/calling_agents.py
```

Notes:

- This script uses pickled agent objects from `agent_pickles/`.
- Persona/fixing agents use GPT-based configs and require appropriate LLM credentials/configuration.

## Evaluation Study Summary

The final project evaluation (presented in CS 568, Spring 2025) reported:

- 11 real-world websites evaluated
- About 4 accessibility issues + proposed fixes per site
- 14 unique violation categories
- About 13 reviewers per website (estimated total: 142)
- 548 total votes (upvotes + downvotes)
- Average reviewer agreement with fixes: **84.07%**

Key findings highlighted in the presentation:

- High agreement categories (strong agent performance): missing `<main>` landmark, non-discernible links, some alt-text and `html lang` issues.
- Lower agreement categories (still needs human review): missing `<title>`, high positive `tabindex`, heading hierarchy issues, and inter-dependent fix clusters.

Feedback platform used in the study:

- https://ai-assistant-for-accessibility.streamlit.app/

## Known Limitations and Implementation Notes

- Notebook files (`baseCode.ipynb`, `training/contrast_agent.ipynb`) still include Google Colab-specific paths (for example `/content/drive/...`) as part of the original experimentation workflow.
- `webapp/accessibility_eval_app.py` currently includes Supabase credentials directly in code; move these to environment variables before production use.
- `scripts/calling_agents.py` references pickle filenames that may not exactly match current files in `agent_pickles/`; adjust names/paths as needed.
- Large model files in `agent_pickles/` make repository operations heavier.

## Research Paper Report and Presentations

Project presentation files are stored under:

- `reports_and_presentations/CS 568 Group 51 Final Presentation.pdf`
- `reports_and_presentations/CS 568 Group 51 Final Presentation.pptx`
