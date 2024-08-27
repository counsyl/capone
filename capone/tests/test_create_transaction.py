from decimal import Decimal as D

import pytest
from django.utils import timezone

from capone.exceptions import ExistingLedgerEntriesException
from capone.exceptions import NoLedgerEntriesException
from capone.exceptions import TransactionBalanceException
from capone.models import LedgerEntry
from capone.models import Transaction
from capone.api.actions import create_transaction
from capone.api.actions import credit
from capone.api.actions import debit
from capone.api.queries import get_balances_for_object
from capone.api.queries import validate_transaction
from capone.tests.factories import CreditCardTransactionFactory
from capone.tests.factories import LedgerFactory
from capone.tests.factories import OrderFactory
from capone.tests.factories import TransactionTypeFactory
from capone.tests.factories import UserFactory


AMOUNT = D(100)


@pytest.fixture
def create_objects():
    user = UserFactory()
    accounts_receivable = LedgerFactory(name='Accounts Receivable')
    cash_unrecon = LedgerFactory(name='Cash (unreconciled)')
    cash_recon = LedgerFactory(name='Cash (reconciled)')
    revenue = LedgerFactory(name='Revenue', increased_by_debits=False)
    recon_ttype = TransactionTypeFactory(name='Recon')
    return (
        user,
        accounts_receivable,
        cash_unrecon,
        cash_recon,
        revenue,
        recon_ttype,
    )


def test_using_ledgers_for_reconciliation(create_objects):
    """
    Test ledger behavior with a revenue reconciliation worked example.

    This test creates an Order and a CreditCardTransaction and, using the
    four Ledgers created in setUp, it makes all of the ledger entries that
    an Order and Transaction would be expected to have.  There are three,
    specifically: Revenue Recognition (credit: Revenue, debit:A/R), recording
    incoming cash (credit: A/R, debit: Cash (unreconciled)) and Reconciliation
    (credit: Cash (reconciled), debit: Cash (unreconciled)).

    In table form:

    Event                   | Accounts Receivable (unreconciled) | Revenue | Cash (unreconciled) | Cash (reconciled) | Evidence Models
    ----------------------- | ---------------------------------- | ------- | ------------------- | ----------------- | --------------------------------------------------------------
    Test is complete        | -$500                              | +$500   |                     |                   | `Order`
    Patient pays            | +$500                              |         | -$500               |                   | `CreditCardTransaction`
    Payments are reconciled |                                    |         | +$500               | -$500             | both `Order` and `CreditCardTransaction`
    """  # noqa: E501
    (
        user,
        accounts_receivable,
        cash_unrecon,
        cash_recon,
        revenue,
        recon_ttype,
    ) = create_objects
    order = OrderFactory()
    credit_card_transaction = CreditCardTransactionFactory()

    # Assert that this Order looks "unrecognized".
    assert get_balances_for_object(order) == {}

    # Add an entry debiting AR and crediting Revenue: this entry should
    # reference the Order.
    create_transaction(
        user,
        evidence=[order],
        ledger_entries=[
            LedgerEntry(
                ledger=revenue,
                amount=credit(AMOUNT)),
            LedgerEntry(
                ledger=accounts_receivable,
                amount=debit(AMOUNT)),
        ],
    )

    # Assert that the correct entries were created.
    assert LedgerEntry.objects.count() == 2
    assert Transaction.objects.count() == 1

    # Assert that this Order looks "recognized".
    assert get_balances_for_object(order) == {
        revenue: -AMOUNT,
        accounts_receivable: AMOUNT,
    }

    # Add an entry crediting "A/R" and debiting "Cash (unreconciled)": this
    # entry should reference the CreditCardTransaction.
    create_transaction(
        user,
        evidence=[credit_card_transaction],
        ledger_entries=[
            LedgerEntry(
                ledger=accounts_receivable,
                amount=credit(AMOUNT)),
            LedgerEntry(
                ledger=cash_unrecon,
                amount=debit(AMOUNT))
        ],
    )

    # Assert that the correct entries were created
    assert LedgerEntry.objects.count() == 4
    assert Transaction.objects.count() == 2

    # Assert the CreditCardTransaction is in "Cash (unreconciled)".
    assert get_balances_for_object(credit_card_transaction) == {
        accounts_receivable: -AMOUNT,
        cash_unrecon: AMOUNT,
    }

    # Add an entry crediting "Cash (Unreconciled)" and debiting "Cash
    # (Reconciled)": this entry should reference both an Order and
    # a CreditCardTransaction.
    create_transaction(
        user,
        evidence=[order, credit_card_transaction],
        ledger_entries=[
            LedgerEntry(
                ledger=cash_unrecon,
                amount=credit(AMOUNT)),
            LedgerEntry(
                ledger=cash_recon,
                amount=debit(AMOUNT))
        ],
        type=recon_ttype,
    )

    # Assert that the correct entries were created.
    assert LedgerEntry.objects.count() == 6
    assert Transaction.objects.count() == 3

    # Assert that revenue is recognized and reconciled.
    assert get_balances_for_object(order) == {
        accounts_receivable: AMOUNT,
        cash_unrecon: -AMOUNT,
        cash_recon: AMOUNT,
        revenue: -AMOUNT,
    }


def test_setting_posted_timestamp(create_objects):
    (
        user,
        accounts_receivable,
        cash_unrecon,
        cash_recon,
        revenue,
        recon_ttype,
    ) = create_objects
    POSTED_DATETIME = timezone.now()
    order = OrderFactory(amount=AMOUNT)

    txn_recognize = create_transaction(
        user,
        evidence=[order],
        ledger_entries=[
            LedgerEntry(
                ledger=revenue,
                amount=credit(AMOUNT)),
            LedgerEntry(
                ledger=accounts_receivable,
                amount=debit(AMOUNT)),
        ],
        posted_timestamp=POSTED_DATETIME,
    )

    assert txn_recognize.posted_timestamp == POSTED_DATETIME


def test_debits_not_equal_to_credits(create_objects):
    (
        user,
        accounts_receivable,
        cash_unrecon,
        cash_recon,
        revenue,
        recon_ttype,
    ) = create_objects
    with pytest.raises(TransactionBalanceException):
        validate_transaction(
            user,
            ledger_entries=[
                LedgerEntry(
                    ledger=revenue,
                    amount=credit(AMOUNT)),
                LedgerEntry(
                    ledger=accounts_receivable,
                    amount=debit(AMOUNT + 2)),
            ],
        )


def test_no_ledger_entries(create_objects):
    (
        user,
        accounts_receivable,
        cash_unrecon,
        cash_recon,
        revenue,
        recon_ttype,
    ) = create_objects
    with pytest.raises(NoLedgerEntriesException):
        validate_transaction(user)


def test_with_existing_ledger_entry():
    amount = D(100)
    user = UserFactory()

    accounts_receivable = LedgerFactory(name='Accounts Receivable')

    existing_transaction = create_transaction(
        user,
        ledger_entries=[
            LedgerEntry(
                ledger=accounts_receivable,
                amount=credit(amount)),
            LedgerEntry(
                ledger=accounts_receivable,
                amount=debit(amount)),
        ],
    )

    with pytest.raises(ExistingLedgerEntriesException):
        create_transaction(
            user,
            ledger_entries=list(existing_transaction.entries.all()),
        )


def test_credit_and_debit_helper_functions(settings):
    """
    Test that `credit` and `debit` return the correctly signed amounts.
    """
    settings.DEBITS_ARE_NEGATIVE = True
    assert credit(AMOUNT) > 0
    assert debit(AMOUNT) < 0

    settings.DEBITS_ARE_NEGATIVE = False
    assert credit(AMOUNT) < 0
    assert debit(AMOUNT) > 0


def test_validation_error():
    """
    Test that `credit` and `debit` return the correctly signed amounts.
    """
    pytest.raises(ValueError, credit, -AMOUNT)
    pytest.raises(ValueError, debit, -AMOUNT)


def _create_transaction_and_compare_to_amount(
        amount, comparison_amount=None):
    ledger1 = LedgerFactory()
    ledger2 = LedgerFactory()
    transaction = create_transaction(
        UserFactory(),
        ledger_entries=[
            LedgerEntry(
                ledger=ledger1,
                amount=amount),
            LedgerEntry(
                ledger=ledger2,
                amount=-amount),
        ]
    )

    entry1 = transaction.entries.get(ledger=ledger1)
    entry2 = transaction.entries.get(ledger=ledger2)
    if comparison_amount:
        assert entry1.amount != amount
        assert entry1.amount == comparison_amount
        assert entry2.amount != -amount
        assert -entry2.amount == comparison_amount
    else:
        assert entry1.amount == amount
        assert entry2.amount == -amount


def test_precision():
    _create_transaction_and_compare_to_amount(
        D('-499.9999'))


def test_round_up():
    _create_transaction_and_compare_to_amount(
        D('499.99995'), D('500'))


def test_round_down():
    _create_transaction_and_compare_to_amount(
        D('499.99994'), D('499.9999'))


def test_round_up_negative():
    _create_transaction_and_compare_to_amount(
        D('-499.99994'), D('-499.9999'))


def test_round_down_negative():
    _create_transaction_and_compare_to_amount(
        D('-499.99995'), D('-500'))
