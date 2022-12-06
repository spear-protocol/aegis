from contractor.abi import load_abi
from contractor.decoders.ethereum_event_decoder import EthereumEventDecoder
from operator_api.util import Singleton


nocust_contract_abi = load_abi('NOCUSTCommitChain.json')


class NOCUSTContractEventDecoder(EthereumEventDecoder, metaclass=Singleton):
    def __init__(self):
        super(NOCUSTContractEventDecoder, self).__init__(nocust_contract_abi)
