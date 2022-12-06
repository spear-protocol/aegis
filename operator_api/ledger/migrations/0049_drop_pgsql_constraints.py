from django.db import migrations
from ledger import integrity


class Migration(migrations.Migration):

    initial = False

    dependencies = [
        ('ledger', '0048_transfer_final_receipt_values'),
    ]

    operations = [
        # Triggers
        # Wallet
        migrations.RunSQL(integrity.sql_utils.drop_ledger_trigger_if_exists(
            "wallet", "registration_must_be_provable")),
        # Aggregate
        migrations.RunSQL(integrity.sql_utils.drop_ledger_trigger_if_exists(
            "aggregate", "spend_and_gain_increase_monotonically")),
        # Balance
        migrations.RunSQL(integrity.sql_utils.drop_ledger_trigger_if_exists(
            "balance", "non_intersecting_boundaries")),
        migrations.RunSQL(integrity.sql_utils.drop_ledger_trigger_if_exists(
            "balance", "continuous_boundaries")),
        # Transfer
        migrations.RunSQL(integrity.sql_utils.drop_ledger_trigger_if_exists(
            "transfer", "only_transferrable_amounts_may_be_sent")),

        # Constraints
        # Wallet
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "wallet", "fixed_address_size")),
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "wallet", "non_negative_registration_eon_number")),
        # Signature
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "signature", "fixed_checksum_size")),
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "signature", "fixed_value_size")),
        # Aggregate
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "aggregate", "non_negative_spend_gain")),
        # Balance
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "balance", "non_negative_locally_ordered_bounds")),
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "balance", "non_negative_eon_number")),
        # Deposit
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "deposit", "non_negative_amount")),
        # WithdrawalRequest
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "withdrawalrequest", "non_negative_amount")),
        # Withdrawal
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "withdrawal", "non_negative_amount")),
        # Transfer
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "transfer", "non_negative_transfer_amount")),
        migrations.RunSQL(integrity.sql_utils.drop_ledger_constraint_if_exists(
            "transfer", "only_processed_transfers_may_be_sent")),
    ]
