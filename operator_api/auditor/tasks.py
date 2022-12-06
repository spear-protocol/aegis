from django.shortcuts import get_object_or_404
from celery import shared_task
from asgiref.sync import async_to_sync
from auditor.serializers import WalletStateSerializer, ConciseTransactionSerializer
from transactor.serializers import TransferSerializer
from swapper.serializers import SwapSerializer, SwapCancellationSerializer, SwapFinalizationSerializer
from ledger.models import Wallet, Transfer
from contractor.interfaces import LocalViewInterface
from synchronizer.utils import send_response, send_error, send_notification, CHECKPOINT_CREATED
from operator_api.models import MockModel
from synchronizer.utils import send_notification, TRANSFER_CONFIRMATION, SWAP_CONFIRMATION, SWAP_CANCELLATION, SWAP_FINALIZATION, INCOMING_SWAP, MATCHED_SWAP, CANCELLED_SWAP
from operator_api.celery import operator_celery
import os
import json
import logging
from celery.utils.log import get_task_logger


logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)

# task to fetch wallet audit endpoint data
@shared_task
def get_wallet_data(channel_name, operation, wallet_address, token_address, eon_number=None):

    # default eon_number is the latest eon
    if eon_number is None:
        eon_number = LocalViewInterface.latest().eon_number()

    # wrap negative eon_number
    if eon_number < 0:
        eon_number += LocalViewInterface.latest().eon_number()

    try:
        wallet = Wallet.objects.get(
            address__iexact=wallet_address, token__address__iexact=token_address)

        request_model = MockModel(
            eon_number=eon_number,
            wallet=wallet,
            transfer_id=0)

        data = WalletStateSerializer(request_model).data

        # send response to websocket channel
        async_to_sync(send_response)(
            channel_name=channel_name,
            resource="wallet",
            data=data,
        )
    except Wallet.DoesNotExist:
        # send error to websocket channel
        async_to_sync(send_error)(
            channel_name=channel_name,
            error='Wallet does not exist.',
            cause=operation
        )


# task to fetch operator audit endpoint data
@shared_task
def get_operator_data(channel_name, operation):
    latest = LocalViewInterface.latest()
    confirmed = LocalViewInterface.confirmed()

    data = {
        'latest': {
            'block': latest.block,
            'eon_number': latest.eon_number(),
        },
        'confirmed': {
            'block': confirmed.block,
            'eon_number': confirmed.eon_number(),
        }
    }

    # send response to websocket channel
    async_to_sync(send_response)(
        channel_name=channel_name,
        resource="operator",
        data=data,
    )

# task to push wallet data on checkpoint creation
@shared_task
def broadcast_wallet_data():
    eon_number = LocalViewInterface.latest().eon_number()
    for wallet in Wallet.objects.all():

        request_model = MockModel(
            eon_number=eon_number,
            wallet=wallet,
            transfer_id=0)

        data = WalletStateSerializer(request_model).data

        send_notification(
            stream_prefix='wallet',
            stream_id="{}/{}".format(wallet.token.address, wallet.address),
            event_name=CHECKPOINT_CREATED,
            data=data
        )

# cache wallet data if requested data is for an old eon
@shared_task
def cache_wallet_data(eon_number, token_address, wallet_address, data):
    if eon_number < LocalViewInterface.latest().eon_number():
        path = f"/audit_data_cache/{eon_number}/{token_address}"

        if not os.path.exists(path):
            os.makedirs(path)

        with open(f"{path}/{wallet_address}.json", "w+") as f:
            f.write(json.dumps(data))

        logger.info(f"Cached {eon_number}/{token_address}/{wallet_address} .")
    else:
        logger.info(
            f"Skipping cache for {eon_number}/{token_address}/{wallet_address}, eon {eon_number} is not over yet.")


@shared_task
def on_transfer_confirmation(transaction_id):
    transfer = Transfer.objects.get(id=transaction_id, swap=False)
    transfer_data = TransferSerializer(transfer, read_only=True).data

    # send transfer confirmed notification to both wallets
    # to cover use cases where multiple clients might be listening for the same wallet's state
    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(transfer.recipient.token.address,
                                 transfer.recipient.address),
        event_name=TRANSFER_CONFIRMATION,
        data=transfer_data
    )

    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(transfer.wallet.token.address,
                                 transfer.wallet.address),
        event_name=TRANSFER_CONFIRMATION,
        data=transfer_data
    )

    operator_celery.send_task(
        'synchronizer.tasks.trigger_hook',
        args=[
            ConciseTransactionSerializer(transfer).data,
        ],
    )


@shared_task
def on_swap_confirmation(transaction_id):
    swap = Transfer.objects.get(id=transaction_id, swap=True)
    swap_data = SwapSerializer(swap, read_only=True).data

    # send swap confirmed notification to both wallets
    # to cover use cases where multiple clients might be listening for the same wallet's state
    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(swap.recipient.token.address,
                                 swap.recipient.address),
        event_name=SWAP_CONFIRMATION,
        data=swap_data
    )

    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(swap.wallet.token.address,
                                 swap.wallet.address),
        event_name=SWAP_CONFIRMATION,
        data=swap_data
    )

    # send swap incoming notification to clients interested in pairs
    send_notification(
        stream_prefix="tokenpair",
        stream_id="{}/{}".format(swap.wallet.token.address,
                                 swap.recipient.token.address),
        event_name=INCOMING_SWAP,
        data=swap_data
    )


@shared_task
def on_swap_cancellation(transaction_id):
    swap = Transfer.objects.get(id=transaction_id, swap=True)
    swap_data = SwapCancellationSerializer(swap, read_only=True).data

    # send swap cancellation notification to both wallets
    # to cover use cases where multiple clients might be listening for the same wallet's state
    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(swap.recipient.token.address,
                                 swap.recipient.address),
        event_name=SWAP_CANCELLATION,
        data=swap_data
    )

    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(swap.wallet.token.address,
                                 swap.wallet.address),
        event_name=SWAP_CANCELLATION,
        data=swap_data
    )

    # send swap incoming notification to clients interested in pairs
    send_notification(
        stream_prefix="tokenpair",
        stream_id="{}/{}".format(swap.wallet.token.address,
                                 swap.recipient.token.address),
        event_name=CANCELLED_SWAP,
        data=swap_data
    )


@shared_task
def on_swap_finalization(transaction_id):
    swap = Transfer.objects.get(id=transaction_id, swap=True)
    swap_data = SwapFinalizationSerializer(swap, read_only=True).data

    # send swap cancellation notification to both wallets
    # to cover use cases where multiple clients might be listening for the same wallet's state
    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(swap.recipient.token.address,
                                 swap.recipient.address),
        event_name=SWAP_FINALIZATION,
        data=swap_data
    )

    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(swap.wallet.token.address,
                                 swap.wallet.address),
        event_name=SWAP_FINALIZATION,
        data=swap_data
    )


@shared_task
def on_swap_matching(swap_id, opposite_id):
    swap = Transfer.objects.get(id=swap_id, swap=True)
    opposite = Transfer.objects.get(id=opposite_id, swap=True)

    swap_data = SwapSerializer(
        swap, read_only=True).data
    opposite_data = SwapSerializer(
        opposite, read_only=True).data

    # send swap matched notification to recipient
    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(
            opposite.recipient.token.address, opposite.recipient.address),
        event_name=MATCHED_SWAP,
        data=opposite_data)
    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(
            swap.recipient.token.address, swap.recipient.address),
        event_name=MATCHED_SWAP,
        data=swap_data)

    # send swap matched notification to sender
    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(
            opposite.wallet.token.address, opposite.wallet.address),
        event_name=MATCHED_SWAP,
        data=opposite_data
    )
    send_notification(
        stream_prefix="wallet",
        stream_id="{}/{}".format(
            swap.wallet.token.address, swap.wallet.address),
        event_name=MATCHED_SWAP,
        data=swap_data
    )

    # send swap matched notification to tokenpair listeners
    send_notification(
        stream_prefix="tokenpair",
        stream_id="{}/{}".format(
            opposite.wallet.token.address, swap.wallet.token.address),
        event_name=MATCHED_SWAP,
        data=opposite_data
    )
    # send swap matched notification to tokenpair listeners
    send_notification(
        stream_prefix="tokenpair",
        stream_id="{}/{}".format(
            swap.wallet.token.address, opposite.wallet.token.address),
        event_name=MATCHED_SWAP,
        data=swap_data
    )
