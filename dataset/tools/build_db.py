#!/usr/bin/env python3
"""Rebuild dataset.sqlite from the source-of-truth CSVs. Stdlib only.

Run:  python dataset/tools/build_db.py
"""
from __future__ import annotations
import csv
import os
import sqlite3

DATASET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(DATASET, "dataset.sqlite")
SCHEMA = os.path.join(DATASET, "schema.sql")

TABLES = {
    "sets": "sets.csv",
    "rep_metrics": "rep_metrics.csv",
    "raw_files": "raw_files.csv",
    "clip_manifest": os.path.join("raw", "manifest.csv"),
    "clips": "clips.csv",
}

def load_csv(path):
    if not os.path.exists(path):
        return [], []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames or [], list(r)

def main():
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    with open(SCHEMA) as f:
        conn.executescript(f.read())

    total = 0
    for table, fname in TABLES.items():
        cols, rows = load_csv(os.path.join(DATASET, fname))
        if not rows:
            continue
        placeholders = ",".join("?" for _ in cols)
        collist = ",".join(cols)
        data = [tuple((c if c != "" else None) for c in (row[k] for k in cols)) for row in rows]
        conn.executemany(f"INSERT INTO {table} ({collist}) VALUES ({placeholders})", data)
        total += len(rows)
        print(f"  {table}: {len(rows)} rows")

    conn.commit()
    n_sets = conn.execute("SELECT COUNT(*) FROM sets").fetchone()[0]
    n_vendors = conn.execute("SELECT COUNT(DISTINCT vendor) FROM rep_metrics").fetchone()[0]
    n_clips = conn.execute("SELECT COUNT(*) FROM clips").fetchone()[0]
    conn.close()
    print(f"Built {DB}: {total} rows, {n_sets} sets, {n_vendors} vendors, {n_clips} clips.")

if __name__ == "__main__":
    main()
