# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```
streamlit run streamlit_app.py
```

Login credentials: `user` / `pass123` (hardcoded in `streamlit_app.py`).

## Architecture

Single-file Streamlit app (`streamlit_app.py`) with SQLite persistence.

**Data flow:**
- Question banks live in `data/{qb}.parquet` with columns: `name`, `prompt`, `explanation`
- Per-QB SQLite databases live in `db/history_{qb}.db` with two tables: `attempts` and `comparisons`
- Active QB is stored in `st.session_state.active_qb` (default `"example"`); `db_path` and `data_path` are derived from it before the tabs render

**Session state keys:**
- `logged_in` — login gate
- `active_qb` — currently selected question bank name
- `current_pair` — list of 2 question dicts being displayed
- `previous_pair` — one level of undo for Next navigation
- `answered` — `set` of question indices already marked correct/wrong in current display
- `pending_comparison` — `{"label": str, "result": str}` or `None`; drives the `@st.dialog` confirmation modal
- `confirm_clear` — bool for the two-step Clear All History confirmation

**Tabs:** Study | Question Bank | Analytics | Database | Debug

**Adding a new question bank:** Add `data/{name}.parquet` (columns: `name`, `prompt`, `explanation`) and add `"{name}"` to the `qb_options` list in the Question Bank tab.
