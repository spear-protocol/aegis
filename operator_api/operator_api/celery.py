import os
from celery import Celery
from operator_api.util import cyan, red

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'operator_api.settings')

operator_celery = Celery('operator_api')
operator_celery.config_from_object('django.conf:settings', namespace='CELERY')
operator_celery.autodiscover_tasks()

IS_DEV_POA = os.environ.get('RUNNING_IN_PRODUCTION', '').lower() == 'false' \
    and os.environ.get('HUB_ETHEREUM_NETWORK_IS_POA', '').lower() == 'true'

if IS_DEV_POA:
    sync_interval = 1.0
else:
    sync_interval = 10.0

operator_celery.conf.beat_schedule = {
    'heartbeat_accounting': {
        'task': 'heartbeat.tasks.heartbeat_accounting',
        'schedule': 1.0
    },
    'heartbeat_verifier': {
        'task': 'heartbeat.tasks.heartbeat_verifier',
        'schedule': sync_interval
    },
    'check_eth_level': {
        'task': 'contractor.tasks.health_checks.check_eth_level',
        'schedule': 3600.0  # 1 hour
    },
    'update_tos': {
        'task': 'tos.tasks.update_tos',
        'schedule': 3600.0*24  # 1 day
    }
}

operator_celery.conf.task_routes = {
    'contractor.tasks.fetch_blocks.*': {
        'queue': 'blockchain'
    },
    'contractor.tasks.health_checks.*': {
        'queue': 'blockchain'
    },
    'auditor.tasks.*': {
        'queue': 'audit'
    },
    'synchronizer.tasks.*': {
        'queue': 'audit'
    },
    'tos.tasks.*': {
        'queue': 'audit'
    },
    'heartbeat.tasks.heartbeat_accounting': {
        'queue': 'accounting'
    },
}

# wrap register_token tasks
@operator_celery.task
def register_token_callback():
    operator_celery.send_task(
        'ledger.tasks.register_eth_token.register_eth_token')
    operator_celery.send_task(
        'ledger.tasks.register_sla_token.register_sla_token')
    operator_celery.send_task(
        'ledger.tasks.whitelist_default_token_pairs.whitelist_default_token_pairs')

# wrap update tos task
@operator_celery.task
def update_tos_callback():
    operator_celery.send_task(
        'tos.tasks.update_tos',
        chain=[
            register_token_callback.si()
        ]
    )

# wait untill app is initialized, give application chance to autodiscover tasks
@operator_celery.on_after_finalize.connect
def schedule_one_time_tasks(sender, **kwargs):
    if os.environ.get('RUN_STARTUP_TASKS', '').lower() != 'true':
        return

    # send tasks in a specific order
    # wait for populate_contract_parameters then register eth token
    contract_parameters_task_path = 'contractor.tasks.populate_contract_parameters.populate_contract_parameters'
    operator_celery.send_task(
        contract_parameters_task_path,
        chain=[
            update_tos_callback.si(),
        ]
    )
