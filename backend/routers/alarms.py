from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import case
from typing import Optional
from database import get_db
from models import Alarm, Account, Customer

router = APIRouter()

# CASE expression: ALARM=0 < INSUFFICIENT_DATA=1 < OK=2 < other=3
_STATE_ORDER = case(
    (Alarm.state == "ALARM", 0),
    (Alarm.state == "INSUFFICIENT_DATA", 1),
    (Alarm.state == "OK", 2),
    else_=3,
)


@router.get("/alarms")
def list_alarms(
    customer_ids: Optional[str] = Query(None, description="Comma-separated customer IDs"),
    state:        Optional[str] = Query(None, description="Comma-separated states: ALARM,INSUFFICIENT_DATA,OK"),
    region:       Optional[str] = Query(None, description="Single region name"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Alarm, Account, Customer)
        .join(Account,  Alarm.account_id_fk  == Account.id)
        .join(Customer, Account.customer_id  == Customer.id)
    )

    if customer_ids:
        ids = [int(x.strip()) for x in customer_ids.split(",") if x.strip().isdigit()]
        if ids:
            query = query.filter(Customer.id.in_(ids))

    if state:
        states = [s.strip().upper() for s in state.split(",") if s.strip()]
        if states:
            query = query.filter(Alarm.state.in_(states))

    if region:
        query = query.filter(Alarm.region == region)

    query = query.order_by(_STATE_ORDER, Alarm.updated_at.desc())

    results = []
    for alarm, account, customer in query.all():
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
            "customer_id":       customer.id,
            "customer_name":     customer.name,
        })
    return results
