from datetime import datetime, timezone

from typing import List, Optional

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, Boolean, Enum

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

import enum


class Base(DeclarativeBase):

    pass


class OrderType(enum.Enum):

    BUY = "buy"

    SELL = "sell"

    MIX = "mix"


class OrderStatus(enum.Enum):

    PENDING = "pending"

    PROCESSING = "processing"

    COMPLETED = "completed"

    CANCELLED = "cancelled"


class User(Base):

    __tablename__ = "users"


    id: Mapped[int] = mapped_column(primary_key=True)

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)

    username: Mapped[Optional[str]] = mapped_column(String(255))

    balance: Mapped[float] = mapped_column(Float, default=0.0)

    referral_code: Mapped[str] = mapped_column(String(50), unique=True)

    referrer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    language: Mapped[str] = mapped_column(String(5), default="ru")

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


    orders: Mapped[List["Order"]] = relationship(back_populates="user")

    referrals = relationship("User", backref="referrer", remote_side=[id])


class Order(Base):

    __tablename__ = "orders"


    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    type: Mapped[OrderType] = mapped_column(Enum(OrderType))

    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING)


    amount_in: Mapped[float] = mapped_column(Float)

    currency_in: Mapped[str] = mapped_column(String(20))

    amount_out: Mapped[float] = mapped_column(Float)

    currency_out: Mapped[str] = mapped_column(String(20))


    payment_method: Mapped[Optional[str]] = mapped_column(String(50))

    wallet_address: Mapped[Optional[str]] = mapped_column(String(255))



    requisites_phone: Mapped[Optional[str]] = mapped_column(String(20))

    requisites_fio: Mapped[Optional[str]] = mapped_column(String(255))

    bank_name: Mapped[Optional[str]] = mapped_column(String(100))


    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


    user: Mapped["User"] = relationship(back_populates="orders")


class Rate(Base):

    __tablename__ = "rates"


    id: Mapped[int] = mapped_column(primary_key=True)

    currency: Mapped[str] = mapped_column(String(20), unique=True)

    buy_rate: Mapped[float] = mapped_column(Float)

    sell_rate: Mapped[float] = mapped_column(Float)

    last_updated: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PaymentMethod(Base):

    __tablename__ = "payment_methods"


    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(100))

    type: Mapped[str] = mapped_column(String(20))                  

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FileCache(Base):

    __tablename__ = "file_cache"


    key: Mapped[str] = mapped_column(String(100), primary_key=True)

    file_id: Mapped[str] = mapped_column(String(255))


class Setting(Base):

    __tablename__ = "settings"


    key: Mapped[str] = mapped_column(String(100), primary_key=True)

    value: Mapped[str] = mapped_column(String(255))

