from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from aws_client import get_boto3_session, get_active_regions
from scheduler import sync_all_customers, sync_customer, sync_account

router = APIRouter()


# ── Debug endpoint (M3) — keep until M8 cleanup ───────────────

class AssumeRoleTest(BaseModel):
    role_arn: str
    external_id: Optional[str] = None


@router.post("/sync/test-assume-role")
def test_assume_role(data: AssumeRoleTest):
    """Test AssumeRole and return accessible regions. Remove before production."""
    try:
        session = get_boto3_session(data.role_arn, data.external_id)
        regions = get_active_regions(session)
        return {
            "success": True,
            "role_arn": data.role_arn,
            "region_count": len(regions),
            "regions": sorted(regions),
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}


# ── Sync trigger endpoints ────────────────────────────────────

@router.post("/sync")
def trigger_sync_all(background_tasks: BackgroundTasks):
    """Trigger a full sync for all customers."""
    background_tasks.add_task(sync_all_customers)
    return {"status": "sync_started"}


@router.post("/sync/{customer_id}")
def trigger_sync_customer(customer_id: int, background_tasks: BackgroundTasks):
    """Trigger sync for a single customer."""
    background_tasks.add_task(sync_customer, customer_id)
    return {"status": "sync_started", "customer_id": customer_id}


@router.post("/sync/account/{account_id}")
def trigger_sync_account(account_id: int, background_tasks: BackgroundTasks):
    """Trigger sync for a single account."""
    background_tasks.add_task(sync_account, account_id)
    return {"status": "sync_started", "account_id": account_id}
