from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    account_type = Column(Text, nullable=False)   # 'payer' or 'standalone'
    root_account_id = Column(Text, nullable=False)
    role_arn = Column(Text, nullable=False)
    external_id = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    accounts = relationship("Account", back_populates="customer", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(Text, nullable=False)
    account_name = Column(Text)
    role_arn = Column(Text, nullable=False)
    is_root = Column(Integer, default=0)
    last_sync_at = Column(DateTime)
    sync_status = Column(Text, default="pending")
    sync_error = Column(Text)

    customer = relationship("Customer", back_populates="accounts")
    alarms = relationship("Alarm", back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("customer_id", "account_id"),)


class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id_fk = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    alarm_name = Column(Text, nullable=False)
    alarm_arn = Column(Text)
    alarm_description = Column(Text)
    state = Column(Text, nullable=False)          # 'ALARM', 'OK', 'INSUFFICIENT_DATA'
    region = Column(Text, nullable=False)
    namespace = Column(Text)
    metric_name = Column(Text)
    updated_at = Column(DateTime)
    fetched_at = Column(DateTime, server_default=func.now())

    account = relationship("Account", back_populates="alarms")

    __table_args__ = (UniqueConstraint("account_id_fk", "alarm_name", "region"),)
