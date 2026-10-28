from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal

class TransactionIn(BaseModel):
    kind: Literal['income','expense','transfer']
    amount: float = Field(gt=0, le=1000000000)
    date: str
    category: str = ''
    source: str = ''
    merchant: str = ''
    description: str = ''
    payment_method: str = ''
    account_id: Optional[int] = None
    to_account_id: Optional[int] = None
    tags: str = ''
    notes: str = ''
    goal_id: Optional[int] = None

class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: str = 'Cash'
    opening_balance: float = 0

class BudgetIn(BaseModel):
    month: str = Field(pattern=r'^\d{4}-\d{2}$')
    category: str = 'All expenses'
    amount: float = Field(gt=0)
    recurring: bool = False

class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target_amount: float = Field(gt=0)
    saved_amount: float = Field(ge=0, default=0)
    target_date: Optional[str] = None
    priority: str = 'Medium'
    icon: str = '🎯'
    notes: str = ''

class GoalContribution(BaseModel):
    amount: float = Field(gt=0)
    action: Literal['add','withdraw'] = 'add'

class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: Literal['income','expense']
    color: str = '#62d6ad'
    icon: str = 'circle'

class ImportIn(BaseModel):
    backup: dict
    replace_existing: bool = False
