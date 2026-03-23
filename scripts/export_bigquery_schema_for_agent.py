#!/usr/bin/env python3
"""
Export BigQuery table schemas (and optional sample rows) as Markdown for agent instructions.

Uses Application Default Credentials or GOOGLE_APPLICATION_CREDENTIALS (same as the agent).

Examples:
  uv run python scripts/export_bigquery_schema_for_agent.py --no-samples
  uv run python scripts/export_bigquery_schema_for_agent.py --include-staging --no-samples
  uv run python scripts/export_bigquery_schema_for_agent.py --tables jobs customers
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from google.cloud import bigquery

PROJECT_ID = "mastermechanical"
DATASET_ID = "dev_Master_Mechanical"


def _is_staging_table(table_id: str) -> bool:
    return table_id.endswith("_staging")


def _field_lines(fields: Sequence[bigquery.SchemaField], indent: int = 0) -> list[str]:
    lines: list[str] = []
    pad = "  " * indent
    for f in fields:
        mode = f.mode or "NULLABLE"
        rep = f" ({mode})" if mode != "NULLABLE" else ""
        lines.append(f"{pad}- `{f.name}`: `{f.field_type}`{rep}")
        if f.fields:
            lines.extend(_field_lines(f.fields, indent + 1))
    return lines


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--no-samples",
        action="store_true",
        help="Schema only (recommended for commits; sample rows may contain PII).",
    )
    p.add_argument(
        "--tables",
        nargs="*",
        help="Subset of table IDs; default is all tables in the dataset.",
    )
    p.add_argument(
        "--max-rows",
        type=int,
        default=2,
        help="Sample rows per table when samples are enabled (default: 2).",
    )
    p.add_argument(
        "--include-staging",
        action="store_true",
        help="Include tables whose names end with _staging (default: exclude them).",
    )
    args = p.parse_args()

    client = bigquery.Client(project=PROJECT_ID)
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"

    if args.tables:
        table_ids = list(args.tables)
    else:
        table_ids = [t.table_id for t in client.list_tables(dataset_ref)]
        if not args.include_staging:
            table_ids = [t for t in table_ids if not _is_staging_table(t)]

    print(f"# BigQuery schema snapshot: `{dataset_ref}`\n")
    if not args.tables and not args.include_staging:
        print("_Excluding `*_staging` tables. Use `--include-staging` to list them._\n")
    print(f"_Generated for pasting into agent instructions. Review before sharing._\n")

    for tid in sorted(table_ids):
        table = client.get_table(f"{dataset_ref}.{tid}")
        print(f"## `{tid}`\n")
        print("**Fields:**\n")
        print("\n".join(_field_lines(table.schema)))
        print()

        if args.no_samples:
            continue

        q = f"SELECT * FROM `{dataset_ref}.{tid}` LIMIT {args.max_rows}"
        job = client.query(q)
        rows = list(job.result())
        print(f"**Sample rows** (up to {args.max_rows}; may contain PII — redact before committing):\n")
        if not rows:
            print("_No rows returned._\n")
            continue
        for i, row in enumerate(rows, 1):
            d = dict(row.items())
            # Compact JSON for readability; truncate very long strings
            s = json.dumps(d, default=str, indent=2)
            if len(s) > 8000:
                s = s[:8000] + "\n... [truncated]"
            print(f"### Row {i}\n```json\n{s}\n```\n")

    print(
        "---\n"
        "**Next steps:** Paste relevant sections into `_AGENT_INSTRUCTION` in "
        "`src/agents/MasterMechanicalAgent/agent.py`, or keep a private `schema_private.md` "
        "(gitignored) and load from file if you automate that later."
    )


if __name__ == "__main__":
    main()
