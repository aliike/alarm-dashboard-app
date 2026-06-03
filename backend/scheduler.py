"""
M4 — Sync Engine
Scheduler + all sync logic lives here.
Each function creates its own DB session so it can run in background threads.
"""

import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from models import Customer, Account, Alarm
import aws_client

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="UTC")


# ── Low-level: single account ─────────────────────────────────

def sync_account(db_account_id: int) -> None:
    """
    Sync CloudWatch alarms for one account.
    SUCCESS → deletes old alarms, inserts new, sets sync_status='ok'.
    FAILURE → keeps old alarms, sets sync_status='error'.
    """
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == db_account_id).first()
        if not account:
            logger.warning(f"[sync] account id={db_account_id} not found, skipping")
            return

        customer = db.query(Customer).filter(Customer.id == account.customer_id).first()
        label = f"account={account.account_id} customer='{customer.name if customer else '?'}'"
        logger.info(f"[sync] START {label}")

        try:
            external_id = customer.external_id if customer else None
            session = aws_client.get_boto3_session(account.role_arn, external_id)
            regions  = aws_client.get_active_regions(session)
            logger.info(f"[sync] {label} — {len(regions)} regions")

            alarm_rows = []
            for region in regions:
                alarms = aws_client.get_cloudwatch_alarms(session, region)
                logger.debug(f"[sync] {label} / {region} — {len(alarms)} alarms")
                for a in alarms:
                    ts = a.get("StateUpdatedTimestamp")
                    if ts and getattr(ts, "tzinfo", None) is not None:
                        ts = ts.replace(tzinfo=None)
                    alarm_rows.append(dict(
                        account_id_fk=db_account_id,
                        alarm_name=a["AlarmName"],
                        alarm_arn=a.get("AlarmArn"),
                        alarm_description=a.get("AlarmDescription"),
                        state=a["StateValue"],
                        region=region,
                        namespace=a.get("Namespace"),
                        metric_name=a.get("MetricName"),
                        updated_at=ts,
                    ))

            # Commit in one shot: delete old + insert new
            db.query(Alarm).filter(Alarm.account_id_fk == db_account_id).delete()
            for row in alarm_rows:
                db.add(Alarm(**row))

            account.sync_status = "ok"
            account.sync_error  = None
            account.last_sync_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            logger.info(f"[sync] OK {label} — {len(alarm_rows)} alarms stored")

        except Exception as exc:
            logger.error(f"[sync] FAIL {label}: {exc}")
            try:
                db.rollback()
                acct = db.query(Account).filter(Account.id == db_account_id).first()
                if acct:
                    acct.sync_status = "error"
                    acct.sync_error  = str(exc)
                    db.commit()
            except Exception as e2:
                logger.error(f"[sync] Could not write error status for account {db_account_id}: {e2}")
    finally:
        db.close()


# ── Mid-level: single customer ────────────────────────────────

def sync_customer(customer_id: int) -> None:
    """
    Sync all accounts of a customer.
    For payer accounts: first discovers sub-accounts via Organizations.
    Each account is synced independently.
    """
    # ── Phase 1: org discovery (payer only) + collect account IDs ──
    account_ids: list[int] = []
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            logger.warning(f"[sync] customer id={customer_id} not found, skipping")
            return

        logger.info(f"[sync] customer='{customer.name}' type={customer.account_type}")

        if customer.account_type == "payer":
            root = db.query(Account).filter(
                Account.customer_id == customer_id,
                Account.is_root == 1,
            ).first()

            if root:
                try:
                    session = aws_client.get_boto3_session(root.role_arn, customer.external_id)
                    org_accounts = aws_client.get_organization_accounts(session)
                    logger.info(f"[sync] customer='{customer.name}' — {len(org_accounts)} org accounts")

                    for oa in org_accounts:
                        existing = db.query(Account).filter(
                            Account.customer_id == customer_id,
                            Account.account_id  == oa["Id"],
                        ).first()

                        if existing:
                            if existing.account_name != oa["Name"]:
                                existing.account_name = oa["Name"]
                        else:
                            role_arn = f"arn:aws:iam::{oa['Id']}:role/AlarmDashboardRole"
                            db.add(Account(
                                customer_id  = customer_id,
                                account_id   = oa["Id"],
                                account_name = oa["Name"],
                                role_arn     = role_arn,
                                is_root      = 0,
                                sync_status  = "pending",
                            ))
                            logger.info(f"[sync] Discovered sub-account {oa['Id']} ({oa['Name']})")

                    db.commit()

                except ValueError as exc:
                    # Non-fatal: log and continue with existing accounts
                    logger.warning(f"[sync] customer='{customer.name}' org discovery failed: {exc}")

        account_ids = [
            a.id for a in
            db.query(Account).filter(Account.customer_id == customer_id).all()
        ]
    finally:
        db.close()

    # ── Phase 2: sync each account independently ──────────────────
    for acct_id in account_ids:
        try:
            sync_account(acct_id)
        except Exception as exc:
            logger.error(f"[sync] Unexpected error for account id={acct_id}: {exc}")


# ── Top-level: all customers ──────────────────────────────────

def sync_all_customers() -> None:
    """Sync every customer in the database."""
    db = SessionLocal()
    try:
        customer_ids = [c.id for c in db.query(Customer).all()]
    finally:
        db.close()

    if not customer_ids:
        logger.debug("[sync] No customers to sync")
        return

    logger.info(f"[sync] Starting full sync — {len(customer_ids)} customer(s)")
    for cid in customer_ids:
        try:
            sync_customer(cid)
        except Exception as exc:
            logger.error(f"[sync] Unexpected error for customer id={cid}: {exc}")
    logger.info("[sync] Full sync complete")


# ── Scheduler lifecycle ───────────────────────────────────────

def setup_scheduler() -> None:
    """Start APScheduler: periodic 5-min sync + one-shot initial sync after 10 s."""
    _scheduler.add_job(
        sync_all_customers,
        "interval",
        minutes=5,
        id="sync_periodic",
        replace_existing=True,
    )
    _scheduler.add_job(
        sync_all_customers,
        "date",
        run_date=datetime.now(timezone.utc) + timedelta(seconds=10),
        id="sync_initial",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("[scheduler] Started — first sync in 10 s, then every 5 min")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] Stopped")
