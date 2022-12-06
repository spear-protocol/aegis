import uuid
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.core.validators import MinValueValidator
from decimal import Decimal
from rest_framework import serializers
from auditor.serializers import WalletSerializer, ActiveStateSerializer, SwapMatchedAmountSerializer
from contractor.interfaces import LocalViewInterface
from operator_api import crypto
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Transfer, MinimumAvailableBalanceMarker, Signature, ActiveState, TokenPair, RootCommitment
from ledger.serializers import SignatureSerializer
from swapper.util import check_active_state_signature, SignatureType
from operator_api.models import ErrorCode
from operator_api.celery import operator_celery


class SwapSerializer(serializers.ModelSerializer):
    # wallet references
    wallet = WalletSerializer()
    recipient = WalletSerializer()

    amount_swapped = serializers.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('1'))])

    # user signatures
    debit_signature = SignatureSerializer(
        write_only=True,
        many=True)
    debit_balance_signature = SignatureSerializer(
        write_only=True,
        many=True)
    credit_signature = SignatureSerializer(
        write_only=True,
        many=True)
    credit_balance_signature = SignatureSerializer(
        write_only=True,
        many=True)
    credit_fulfillment_signature = SignatureSerializer(
        write_only=True,
        many=True)

    # swap state data
    sender_active_state = ActiveStateSerializer(
        read_only=True)
    recipient_active_state = ActiveStateSerializer(
        read_only=True)
    recipient_fulfillment_active_state = ActiveStateSerializer(
        read_only=True)
    time = serializers.IntegerField(
        source='get_timestamp',
        read_only=True)
    matched_amounts = SwapMatchedAmountSerializer(
        source='*',
        read_only=True)

    class Meta:
        model = Transfer
        fields = ('id', 'wallet', 'amount', 'time', 'eon_number', 'complete', 'sender_active_state', 'recipient', 'recipient_active_state', 'recipient_fulfillment_active_state', 'nonce', 'amount_swapped',
                  'debit_signature', 'debit_balance_signature', 'credit_signature', 'credit_fulfillment_signature', 'credit_balance_signature', 'tx_id', 'matched_amounts', 'sell_order')

        read_only_fields = ('id', 'time', 'complete', 'sender_active_state',
                            'recipient_active_state', 'recipient_fulfillment_active_state', 'tx_id', 'matched_amounts')
        error_codes = [
            ErrorCode.INVALID_DEBIT_AMOUNT,
            ErrorCode.INVALID_CREDIT_AMOUNT,
            ErrorCode.SWAPPING_DISABLED,
            ErrorCode.TOO_MANY_FUTURE_SIGNATURES,
            ErrorCode.WRONG_NUMBER_OF_SIGNATURES,
            ErrorCode.DEBIT_WALLET_NOT_ADMITTED,
            ErrorCode.CREDIT_WALLET_NOT_ADMITTED,
            ErrorCode.DEBIT_CREDIT_WALLET_ADDRESS_MISMATCH,
            ErrorCode.DEBIT_CREDIT_TOKEN_ADDRESS_MATCH,
            ErrorCode.TOKEN_PAIR_BLOCKED,
            ErrorCode.EON_NUMBER_OUT_OF_SYNC,
            ErrorCode.DEBIT_WALLET_CANNOT_ADD_TRANSACTION,
            ErrorCode.CREDIT_WALLET_CANNOT_ADD_TRANSACTION,
            ErrorCode.DEBIT_WALLET_OVERSPENDING,
            ErrorCode.DEBIT_WALLET_BALANCE_AMOUNT_MISMATCH,
            ErrorCode.CREDIT_WALLET_BALANCE_NOT_ZERO,
            ErrorCode.INVALID_DEBIT_BALANCE_SIGNATURE,
            ErrorCode.INVALID_CREDIT_BALANCE_SIGNATURE,
            ErrorCode.INVALID_FUTURE_CREDIT_SIGNATURE,
            ErrorCode.INVALID_CREDIT_SIGNATURE,
            ErrorCode.INVALID_FUTURE_DEBIT_SIGNATURE,
            ErrorCode.INVALID_DEBIT_SIGNATURE,
            ErrorCode.INVALID_FUTURE_CREDIT_FULFILLMENT_SIGNATURE,
            ErrorCode.INVALID_CREDIT_FULFILLMENT_SIGNATURE,
        ]

    # noinspection PyMethodMayBeStatic
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.INVALID_DEBIT_AMOUNT)
        return value

    # noinspection PyMethodMayBeStatic
    def validate_amount_swapped(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.INVALID_CREDIT_AMOUNT)
        return value

    def validate(self, attrs):
        if not settings.SWAPS_ENABLED:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.SWAPPING_DISABLED)

        if len(attrs.get('debit_signature')) > settings.SWAPS_PERSISTENCE_LIMIT:
            raise serializers.ValidationError(detail='Too many signatures, swaps are only allowed to persist {} Eons.'.format(
                settings.SWAPS_PERSISTENCE_LIMIT), code=ErrorCode.TOO_MANY_FUTURE_SIGNATURES)

        signature_lengths = [
            len(attrs.get('debit_signature')),
            len(attrs.get('debit_balance_signature')),
            len(attrs.get('credit_signature')),
            len(attrs.get('credit_balance_signature')),
            len(attrs.get('credit_fulfillment_signature'))
        ]

        if len(set(signature_lengths)) > 1:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.WRONG_NUMBER_OF_SIGNATURES)

        if signature_lengths[0] < 1:
            raise serializers.ValidationError(
                detail='There should be at least 1 signature provided.', code=ErrorCode.WRONG_NUMBER_OF_SIGNATURES)

        attrs['valid_eons'] = signature_lengths[0]

        wallet = attrs.get('wallet')
        recipient = attrs.get('recipient')

        if wallet.registration_operator_authorization is None:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.DEBIT_WALLET_NOT_ADMITTED)
        if recipient.registration_operator_authorization is None:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.CREDIT_WALLET_NOT_ADMITTED)

        if not crypto.same_hex_value(wallet.address, recipient.address):
            raise serializers.ValidationError(
                detail='', code=ErrorCode.DEBIT_CREDIT_WALLET_ADDRESS_MISMATCH)
        elif wallet.token == recipient.token:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.DEBIT_CREDIT_TOKEN_ADDRESS_MATCH)

        return attrs

    def create(self, validated_data):
        wallet = validated_data.pop('wallet')
        recipient = validated_data.pop('recipient')

        if not TokenPair.objects.filter(token_from=wallet.token, token_to=recipient.token).exists():
            raise serializers.ValidationError(
                detail='', code=ErrorCode.TOKEN_PAIR_BLOCKED)

        # swap data
        valid_eons = validated_data.pop('valid_eons')
        swap_amount = validated_data.pop('amount')
        swap_nonce = validated_data.pop('nonce')
        sell_order = validated_data.pop('sell_order', True)
        swap_amount_swapped = validated_data.pop('amount_swapped')
        debit_signatures = validated_data.pop('debit_signature')
        debit_balance_signatures = validated_data.pop(
            'debit_balance_signature')
        credit_balance_signatures = validated_data.pop(
            'credit_balance_signature')
        credit_signatures = validated_data.pop('credit_signature')
        recipient_fulfillment_signatures = validated_data.pop(
            'credit_fulfillment_signature')

        # common transaction id
        tx_id = uuid.uuid4()
        tx_time = timezone.now()

        # cached items to be used later
        sender_available_balance = 0
        recipient_available_balance = 0

        swap_set = []

        debit_tx_set_index = []
        credit_tx_set_index = []
        # recipient_fulfillment_tx_set_index = []

        debit_tx_set_cache = []
        credit_tx_set_cache = []
        # recipient_fulfillment_tx_set_cache = []

        debit_balance_signature_records = []
        credit_balance_signature_records = []
        debit_signature_records = []
        credit_signature_records = []
        recipient_fulfillment_signature_records = []

        debit_balance_records = []
        credit_balance_records = []
        debit_active_state_records = []
        credit_active_state_records = []
        recipient_fulfillment_active_state_records = []

        initial_swap_confirmed = False

        # get current eon
        current_eon = LocalViewInterface.latest().eon_number()

        # initial swap eon should be the current eon number
        if validated_data.pop('eon_number') != current_eon:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.EON_NUMBER_OUT_OF_SYNC)

        wallets = sorted([wallet, recipient], key=lambda w: w.token.id)
        with RootCommitment.read_write_lock(suffix=current_eon, auto_renewal=False), wallets[0].lock(auto_renewal=False), wallets[1].lock(auto_renewal=False):
            if RootCommitment.objects.filter(eon_number=current_eon+1).exists():
                raise serializers.ValidationError(
                    detail='Checkpoint was already created for this eon.', code=ErrorCode.EON_NUMBER_OUT_OF_SYNC)

            for eon_number in range(current_eon, current_eon + valid_eons):
                swap = Transfer(
                    tx_id=tx_id,
                    wallet=wallet,
                    amount=swap_amount,
                    eon_number=eon_number,
                    recipient=recipient,
                    nonce=swap_nonce,
                    amount_swapped=swap_amount_swapped,
                    swap=True,
                    sell_order=sell_order,
                    time=tx_time)

                wallet_view_context = WalletTransferContext(
                    wallet=wallet, transfer=swap)
                recipient_view_context = WalletTransferContext(
                    wallet=recipient, transfer=swap)

                if eon_number == current_eon:
                    # Ensure sender log consistency
                    can_append_to_sender_log = wallet_view_context.can_schedule_transfer()
                    if can_append_to_sender_log is not True:
                        raise serializers.ValidationError(detail='Sender: {}'.format(
                            can_append_to_sender_log), code=ErrorCode.DEBIT_WALLET_CANNOT_ADD_TRANSACTION)

                    # Ensure recipient log consistency
                    can_append_to_recipient_log = recipient_view_context.can_schedule_transfer()
                    if can_append_to_recipient_log is not True:
                        raise serializers.ValidationError(detail='Recipient: {}'.format(
                            can_append_to_recipient_log), code=ErrorCode.CREDIT_WALLET_CANNOT_ADD_TRANSACTION)

                    # Ensure swap consistency
                    can_spend, sender_available_balance = wallet_view_context.can_send_transfer(
                        current_eon_number=current_eon,
                        using_only_appended_funds=False)
                    if can_spend is not True:
                        raise serializers.ValidationError(
                            detail=can_spend, code=ErrorCode.DEBIT_WALLET_OVERSPENDING)

                    # Ensure that sender balance is exactly equal to total outgoing amount
                    if sender_available_balance != swap.amount:
                        raise serializers.ValidationError(detail='Sender balance should be exactly equal to outgoing swap amount, {} != {}.'.format(
                            sender_available_balance, swap.amount), code=ErrorCode.DEBIT_WALLET_BALANCE_AMOUNT_MISMATCH)

                    # Ensure that recipient balance is zero
                    recipient_available_balance = recipient_view_context.available_funds_at_eon(
                        eon_number=eon_number, only_appended=False)
                    if recipient_available_balance != 0:
                        raise serializers.ValidationError(
                            detail='Recipient balance should be exactly zero.', code=ErrorCode.CREDIT_WALLET_BALANCE_NOT_ZERO)

                    current_eon_swap = swap
                    sender_highest_spendings, sender_highest_gains = wallet_view_context.off_chain_actively_sent_received_amounts(
                        eon_number=swap.eon_number,
                        only_appended=False)
                    recipient_highest_spendings, recipient_highest_gains = recipient_view_context.off_chain_actively_sent_received_amounts(
                        eon_number=swap.eon_number,
                        only_appended=False)
                else:
                    sender_highest_spendings, sender_highest_gains = 0, 0
                    recipient_highest_spendings, recipient_highest_gains = 0, 0

                # Minimum Debit Balance Marker
                debit_balance_marker_signature_data = debit_balance_signatures[
                    eon_number - current_eon]
                debit_balance_marker = MinimumAvailableBalanceMarker(
                    wallet=wallet,
                    eon_number=eon_number,
                    amount=0)

                debit_balance_marker_checksum = crypto.hex_value(
                    debit_balance_marker.checksum())
                debit_balance_marker_signature = Signature(
                    wallet=wallet,
                    checksum=debit_balance_marker_checksum,
                    value=debit_balance_marker_signature_data.get('value'))
                if not debit_balance_marker_signature.is_valid():
                    raise serializers.ValidationError(
                        detail='', code=ErrorCode.INVALID_DEBIT_BALANCE_SIGNATURE)

                # Minimum Credit Balance Marker
                credit_balance_marker_signature_data = credit_balance_signatures[
                    eon_number - current_eon]
                credit_balance_marker = MinimumAvailableBalanceMarker(
                    wallet=recipient,
                    eon_number=eon_number,
                    amount=0)

                credit_balance_marker_checksum = crypto.hex_value(
                    credit_balance_marker.checksum())
                credit_balance_marker_signature = Signature(
                    wallet=recipient,
                    checksum=credit_balance_marker_checksum,
                    value=credit_balance_marker_signature_data.get('value'))
                if not credit_balance_marker_signature.is_valid():
                    raise serializers.ValidationError(
                        detail='', code=ErrorCode.INVALID_CREDIT_BALANCE_SIGNATURE)
                assert(sender_available_balance == swap.amount)
                # Debit Authorization
                debit_active_state_signature_data = debit_signatures[eon_number - current_eon]
                debit_active_state, \
                    debit_active_state_signature, \
                    debit_transfer_index, \
                    debit_transfer_cache = check_active_state_signature(
                        swap,
                        wallet,
                        debit_active_state_signature_data,
                        eon_number > current_eon,
                        sender_available_balance,
                        sender_highest_spendings,
                        sender_highest_gains,
                        signature_type=SignatureType.DEBIT)

                # Credit Authorization
                credit_active_state_signature_data = credit_signatures[eon_number - current_eon]
                credit_active_state, \
                    credit_active_state_signature, \
                    credit_transfer_index, \
                    credit_transfer_cache = check_active_state_signature(
                        swap,
                        recipient,
                        credit_active_state_signature_data,
                        eon_number > current_eon,
                        recipient_available_balance,
                        recipient_highest_spendings,
                        recipient_highest_gains,
                        signature_type=SignatureType.CREDIT)

                # Finality Authorization
                recipient_fulfillment_active_state_signature_data = recipient_fulfillment_signatures[
                    eon_number - current_eon]
                recipient_fulfillment_active_state, \
                    recipient_fulfillment_active_state_signature, \
                    recipient_fulfillment_transfer_index, \
                    recipient_fulfillment_transfer_cache = check_active_state_signature(
                        swap,
                        recipient,
                        recipient_fulfillment_active_state_signature_data,
                        eon_number > current_eon,
                        recipient_available_balance,
                        recipient_highest_spendings,
                        recipient_highest_gains,
                        signature_type=SignatureType.FULFILLMENT)

                # accumulate records to be saved
                debit_balance_signature_records.append(
                    debit_balance_marker_signature)
                credit_balance_signature_records.append(
                    credit_balance_marker_signature)
                debit_signature_records.append(debit_active_state_signature)
                credit_signature_records.append(credit_active_state_signature)
                recipient_fulfillment_signature_records.append(
                    recipient_fulfillment_active_state_signature)

                debit_balance_records.append(debit_balance_marker)
                credit_balance_records.append(credit_balance_marker)
                debit_active_state_records.append(debit_active_state)
                credit_active_state_records.append(credit_active_state)
                recipient_fulfillment_active_state_records.append(
                    recipient_fulfillment_active_state)

                debit_tx_set_index.append(debit_transfer_index)
                credit_tx_set_index.append(credit_transfer_index)
                # recipient_fulfillment_tx_set_index.append(recipient_fulfillment_transfer_index)

                debit_tx_set_cache.append(debit_transfer_cache)
                credit_tx_set_cache.append(credit_transfer_cache)
                # recipient_fulfillment_tx_set_cache.append(recipient_fulfillment_transfer_cache)
                swap_set.append(swap)

            assert(
                swap_set[0] is not None and swap_set[0].eon_number == current_eon)
            assert(len(swap_set) == valid_eons)

            # locking context covers saving the state as well to make sure checkpoint creation is consistent
            with transaction.atomic():
                Signature.objects.bulk_create(
                    debit_balance_signature_records
                    +
                    credit_balance_signature_records
                    +
                    debit_signature_records
                    +
                    credit_signature_records
                    +
                    recipient_fulfillment_signature_records
                )

                for index in range(valid_eons):
                    debit_balance_records[index].signature = debit_balance_signature_records[index]
                    credit_balance_records[index].signature = credit_balance_signature_records[index]
                    debit_active_state_records[index].wallet_signature = debit_signature_records[index]
                    credit_active_state_records[index].wallet_signature = credit_signature_records[index]
                    recipient_fulfillment_active_state_records[
                        index].wallet_signature = recipient_fulfillment_signature_records[index]

                ActiveState.objects.bulk_create(
                    debit_active_state_records
                    +
                    credit_active_state_records
                    +
                    recipient_fulfillment_active_state_records
                )

                MinimumAvailableBalanceMarker.objects.bulk_create(
                    debit_balance_records
                    +
                    credit_balance_records
                )

                for index in range(valid_eons):
                    swap_set[index].sender_active_state = debit_active_state_records[index]
                    swap_set[index].recipient_active_state = credit_active_state_records[index]
                    swap_set[index].recipient_fulfillment_active_state = recipient_fulfillment_active_state_records[index]
                    swap_set[index].sender_balance_marker = debit_balance_records[index]

                    swap_set[index].sender_starting_balance = sender_available_balance
                    swap_set[index].recipient_starting_balance = recipient_available_balance

                    # cache swap index in sender active set
                    swap_set[index].sender_merkle_index = debit_tx_set_index[index]
                    # cache swap index in recipient active set
                    swap_set[index].recipient_merkle_index = credit_tx_set_index[index]
                    # cache active set merkle mountains height array and hash array for sender active set
                    swap_set[index].sender_merkle_hash_cache, swap_set[index].sender_merkle_height_cache = debit_tx_set_cache[index]
                    # cache active set merkle mountains height array and hash array for recipient active set
                    swap_set[index].recipient_merkle_hash_cache, swap_set[index].recipient_merkle_height_cache = debit_tx_set_cache[index]

                Transfer.objects.bulk_create(
                    swap_set
                )

                swap_set[0].sign_swap(
                    settings.HUB_OWNER_ACCOUNT_ADDRESS,
                    settings.HUB_OWNER_ACCOUNT_KEY)
                initial_swap_confirmed = True

        if initial_swap_confirmed:
            operator_celery.send_task(
                'auditor.tasks.on_swap_confirmation', args=[swap_set[0].id])

        return swap_set[0]
