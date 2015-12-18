from datetime import datetime
from decimal import Decimal as D

from django.test import TestCase

from ledger.models import Ledger
from ledger.models import LedgerEntry
from ledger.models import Transaction
from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.api.actions import ReconciliationTransactionContext
from ledger.api.actions import TransactionContext
from ledger.api.queries import get_all_transactions_for_object
from ledger.api.queries import get_balances_for_object
from ledger.api.queries import get_ledger_balances_for_transactions
from ledger.tests.factories import CreditCardTransactionFactory
from ledger.tests.factories import OrderFactory
from ledger.tests.factories import UserFactory
from ledger.tests.models import CreditCardTransaction
from ledger.tests.models import Order


def get_full_ledger_for_object_using_reconciliation(obj):
    """
    Get all Transactions for all objects related to `obj`.

    "Related to" above is defined as any object that is in
    `Transaction.related_objects` along with `obj` where that Transaction is of
    type `RECONCILIATION`.

    For instance, if a CreditCardTransaction has been reconciled with
    a particular Order, this function should first find that Reconciliation
    Transaction, and then get all Transactions that are either attached to
    `obj` or any other object that was attached to the Reconciliation
    Transaction, in this case the Revenue Recognition for the original Order,
    the original ledger entry for the CreditCardTransaction, and then finally,
    the Reconciliation entry.
    """
    recon_transactions = (
        get_all_transactions_for_object(obj)
        .filter(type=Transaction.RECONCILIATION)
    )

    linked_objects = []
    for transaction in recon_transactions:
        for related_object in transaction.related_objects.all():
            linked_objects.append(related_object.related_object)

    transactions = []

    for linked_object in linked_objects:
        transactions.extend(get_all_transactions_for_object(linked_object))

    # Cast to set() to de-dupe entries, since `obj` should appear twice for
    # a reconciled entry.
    return set(transactions)


def create_recon_report():
    """
    Return a report for all existing Orders showing their Recon status

    This report has one entry for each order and gives important information
    about that Order: ID, datetime created, the amount originally charged for
    it, and its barcode: its unique identifier in the lab.  Then the remaining
    three columns contain the ID, create datetime, and barcode for the
    CreditCardTransaction that is reconciled to it.

    This report is meant to mimic the one with the same columns we create in
    Looker to perform Revenue Recognition.
    """
    report = ""
    for transaction in Transaction.objects.filter(
            type=Transaction.RECONCILIATION):
        related_objects = {
            type(related_object.related_object): related_object.related_object
            for related_object in transaction.related_objects.all()
        }
        order = related_objects[Order]
        credit_card_transaction = related_objects[CreditCardTransaction]
        report += ",".join(map(str, [
            order.id,
            order.datetime,
            order.amount,
            order.barcode,
            credit_card_transaction.id,
            credit_card_transaction.datetime,
            credit_card_transaction.amount,
        ]))
        report += '\n'
    return report


class TestCompanyWideLedgers(TestCase):
    def setUp(self):
        self.AMOUNT = D(100)
        self.user = UserFactory()

        # Create four company-wide ledgers: "Stripe Cash (unreconciled)",
        # "Stripe Cash (reconciled)", "A/R", and "Revenue".
        self.accounts_receivable = Ledger.objects.get_or_create_ledger_by_name(
            'Accounts Receivable',
            increased_by_debits=True,
        )
        self.stripe_unrecon = Ledger.objects.get_or_create_ledger_by_name(
            'Stripe Cash (unreconciled)',
            increased_by_debits=True,
        )
        self.stripe_recon = Ledger.objects.get_or_create_ledger_by_name(
            'Stripe Cash (reconciled)',
            increased_by_debits=True,
        )
        self.revenue = Ledger.objects.get_or_create_ledger_by_name(
            'Revenue',
            increased_by_debits=False,
        )

    def test_using_company_wide_ledgers_for_reconciliation(self):
        """
        Test ledger behavior with a Recon and Recog proof-of-principle

        This test creates an Order and a CreditCardTransaction and using the
        four Ledgers created in setUp, it makes all of the ledger entries that
        an Order and Transaction would be expected to have.  There are three,
        specifically: Revenue Recognition (CR: Revenue, DR:A/R), recording
        incoming cash (CR: A/R, DR: Stripe Cash (unreconciled)) and
        Reconciliation (CR: Stripe Cash (reconciled), DR: Stripe Cash
        (unreconciled)).

        In table form:

        Event                   | Accounts Receivable (unreconciled) | Revenue | Cash (unreconciled) | Cash (reconciled) | Evidence Models
        ----------------------- | ---------------------------------- | ------- | ------------------- | ----------------- | --------------------------------------------------------------
        Test is complete        | -$500                              | +$500   |                     |                   | `Order`
        Patient pays            | +$500                              |         | -$500               |                   | `CreditCardTransaction`
        Payments are reconciled |                                    |         | +$500               | -$500             | both `Order` and `CreditCardTransaction`
        """  # nopep8
        order = OrderFactory()
        credit_card_transaction = CreditCardTransactionFactory()

        # Assert that this Order looks "unrecognized".
        self.assertEqual(
            get_balances_for_object(order),
            {},
        )

        # Add an entry debiting AR and crediting Revenue: this entry should
        # reference the Order.
        with TransactionContext(order, self.user) as txn_recognize:
            txn_recognize.record_entries([
                LedgerEntry(
                    ledger=self.revenue,
                    amount=credit(self.AMOUNT)),
                LedgerEntry(
                    ledger=self.accounts_receivable,
                    amount=debit(self.AMOUNT)),
            ])

        # Assert that the correct entries were created.
        self.assertEqual(LedgerEntry.objects.count(), 2)
        self.assertEqual(Transaction.objects.count(), 1)

        # Assert that this Order looks "recognized".
        self.assertEqual(
            get_balances_for_object(order),
            {
                self.revenue: -self.AMOUNT,
                self.accounts_receivable: self.AMOUNT,
            },
        )

        # Add an entry crediting "A/R" and debiting "Stripe Cash
        # (unreconciled)": this entry should reference the
        # CreditCardTransaction.
        with TransactionContext(
                credit_card_transaction, self.user) as txn_take_payment:
            txn_take_payment.record_entries([
                LedgerEntry(
                    ledger=self.accounts_receivable,
                    amount=credit(self.AMOUNT)),
                LedgerEntry(
                    ledger=self.stripe_unrecon,
                    amount=debit(self.AMOUNT))
            ])

        # Assert that the correct entries were created
        self.assertEqual(LedgerEntry.objects.count(), 4)
        self.assertEqual(Transaction.objects.count(), 2)

        # Assert the CreditCardTransaction is in "Stripe Cash (unreconciled)".
        self.assertEqual(
            get_balances_for_object(credit_card_transaction),
            {
                self.accounts_receivable: -self.AMOUNT,
                self.stripe_unrecon: self.AMOUNT,
            },
        )

        # Add an entry crediting "Stripe Cash (Unreconciled)" and debiting
        # "Stripe Cash Reconciled": this entry should reference both an Order
        # and a CreditCardTransaction.
        with ReconciliationTransactionContext(
                order,
                self.user,
                secondary_related_objects=[credit_card_transaction]
        ) as txn_reconcile:
            txn_reconcile.record_entries([
                LedgerEntry(
                    ledger=self.stripe_unrecon,
                    amount=credit(self.AMOUNT)),
                LedgerEntry(
                    ledger=self.stripe_recon,
                    amount=debit(self.AMOUNT))
            ])

        # Assert that the correct entries were created.
        self.assertEqual(LedgerEntry.objects.count(), 6)
        self.assertEqual(Transaction.objects.count(), 3)

        # Assert that revenue is recognized and reconciled.
        self.assertEqual(
            get_ledger_balances_for_transactions(
                get_full_ledger_for_object_using_reconciliation(
                    order)),
            {
                self.accounts_receivable: 0,
                self.stripe_unrecon: 0,
                self.stripe_recon: self.AMOUNT,
                self.revenue: -self.AMOUNT,
            },
        )

    def test_creating_demo_reconciliation_report(self):
        """
        Create a Reconciliation Report like the one we need in Website.

        See `create_recon_report` for more details.
        """
        new_now = datetime(2015, 12, 16, 12, 0, 0, 0)
        order1 = OrderFactory(amount=self.AMOUNT)
        order2 = OrderFactory(amount=self.AMOUNT)
        credit_card_transaction1 = CreditCardTransactionFactory(
            amount=self.AMOUNT)
        credit_card_transaction2 = CreditCardTransactionFactory(
            amount=self.AMOUNT)
        order1.datetime = new_now
        order1.save()
        order2.datetime = new_now
        order2.save()
        credit_card_transaction1.datetime = new_now
        credit_card_transaction1.save()
        credit_card_transaction2.datetime = new_now
        credit_card_transaction2.save()

        CASES = [
            (order1, credit_card_transaction1),
            (order2, credit_card_transaction2),
        ]

        for order, credit_card_transaction in CASES:
            with TransactionContext(order, self.user) as txn_recognize:
                txn_recognize.record_entries([
                    LedgerEntry(
                        ledger=self.revenue,
                        amount=credit(self.AMOUNT)),
                    LedgerEntry(
                        ledger=self.accounts_receivable,
                        amount=debit(self.AMOUNT)),
                ])

            with TransactionContext(
                    credit_card_transaction, self.user) as txn_take_payment:
                txn_take_payment.record_entries([
                    LedgerEntry(
                        ledger=self.accounts_receivable,
                        amount=credit(self.AMOUNT)),
                    LedgerEntry(
                        ledger=self.stripe_unrecon,
                        amount=debit(self.AMOUNT))
                ])

            with ReconciliationTransactionContext(
                    order,
                    self.user,
                    secondary_related_objects=[credit_card_transaction]
            ) as txn_reconcile:
                txn_reconcile.record_entries([
                    LedgerEntry(
                        ledger=self.stripe_unrecon,
                        amount=credit(self.AMOUNT)),
                    LedgerEntry(
                        ledger=self.stripe_recon,
                        amount=debit(self.AMOUNT))
                ])

            self.assertEqual(
                get_ledger_balances_for_transactions(
                    get_full_ledger_for_object_using_reconciliation(
                        order)),
                {
                    self.accounts_receivable: 0,
                    self.stripe_unrecon: 0,
                    self.stripe_recon: self.AMOUNT,
                    self.revenue: -self.AMOUNT,
                },
            )

        self.assertEqual(self.accounts_receivable.get_balance(), 0)
        self.assertEqual(self.stripe_recon.get_balance(), self.AMOUNT * 2)
        self.assertEqual(self.stripe_unrecon.get_balance(), 0)
        self.assertEqual(self.revenue.get_balance(), -self.AMOUNT * 2)

        self.assertEqual(
            create_recon_report(),
            "%s,2015-12-16 12:00:00,100.0000,%s,%s,2015-12-16 12:00:00,100.0000\n%s,2015-12-16 12:00:00,100.0000,%s,%s,2015-12-16 12:00:00,100.0000\n" %  # nopep8
            (
                order1.id,
                order1.barcode,
                credit_card_transaction1.id,
                order2.id,
                order2.barcode,
                credit_card_transaction2.id,
            ),
        )


class TestLedger(TestCompanyWideLedgers):
    def test_unicode(self):
        self.assertEqual(
            unicode(self.accounts_receivable), "Accounts Receivable")


class TestGetAllTransactionsForObject(TestCompanyWideLedgers):
    def test_restricting_get_all_transactions_by_ledger(self):
        order = OrderFactory(amount=self.AMOUNT)

        with TransactionContext(order, self.user) as txn_recognize:
            txn_recognize.record_entries([
                LedgerEntry(
                    ledger=self.revenue,
                    amount=credit(self.AMOUNT)),
                LedgerEntry(
                    ledger=self.accounts_receivable,
                    amount=debit(self.AMOUNT)),
            ])

        # NOTE: I'm fudging this TransactionContext a bit for the sake of this
        # test: I'm attaching the txn_take_payment LedgerEntries to `order` and
        # not to a CreditCardTransaction.
        with TransactionContext(order, self.user) as txn_take_payment:
            txn_take_payment.record_entries([
                LedgerEntry(
                    ledger=self.accounts_receivable,
                    amount=credit(self.AMOUNT)),
                LedgerEntry(
                    ledger=self.stripe_unrecon,
                    amount=debit(self.AMOUNT))
            ])

        self.assertEqual(
            set(get_all_transactions_for_object(order)),
            {txn_recognize.transaction, txn_take_payment.transaction})
        self.assertEqual(
            set(get_all_transactions_for_object(
                order, ledgers=[self.revenue])),
            {txn_recognize.transaction})
        self.assertEqual(
            set(get_all_transactions_for_object(
                order, ledgers=[self.stripe_unrecon])),
            {txn_take_payment.transaction})
        self.assertEqual(
            set(get_all_transactions_for_object(
                order, ledgers=[self.revenue, self.stripe_unrecon])),
            {txn_recognize.transaction, txn_take_payment.transaction})
