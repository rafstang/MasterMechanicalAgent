"""Local smoke test for HouseCall Pro API connectivity (read-only)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "src/agents/MasterMechanicalAgent/.env")


async def _bq_sample_ids() -> tuple[str | None, str | None]:
    try:
        from google.cloud import bigquery

        project = os.getenv("GOOGLE_CLOUD_PROJECT") or "mastermechanical"
        client = bigquery.Client(project=project)
        query = f"""
        SELECT c.id AS customer_id, j.id AS job_id
        FROM `{project}.dev_Master_Mechanical.customers` AS c
        JOIN `{project}.dev_Master_Mechanical.jobs` AS j ON j.customer.id = c.id
        WHERE c.id IS NOT NULL AND j.id IS NOT NULL
        LIMIT 1
        """
        rows = list(client.query(query).result())
        if not rows:
            print("BigQuery: no sample customer/job rows found.")
            return None, None
        row = rows[0]
        print(f"BigQuery sample customer_id: {row.customer_id}")
        print(f"BigQuery sample job_id: {row.job_id}")
        return str(row.customer_id), str(row.job_id)
    except Exception as exc:
        print(f"BigQuery skipped ({type(exc).__name__}): {exc}")
        return None, None


async def _test_hcp_reads(customer_id: str | None, job_id: str | None) -> bool:
    from src.agents.MasterMechanicalAgent.hcp.client import HcpApiError, HcpClient

    key = (os.getenv("HOUSECALL_PRO_API_KEY") or "").strip()
    if not key:
        print("FAIL: HOUSECALL_PRO_API_KEY is not set.")
        return False
    print("HOUSECALL_PRO_API_KEY: configured")

    client = HcpClient()
    ok = False

    if customer_id:
        try:
            record = await client.get_customer(customer_id)
            print(
                "hcp_get_customer OK:",
                record.get("id"),
                (record.get("first_name") or "")[:40],
            )
            ok = True
        except HcpApiError as exc:
            print(f"hcp_get_customer FAIL: {exc}")

    if job_id:
        try:
            record = await client.get_job(job_id)
            print(
                "hcp_get_job OK:",
                record.get("id"),
                record.get("work_status"),
            )
            ok = True
        except HcpApiError as exc:
            print(f"hcp_get_job FAIL: {exc}")

    return ok


async def _test_propose_only(job_id: str | None) -> bool:
    if not job_id:
        print("propose_update: skipped (no job id)")
        return False

    class _State(dict):
        pass

    class _Ctx:
        def __init__(self) -> None:
            self.state = _State(headers={"user_email": "local-smoke-test@example.com"})

    from src.agents.MasterMechanicalAgent.hcp.tools import hcp_propose_update

    result = await hcp_propose_update(
        "job",
        job_id,
        {"notes": "LOCAL SMOKE TEST — do not confirm or apply"},
        _Ctx(),  # type: ignore[arg-type]
    )
    if "Proposed job update" in result and "Confirmation token" in result:
        print("hcp_propose_update OK (read + diff + pending token stored)")
        return True
    print(f"hcp_propose_update unexpected: {result[:300]}")
    return False


async def main() -> int:
    customer_id, job_id = await _bq_sample_ids()
    read_ok = await _test_hcp_reads(customer_id, job_id)
    propose_ok = await _test_propose_only(job_id)

    if read_ok and propose_ok:
        print("\nSmoke test PASSED (read + propose; no writes applied).")
        return 0
    if read_ok:
        print("\nSmoke test PARTIAL (reads OK; propose skipped or failed).")
        return 0 if not job_id else 1
    print("\nSmoke test FAILED.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
