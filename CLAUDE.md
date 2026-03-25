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
- `previous_pair` — one level of undo for Previous navigation
- `answered` — `set` of question indices already marked correct/wrong in current display
- `answer_choices` — `dict` mapping question index to `"correct"` or `"wrong"`
- `pending_comparison` — `{"label": str, "result": str}` or `None`; drives the `@st.dialog` confirmation modal
- `compared_pairs` — `set` of `frozenset({a_idx, b_idx})` pairs already compared this session
- `comparison_chosen` — `dict` mapping `frozenset({a_idx, b_idx})` to the chosen result value
- `confirm_clear_attempts` — bool for the two-step Clear All Attempts confirmation
- `confirm_clear_comparisons` — bool for the two-step Clear All Comparisons confirmation
- `qbank_pos` — current position (int) in the Question Bank tab selectbox

**Tabs:** Study | Question Bank | Analytics | Database | Debug

**Analytics tab:** Currently shows a placeholder ("Analytics coming soon").

**Adding a new question bank:** Add `data/{name}.parquet` (columns: `name`, `prompt`, `explanation`) and add `"{name}"` to the `qb_options` list in the Question Bank tab.
