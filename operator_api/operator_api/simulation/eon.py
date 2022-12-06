from contractor.rpctestcase import RPCTestCase
from operator_api.simulation.epoch import commit_eon
from operator_api.simulation.transaction import make_random_valid_transactions
from operator_api.util import cyan
from ledger.models import Transfer, Token


def simulate_eon_with_random_transfers(test_case: RPCTestCase, eon_number, accounts, token: Token, make_deposits=True):
    cyan("Simulate random transactions in eon number: {}".format(eon_number))

    make_random_valid_transactions(
        test_case, eon_number, accounts, token, make_deposits)

    transfers = Transfer.objects.all()

    # Verify transfers were complete
    for transfer in transfers:
        test_case.assertTrue(transfer.processed)
        test_case.assertTrue(transfer.complete)

    advance_to_next_eon(
        test_case=test_case,
        eon_number=eon_number)
    commit_eon(
        test_case=test_case,
        eon_number=eon_number + 1)


def advance_until_sub_block(test_case: RPCTestCase, sub_block):
    start = test_case.contract_interface.get_current_subblock()
    blocks_to_sub_block = sub_block - start
    if blocks_to_sub_block <= 0:
        cyan("No advancement needed.")
        return

    for _ in range(blocks_to_sub_block):
        test_case.contract_interface.do_nothing()
    cyan("Advance {} blocks ({} -> {})".format(blocks_to_sub_block,
                                               start, test_case.contract_interface.get_current_subblock()))


def advance_to_next_eon(test_case: RPCTestCase, eon_number):
    advance_until_sub_block(
        test_case, test_case.contract_interface.get_blocks_per_eon())
    cyan("From eon {} to {}".format(eon_number,
                                    test_case.contract_interface.get_current_eon_number()))


def advance_past_slack_period(test_case: RPCTestCase):
    advance_until_sub_block(
        test_case, test_case.contract_interface.get_slack_period() + 1)
    cyan("Move past slack period.")


def advance_past_extended_slack_period(test_case: RPCTestCase):
    advance_until_sub_block(
        test_case, test_case.contract_interface.get_extended_slack_period() + 1)
    cyan("Move past extended slack period.")
