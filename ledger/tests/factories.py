import factory  # FactoryBoy
from django.contrib.auth import get_user_model

from counsyl.product.ledger.models import Ledger


class UserFactory(factory.DjangoModelFactory):
    """Create User instances with monotonically increasing usernames."""
    class Meta:
        model = get_user_model()
    email = username = factory.Sequence(lambda n: "TransactionUser #%s" % n)


class LedgerFactory(factory.DjangoModelFactory):
    class Meta:
        model = Ledger
