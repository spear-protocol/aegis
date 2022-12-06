from django.db import migrations
from ledger import integrity


class Migration(migrations.Migration):

    initial = False

    dependencies = [
        ('ledger', '0061_populate_swap'),
    ]

    operations = [
        # Wallet
        migrations.RunSQL(integrity.wallet.fixed_address_size),
        migrations.RunSQL(
            integrity.wallet.non_negative_registration_eon_number),
        migrations.RunSQL(integrity.wallet.registration_must_be_provable),
        # Signature
        migrations.RunSQL(integrity.signature.fixed_checksum_size),
        migrations.RunSQL(integrity.signature.fixed_value_size),
        # Aggregate
        migrations.RunSQL(integrity.active_state.non_negative_spend_gain),
        migrations.RunSQL(
            integrity.active_state.spend_and_gain_increase_monotonically),
        # Balance
        migrations.RunSQL(
            integrity.exclusive_balance_allotment.non_negative_locally_ordered_bounds),
        migrations.RunSQL(
            integrity.exclusive_balance_allotment.non_negative_eon_number),
        migrations.RunSQL(
            integrity.exclusive_balance_allotment.non_intersecting_boundaries),
        migrations.RunSQL(
            integrity.exclusive_balance_allotment.continuous_boundaries),
        # Deposit
        migrations.RunSQL(integrity.deposit.non_negative_amount),
        # WithdrawalRequest
        migrations.RunSQL(integrity.withdrawal_request.non_negative_amount),
        # Withdrawal
        migrations.RunSQL(integrity.withdrawal.non_negative_amount),
        # Transfer
        migrations.RunSQL(integrity.transfer.non_negative_transfer_amount),
        migrations.RunSQL(
            integrity.transfer.only_processed_transfers_may_be_sent),
        migrations.RunSQL(
            integrity.transfer.only_transferrable_amounts_may_be_sent),
        migrations.RunSQL(integrity.transfer.swap_flag),
        # TODO many more advanced integrity constraints using triggers
    ]
