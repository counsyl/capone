Capone
======

*Never let your books land you in the pen.*

|Al Capone's Miami Mugshot|

``Capone`` is a library that provides double-entry bookkeeping (the
foundation of all modern accounting) for Django with the ability to link
each recorded transaction to zero or more other Django models as
evidence for that transaction.

Introduction
------------

In double-entry bookkeeping (DEB), all recordable events (purchases,
sales, equipment depreciation, bad debt markdowns, etc.) are tracked as
"ledger entries" or "transactions" in "ledgers". Each ledger entry is
made up of one or more "credit" and one or more "debit" entries. For the
sake of this brief example, you can think of credits as increasing the
amount of money recorded in a ledger and a debit decreasing it. With
that assumption, the central idea behind double-entry bookkeeping is
that the sum of every ledger entry's debits must equal the sum of its
credits. ``capone`` implements a double-entry bookkeeping system by
providing an API for checking that all created entries satisfy this
condition or rolling back the transaction if not.

In addition to this standard bookkeeping functionality, ``capone`` also
allows any number of arbitrary objects to be attached, via generic
foreign keys, to a ledger entry as "evidence" for that transaction's
having happened. For instance, a transaction recording a bank deposit
paying for several medical tests at a time from an insurance company to
your medical testing company could be linked to the original ``Order``
objects that recorded the test. ``capone`` also provides an API for the
efficient querying of ledger entries by evidence.

For more information on the concept of double-entry bookkeeping itself,
we recommend the Wikipedia article:
`https://en.wikipedia.org/wiki/Double-entry_bookkeeping_system <https://en.wikipedia.org/wiki/Double-entry_bookkeeping_system>`__.

Local Development
-----------------

Setup:
~~~~~~

First, you must set up your working environment:

::

   make setup

This will build a local virtualenv and all other requirements for local
development.

Running Commands:
~~~~~~~~~~~~~~~~~

The following commands are available for interacting with the app:

To start a shell instance so that you can interact with the app via the
ORM:

::

   make shell

Note: before any of the following instructions, you may have to run
``make develop`` to set up a postgres database for this app.

First, activate a virtualenv so that your commands have access to the
environment built by ``make setup``:

From the repository root, run:

::

   source .venv/bin/activate

Then you should be free to run

::

   ./manage.py makemigrations --settings=capone.tests.settings

or any other ``manage.py`` command, even those in the Makefile.

To run individual tests, use the following:

::

   ./manage.py test --settings=capone.tests.settings capone.tests

Notice the ``--settings=capone.tests.settings`` argument: because this
repository is a django sub-module, it wouldn't make sense for it to come
with its own default ``settings.py`` file. Instead, it ships with one
used to run its tests. To use ``manage.py``, we have to pass an import
path to the settings file explicitly.

Models
------

Let's introduce the models provided by ``capone`` and how they relate to
one another.

Note that all objects in this library have ``created_at`` and
``modified_at`` fields that are ``auto_now_add`` and ``auto_now``,
respectively.

Accounting Models
~~~~~~~~~~~~~~~~~

The models in this section are those that correspond most to well known
accounting concepts, i.e. those involved in keeping accounts using the
principles of double-entry bookkeeping. They model ledgers, journal
entries, credits and debits, and any metadata one wishes to store with
these objects.

Ledger
^^^^^^

A ``Ledger`` is the top-most level of organization of information in
double-entry bookkeeping as well as the ``capone`` app. Most ledgers
have names familiar to those with any knowledge of accounting, such as
"revenue" or "accounts receivable".

``Ledgers`` are synonymous with the accounting concept of an "account",
so you may see references to accounts in this documentation or elsewhere
in the accounting literature.

As a data structure, a ``Ledger`` in this library is little more than a
name, description, and unique number: ``LedgerEntries`` (see below)
point to a ``Ledger`` to represent their being "in" a ``Ledger``.
``Transactions`` (see below also) that are "between" two ``Ledgers``
have a ``LedgerEntry`` pointing to one ``Ledger`` and another
``LedgerEntry`` pointing to the other ``Ledger``.

``increased_by_debits``
'''''''''''''''''''''''

``Ledger`` also has the sometimes confusing field
``increased_by_debits``. All ``Ledgers`` are of one of two types: either
debits increase the "value" of an account or credits do. By convention,
asset and expense accounts are of the former type, while liabilities,
equity, and revenue are of the latter: in short, an increase to an
"asset"-type account is a debit, and an increase to a "liability" or
"equity"-type account is a credit.

Here's a handy mnemonic for the two types of accounts: The accounting
equation says (by definition) that:

::

   assets == liabilities + owner equity

The terms on the right of the equals sign are increased by debits, and
terms on the left of the equals sign are decreased by debits. We can
therefore use the accounting equation to know whether to use debits or
credits to model an increase in a ledger.

**So because debits and credits mean different things in different types
of accounts, we can have a transaction with an "equal and opposite"
credit and debit pair of the same currency amount, but that still
represents a net increase in the value of a company: a debit in Accounts
Receivable and a credit in Revenue increases both accounts while
satisfying the accounting equation.**

Currently, field ``increased_by_debits`` is not used by the code in
``capone`` but is provided as a convenience to users who might wish to
incorporate this information into an external report or calculation.

Transaction
^^^^^^^^^^^

A ``Transaction`` is a record of a discrete financial action,
represented by a collection of debits and credits whose sums equal one
another. Practically all models in ``capone`` link to or through
``Transaction``: in a sense you could say it's the main model provided
by ``capone``. A ``Transaction`` can sometimes be referred to as a
"journal entry".

The ``Transaction`` model records debits and credits by linking to
``LedgerEntries``, which include currency amounts of the proper sign,
and those ``LedgerEntries`` themselves point to ``Ledger``. In other
words, ``Transaction`` and ``Ledger`` are linked in a many-to-many
fashion by going through ``LedgerEntry`` as a custom through model. The
"proper sign" part is taken care of by the ``credit`` and ``debit``
convenience methods (see examples below).

``Transactions`` should never be deleted. Instead, a new ``Transaction``
with debits and credits swapped should be created using
``capone.api.actions.void_transaction`` to negate the effect of the
``Transaction`` you'd like to remove. The ``voids`` field on the new
``Transaction`` will automatically be filled in with the old
``Transaction`` you wish to remove. By this method, you'll never have to
delete data from your system as a part of normal operation, which mimics
one of the many benefits of traditional, non-computerized double-entry
bookkeeping.

``Transaction`` also has the following fields to provide metadata for
each transaction:

-  ``created_by``: The user who created this ``Transaction``.
-  ``notes``: A free-form text field for adding to a ``Transaction`` any
   information not expressed in the numerous metadata fields.
-  ``posted_timestamp``: The time a ``Transaction`` should be considered
   valid from. ``capone.api.actions.create_transaction`` automatically
   deals with filling in this value with the current time. You can
   change this value to post-date or back-date ``Transactions`` because
   ``created_at`` will always represent the true object creation time.
-  ``transaction_id``: A Universally Unique Identifier (UUID) for the
   ``Transaction``, useful for unambiguously referring to a
   ``Transaction`` without using primary keys or other database
   internals.
-  ``type``: A user-defined type for the ``Transaction`` (see the
   ``TransactionType`` model below).

TransactionType
^^^^^^^^^^^^^^^

A ``TransactionType`` is a user-defined, human-readable "type" for a
``Transaction``, useful for sorting, aggregating, or annotating
``Transactions``. The default ``TransactionType`` is ``MANUAL``, which
is created automatically by the library, but you can define others, say
for bots or certain classes of users.

Currently, ``TransactionType`` is not used by the code in ``capone`` but
is provided as a convenience to users who might wish to incorporate this
information into an external report or calculation.

LedgerEntry
^^^^^^^^^^^

``LedgerEntries`` represent single debit or credit entries in a single
``Ledger``. ``LedgerEntries`` are grouped together into ``Transactions``
(see above) with the constraint that the sum of all credit and debit
``LedgerEntries`` for a given ``Transaction`` must equal zero.

``LedgerEntries`` have a field ``entry_id``, which is a UUID for
unambiguously referring to a single ``LedgerEntry``.

Evidence Models
~~~~~~~~~~~~~~~

The models in this section deal with adding evidence to ``Transactions``
and searching over that evidence.

TransactionRelatedObject
^^^^^^^^^^^^^^^^^^^^^^^^

A ``TransactionRelatedObject`` (``TRO``) represents the "evidence"
relationship that makes the ``capone`` library more useful. A ``TRO``
links a ``Transaction`` to an arbitrary object in the larger app that
this library is used in using a generic foreign key. One ``TRO`` links
one ``Transaction`` and one arbitrary object, so we make as many
``TROs`` as we want pieces of evidence. There are several convenience
methods in ``capone.api.queries`` for efficiently querying over
``Transactions`` based on evidence and evidence objects based on their
``Transactions`` (see examples below).

LedgerBalance
^^^^^^^^^^^^^

A ``LedgerBalance`` is similar to a ``TRO`` in that it allows linking
``ledger`` objects with objects from the wider app that the library is
used in via generic foreign keys. The purpose of ``LedgerBalance`` is to
denormalize for more efficient querying the current sum of debits and
credits for an object in a specific Ledger. Therefore, there is only one
``LedgerBalance`` for each ``(ledger, related_object)`` tuple.

You should never have to manually create or edit a ``LedgerBalance``:
doing so, as well as keeping them up-to-date, is handled by ``capone``
internals. For the same reasons, deleting them is not necessary or a
good idea.

The purpose of ``LedgerBalance`` can best be demonstrated by considering
the deceptively simple query, "how many Orders (a non-``capone`` model
we presumably created in the app where we include ``capone`` as a
library) have an Accounts Receivable balance greater than zero?" One
would have to calculate the ledger balance over literally the product of
all ledgers and all non-``capone`` objects in the database, and then
filter them for all those with balances above zero, to answer this
question, which is obviously too expensive. By keeping track of the
per-``Ledger`` balance for each object used as evidence in a
``Transaction``, we can much more easily make these queries with
reasonable overhead.

Usage
-----

Creating Ledgers
~~~~~~~~~~~~~~~~

Let's start by creating two common ledger types, "Accounts Receivable"
and "Revenue", which usually have transactions between themselves:

::

   >>> from capone.models import Ledger
   >>> ar = Ledger.objects.create(name='Accounts Receivable', number=1, increased_by_debits=True)
   <Ledger: Ledger Accounts Receivable>
   >>> revenue = Ledger.objects.create(name='Revenue', number=2, increased_by_debits=True)
   <Ledger: Ledger Revenue>

Both of these accounts are asset accounts, so they're both increased by
debits. Please consult the double-entry bookkeeping Wikipedia article or
the explanation for ``increased_by_debits`` above for a more in-depth
explanation of the "accounting equation" and whether debits increase or
decrease an account.

Also, note that the default convention in ``capone`` is to store debits
as positive numbers and credits as negative numbers. This convention is
common but completely arbitrary. If you want to switch the convention
around, you can set ``DEBITS_ARE_NEGATIVE`` to ``True`` in your
settings.py file. By default, that constant doesn't need to be defined,
and if it remains undefined, ``capone`` will interpret its value as
``False``.

Faking Evidence Models
~~~~~~~~~~~~~~~~~~~~~~

Now let's create a fake Order, so that we have some evidence for these
ledger entries, and a fake User, so we'll have someone to blame for
these transactions:

::

   >>> from capone.tests.factories import OrderFactory
   >>> order = OrderFactory()
   >>> from capone.tests.factories import UserFactory
   >>> user = UserFactory()

Creating Transactions
~~~~~~~~~~~~~~~~~~~~~

We're now ready to create a simple transaction:

::

   >>> from capone.api.actions import create_transaction
   >>> from capone.api.actions import credit
   >>> from capone.api.actions import debit
   >>> from decimal import Decimal
   >>> from capone.models import LedgerEntry
   >>> txn = create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])
   >>> txn.summary()
   {
       u'entries': [
           'LedgerEntry: $100.0000 in Accounts Receivable',
           'LedgerEntry: $-100.0000 in Revenue',
       ],
       u'related_objects': [
           'TransactionRelatedObject: Order(id=1)',
       ]
   }

Note that we use the helper functions ``credit`` and ``debit`` with
positive numbers to keep the signs consistent in our code. There should
be no reason to use negative numbers with ``capone``.

Note also that the value for the credit and debit is the same: $100. If
we tried to create a transaction with mismatching amounts, we would get
an error:

::

   >>> create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(101)), ledger=revenue)])
   ---------------------------------------------------------------------------
   TransactionBalanceException               Traceback (most recent call last)

   [...]

   TransactionBalanceException: Credits do not equal debits. Mis-match of -1.

So the consistency required of double-entry bookkeeping is automatically
kept.

There are many other options for ``create_transaction``: see below or
its docstring for details.

Ledger Balances
~~~~~~~~~~~~~~~

``capone`` keeps track of the balance in each ledger for each evidence
object in a denormalized and efficient way. Let's use this behavior to
get the balances of our ledgers as well as the balances in each ledger
for our ``order`` object:

::

   >>> from capone.api.queries import get_balances_for_object

   >>> get_balances_for_object(order)
   defaultdict(<function <lambda> at 0x7fd7ecfa96e0>, {<Ledger: Ledger Accounts Receivable>: Decimal('100.0000'), <Ledger: Ledger Revenue>: Decimal('-100.0000')})

   >>> ar.get_balance()
   Decimal('100.0000')

   >>> revenue.get_balance()
   Decimal('-100.0000')

Voiding Transactions
~~~~~~~~~~~~~~~~~~~~

We can also void that transaction, which enters a transaction with the
same evidence but with all values of the opposite sign:

::

   >>> from capone.api.actions import void_transaction
   >>> void = void_transaction(txn, user)
   <Transaction: Transaction 9cd85014-c588-43ff-9532-a6fc2429069e>

   >>> void_transaction(txn, user)
   ---------------------------------------------------------------------------
   UnvoidableTransactionException            Traceback (most recent call last)

   [...]

   UnvoidableTransactionException: Cannot void the same Transaction #(e0842107-3a5b-4487-9b86-d1a5d7ab77b4) more than once.

   >>> void.summary()
   {u'entries': ['LedgerEntry: $-100.0000 in Accounts Receivable',
     'LedgerEntry: $100.0000 in Revenue'],
    u'related_objects': ['TransactionRelatedObject: Order(id=1)']}

   >>> txn.voids

   >>> void.voids
   <Transaction: Transaction e0842107-3a5b-4487-9b86-d1a5d7ab77b4>

Note the new balances for evidence objects and ``Ledgers``:

::

   >>> get_balances_for_object(order)
   defaultdict(<function <lambda> at 0x7fd7ecfa9758>, {<Ledger: Ledger Accounts Receivable>: Decimal('0.0000'), <Ledger: Ledger Revenue>: Decimal('0.0000')})

   >>> ar.get_balance()
   Decimal('0.0000')

   >>> revenue.get_balance()
   Decimal('0.0000')

Transaction Types
~~~~~~~~~~~~~~~~~

You can label a ``Transaction`` using a foreign key to the
``TransactionType`` to, say, distinguish between manually made
``Transactions`` and those made by a bot, or between ``Transactions``
that represent two different types of financial transaction, such as
"Reconciliation" and "Revenue Recognition".

By default, ``Transactions`` are of a special, auto-generated "manual"
type:

::

   >>> txn.type
   <TransactionType: Transaction Type Manual>

but you can create and assign ``TransactionTypes`` when creating
``Transactions``:

::

   >>> from capone.models import TransactionType
   >>> new_type = TransactionType.objects.create(name='New type')
   >>> txn = create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)], type=new_type)
   >>> txn.type
   <TransactionType: Transaction Type New type>

Querying Transactions
~~~~~~~~~~~~~~~~~~~~~

Getting Balances
^^^^^^^^^^^^^^^^

``Transaction`` has a ``summary`` method to summarize the data on the
many models that can link to it:

::

   >>> txn.summary()
   {u'entries': ['LedgerEntry: $100.0000 in Accounts Receivable',
     'LedgerEntry: $-100.0000 in Revenue'],
    u'related_objects': ['TransactionRelatedObject: Order(id=1)']}

To get the balance for a ``Ledger``, use its ``get_balance`` method:

::

   >>> ar.get_balance()
   Decimal('100.0000')

To efficiently get the balance of all transactions with a particular
object as evidence, use ``get_balances_for_objects``:

::

   >>> get_balances_for_object(order)
   defaultdict(<function <lambda> at 0x7fd7ecfa9230>, {<Ledger: Ledger Accounts Receivable>: Decimal('100.0000'), <Ledger: Ledger Revenue>: Decimal('-100.0000')})

``Transactions`` are validated before they are created, but if you need
to do this manually for some reason, use the ``validate_transaction``
function, which has the same prototype as ``create_transaction``:

::

   >>> validate_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)], type=new_type)
   >>> validate_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(101)), ledger=revenue)], type=new_type)
   ---------------------------------------------------------------------------
   TransactionBalanceException               Traceback (most recent call last)
   <ipython-input-64-07b6d139bb37> in <module>()
   ----> 1 validate_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(101)), ledger=revenue)], type=new_type)

   /home/hunter/capone/capone/api/queries.pyc in validate_transaction(user, evidence, ledger_entries, notes, type, posted_timestamp)
        67     if total != Decimal(0):
        68         raise TransactionBalanceException(
   ---> 69             "Credits do not equal debits. Mis-match of %s." % total)
        70
        71     if not ledger_entries:

   TransactionBalanceException: Credits do not equal debits. Mis-match of -1.

Queries
~~~~~~~

Along with the query possibilities from the Django ORM, ``capone``
provides ``Transaction.filter_by_related_objects`` for finding
``Transactions`` that are related to certain models as evidence.

::

   >>> Transaction.objects.count()
   5

   >>> Transaction.objects.filter_by_related_objects([order]).count()
   5

   >>> order2 = OrderFactory()

   >>> create_transaction(user, evidence=[order2], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])
   <Transaction: Transaction 68a4adb1-b898-493f-b5f3-4fe7132dd28d>

   >>> Transaction.objects.filter_by_related_objects([order2]).count()
   1

``filter_by_related_objects`` is defined on a custom ``QuerySet``
provided for ``Transaction``, so calls to it can be chained like
ordinary ``QuerySet`` function calls:

::

   >>> create_transaction(user, evidence=[order2], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])
   <Transaction: Transaction 92049712-4982-4718-bc71-a405b0d762ac>

   >>> Transaction.objects.filter_by_related_objects([order2]).count()
   2

   >>> Transaction.objects.filter_by_related_objects([order2]).filter(transaction_id='92049712-4982-4718-bc71-a405b0d762ac').count()
   1

``filter_by_related_objects`` takes an optional ``match_type`` argument,
which is of type ``MatchType(Enum)`` that allows one to filter in
different ways, namely whether the matching transactions may have "any",
"all", "none", or "exactly" the evidence provided, determined by
``MatchTypes`` ``ANY``, ``ALL``, ``NONE``, and ``EXACT``, respectively.

Asserting over Transactions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

For writing tests, the method
``assert_transaction_in_ledgers_for_amounts_with_evidence`` is provided
for convenience. As its name implies, it allows asserting the existence
of exactly one ``Transaction`` with the ledger amounts, evidence, and
other fields on Ledger provided to the method.

::

   >>> create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])
   <Transaction: Transaction b3e73f1d-6b10-4597-b19b-84800839d5b3>
   >>> with assert_raises(Transaction.DoesNotExist):
   ...     assert_transaction_in_ledgers_for_amounts_with_evidence(ledger_amount_pairs=[(revenue.name, credit(Decimal(100))), (ar.name, debit(Decimal(100)))], evidence=[])
   ...
   >>> assert_transaction_in_ledgers_for_amounts_with_evidence(ledger_amount_pairs=[(revenue.name, credit(Decimal(100))), (ar.name, debit(Decimal(100)))], evidence=[order])
   >>> with assert_raises(Transaction.DoesNotExist):
   ...     assert_transaction_in_ledgers_for_amounts_with_evidence(ledger_amount_pairs=[(revenue.name, credit(Decimal(100))), (ar.name, debit(Decimal(100)))], evidence=[order])
   ...
   Traceback (most recent call last):
     File "<console>", line 2, in <module>
       File "/usr/lib/python2.7/unittest/case.py", line 116, in __exit__
           "{0} not raised".format(exc_name))
           AssertionError: DoesNotExist not raised

You can see
``capone.tests.test_assert_transaction_in_ledgers_for_amounts_with_evidence``
for more examples!

Image Credits
-------------

Image courtesy
`Officer <https://commons.wikimedia.org/wiki/User:Officer>`__ on
`Wikipedia <https://commons.wikimedia.org/wiki/File:Al_Capone_in_Florida.jpg>`__.
This work was created by a government unit (including state, county, and
municipal government agencies) of the U.S. state of Florida. It is a
public record that was not created by an agency which state law has
allowed to claim copyright and is therefore in the public domain in the
United States.

.. |Al Capone's Miami Mugshot| image:: Al_Capone_in_Florida.jpg
