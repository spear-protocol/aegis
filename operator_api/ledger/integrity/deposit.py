# Deposit amount must be non-negative
non_negative_amount = \
    """
ALTER TABLE ledger_deposit DROP CONSTRAINT IF EXISTS non_negative_amount;
ALTER TABLE ledger_deposit ADD CONSTRAINT non_negative_amount CHECK ("amount" >= 0);
ALTER TABLE ledger_deposit VALIDATE CONSTRAINT non_negative_amount;
"""
