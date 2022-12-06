from celery.utils.log import get_task_logger

from eth_utils import remove_0x_prefix
from operator_api import crypto
from operator_api.util import csf_to_list, long_string_to_list, cyan
from contractor.rpctestcase import RPCTestCase
from ledger.models import Wallet, TokenCommitment
from ledger.context.wallet_transfer import WalletTransferContext

logger = get_task_logger(__name__)

# withdraw a third of withdrawable amount


def place_parallel_withdrawals(test_case: RPCTestCase, token, wallet_address, current_eon, dishonest=False):
    token_commitment = TokenCommitment.objects.get(
        token=token,
        root_commitment__eon_number=current_eon-1)

    wallet = Wallet.objects.get(
        token=token, address=remove_0x_prefix(wallet_address))
    wallet_transfer_context = WalletTransferContext(
        wallet=wallet, transfer=None)
    allotment = wallet_transfer_context.balance_as_of_eon(
        eon_number=current_eon-1)

    passive_checksum, passive_amount, passive_marker = wallet_transfer_context.get_passive_values(
        eon_number=current_eon-1)

    available_balance = wallet_transfer_context.loosely_available_funds_at_eon(
        eon_number=current_eon,
        current_eon_number=current_eon,
        is_checkpoint_created=True,
        only_appended=True)

    overdraw = dishonest and available_balance < allotment.amount()

    if overdraw:
        total_draw = max(available_balance, allotment.amount()) // 4
    else:
        total_draw = min(available_balance, allotment.amount()) // 4

    total_amount = 0

    if(total_draw == 0):
        return (total_amount, [], False)

    withdrawal_amounts = [total_draw // 4, total_draw // 2, total_draw // 4]

    for withdrawal_amount in withdrawal_amounts:

        cyan([wallet.address, wallet.token.address,
              withdrawal_amount, available_balance])

        test_case.contract_interface.withdraw(
            token_address=wallet.token.address,
            wallet=wallet.address,
            active_state_checksum=crypto.zfill(
                allotment.active_state_checksum()),
            trail=int(allotment.merkle_proof_trail),
            allotment_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                             long_string_to_list(allotment.merkle_proof_hashes, 64)],
            membership_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                              long_string_to_list(token_commitment.membership_hashes, 64)],
            values=csf_to_list(allotment.merkle_proof_values, int),
            exclusive_allotment_interval=[
                int(allotment.left), int(allotment.right)],
            withdrawal_amount=int(withdrawal_amount),
            passive_checksum=passive_checksum,
            passive_amount=passive_amount,
            passive_marker=passive_marker)

        total_amount += int(withdrawal_amount)

    return (total_amount, withdrawal_amounts, overdraw)
