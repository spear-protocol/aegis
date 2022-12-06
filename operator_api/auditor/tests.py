from django.urls import reverse
from contractor.rpctestcase import RPCTestCase
from rest_framework import status
from operator_api.simulation.registration import register_testrpc_accounts
from operator_api.simulation.transaction import make_random_valid_transactions
from ledger.models import Token


class AuditorTests(RPCTestCase):
    def test_request_audit(self):
        eth_token = Token.objects.first()
        registered_accounts = register_testrpc_accounts(self, token=eth_token)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)

        make_random_valid_transactions(
            test_case=self,
            eon_number=1,
            accounts=registered_accounts,
            token=eth_token)

        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), self.contract_interface.get_total_balance(eth_token.address))
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)

        for account in registered_accounts:
            url = reverse(
                'wallet-sync', kwargs={'wallet': account['address'], 'token': eth_token.address})
            response = self.client.get(url, None, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
