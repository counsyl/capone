from decimal import Decimal as D

from django.test import TestCase

from ledger.models import Ledger
from ledger.models import LedgerEntry
from ledger.models import Transaction
from ledger.api.actions import TransactionContext
from ledger.api.queries import get_balances_for_object
from ledger.api.queries import get_all_transactions_for_object
from ledger.tests.factories import CreditCardTransactionFactory
from ledger.tests.factories import OrderFactory
from ledger.tests.factories import UserFactory


class TestCompanyWideLedgers(TestCase):
    def test_using_company_wide_ledgers_for_reconciliation(self):
        AMOUNT = D(100)
        user = UserFactory()
        order = OrderFactory()
        credit_card_transaction = CreditCardTransactionFactory()

        # create four company-wide ledgers: "Stripe Cash (unreconciled)",
        # "Stripe Cash (reconciled)", "A/R", and "Revenue"
        accounts_receivable = Ledger.objects.get_or_create_ledger_by_name(
            'Accounts Receivable',
            are_debits_positive=True,
        )
        stripe_unrecon = Ledger.objects.get_or_create_ledger_by_name(
            'Stripe Cash (unreconciled)',
            are_debits_positive=True,
        )
        stripe_recon = Ledger.objects.get_or_create_ledger_by_name(
            'Stripe Cash (reconciled)',
            are_debits_positive=True,
        )
        revenue = Ledger.objects.get_or_create_ledger_by_name(
            'Revenue',
            are_debits_positive=False,
        )

        # assert that this Order looks "unrecognized"
        self.assertEqual(
            get_balances_for_object(order),
            {},
        )

        # add an entry debiting AR and crediting Revenue: this entry should
        # reference the Order
        with TransactionContext(order, user) as txn_recognize:
            txn_recognize.record_entries([
                LedgerEntry(ledger=revenue, amount=AMOUNT),
                LedgerEntry(ledger=accounts_receivable, amount=-AMOUNT),
            ])

        # assert that the correct entries were created
        self.assertEqual(LedgerEntry.objects.count(), 2)
        self.assertEqual(Transaction.objects.count(), 1)

        # assert that this Order looks "recognized"
        self.assertEqual(
            get_balances_for_object(order),
            {
                revenue: AMOUNT,
                accounts_receivable: -AMOUNT,
            },
        )
        # TODO: assert Ledger balances

        # add an entry crediting AR and debiting Stripe/un: this entry should
        # reference the PGXX
        with TransactionContext(
                credit_card_transaction, user) as txn_recognize:
            txn_recognize.record_entries([
                LedgerEntry(ledger=accounts_receivable, amount=AMOUNT),
                LedgerEntry(ledger=stripe_unrecon, amount=-AMOUNT)
            ])

        # assert that the correct entries were created
        self.assertEqual(LedgerEntry.objects.count(), 4)
        self.assertEqual(Transaction.objects.count(), 2)

        # assert the credit card transaction is in stripe_unrecon
        self.assertEqual(
            get_balances_for_object(credit_card_transaction),
            {
                accounts_receivable: AMOUNT,
                stripe_unrecon: -AMOUNT,
            },
        )
        # TODO: assert Ledger balances

        # add an entry crediting Stripe/un and debiting Stripe/recon: this
        # entry should reference both an Order and a PGXX
        with TransactionContext(
                order,
                user,
                secondary_related_objects=[credit_card_transaction]
        ) as txn_recognize:
            txn_recognize.record_entries([
                LedgerEntry(ledger=stripe_unrecon, amount=AMOUNT),
                LedgerEntry(ledger=stripe_recon, amount=-AMOUNT)
            ])

        # assert that the correct entries were created
        self.assertEqual(LedgerEntry.objects.count(), 6)
        self.assertEqual(Transaction.objects.count(), 3)

        # TODO: assert that revenue is recognized and reconciled
        # TODO: assert Ledger balances

    def test_adding_more_than_two_ledger_entries(self):
        pass
