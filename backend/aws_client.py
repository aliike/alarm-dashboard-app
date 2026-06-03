"""
AWS helper functions — all boto3 interactions live here.
All functions raise ValueError with a human-readable message on failure.
"""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointResolutionError


def get_boto3_session(
    role_arn: str,
    external_id: str | None = None,
    session_name: str = "AlarmDashboard",
) -> boto3.Session:
    """
    AssumeRole into role_arn and return a boto3 Session using the temporary credentials.
    Raises ValueError on any failure.
    """
    try:
        sts = boto3.client("sts")
        kwargs = {
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
            "DurationSeconds": 3600,
        }
        if external_id:
            kwargs["ExternalId"] = external_id

        resp = sts.assume_role(**kwargs)
        creds = resp["Credentials"]

        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )

    except NoCredentialsError:
        raise ValueError(
            "No AWS credentials found. Ensure the EC2 instance has an IAM Instance Profile attached."
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg  = e.response["Error"]["Message"]
        if code == "AccessDenied":
            raise ValueError(
                f"Access denied when assuming role '{role_arn}'. "
                f"Check the Trust Policy allows this EC2's account. AWS: {msg}"
            )
        if code == "NoSuchEntity":
            raise ValueError(f"Role not found: '{role_arn}'. Verify the ARN is correct.")
        raise ValueError(f"AssumeRole failed ({code}): {msg}")


def get_active_regions(session: boto3.Session) -> list[str]:
    """
    Return a list of active AWS region names accessible from this session.
    Raises ValueError on failure.
    """
    try:
        ec2 = session.client("ec2", region_name="us-east-1")
        resp = ec2.describe_regions(
            Filters=[
                {
                    "Name": "opt-in-status",
                    "Values": ["opt-in-not-required", "opted-in"],
                }
            ]
        )
        return [r["RegionName"] for r in resp["Regions"]]
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg  = e.response["Error"]["Message"]
        raise ValueError(f"Failed to list regions ({code}): {msg}")


def get_cloudwatch_alarms(session: boto3.Session, region: str) -> list[dict]:
    """
    Fetch all CloudWatch alarms (all states) in the given region.
    Returns an empty list if the region is inaccessible — caller should log the error.
    """
    try:
        cw = session.client("cloudwatch", region_name=region)
        alarms = []
        paginator = cw.get_paginator("describe_alarms")
        for page in paginator.paginate(AlarmTypes=["MetricAlarm"]):
            for alarm in page.get("MetricAlarms", []):
                alarms.append({
                    "AlarmName":             alarm.get("AlarmName"),
                    "AlarmArn":              alarm.get("AlarmArn"),
                    "AlarmDescription":      alarm.get("AlarmDescription"),
                    "StateValue":            alarm.get("StateValue"),
                    "Namespace":             alarm.get("Namespace"),
                    "MetricName":            alarm.get("MetricName"),
                    "StateUpdatedTimestamp": alarm.get("StateUpdatedTimestamp"),
                })
        return alarms
    except Exception:
        # Region may be disabled or network error — caller logs, we continue
        return []


def get_organization_accounts(session: boto3.Session) -> list[dict]:
    """
    List all ACTIVE accounts in the AWS Organization.
    Raises ValueError — failure here is critical (caller should abort sync).
    """
    try:
        org = session.client("organizations", region_name="us-east-1")
        accounts = []
        paginator = org.get_paginator("list_accounts")
        for page in paginator.paginate():
            for acct in page.get("Accounts", []):
                if acct.get("Status") == "ACTIVE":
                    accounts.append({
                        "Id":     acct["Id"],
                        "Name":   acct.get("Name", ""),
                        "Status": acct["Status"],
                    })
        return accounts
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg  = e.response["Error"]["Message"]
        if code == "AWSOrganizationsNotInUseException":
            raise ValueError("This account is not part of an AWS Organization.")
        if code == "AccessDeniedException":
            raise ValueError(
                f"Access denied for organizations:ListAccounts. "
                f"This permission is required on Payer accounts. AWS: {msg}"
            )
        raise ValueError(f"Failed to list organization accounts ({code}): {msg}")
