import glob
import os
import random
import sqlite3
from datetime import datetime

import pandas as pd
from bradley_terry import bradley_terry_leaderboard
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide", page_title="QG Study", page_icon=":books:")

USERNAME = "user"
PASSWORD = "pass123"

# --- DB setup ---
def get_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_index INTEGER,
            question_name TEXT,
            result TEXT,
            timestamp TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_a_index INTEGER,
            question_a_name TEXT,
            question_b_index INTEGER,
            question_b_name TEXT,
            result TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    return conn

def log_attempt(db_path, question_index, question_name, result):
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO attempts (question_index, question_name, result, timestamp) VALUES (?, ?, ?, ?)",
        (question_index, question_name, result, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def log_comparison(db_path, row_a, row_b, result):
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO comparisons (question_a_index, question_a_name, question_b_index, question_b_name, result, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (row_a["index"], row_a["name"], row_b["index"], row_b["name"], result, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# --- Login ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    _, login_col, _ = st.columns([2, 1, 2])
    with login_col:
        st.title("Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            if username == USERNAME and password == PASSWORD:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# --- Active QB (set from Question Bank tab) ---
qb = st.session_state.get("active_qb", "example")

db_path = f"db/history_{qb}.db"
data_path = f"data/{qb}.parquet"

# Reset state if QB changed
if st.session_state.get("active_qb") != qb:
    st.session_state.active_qb = qb
    st.session_state.current_pair = None
    st.session_state.previous_pair = None
    st.session_state.answered = set()
    st.session_state.pending_comparison = None
    st.session_state.compared_pairs = set()
    st.session_state.bt_leaderboard = None
    st.session_state.bt_leaderboard_ts = None
    _lb_files = sorted(glob.glob(f"leaderboard/lb_{qb}_*.parquet"))
    if _lb_files:
        _latest = _lb_files[-1]
        st.session_state.bt_leaderboard = pd.read_parquet(_latest)
        _ts_str = _latest.rsplit("_", 2)[-2] + "_" + _latest.rsplit("_", 1)[-1].replace(".parquet", "")
        st.session_state.bt_leaderboard_ts = datetime.strptime(_ts_str, "%Y%m%d_%H%M%S")

# --- Load data ---
df = pd.read_parquet(data_path).reset_index()

# --- Session state init ---
if not st.session_state.get("current_pair"):
    st.session_state.current_pair = df.sample(2).to_dict("records")
if "previous_pair" not in st.session_state:
    st.session_state.previous_pair = None
if "answered" not in st.session_state:
    st.session_state.answered = set()
if "pending_comparison" not in st.session_state:
    st.session_state.pending_comparison = None
if "compared_pairs" not in st.session_state:
    st.session_state.compared_pairs = set()
if "confirm_clear_attempts" not in st.session_state:
    st.session_state.confirm_clear_attempts = False
if "confirm_clear_comparisons" not in st.session_state:
    st.session_state.confirm_clear_comparisons = False
if "answer_choices" not in st.session_state:
    st.session_state.answer_choices = {}
if "comparison_chosen" not in st.session_state:
    st.session_state.comparison_chosen = {}
if "qbank_pos" not in st.session_state:
    st.session_state.qbank_pos = 0

# --- Comparison dialog ---
@st.dialog("Confirm Comparison")
def show_confirm_dialog():
    pending = st.session_state.pending_comparison
    st.write(f"Log comparison: **{pending['label']}**?")
    ccol1, ccol2 = st.columns(2)
    with ccol1:
        if st.button("Confirm"):
            row_a, row_b = st.session_state.current_pair
            log_comparison(db_path, row_a, row_b, pending["result"])
            _pair_key = frozenset({row_a["index"], row_b["index"]})
            st.session_state.compared_pairs.add(_pair_key)
            st.session_state.comparison_chosen[_pair_key] = pending["result"]
            st.session_state.pending_comparison = None
            st.rerun()
    with ccol2:
        if st.button("Cancel"):
            st.session_state.pending_comparison = None
            st.rerun()

if st.session_state.pending_comparison:
    show_confirm_dialog()

# --- Tabs ---
study_tab, qbank_tab, analytics_tab, database_tab, debug_tab = st.tabs(
    ["Study", "Question Bank", "Analytics", "Database", "Debug"]
)

# ── Study tab ──
with study_tab:
    st.markdown("""
    <style>
    /* General button polish */
    div[data-testid="stButton"] > button {
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.95rem;
        padding: 0.45rem 1rem;
        transition: filter 0.15s ease, box-shadow 0.15s ease;
        width: 100%;
    }
    div[data-testid="stButton"] > button:hover:not(:disabled) {
        filter: brightness(1.12);
        box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    }
    div[data-testid="stButton"] > button:disabled {
        opacity: 0.35;
        cursor: not-allowed;
    }
    /* Correct button — green text, transparent bg */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: transparent !important;
        border: 2px solid #1e7e34 !important;
        color: #1e7e34 !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover:not(:disabled) {
        background-color: rgba(30, 126, 52, 0.2) !important;
        border-color: #1e7e34 !important;
        filter: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, _, col2 = st.columns([10, 1, 10])
    for col, row in zip([col1, col2], st.session_state.current_pair):
        with col:
            idx = row["index"]
            st.header(f"{idx}. {row['name']}")
            st.markdown(row["prompt"])
            with st.expander("Explanation"):
                st.markdown(row["explanation"])

            already_answered = idx in st.session_state.answered
            chosen = st.session_state.answer_choices.get(idx)
            bcol1, bcol2 = st.columns(2)
            _S = "border-radius:8px;font-weight:600;font-size:0.95rem;padding:0.45rem 1rem;text-align:center;width:100%;display:block;box-sizing:border-box;"
            if already_answered:
                with bcol1:
                    if chosen == "correct":
                        st.markdown(f'<div style="{_S}background:#1e7e34;color:white;border:2px solid #1e7e34;">✓ Correct</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="{_S}background:transparent;color:#aaa;border:2px solid #ccc;opacity:0.4;">✓ Correct</div>', unsafe_allow_html=True)
                with bcol2:
                    if chosen == "wrong":
                        st.markdown(f'<div style="{_S}background:#dc3545;color:white;border:2px solid #dc3545;">✗ Wrong</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="{_S}background:transparent;color:#aaa;border:2px solid #ccc;opacity:0.4;">✗ Wrong</div>', unsafe_allow_html=True)
            else:
                with bcol1:
                    if st.button("✓ Correct", key=f"correct_{idx}", type="primary", use_container_width=True):
                        log_attempt(db_path, idx, row["name"], "correct")
                        st.session_state.answered.add(idx)
                        st.session_state.answer_choices[idx] = "correct"
                        st.rerun()
                with bcol2:
                    if st.button("✗ Wrong", key=f"wrong_{idx}", use_container_width=True):
                        log_attempt(db_path, idx, row["name"], "wrong")
                        st.session_state.answered.add(idx)
                        st.session_state.answer_choices[idx] = "wrong"
                        st.rerun()

    # Comparison buttons
    st.divider()
    a_row, b_row = st.session_state.current_pair
    a_idx, b_idx = a_row["index"], b_row["index"]
    comparisons = [
        (f"A ({a_idx}) much harder", "A_much_harder"),
        (f"A ({a_idx}) harder",      "A_harder"),
        ("Same",                     "same"),
        (f"B ({b_idx}) harder",      "B_harder"),
        (f"B ({b_idx}) much harder", "B_much_harder"),
    ]
    already_compared = frozenset({a_idx, b_idx}) in st.session_state.compared_pairs
    chosen_cmp = st.session_state.comparison_chosen.get(frozenset({a_idx, b_idx}))
    _S = "border-radius:8px;font-weight:600;font-size:0.95rem;padding:0.45rem 1rem;text-align:center;width:100%;display:block;box-sizing:border-box;"
    cmp_cols = st.columns(5)
    if already_compared:
        for col, (label, result_val) in zip(cmp_cols, comparisons):
            with col:
                if result_val == chosen_cmp:
                    st.markdown(f'<div style="{_S}background:#0d6efd;color:white;border:2px solid #0d6efd;">{label}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="{_S}background:transparent;color:#aaa;border:2px solid #ccc;opacity:0.4;">{label}</div>', unsafe_allow_html=True)
    else:
        for col, (label, result_val) in zip(cmp_cols, comparisons):
            with col:
                if st.button(label, key=f"cmp_{result_val}_{a_idx}_{b_idx}", use_container_width=True):
                    st.session_state.pending_comparison = {"label": label, "result": result_val}
                    st.rerun()

    # JS: style Wrong buttons red (pre-selection only — post-selection uses HTML divs)
    components.html("""<script>
function styleWrongBtns() {
    window.parent.document.querySelectorAll('[data-testid="stButton"] button').forEach(function(btn) {
        if (btn.innerText.trim().startsWith('\u2717 Wrong')) {
            btn.style.color = '#dc3545';
            btn.style.borderColor = '#dc3545';
            btn.style.transition = 'background-color 0.15s ease, box-shadow 0.15s ease';
            if (!btn._wrongHoverBound) {
                btn.addEventListener('mouseenter', function() {
                    btn.style.backgroundColor = 'rgba(220, 53, 69, 0.2)';
                    btn.style.filter = 'none';
                });
                btn.addEventListener('mouseleave', function() {
                    btn.style.backgroundColor = 'transparent';
                });
                btn._wrongHoverBound = true;
            }
        }
    });
}
styleWrongBtns();
setTimeout(styleWrongBtns, 100);
</script>""", height=0)

    # Navigation
    st.divider()
    nav1, _, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("← Previous", disabled=st.session_state.previous_pair is None,
                     use_container_width=True):
            st.session_state.current_pair = st.session_state.previous_pair
            st.session_state.previous_pair = None
            st.session_state.answered = set()
            st.session_state.answer_choices = {}
            st.rerun()
    with nav3:
        if st.button("Next →", use_container_width=True):
            st.session_state.previous_pair = st.session_state.current_pair
            st.session_state.current_pair = df.sample(2).to_dict("records")
            st.session_state.answered = set()
            st.session_state.answer_choices = {}
            st.rerun()

# ── Question Bank tab ──
with qbank_tab:
    qb_options = ["example", "qg"]
    new_qb = st.selectbox("Question Bank", qb_options, index=qb_options.index(qb), key="qb_selector", format_func=str.title)
    if new_qb != qb:
        st.session_state.active_qb = new_qb
        st.rerun()

    filtered_df = df.reset_index(drop=True)
    total_all = len(df)
    total_filtered = total_all

    st.caption(f"{total_all} questions")

    if total_filtered == 0:
        st.warning("No questions available.")
    else:
        # Clamp pos to valid range (e.g. after search narrows results)
        qbank_pos = st.session_state.qbank_pos
        if qbank_pos >= total_filtered:
            qbank_pos = 0
            st.session_state.qbank_pos = 0

        # ── Selectbox (synced to pos) ──
        options_list = [f"{row['index']}. {row['name']}" for _, row in filtered_df.iterrows()]
        selected_label = st.selectbox("Select a question", options_list, index=qbank_pos, key="qbank_selectbox")
        new_pos = options_list.index(selected_label)
        if new_pos != qbank_pos:
            st.session_state.qbank_pos = new_pos
            st.rerun()

        # ── Prev / Random / Next buttons ──
        nav1, nav2, nav3 = st.columns([1, 1, 1])
        with nav1:
            if st.button("← Prev", key="qbank_prev", disabled=(qbank_pos == 0), use_container_width=True):
                st.session_state.qbank_pos -= 1
                st.rerun()
        with nav2:
            if st.button("Random", key="qbank_random", use_container_width=True):
                st.session_state.qbank_pos = random.randint(0, total_filtered - 1)
                st.rerun()
        with nav3:
            if st.button("Next →", key="qbank_next", disabled=(qbank_pos == total_filtered - 1), use_container_width=True):
                st.session_state.qbank_pos += 1
                st.rerun()

        # ── Display selected question ──
        row = filtered_df.iloc[qbank_pos]
        st.header(f"{row['index']}. {row['name']}")
        st.markdown(row["prompt"])

        # ── Explanation (collapsed) ──
        with st.expander("Explanation"):
            st.markdown(row["explanation"])

        # ── Attempt history ──
        conn = get_conn(db_path)
        attempt_row = conn.execute(
            "SELECT COUNT(*), MAX(timestamp) FROM attempts WHERE question_index = ?",
            (int(row["index"]),)
        ).fetchone()
        conn.close()
        count, last_ts = attempt_row
        if count and count > 0:
            last_dt = datetime.fromisoformat(last_ts)
            last_str = last_dt.strftime("%b %d, %Y  %I:%M %p")
            st.caption(f"{count} attempt{'s' if count != 1 else ''} · Last: {last_str}")
        else:
            st.caption("No attempts yet")

    # ── Difficulty Leaderboard ──
    st.divider()
    if st.button("Generate Leaderboard", key="gen_leaderboard", use_container_width=False):
        with st.spinner("Running Bradley-Terry model..."):
            lb = bradley_terry_leaderboard(db_path, data_path)
            st.session_state.bt_leaderboard = lb
            now = datetime.now()
            st.session_state.bt_leaderboard_ts = now
            os.makedirs("leaderboard", exist_ok=True)
            fname = f"leaderboard/lb_{qb}_{now.strftime('%Y%m%d_%H%M%S')}.parquet"
            lb.to_parquet(fname, index=False)

    if st.session_state.get("bt_leaderboard_ts") is not None:
        ts = st.session_state.bt_leaderboard_ts
        st.caption(f"Last generated: {ts.strftime('%b %d, %Y  %I:%M %p')}")

    if st.session_state.get("bt_leaderboard") is not None:
        st.subheader("Difficulty Leaderboard")
        st.dataframe(
            st.session_state.bt_leaderboard,
            hide_index=True,
            use_container_width=True,
        )

# ── Analytics tab ──
with analytics_tab:
    st.info("Analytics coming soon")

# ── Database tab ──
with database_tab:
    n_rows = st.selectbox("Show last N entries", [10, 20, 50, 100], index=0, key="db_n_rows")

    conn = get_conn(db_path)

    # ── Attempts ──
    st.subheader("Attempts")
    attempts_df = pd.read_sql_query(
        f"SELECT * FROM attempts ORDER BY timestamp DESC LIMIT {n_rows}", conn
    )
    if not attempts_df.empty:
        attempts_df["timestamp"] = pd.to_datetime(attempts_df["timestamp"]).dt.strftime("%b %d, %Y  %I:%M %p")
        attempts_df.insert(0, "Delete", False)
        edited_attempts = st.data_editor(
            attempts_df, hide_index=True, use_container_width=True,
            column_config={"Delete": st.column_config.CheckboxColumn("🗑", default=False)},
            key="attempts_editor",
        )
        adcol, accol, _ = st.columns([1, 1, 4])
        with adcol:
            del_attempts_clicked = st.button("Delete selected", key="del_attempts", use_container_width=True)
        with accol:
            clr_attempts_clicked = st.button("Clear All", key="clear_attempts_btn", use_container_width=True)
        if del_attempts_clicked:
            ids = edited_attempts.loc[edited_attempts["Delete"], "id"].tolist()
            if ids:
                conn.execute(f"DELETE FROM attempts WHERE id IN ({','.join(str(i) for i in ids)})")
                conn.commit()
                st.rerun()
        if clr_attempts_clicked:
            st.session_state.confirm_clear_attempts = True
            st.rerun()
    else:
        st.info("No attempts recorded yet.")
        if st.button("Clear All", key="clear_attempts_btn"):
            st.session_state.confirm_clear_attempts = True
            st.rerun()

    if st.session_state.confirm_clear_attempts:
        st.warning("This will delete all attempts. Are you sure?")
        yca, nca, _ = st.columns([1, 1, 4])
        with yca:
            if st.button("Yes, clear", key="yes_clear_attempts", use_container_width=True):
                conn.execute("DELETE FROM attempts")
                conn.execute("DELETE FROM sqlite_sequence WHERE name='attempts'")
                conn.commit()
                st.session_state.confirm_clear_attempts = False
                st.rerun()
        with nca:
            if st.button("Cancel", key="cancel_clear_attempts", use_container_width=True):
                st.session_state.confirm_clear_attempts = False
                st.rerun()

    st.divider()

    # ── Comparisons ──
    st.subheader("Comparisons")
    comparisons_df = pd.read_sql_query(
        f"SELECT * FROM comparisons ORDER BY timestamp DESC LIMIT {n_rows}", conn
    )
    if not comparisons_df.empty:
        comparisons_df["timestamp"] = pd.to_datetime(comparisons_df["timestamp"]).dt.strftime("%b %d, %Y  %I:%M %p")
        comparisons_df.insert(0, "Delete", False)
        edited_comparisons = st.data_editor(
            comparisons_df, hide_index=True, use_container_width=True,
            column_config={"Delete": st.column_config.CheckboxColumn("🗑", default=False)},
            key="comparisons_editor",
        )
        cdcol, cccol, _ = st.columns([1, 1, 4])
        with cdcol:
            del_comparisons_clicked = st.button("Delete selected", key="del_comparisons", use_container_width=True)
        with cccol:
            clr_comparisons_clicked = st.button("Clear All", key="clear_comparisons_btn", use_container_width=True)
        if del_comparisons_clicked:
            ids = edited_comparisons.loc[edited_comparisons["Delete"], "id"].tolist()
            if ids:
                conn.execute(f"DELETE FROM comparisons WHERE id IN ({','.join(str(i) for i in ids)})")
                conn.commit()
                st.rerun()
        if clr_comparisons_clicked:
            st.session_state.confirm_clear_comparisons = True
            st.rerun()
    else:
        st.info("No comparisons recorded yet.")
        if st.button("Clear All", key="clear_comparisons_btn"):
            st.session_state.confirm_clear_comparisons = True
            st.rerun()

    conn.close()

    if st.session_state.confirm_clear_comparisons:
        st.warning("This will delete all comparisons. Are you sure?")
        ycc, ncc, _ = st.columns([1, 1, 4])
        with ycc:
            if st.button("Yes, clear", key="yes_clear_comparisons", use_container_width=True):
                conn = get_conn(db_path)
                conn.execute("DELETE FROM comparisons")
                conn.execute("DELETE FROM sqlite_sequence WHERE name='comparisons'")
                conn.commit()
                conn.close()
                st.session_state.confirm_clear_comparisons = False
                st.rerun()
        with ncc:
            if st.button("Cancel", key="cancel_clear_comparisons", use_container_width=True):
                st.session_state.confirm_clear_comparisons = False
                st.rerun()

# ── Debug tab ──
with debug_tab:
    st.subheader("Session State")
    st.json({
        "active_qb": st.session_state.get("active_qb"),
        "current_pair": st.session_state.current_pair,
        "previous_pair": st.session_state.previous_pair,
        "answered": list(st.session_state.answered),
        "compared_pairs": [sorted(p) for p in st.session_state.compared_pairs],
        "pending_comparison": st.session_state.pending_comparison,
    })
