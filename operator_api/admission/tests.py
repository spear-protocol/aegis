from contractor.rpctestcase import RPCTestCase
from operator_api.simulation.registration import register_random_accounts, register_testrpc_accounts
from ledger.models import Token


class AdmissionTests(RPCTestCase):
    def test_register_random_accounts(self):
        eth_token = Token.objects.first()
        register_random_accounts(self, number_of_accounts=25, token=eth_token)

    def test_register_testrpc_accounts(self):
        eth_token = Token.objects.first()
        register_testrpc_accounts(self, token=eth_token)

    def test_register_bulk_random_accounts(self):
        eth_token = Token.objects.first()
        register_random_accounts(
            self, number_of_accounts=20, token=eth_token, bulk=True)
