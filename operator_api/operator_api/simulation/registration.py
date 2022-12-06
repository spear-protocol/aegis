from celery.utils.log import get_task_logger
from django.urls import reverse
from eth_utils import remove_0x_prefix, decode_hex
from rest_framework import status
from django.conf import settings
from admission.tasks import process_admissions
from contractor.rpctestcase import RPCTestCase
from operator_api import testrpc_accounts
from operator_api.util import cyan
from ledger.models import Wallet, Signature, Token
from operator_api.crypto import generate_wallet, encode_signature, sign_message
from tos.models import TOSConfig, TOSSignature

logger = get_task_logger(__name__)


def register_account(test_case: RPCTestCase, token, address, authorization, tos_signature):
    # Create a request
    url = reverse('admission-endpoint')
    data = {
        'token': remove_0x_prefix(token),
        'address': remove_0x_prefix(address),
        'authorization': {
            'value': encode_signature(authorization)
        },
        'tos_signature': {
            'value': encode_signature(tos_signature)

        }
    }
    response = test_case.client.post(url, data, format='json')

    test_case.assertEqual(response.status_code, status.HTTP_201_CREATED)


def register_bulk_accounts(test_case: RPCTestCase, accounts):
    # Create a request
    url = reverse('bulk-admission-endpoint')
    data = {'admissions': []}
    for i in range(len(accounts)):
        data['admissions'].append({
            'token': remove_0x_prefix(accounts[i]['token']),
            'address': remove_0x_prefix(accounts[i]['address']),
            'authorization': {
                'value': encode_signature(accounts[i]['authorization'])
            },
            'tos_signature': {
                'value': encode_signature(accounts[i]['tos_signature'])
            }
        })

    response = test_case.client.post(url, data, format='json')
    test_case.assertEqual(response.status_code, status.HTTP_201_CREATED)


def register_random_accounts(test_case: RPCTestCase, number_of_accounts, token: Token, bulk=False):
    signature_starting_count = Signature.objects.count()

    accounts = []
    account_requests = []
    for _ in range(number_of_accounts):
        private_key, public_key, address = generate_wallet()
        accounts.append({
            'pk': private_key.to_string(),
            'address': test_case.contract_interface.web3.toChecksumAddress(address)
        })
        authorization_digest = Wallet(
            token=token, address=address).get_admission_hash(1)
        authorization = sign_message(
            authorization_digest, private_key.to_string())
        latest_tos_config = TOSConfig.objects.all().order_by('time').last()
        tos_signature = sign_message(
            decode_hex(latest_tos_config.digest()), private_key.to_string())
        # register_account(test_case, token.address, address, authorization)
        account_requests.append({
            'token': token.address,
            'address': address,
            'authorization': authorization,
            'tos_signature': tos_signature
        })

    new_accounts = len(accounts)

    before_count = Wallet.objects.filter(
        registration_operator_authorization__isnull=True).count()

    if bulk:
        register_bulk_accounts(test_case, account_requests)
    else:
        for i in range(new_accounts):
            register_account(test_case,
                             token=token.address,
                             address=account_requests[i]['address'],
                             authorization=account_requests[i]['authorization'],
                             tos_signature=account_requests[i]['tos_signature'])

    after_count = Wallet.objects.filter(
        registration_operator_authorization__isnull=True).count()

    test_case.assertEqual(after_count - before_count, number_of_accounts)

    process_admissions()

    test_case.assertEqual(Wallet.objects.filter(
        trail_identifier__isnull=True).count(), 0)
    test_case.assertEqual(Wallet.objects.filter(
        registration_operator_authorization__isnull=True).count(), 0)

    for account in account_requests:
        test_case.assertTrue(
            TOSSignature.objects.filter(
                address__iexact=remove_0x_prefix(account['address'])).exists()
        )

    cyan("Registered {} random accounts.".format(len(accounts)))
    return accounts


def register_testrpc_accounts(test_case: RPCTestCase, token: Token):
    signature_starting_count = Signature.objects.count()
    wallet_starting_count = Wallet.objects.count()

    accounts = testrpc_accounts.accounts
    for account in accounts:
        account['address'] = test_case.contract_interface.web3.toChecksumAddress(
            account['address'])

    for i in range(1, len(accounts)):
        authorization_digest = Wallet(
            token=token, address=accounts[i].get('address')).get_admission_hash(1)
        authorization = sign_message(
            authorization_digest, accounts[i].get('pk'))
        latest_tos_config = TOSConfig.objects.all().order_by('time').last()

        tos_signature = sign_message(
            decode_hex(latest_tos_config.digest()), accounts[i].get('pk'))
        register_account(test_case, token.address,
                         accounts[i].get('address'), authorization, tos_signature)

    new_accounts = len(accounts) - 1

    process_admissions()
    test_case.assertEqual(Wallet.objects.count(),
                          wallet_starting_count + new_accounts)
    test_case.assertEqual(Wallet.objects.filter(
        trail_identifier__isnull=True).count(), 0)
    test_case.assertEqual(Wallet.objects.filter(
        registration_operator_authorization__isnull=True).count(), 0)
    cyan("Registered {} testrpc accounts.".format(len(accounts)))
    return accounts
