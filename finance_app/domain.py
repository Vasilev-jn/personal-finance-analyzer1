from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional


class OperationType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"


@dataclass
class Operation:
    id: str
    account_id: str
    bank: str
    date: date
    amount: Decimal
    currency: str
    type: OperationType
    description: str
    merchant: Optional[str] = None
    mcc: Optional[str] = None
    bank_category: Optional[str] = None
    category_id: Optional[str] = None
    categorization_source: Optional[str] = None
    source_file_id: Optional[str] = None


@dataclass
class Account:
    id: str
    bank: str
    name: str
    number: Optional[str]


@dataclass
class Category:
    id: str
    name: str
    parent_id: Optional[str]


@dataclass
class Vault:
    operations: List[Operation] = field(default_factory=list)
    accounts: Dict[str, Account] = field(default_factory=dict)
    categories: Dict[str, Category] = field(default_factory=dict)

    def reset(self) -> None:
        self.operations.clear()
        self.accounts.clear()

    def ensure_account(self, bank: str, name: str, number: Optional[str]) -> str:
        account_id = f"{bank}:{number or name}"
        if account_id not in self.accounts:
            self.accounts[account_id] = Account(
                id=account_id, bank=bank, name=name, number=number
            )
        return account_id

    def add_operation(self, operation: Operation) -> None:
        self.operations.append(operation)
