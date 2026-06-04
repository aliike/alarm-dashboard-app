from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Customer, Account, Alarm

router = APIRouter()

_STATE_ORDER = case(
    (Alarm.state == "ALARM", 0),
    (Alarm.state == "INSUFFICIENT_DATA", 1),
    (Alarm.state == "OK", 2),
    else_=3,
)


class CustomerCreate(BaseModel):
    name: str
    account_name: Optional[str] = None  # root account display name; defaults to name
    account_type: str
    root_account_id: str
    role_arn: str
    external_id: Optional[str] = None


class AccountCreate(BaseModel):
    account_name: str
    account_id: str    # 12-digit AWS account ID
    role_arn: str
    external_id: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────

def _alarm_counts_for_account(account_id: int, db: Session) -> dict:
    rows = (
        db.query(Alarm.state, func.count(Alarm.id))
        .filter(Alarm.account_id_fk == account_id)
        .group_by(Alarm.state)
        .all()
    )
    counts = {"ALARM": 0, "INSUFFICIENT_DATA": 0, "OK": 0}
    for state, n in rows:
        if state in counts:
            counts[state] = n
    return counts


def _alarm_summary_for_customer(customer_id: int, db: Session) -> dict:
    rows = (
        db.query(Alarm.state, func.count(Alarm.id))
        .join(Account, Alarm.account_id_fk == Account.id)
        .filter(Account.customer_id == customer_id)
        .group_by(Alarm.state)
        .all()
    )
    summary = {"ALARM": 0, "INSUFFICIENT_DATA": 0, "OK": 0}
    for state, n in rows:
        if state in summary:
            summary[state] = n
    return summary


def _customer_dict(c: Customer, db: Session) -> dict:
    account_count = db.query(func.count(Account.id)).filter(Account.customer_id == c.id).scalar()
    alarm_count = (
        db.query(func.count(Alarm.id))
        .join(Account, Alarm.account_id_fk == Account.id)
        .filter(Account.customer_id == c.id)
        .scalar()
    )
    last_sync = (
        db.query(func.max(Account.last_sync_at))
        .filter(Account.customer_id == c.id)
        .scalar()
    )
    return {
        "id": c.id,
        "name": c.name,
        "account_type": c.account_type,
        "root_account_id": c.root_account_id,
        "role_arn": c.role_arn,
        "external_id": c.external_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "account_count": account_count,
        "alarm_count": alarm_count,
        "last_sync_at": last_sync.isoformat() if last_sync else None,
    }


def _accounts_list(accounts: list, db: Session) -> list[dict]:
    result = []
    for a in accounts:
        result.append({
            "id": a.id,
            "account_id": a.account_id,
            "account_name": a.account_name,
            "role_arn": a.role_arn,
            "is_root": bool(a.is_root),
            "last_sync_at": a.last_sync_at.isoformat() if a.last_sync_at else None,
            "sync_status": a.sync_status,
            "sync_error": a.sync_error,
            "alarm_counts": _alarm_counts_for_account(a.id, db),
        })
    return result


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/customers")
def list_customers(db: Session = Depends(get_db)):
    customers = db.query(Customer).order_by(Customer.created_at.desc()).all()
    return [_customer_dict(c, db) for c in customers]


@router.post("/customers", status_code=201)
def create_customer(data: CustomerCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if data.account_type not in ("payer", "standalone"):
        raise HTTPException(status_code=400, detail="account_type must be 'payer' or 'standalone'")

    customer = Customer(
        name=data.name,
        account_type=data.account_type,
        root_account_id=data.root_account_id,
        role_arn=data.role_arn,
        external_id=data.external_id or None,
    )
    db.add(customer)
    db.flush()

    db.add(Account(
        customer_id=customer.id,
        account_id=data.root_account_id,
        account_name=data.account_name or data.name,
        role_arn=data.role_arn,
        is_root=1,
        sync_status="pending",
    ))
    db.commit()
    db.refresh(customer)

    from scheduler import sync_customer
    background_tasks.add_task(sync_customer, customer.id)

    return {
        "id": customer.id,
        "name": customer.name,
        "account_type": customer.account_type,
        "root_account_id": customer.root_account_id,
        "role_arn": customer.role_arn,
        "external_id": customer.external_id,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
    }


@router.post("/customers/{customer_id}/accounts", status_code=201)
def add_account(
    customer_id: int,
    data: AccountCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    existing = db.query(Account).filter(
        Account.customer_id == customer_id,
        Account.account_id  == data.account_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="This account ID already exists for this customer")

    account = Account(
        customer_id  = customer_id,
        account_id   = data.account_id,
        account_name = data.account_name,
        role_arn     = data.role_arn,
        is_root      = 0,
        sync_status  = "pending",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    from scheduler import sync_account
    background_tasks.add_task(sync_account, account.id)

    return {
        "id":           account.id,
        "account_id":   account.account_id,
        "account_name": account.account_name,
        "role_arn":     account.role_arn,
        "sync_status":  account.sync_status,
    }


@router.get("/customers/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    accounts = db.query(Account).filter(Account.customer_id == customer_id).all()
    result = _customer_dict(customer, db)
    result["accounts"] = _accounts_list(accounts, db)
    result["alarm_summary"] = _alarm_summary_for_customer(customer_id, db)
    return result


@router.get("/customers/{customer_id}/accounts")
def list_accounts(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    accounts = db.query(Account).filter(Account.customer_id == customer_id).all()
    return _accounts_list(accounts, db)


@router.get("/customers/{customer_id}/alarms")
def get_customer_alarms(
    customer_id: int,
    state:  Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    query = (
        db.query(Alarm, Account)
        .join(Account, Alarm.account_id_fk == Account.id)
        .filter(Account.customer_id == customer_id)
    )

    if state:
        states = [s.strip().upper() for s in state.split(",") if s.strip()]
        if states:
            query = query.filter(Alarm.state.in_(states))

    if region:
        query = query.filter(Alarm.region == region)

    query = query.order_by(_STATE_ORDER, Alarm.updated_at.desc())

    results = []
    for alarm, account in query.all():
        results.append({
            "id":                alarm.id,
            "alarm_name":        alarm.alarm_name,
            "alarm_arn":         alarm.alarm_arn,
            "alarm_description": alarm.alarm_description,
            "state":             alarm.state,
            "region":            alarm.region,
            "namespace":         alarm.namespace,
            "metric_name":       alarm.metric_name,
            "updated_at":        alarm.updated_at.isoformat() if alarm.updated_at else None,
            "fetched_at":        alarm.fetched_at.isoformat() if alarm.fetched_at else None,
            "account_db_id":     account.id,
            "account_id":        account.account_id,
            "account_name":      account.account_name,
            "last_sync_at":      account.last_sync_at.isoformat() if account.last_sync_at else None,
        })
    return results


@router.delete("/customers/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(customer)
    db.commit()
    return {"message": f"Customer {customer_id} deleted"}
