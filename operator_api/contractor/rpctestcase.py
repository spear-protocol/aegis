# import logging
from django.conf import settings
from contractor.tasks import fully_synchronize_contract_state
from contractor.tasks.populate_contract_parameters import populate_contract_parameters
from operator_api import util
from rest_framework.test import APITransactionTestCase
import subprocess
import time
from contractor.interfaces import NOCUSTContractInterface
from django.test.utils import override_settings
from operator_api.celery import operator_celery
from ledger.tasks import register_eth_token
from tos.models import TOSConfig
import os
from django_redis import get_redis_connection


class RPCTestCase(APITransactionTestCase):
    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                       CELERY_ALWAYS_EAGER=True,
                       BROKER_BACKEND='memory')
    def setUp(self):
        # util.yellow("\n=======================SETUP======================")
        # util.cyan('$PATH Variable:')
        # util.cyan(os.getenv('PATH'))
        # logging.basicConfig(level=logging.WARNING)
        operator_celery.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
            result_backend='memory')
        subprocess.call(args=['pkill', '-f', 'ganache-cli'])
        self.test_rpc = subprocess.Popen(
            args=['ganache-cli', '-d', '-i 1337'], stdout=open(os.devnull, 'wb'))
        time.sleep(3)  # Wait for testrpc to come online
        # util.truffle(['deploy'])
        util.just_deploy_linked(
            bytecode_file='../just-deploy/contracts/ethereum-hub-contract-9-dev.json',
            private_key=settings.HUB_OWNER_ACCOUNT_KEY)
        time.sleep(3)
        self.contract_interface = NOCUSTContractInterface()
        populate_contract_parameters()
        TOSConfig.objects.create(
            privacy_policy_digest='33F8560BDE33D87B0DB60633AF2E0481CE0B7952080673F331FA58D7D1C99A9D',
            terms_of_service_digest='4625EFBA932B871BB5BAB4B0000156A995B6164EC133B900A4DEC0DB0E1242C9'
        )
        register_eth_token()
        fully_synchronize_contract_state()
        # util.yellow("\n=======================TEST=======================")

    def tearDown(self):
        # util.yellow("\n=====================TEARDOWN=====================")
        self.test_rpc.terminate()
        get_redis_connection("default").flushall()
        # util.yellow("\n=======================DONE=======================")
