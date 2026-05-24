import os
import secrets
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import JSON

from finance_app.category_tree import CATEGORY_INDEX
from finance_app.domain import Account, Operation, OperationType, Vault


DEFAULT_DATABASE_URL = "sqlite:///data/moneymap.db"
DATABASE_URL = os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


engine = create_engine(DATABASE_URL, future=True, **_engine_kwargs(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


json_type = JSON().with_variant(JSONB, "postgresql")


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_record: Mapped[dict] = mapped_column(json_type, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SessionModel(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CategoryModel(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)


class AccountModel(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("user_id", "account_id", name="uq_accounts_user_account"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    bank: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)


class UploadedFileModel(Base):
    __tablename__ = "uploaded_files"
    __table_args__ = (UniqueConstraint("user_id", "content_hash", name="uq_uploaded_files_user_hash"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank: Mapped[str] = mapped_column(String(80), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("user_id", "fingerprint", name="uq_transactions_user_fingerprint"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    bank: Mapped[str] = mapped_column(String(80), nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(12), nullable=False)
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    merchant: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mcc: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    bank_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    categorization_source: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    source_file_id: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    profile: Mapped[dict] = mapped_column(json_type, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CategoryCorrectionModel(Base):
    __tablename__ = "category_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    operation_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(json_type, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CustomCategoryMappingModel(Base):
    __tablename__ = "custom_category_mappings"
    __table_args__ = (
        UniqueConstraint("user_id", "bank", "bank_category", name="uq_custom_mapping_user_bank_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    bank: Mapped[str] = mapped_column(String(80), nullable=False)
    bank_category: Mapped[str] = mapped_column(Text, nullable=False)
    base_id: Mapped[str] = mapped_column(String(120), nullable=False)


def configure_database(url: str) -> None:
    global DATABASE_URL, engine, SessionLocal
    DATABASE_URL = url
    engine = create_engine(DATABASE_URL, future=True, **_engine_kwargs(DATABASE_URL))
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def ensure_sqlite_parent() -> None:
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.removeprefix("sqlite:///")
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    ensure_sqlite_parent()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        sync_categories(db)
        db.commit()


def reset_db_for_tests(url: str = "sqlite:///:memory:") -> None:
    configure_database(url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        sync_categories(db)
        db.commit()


def sync_categories(db: Session) -> None:
    existing = {item.id for item in db.scalars(select(CategoryModel)).all()}
    for category_id, category in CATEGORY_INDEX.items():
        if category_id in existing:
            continue
        db.add(CategoryModel(id=category.id, name=category.name, parent_id=category.parent_id))


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def operation_fingerprint(operation: Operation) -> str:
    return "|".join(str(part) for part in Vault._operation_fingerprint(operation))


def account_from_model(item: AccountModel) -> Account:
    return Account(id=item.account_id, bank=item.bank, name=item.name, number=item.number)


def operation_from_model(item: TransactionModel) -> Operation:
    return Operation(
        id=item.id,
        account_id=item.account_id,
        bank=item.bank,
        date=item.date,
        amount=Decimal(item.amount),
        currency=item.currency,
        type=OperationType(item.type),
        description=item.description or "",
        merchant=item.merchant,
        mcc=item.mcc,
        bank_category=item.bank_category,
        category_id=item.category_id,
        categorization_source=item.categorization_source,
        source_file_id=item.source_file_id,
    )


def vault_for_user(db: Session, user_id: int) -> Vault:
    vault = Vault(categories=CATEGORY_INDEX)
    accounts = db.scalars(select(AccountModel).where(AccountModel.user_id == user_id)).all()
    vault.accounts = {item.account_id: account_from_model(item) for item in accounts}
    operations = db.scalars(
        select(TransactionModel).where(TransactionModel.user_id == user_id).order_by(TransactionModel.date.asc())
    ).all()
    vault.operations = [operation_from_model(item) for item in operations]
    return vault


def uploaded_files_for_user(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(select(UploadedFileModel).where(UploadedFileModel.user_id == user_id)).all()
    return [
        {"id": row.id, "name": row.name, "bank": row.bank, "count": row.count}
        for row in rows
    ]


def corrections_for_user(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(
        select(CategoryCorrectionModel)
        .where(CategoryCorrectionModel.user_id == user_id)
        .order_by(CategoryCorrectionModel.id.asc())
    ).all()
    return [dict(row.payload) for row in rows]


def custom_mappings_for_user(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(select(CustomCategoryMappingModel).where(CustomCategoryMappingModel.user_id == user_id)).all()
    return [{"bank": row.bank, "bank_category": row.bank_category, "base_id": row.base_id} for row in rows]


def upsert_accounts(db: Session, user_id: int, accounts: Iterable[Account]) -> None:
    existing = {
        row.account_id: row
        for row in db.scalars(select(AccountModel).where(AccountModel.user_id == user_id)).all()
    }
    for account in accounts:
        row = existing.get(account.id)
        if row:
            row.bank = account.bank
            row.name = account.name
            row.number = account.number
        else:
            db.add(
                AccountModel(
                    user_id=user_id,
                    account_id=account.id,
                    bank=account.bank,
                    name=account.name,
                    number=account.number,
                )
            )


def insert_operations(db: Session, user_id: int, operations: Iterable[Operation]) -> None:
    for op in operations:
        db.add(
            TransactionModel(
                id=op.id,
                user_id=user_id,
                account_id=op.account_id,
                bank=op.bank,
                date=op.date,
                amount=op.amount,
                currency=op.currency,
                type=op.type.value,
                description=op.description or "",
                merchant=op.merchant,
                mcc=op.mcc,
                bank_category=op.bank_category,
                category_id=op.category_id,
                categorization_source=op.categorization_source,
                source_file_id=op.source_file_id,
                fingerprint=operation_fingerprint(op),
            )
        )


def update_operations(db: Session, user_id: int, operations: Iterable[Operation]) -> None:
    ids = [op.id for op in operations]
    if not ids:
        return
    rows = {
        row.id: row
        for row in db.scalars(
            select(TransactionModel).where(TransactionModel.user_id == user_id, TransactionModel.id.in_(ids))
        ).all()
    }
    for op in operations:
        row = rows.get(op.id)
        if not row:
            continue
        row.category_id = op.category_id
        row.categorization_source = op.categorization_source
        row.fingerprint = operation_fingerprint(op)


def add_uploaded_file(db: Session, user_id: int, file_id: str, name: str, bank: str, count: int, content_hash: str) -> None:
    db.add(
        UploadedFileModel(
            id=file_id,
            user_id=user_id,
            name=name,
            bank=bank,
            count=count,
            content_hash=content_hash,
        )
    )


def find_duplicate_file(db: Session, user_id: int, content_hash: str) -> Optional[UploadedFileModel]:
    return db.scalar(
        select(UploadedFileModel).where(
            UploadedFileModel.user_id == user_id,
            UploadedFileModel.content_hash == content_hash,
        )
    )


def save_profile(db: Session, user_id: int, profile: dict) -> None:
    row = db.get(UserProfileModel, user_id)
    if row:
        row.profile = profile
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(UserProfileModel(user_id=user_id, profile=profile))


def load_profile(db: Session, user_id: int) -> Optional[dict]:
    row = db.get(UserProfileModel, user_id)
    return dict(row.profile) if row else None


def add_correction(db: Session, user_id: int, change: dict) -> None:
    db.add(CategoryCorrectionModel(user_id=user_id, operation_id=change.get("operation_id") or "", payload=change))


def replace_corrections(db: Session, user_id: int, corrections: list[dict]) -> None:
    db.query(CategoryCorrectionModel).filter(CategoryCorrectionModel.user_id == user_id).delete()
    for change in corrections:
        add_correction(db, user_id, change)


def upsert_custom_mapping(db: Session, user_id: int, mapping: dict) -> None:
    row = db.scalar(
        select(CustomCategoryMappingModel).where(
            CustomCategoryMappingModel.user_id == user_id,
            CustomCategoryMappingModel.bank == mapping["bank"],
            CustomCategoryMappingModel.bank_category == mapping["bank_category"],
        )
    )
    if row:
        row.base_id = mapping["base_id"]
    else:
        db.add(CustomCategoryMappingModel(user_id=user_id, **mapping))


def replace_custom_mappings(db: Session, user_id: int, mappings: list[dict]) -> None:
    db.query(CustomCategoryMappingModel).filter(CustomCategoryMappingModel.user_id == user_id).delete()
    for mapping in mappings:
        upsert_custom_mapping(db, user_id, mapping)


def delete_file_with_operations(db: Session, user_id: int, file_id: str) -> set[str]:
    operation_ids = {
        op_id
        for op_id in db.scalars(
            select(TransactionModel.id).where(
                TransactionModel.user_id == user_id,
                TransactionModel.source_file_id == file_id,
            )
        ).all()
    }
    db.query(TransactionModel).filter(
        TransactionModel.user_id == user_id,
        TransactionModel.source_file_id == file_id,
    ).delete(synchronize_session=False)
    db.query(UploadedFileModel).filter(
        UploadedFileModel.user_id == user_id,
        UploadedFileModel.id == file_id,
    ).delete(synchronize_session=False)
    if operation_ids:
        db.query(CategoryCorrectionModel).filter(
            CategoryCorrectionModel.user_id == user_id,
            CategoryCorrectionModel.operation_id.in_(operation_ids),
        ).delete(synchronize_session=False)
    return operation_ids


def clear_user_data(db: Session, user_id: int) -> None:
    for model in (
        TransactionModel,
        UploadedFileModel,
        AccountModel,
        CategoryCorrectionModel,
        CustomCategoryMappingModel,
    ):
        db.query(model).filter(model.user_id == user_id).delete(synchronize_session=False)
    row = db.get(UserProfileModel, user_id)
    if row:
        db.delete(row)


def issue_token(db: Session, user_id: int, expires_at: datetime) -> str:
    token = secrets.token_urlsafe(32)
    db.add(SessionModel(token=token, user_id=user_id, expires_at=expires_at))
    return token


def revoke_token(db: Session, token: str) -> None:
    if token:
        db.query(SessionModel).filter(SessionModel.token == token).delete(synchronize_session=False)


def cleanup_sessions(db: Session) -> None:
    db.query(SessionModel).filter(SessionModel.expires_at <= datetime.now(timezone.utc)).delete(synchronize_session=False)
