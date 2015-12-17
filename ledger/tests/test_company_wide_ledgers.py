from datetime import datetime
from decimal import Decimal as D

from django.test import TestCase

from ledger.models import Ledger
from ledger.models import LedgerEntry
from ledger.models import Transaction
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

    # Cast to set() to de-dupe entries, since obj should appear twice for
    # a reconciled entry.
    return set(transactions)


def create_recon_report():
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

        # create four company-wide ledgers: "Stripe Cash (unreconciled)",
        # "Stripe Cash (reconciled)", "A/R", and "Revenue"
        self.accounts_receivable = Ledger.objects.get_or_create_ledger_by_name(
            'Accounts Receivable',
            are_debits_positive=True,
        )
        self.stripe_unrecon = Ledger.objects.get_or_create_ledger_by_name(
            'Stripe Cash (unreconciled)',
            are_debits_positive=True,
        )
        self.stripe_recon = Ledger.objects.get_or_create_ledger_by_name(
            'Stripe Cash (reconciled)',
            are_debits_positive=True,
        )
        self.revenue = Ledger.objects.get_or_create_ledger_by_name(
            'Revenue',
            are_debits_positive=False,
        )

    def test_using_company_wide_ledgers_for_reconciliation(self):
        """
        Test ledger behavior with a Recon and Recog proof-of-principle

        TODO: more
        """
        order = OrderFactory()
        credit_card_transaction = CreditCardTransactionFactory()

        # assert that this Order looks "unrecognized"
        self.assertEqual(
            get_balances_for_object(order),
            {},
        )

        # add an entry debiting AR and crediting Revenue: this entry should
        # reference the Order
        with TransactionContext(order, self.user) as txn_recognize:
            txn_recognize.record_entries([
                LedgerEntry(
                    ledger=self.revenue, amount=self.AMOUNT),
                LedgerEntry(
                    ledger=self.accounts_receivable, amount=-self.AMOUNT),
            ])

        # assert that the correct entries were created
        self.assertEqual(LedgerEntry.objects.count(), 2)
        self.assertEqual(Transaction.objects.count(), 1)

        # assert that this Order looks "recognized"
        self.assertEqual(
            get_balances_for_object(order),
            {
                self.revenue: self.AMOUNT,
                self.accounts_receivable: -self.AMOUNT,
            },
        )

        # add an entry crediting AR and debiting Stripe/un: this entry should
        # reference the PGXX
        with TransactionContext(
                credit_card_transaction, self.user) as txn_take_payment:
            txn_take_payment.record_entries([
                LedgerEntry(
                    ledger=self.accounts_receivable, amount=self.AMOUNT),
                LedgerEntry(
                    ledger=self.stripe_unrecon, amount=-self.AMOUNT)
            ])

        # assert that the correct entries were created
        self.assertEqual(LedgerEntry.objects.count(), 4)
        self.assertEqual(Transaction.objects.count(), 2)

        # assert the credit card transaction is in stripe_unrecon
        self.assertEqual(
            get_balances_for_object(credit_card_transaction),
            {
                self.accounts_receivable: self.AMOUNT,
                self.stripe_unrecon: -self.AMOUNT,
            },
        )

        # add an entry crediting Stripe/un and debiting Stripe/recon: this
        # entry should reference both an Order and a PGXX
        with ReconciliationTransactionContext(
                order,
                self.user,
                secondary_related_objects=[credit_card_transaction]
        ) as txn_reconcile:
            txn_reconcile.record_entries([
                LedgerEntry(ledger=self.stripe_unrecon, amount=self.AMOUNT),
                LedgerEntry(ledger=self.stripe_recon, amount=-self.AMOUNT)
            ])

        # assert that the correct entries were created
        self.assertEqual(LedgerEntry.objects.count(), 6)
        self.assertEqual(Transaction.objects.count(), 3)

        # assert that revenue is recognized and reconciled
        self.assertEqual(
            get_ledger_balances_for_transactions(
                get_full_ledger_for_object_using_reconciliation(
                    order)),
            {
                self.accounts_receivable: 0,
                self.stripe_unrecon: 0,
                self.stripe_recon: -self.AMOUNT,
                self.revenue: self.AMOUNT,
            },
        )

    def test_creating_demo_reconciliation_report(self):
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
                        ledger=self.revenue, amount=self.AMOUNT),
                    LedgerEntry(
                        ledger=self.accounts_receivable, amount=-self.AMOUNT),
                ])

            with TransactionContext(
                    credit_card_transaction, self.user) as txn_take_payment:
                txn_take_payment.record_entries([
                    LedgerEntry(
                        ledger=self.accounts_receivable, amount=self.AMOUNT),
                    LedgerEntry(
                        ledger=self.stripe_unrecon, amount=-self.AMOUNT)
                ])

            with ReconciliationTransactionContext(
                    order,
                    self.user,
                    secondary_related_objects=[credit_card_transaction]
            ) as txn_reconcile:
                txn_reconcile.record_entries([
                    LedgerEntry(
                        ledger=self.stripe_unrecon, amount=self.AMOUNT),
                    LedgerEntry(
                        ledger=self.stripe_recon, amount=-self.AMOUNT)
                ])

            self.assertEqual(
                get_ledger_balances_for_transactions(
                    get_full_ledger_for_object_using_reconciliation(
                        order)),
                {
                    self.accounts_receivable: 0,
                    self.stripe_unrecon: 0,
                    self.stripe_recon: -self.AMOUNT,
                    self.revenue: self.AMOUNT,
                },
            )

        self.assertEqual(self.accounts_receivable.get_balance(), 0)
        self.assertEqual(self.stripe_recon.get_balance(), -self.AMOUNT * 2)
        self.assertEqual(self.stripe_unrecon.get_balance(), 0)
        self.assertEqual(self.revenue.get_balance(), self.AMOUNT * 2)

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
                    ledger=self.revenue, amount=self.AMOUNT),
                LedgerEntry(
                    ledger=self.accounts_receivable, amount=-self.AMOUNT),
            ])

            # NOTE: I'm fudging this TransactionContext a bit for the sake of
            # this test: I'm attaching the txn_take_payment LedgerEntries to
            # `order` and not to a CreditCardTransaction.
        with TransactionContext(order, self.user) as txn_take_payment:
            txn_take_payment.record_entries([
                LedgerEntry(
                    ledger=self.accounts_receivable, amount=self.AMOUNT),
                LedgerEntry(
                    ledger=self.stripe_unrecon, amount=-self.AMOUNT)
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
