import uuid
import random
from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from contractor.interfaces import NOCUSTContractInterface
from operator_api import crypto
from ledger.models import Wallet, Signature, Transfer, Token, MinimumAvailableBalanceMarker, ActiveState
from django.test import Client


class UnittestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.eth_token = Token.objects.create(
            address="9561C133DD8580860B6b7E504bC5Aa500f0f06a7",
            name='Ethereum',
            short_name='ETH',
            trail=1,
            block=1)
        self.private, self.public, self.wallet_address = crypto.generate_wallet()
        self.hub_private, self.hub_public, self.wrong_wallet = crypto.generate_wallet()
        self.api_client = APIClient()
        self.client = Client()
        self.wallet = Wallet.objects.create(
            address=self.wallet_address,
            token=self.eth_token,
            registration_eon_number=3)

        self.hub_wallet = Wallet.objects.create(
            address=self.wrong_wallet,
            token=self.eth_token,
            registration_eon_number=3)

    def update_registration(self, signature, message):
        # this is from Postgresql functions inside DB.
        # Hell know why this exists in first place

        registration = Signature.objects.create(
            wallet=self.wallet,
            checksum=crypto.hex_value(message),
            value=signature
        )
        self.wallet.registration_authorization = registration
        self.wallet.save()
        self.hub_wallet.registration_authorization = registration
        self.hub_wallet.save()


class DelegatedWithdrawalCases(UnittestCase):

    def setUp(self):
        super().setUp()
        message = [
            crypto.address(self.wallet.address),  # wallet
            crypto.address(self.eth_token.address),  # token
            crypto.uint256(10000),  # amount
            crypto.uint256(57)  # expiry
        ]
        message = crypto.hash_array(message)
        signature = crypto.encode_signature(
            crypto.sign_message(message, self.private.to_string()))
        self.right_sig = signature
        self.url = reverse("delegated-withdrawal-endpoint")

        self.update_registration(signature, message)
        self.payload = {
            "signature": self.right_sig,
            "wallet": self.wallet,
            "token": self.eth_token.address,
            "amount": 10000,
            "expiry": 57
        }

    def test_signature_verification(self):
        self.payload['wallet'] = self.hub_wallet
        response = self.client.post(self.url, data=self.payload).json()
        self.assertEqual(response, "Signature is invalid")

    def test_wallet_not_enough_funds(self):
        response = self.client.post(self.url, data=self.payload).json()
        self.assertEqual(response, "Not enough funds")

    def test_wallet_funds(self):
        hub_mba = MinimumAvailableBalanceMarker(
            wallet=self.hub_wallet,
            amount=1,
            eon_number=3
        )

        mba_checksum = hub_mba.checksum()

        sign = Signature(
            wallet=self.hub_wallet,
            checksum=crypto.hex_value(mba_checksum),
            value=crypto.encode_signature(crypto.sign_message(mba_checksum, self.hub_private.to_string())))

        sign.save()
        hub_mba.signature = sign
        hub_mba.save()

        hub_state = ActiveState(
            wallet=self.hub_wallet,
            eon_number=3,
            updated_spendings=4,
            updated_gains=76,
            tx_set_hash=uuid.uuid4().hex,
            tx_set_index=2
        )

        state_checksum = hub_state.checksum()
        sign = Signature(
            wallet=self.hub_wallet,
            checksum=crypto.hex_value(state_checksum),
            value=crypto.encode_signature(crypto.sign_message(state_checksum, self.hub_private.to_string())))
        sign.save()
        hub_state.wallet_signature = sign
        hub_state.save()

        transfer = Transfer(
            wallet=self.hub_wallet,
            sender_balance_marker=hub_mba,
            amount=100000,
            eon_number=NOCUSTContractInterface().get_current_eon_number(),
            recipient=self.wallet,
            nonce=random.randint(1, 1000),
            sender_active_state=hub_state,
            passive=True)
        transfer.save()

        response = self.client.post(self.url, data=self.payload).json()
        self.assertEqual(response, "Ok")
