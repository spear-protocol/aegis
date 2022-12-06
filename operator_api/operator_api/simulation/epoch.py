from admission.tasks import process_admissions
from contractor.rpctestcase import RPCTestCase
from contractor.tasks import fully_synchronize_contract_state
from contractor.tasks.send_queued_transactions import send_queued_transactions
from ledger.models import TokenCommitment, ExclusiveBalanceAllotment, Wallet, RootCommitment
from ledger.tasks import create_checkpoint
from operator_api.util import cyan
from swapper.tasks.cancel_finalize_swaps import cancel_finalize_swaps
from swapper.tasks.confirm_swaps import confirm_swaps
from swapper.tasks.process_swaps import process_swaps


def commit_eon(test_case: RPCTestCase, eon_number):
    cyan("Commit eon: {}".format(eon_number))
    # Make sure we don't miss any on-chain events
    cyan("Skip {} blocks for confirmation".format(max(0, test_case.contract_interface.get_blocks_for_confirmation(
    ) - test_case.contract_interface.get_current_subblock())))
    while test_case.contract_interface.get_current_subblock() <= test_case.contract_interface.get_blocks_for_confirmation():
        test_case.contract_interface.do_nothing()
    # Retrieve confirmed events
    fully_synchronize_contract_state()
    # Create checkpoint
    cyan("Skip {} blocks for creation".format(max(0, test_case.contract_interface.get_blocks_for_creation(
    ) - test_case.contract_interface.get_current_subblock())))
    while test_case.contract_interface.get_current_subblock() <= test_case.contract_interface.get_blocks_for_creation():
        test_case.contract_interface.do_nothing()
    # Retrieve confirmed events
    fully_synchronize_contract_state()
    process_admissions()
    confirm_swaps()
    cancel_finalize_swaps()
    process_swaps()
    create_checkpoint()
    test_case.assertEqual(RootCommitment.objects.count(), eon_number)
    # Verify balances are stored for each wallet
    balances = ExclusiveBalanceAllotment.objects.filter(eon_number=eon_number)
    test_case.assertEqual(len(balances), Wallet.objects.count())
    # Verify that checkpoint is saved on-chain
    cyan("Skip {} blocks for submission".format(max(0, test_case.contract_interface.get_blocks_for_submission(
    ) - test_case.contract_interface.get_current_subblock())))
    while test_case.contract_interface.get_current_subblock() <= test_case.contract_interface.get_blocks_for_submission():
        test_case.contract_interface.do_nothing()
    # Retrieve confirmed events
    fully_synchronize_contract_state()
    send_queued_transactions()
    test_case.assertTrue(
        test_case.contract_interface.get_is_checkpoint_submitted_for_current_eon())
    # Verify that we have been using the same Hub Interface
    # test_case.assertTrue(PaymentHubInterface() is PaymentHubInterface())
    cyan("Eon {} committed.".format(eon_number))


def confirm_on_chain_events(test_case: RPCTestCase):
    for _ in range(test_case.contract_interface.get_blocks_for_confirmation() + 1):
        test_case.contract_interface.do_nothing()
    fully_synchronize_contract_state()
