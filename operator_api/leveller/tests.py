from django.conf import settings
from rest_framework import status
import random
from contractor.rpctestcase import RPCTestCase
from contractor.tasks import send_queued_transactions
from operator_api import testrpc_accounts
from operator_api.simulation.deposit import create_deposits, make_deposit
from operator_api.simulation.epoch import confirm_on_chain_events
from operator_api.simulation.registration import register_random_accounts, register_testrpc_accounts
from django.urls import reverse

from operator_api.simulation.tokens import deploy_new_test_token, distribute_token_balance_to_addresses
from operator_api.simulation.transaction import send_transaction
from ledger.models import Token, Transfer
from ledger.token_registration import register_token


class SLATests(RPCTestCase):
    def setUp(self):
        super(SLATests, self).setUp()
        self.eth_token = Token.objects.first()

        lqd_token_address = deploy_new_test_token(test_case=self)

        distribute_token_balance_to_addresses(
            test_case=self,
            token_address=lqd_token_address,
            recipients=testrpc_accounts.accounts)

        self.lqd_token = register_token(
            token_address=lqd_token_address,
            name='Liquidity',
            short_name='LQD',
            register_on_chain=True)

        send_queued_transactions()

        self.tokens = [
            self.eth_token,
            self.lqd_token
        ]

        self.registered_accounts = {
            self.eth_token: register_testrpc_accounts(self, token=self.eth_token),
            self.lqd_token: register_testrpc_accounts(
                self, token=self.lqd_token)
        }

    def test_sla_payment(self):

        test_account = self.registered_accounts[self.lqd_token][5]

        url = reverse('sla', kwargs={'wallet': test_account.get('address')})

        self.assertEqual(self.client.get(url).status_code,
                         status.HTTP_404_NOT_FOUND)

        make_deposit(self, self.lqd_token, test_account, settings.SLA_PRICE)
        confirm_on_chain_events(self)

        nonce = random.randint(1, 999999)

        send_transaction(  # 1, 5
            test_case=self,
            eon_number=1,
            sender=test_account,
            recipient={'address': settings.SLA_RECIPIENT_ADDRESS},
            amount=settings.SLA_PRICE,
            nonce=nonce,
            token=self.lqd_token,
            expected_status=status.HTTP_201_CREATED)

        data = {
            'transfer_id': Transfer.objects.get(nonce=nonce, eon_number=1).id
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)
