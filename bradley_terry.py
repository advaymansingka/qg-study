import sqlite3

import numpy as np
import pandas as pd


def bradley_terry_leaderboard(db_path, data_path, regularization=1.0, max_iter=100, tol=1e-6):
    # Load questions
    questions = pd.read_parquet(data_path).reset_index()
    n = len(questions)
    idx_map = {int(row["index"]): i for i, row in questions.iterrows()}

    # Load comparisons
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_a_index INTEGER, question_a_name TEXT,
            question_b_index INTEGER, question_b_name TEXT,
            result TEXT, timestamp TEXT
        )
    """)
    rows = conn.execute("SELECT question_a_index, question_b_index, result FROM comparisons").fetchall()
    conn.close()

    # Build win matrix
    W = np.zeros((n, n))
    weight_map = {
        "A_much_harder": (2, 0),
        "A_harder": (1, 0),
        "same": (0.5, 0.5),
        "B_harder": (0, 1),
        "B_much_harder": (0, 2),
    }
    for a_idx, b_idx, result in rows:
        if a_idx not in idx_map or b_idx not in idx_map:
            continue
        a, b = idx_map[a_idx], idx_map[b_idx]
        wa, wb = weight_map.get(result, (0, 0))
        W[a][b] += wa
        W[b][a] += wb

    # Regularization: add virtual win+loss per pair
    for i in range(n):
        for j in range(n):
            if i != j:
                W[i][j] += regularization

    # MM algorithm
    w = W.sum(axis=1)  # total wins per player
    N = W + W.T  # total comparisons per pair

    p = np.ones(n)
    for _ in range(max_iter):
        p_new = np.zeros(n)
        for i in range(n):
            denom = 0.0
            for j in range(n):
                if i != j and N[i][j] > 0:
                    denom += N[i][j] / (p[i] + p[j])
            p_new[i] = w[i] / denom if denom > 0 else 1.0
        p_new = p_new / p_new.sum() * n
        if np.max(np.abs(p_new - p)) < tol:
            p = p_new
            break
        p = p_new

    scores = np.log(p)
    scores -= scores.mean()

    result_df = pd.DataFrame({
        "index": questions["index"],
        "name": questions["name"],
        "score": np.round(scores, 3),
    }).sort_values("score", ascending=False).reset_index(drop=True)

    return result_df
