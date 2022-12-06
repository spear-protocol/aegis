# Withdrawal Request amount must be non-negative
non_negative_amount = \
    """
ALTER TABLE ledger_withdrawalrequest DROP CONSTRAINT IF EXISTS non_negative_amount;
ALTER TABLE ledger_withdrawalrequest ADD CONSTRAINT non_negative_amount CHECK ("amount" >= 0);
ALTER TABLE ledger_withdrawalrequest VALIDATE CONSTRAINT non_negative_amount;
"""
