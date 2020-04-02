from django.db import connection

REBUILD_LEDGER_BALANCES_SQL = '''\
SELECT 1 FROM capone_ledger ORDER BY id FOR UPDATE;

TRUNCATE capone_ledgerbalance;

INSERT INTO
  capone_ledgerbalance (
    ledger_id,
    related_object_content_type_id,
    related_object_id,
    balance,
    created_at,
    modified_at)
SELECT
  capone_ledgerentry.ledger_id,
  capone_transactionrelatedobject.related_object_content_type_id,
  capone_transactionrelatedobject.related_object_id,
  SUM(capone_ledgerentry.amount),
  current_timestamp,
  current_timestamp
FROM
  capone_ledgerentry
INNER JOIN
  capone_transaction
    ON (capone_ledgerentry.transaction_id = capone_transaction.id)
LEFT OUTER JOIN
  capone_transactionrelatedobject
    ON (capone_transaction.id = capone_transactionrelatedobject.transaction_id)
GROUP BY
  capone_ledgerentry.ledger_id,
  capone_transactionrelatedobject.related_object_content_type_id,
  capone_transactionrelatedobject.related_object_id;
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
