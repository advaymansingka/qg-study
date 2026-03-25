import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(layout="wide", page_title="QG Study")

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
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
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
            st.session_state.compared_pairs.add(frozenset({row_a["index"], row_b["index"]}))
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
    /* Correct button — green */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #1e7e34 !important;
        border-color: #1e7e34 !important;
        color: #ffffff !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover:not(:disabled) {
        background-color: #25a244 !important;
        border-color: #25a244 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    for col, row in zip([col1, col2], st.session_state.current_pair):
        with col:
            idx = row["index"]
            st.header(f"{idx}. {row['name']}")
            st.markdown(row["prompt"])
            with st.expander("Explanation"):
                st.markdown(row["explanation"])

            already_answered = idx in st.session_state.answered
            bcol1, bcol2 = st.columns(2)
            with bcol1:
                if st.button("✓ Correct", key=f"correct_{idx}", disabled=already_answered,
                             type="primary", use_container_width=True):
                    log_attempt(db_path, idx, row["name"], "correct")
                    st.session_state.answered.add(idx)
                    st.rerun()
            with bcol2:
                if st.button("✗ Wrong", key=f"wrong_{idx}", disabled=already_answered,
                             use_container_width=True):
                    log_attempt(db_path, idx, row["name"], "wrong")
                    st.session_state.answered.add(idx)
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
    cmp_cols = st.columns(5)
    for col, (label, result_val) in zip(cmp_cols, comparisons):
        with col:
            if st.button(label, key=f"cmp_{result_val}_{a_idx}_{b_idx}",
                         disabled=already_compared, use_container_width=True):
                st.session_state.pending_comparison = {"label": label, "result": result_val}
                st.rerun()

    # Navigation
    st.divider()
    nav1, _, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("← Previous", disabled=st.session_state.previous_pair is None,
                     use_container_width=True):
            st.session_state.current_pair = st.session_state.previous_pair
            st.session_state.previous_pair = None
            st.session_state.answered = set()
            st.rerun()
    with nav3:
        if st.button("Next →", use_container_width=True):
            st.session_state.previous_pair = st.session_state.current_pair
            st.session_state.current_pair = df.sample(2).to_dict("records")
            st.session_state.answered = set()
            st.rerun()

# ── Question Bank tab ──
with qbank_tab:
    qb_options = ["example"]
    new_qb = st.selectbox("Question Bank", qb_options, index=qb_options.index(qb), key="qb_selector")
    if new_qb != qb:
        st.session_state.active_qb = new_qb
        st.rerun()

    options = {f"{row['index']}. {row['name']}": row for row in df.to_dict("records")}
    selection = st.selectbox("Select a question", list(options.keys()))
    if selection:
        row = options[selection]
        st.header(f"{row['index']}. {row['name']}")
        st.markdown(row["prompt"])
        st.markdown("**Explanation:**")
        st.markdown(row["explanation"])

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
        if st.button("Delete selected rows", key="del_attempts"):
            ids = edited_attempts.loc[edited_attempts["Delete"], "id"].tolist()
            if ids:
                conn.execute(f"DELETE FROM attempts WHERE id IN ({','.join(str(i) for i in ids)})")
                conn.commit()
                st.rerun()
    else:
        st.info("No attempts recorded yet.")

    st.divider()
    if not st.session_state.confirm_clear_attempts:
        if st.button("Clear Attempts", key="clear_attempts_btn"):
            st.session_state.confirm_clear_attempts = True
            st.rerun()
    else:
        st.warning("This will delete all attempts. Are you sure?")
        ca1, ca2 = st.columns([1, 5])
        with ca1:
            if st.button("Yes, clear", key="yes_clear_attempts"):
                conn.execute("DELETE FROM attempts")
                conn.commit()
                st.session_state.confirm_clear_attempts = False
                st.rerun()
        with ca2:
            if st.button("Cancel", key="cancel_clear_attempts"):
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
        if st.button("Delete selected rows", key="del_comparisons"):
            ids = edited_comparisons.loc[edited_comparisons["Delete"], "id"].tolist()
            if ids:
                conn.execute(f"DELETE FROM comparisons WHERE id IN ({','.join(str(i) for i in ids)})")
                conn.commit()
                st.rerun()
    else:
        st.info("No comparisons recorded yet.")

    conn.close()

    st.divider()
    if not st.session_state.confirm_clear_comparisons:
        if st.button("Clear Comparisons", key="clear_comparisons_btn"):
            st.session_state.confirm_clear_comparisons = True
            st.rerun()
    else:
        st.warning("This will delete all comparisons. Are you sure?")
        cc1, cc2 = st.columns([1, 5])
        with cc1:
            if st.button("Yes, clear", key="yes_clear_comparisons"):
                conn = get_conn(db_path)
                conn.execute("DELETE FROM comparisons")
                conn.commit()
                conn.close()
                st.session_state.confirm_clear_comparisons = False
                st.rerun()
        with cc2:
            if st.button("Cancel", key="cancel_clear_comparisons"):
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
