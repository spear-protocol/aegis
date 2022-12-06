from .challenge import ChallengeInterpreter
from .event import EventInterpreter
from .deposit import DepositInterpreter
from .withdrawal_request import WithdrawalRequestInterpreter
from .withdrawal_confirmation import WithdrawalConfirmationInterpreter


event_interpreter_map = {
    'Deposit': DepositInterpreter(),
    'WithdrawalRequest': WithdrawalRequestInterpreter(),
    'WithdrawalConfirmation': WithdrawalConfirmationInterpreter(),
    # TODO find a reason to care about these since we are their source
    'CheckpointSubmission': None,
    'ChallengeIssued': ChallengeInterpreter(),
}
