from django.conf import settings
from contractor.models import ContractParameters, ContractState


class LocalViewInterface:
    # CONTRACT PARAMETERS
    contract_parameters: ContractParameters = None
    @staticmethod
    def get_contract_parameters() -> ContractParameters:
        if not LocalViewInterface.contract_parameters:
            LocalViewInterface.contract_parameters = ContractParameters.objects.first()
        return LocalViewInterface.contract_parameters

    # GENESIS
    @staticmethod
    def genesis_block() -> int:
        return LocalViewInterface.get_contract_parameters().genesis_block

    @staticmethod
    def genesis() -> ContractState:
        return ContractState.objects.get(block=LocalViewInterface.genesis_block())

    # LATEST STATE
    @staticmethod
    def latest() -> ContractState:
        return ContractState.objects.order_by('block').last()

    @staticmethod
    def latest_block() -> int:
        latest = LocalViewInterface.latest()
        if not latest:
            return LocalViewInterface.genesis_block() - 1
        return latest.block

    @staticmethod
    def latest_sub_block() -> (int, int):
        blocks_per_eon = LocalViewInterface.get_contract_parameters().blocks_per_eon
        blocks_passed = LocalViewInterface.latest_block() - LocalViewInterface.genesis_block()

        return blocks_passed // blocks_per_eon + 1, blocks_passed % blocks_per_eon

    # LATEST CONFIRMED STATE
    @staticmethod
    def confirmed(eon_number=None) -> ContractState:
        if eon_number is not None:
            blocks_passed_upper = LocalViewInterface.genesis_block()\
                + eon_number * LocalViewInterface.get_contract_parameters().blocks_per_eon
            blocks_passed_lower = blocks_passed_upper\
                - LocalViewInterface.get_contract_parameters().blocks_per_eon

            return ContractState.objects\
                .filter(
                    confirmed=True,
                    block__gte=blocks_passed_lower,
                    block__lt=blocks_passed_upper)\
                .order_by('block')\
                .last()
        else:
            confirmed = ContractState.objects.filter(
                confirmed=True).order_by('block').last()
            if not confirmed:
                return LocalViewInterface.genesis()
            return confirmed

    @staticmethod
    def confirmed_block() -> int:
        confirmed = LocalViewInterface.confirmed()
        if not confirmed:
            return LocalViewInterface.genesis_block()
        return confirmed.block

    # FETCHED
    @staticmethod
    def running(block_number) -> ContractState:
        return ContractState.objects.filter(block=block_number).first()

    @staticmethod
    def running_block(block_number):
        running = LocalViewInterface.running(block_number)
        if not running:
            return None
        return running.block

    # TIMING
    @staticmethod
    def blocks_for_confirmation():
        return settings.HUB_LQD_CONTRACT_CONFIRMATIONS

    @staticmethod
    def blocks_for_creation():
        return 2 * LocalViewInterface.blocks_for_confirmation()

    @staticmethod
    def blocks_for_submission():
        return LocalViewInterface.blocks_for_creation() + 5
