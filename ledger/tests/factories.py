import factory  # FactoryBoy
from django.contrib.auth import get_user_model

from ledger.models import Ledger
from ledger.tests.models import CreditCardTransaction
from ledger.tests.models import Order


class UserFactory(factory.DjangoModelFactory):
    """Create User instances with monotonically increasing usernames."""
    class Meta:
        model = get_user_model()
    email = username = factory.Sequence(lambda n: "TransactionUser #%s" % n)


class LedgerFactory(factory.DjangoModelFactory):
    class Meta:
        model = Ledger


class OrderFactory(factory.DjangoModelFactory):
    class Meta:
        model = Order

    patient_name = factory.Sequence(lambda n: "Patient %s" % n)


class CreditCardTransactionFactory(factory.DjangoModelFactory):
    class Meta:
        model = CreditCardTransaction

    cardholder_name = factory.Sequence(lambda n: "Cardholder %s" % n)
