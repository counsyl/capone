from django.db import connection

REBUILD_LEDGER_BALANCES_SQL = '''\
SELECT 1 FROM ledger_ledger ORDER BY id FOR UPDATE;

TRUNCATE ledger_ledgerbalance;

INSERT INTO
  ledger_ledgerbalance (
    ledger_id,
    related_object_content_type_id,
    related_object_id,
    balance)
SELECT
  ledger_ledgerentry.ledger_id,
  ledger_transactionrelatedobject.related_object_content_type_id,
  ledger_transactionrelatedobject.related_object_id,
  SUM(ledger_ledgerentry.amount)
FROM
  ledger_ledgerentry
INNER JOIN
  ledger_transaction
    ON (ledger_ledgerentry.transaction_id = ledger_transaction.id)
LEFT OUTER JOIN
  ledger_transactionrelatedobject
    ON (ledger_transaction.id = ledger_transactionrelatedobject.transaction_id)
GROUP BY
  ledger_ledgerentry.ledger_id,
  ledger_transactionrelatedobject.related_object_content_type_id,
  ledger_transactionrelatedobject.related_object_id;
'''


def rebuild_ledger_balances():
    """
    Recompute and recreate all LedgerBalance entries.

    This is only needed if the LedgerBalance entries get out of sync, for
    example after data migrations which change historical transactions.
    """
    cursor = connection.cursor()
    cursor.execute(REBUILD_LEDGER_BALANCES_SQL)
    cursor.close()
