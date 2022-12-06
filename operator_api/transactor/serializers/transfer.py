from django.conf import settings
from rest_framework import serializers
from auditor.serializers import ActiveStateSerializer, WalletSerializer
from contractor.interfaces import LocalViewInterface
from operator_api.crypto import hex_value, remove_0x_prefix
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Transfer, ActiveState, Signature, Wallet, MinimumAvailableBalanceMarker, RootCommitment
from django.db import transaction
from ledger.serializers import SignatureSerializer
from django.core.validators import MinValueValidator
from decimal import Decimal
from operator_api.celery import operator_celery
from operator_api.models import ErrorCode


class TransferSerializer(serializers.ModelSerializer):
    debit_signature = SignatureSerializer(write_only=True)
    debit_balance_signature = SignatureSerializer(write_only=True)
    debit_balance = serializers.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        write_only=True)

    wallet = WalletSerializer()
    recipient = WalletSerializer()
    sender_active_state = ActiveStateSerializer(
        read_only=True)
    time = serializers.IntegerField(source='get_timestamp', read_only=True)

    class Meta:
        model = Transfer
        fields = ('id', 'wallet', 'amount', 'time', 'eon_number', 'sender_active_state', 'recipient',
                  'nonce', 'debit_signature', 'debit_balance_signature', 'debit_balance', 'position', 'tx_id')
        read_only_fields = (
            'id', 'time', 'sender_active_state',  'position', 'tx_id')

        error_codes = [
            ErrorCode.INVALID_DEBIT_AMOUNT,
            ErrorCode.CREDIT_WALLET_NOT_ADMITTED,
            ErrorCode.DEBIT_WALLET_NOT_ADMITTED,
            ErrorCode.DEBIT_CREDIT_WALLET_ADDRESS_MATCH,
            ErrorCode.EON_NUMBER_OUT_OF_SYNC,
            ErrorCode.DEBIT_WALLET_EXCEEDED_SLA,
            ErrorCode.CREDIT_WALLET_EXCEEDED_SLA,
            ErrorCode.DEBIT_WALLET_CANNOT_ADD_TRANSACTION,
            ErrorCode.CREDIT_WALLET_CANNOT_ADD_TRANSACTION,
            ErrorCode.DEBIT_WALLET_OVERSPENDING,
            ErrorCode.DEBIT_WALLET_BALANCE_MARKER_EXCEED_BALANCE,
            ErrorCode.INVALID_DEBIT_BALANCE_SIGNATURE,
            ErrorCode.INVALID_DEBIT_SIGNATURE,
        ]

    # noinspection PyMethodMayBeStatic
    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.INVALID_DEBIT_AMOUNT)
        return value

    # noinspection PyMethodMayBeStatic
    def validate(self, attrs):
        wallet = attrs.get('wallet')
        recipient = attrs.get('recipient')

        if recipient.registration_operator_authorization is None:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.CREDIT_WALLET_NOT_ADMITTED)

        if wallet.registration_operator_authorization is None:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.DEBIT_WALLET_NOT_ADMITTED)

        if wallet == recipient:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.DEBIT_CREDIT_WALLET_ADDRESS_MATCH)

        return attrs

    def create(self, validated_data):
        active_state_signature_data = validated_data.pop('debit_signature')
        wallet = validated_data.pop('wallet')
        recipient = validated_data.pop('recipient')

        # get current eon
        current_eon = LocalViewInterface.latest().eon_number()

        # transfer eon should be the current eon number
        if validated_data.pop('eon_number') != current_eon:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.EON_NUMBER_OUT_OF_SYNC)

        # TODO refactor this such that the recipient is only locked after the sender's details are verified
        wallets = sorted([wallet, recipient], key=lambda w: w.trail_identifier)
        with RootCommitment.read_write_lock(suffix=current_eon, auto_renewal=False), wallets[0].lock(auto_renewal=False), wallets[1].lock(auto_renewal=False):
            if RootCommitment.objects.filter(eon_number=current_eon+1).exists():
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.EON_NUMBER_OUT_OF_SYNC)

            transfer = Transfer(
                wallet=wallet,
                amount=validated_data.pop('amount'),
                eon_number=current_eon,
                recipient=recipient,
                nonce=validated_data.pop('nonce'),
                passive=True)

            wallet_view_context = WalletTransferContext(
                wallet=wallet, transfer=transfer)
            recipient_view_context = WalletTransferContext(
                wallet=recipient, transfer=transfer)

            # Minimal SLA
            if not wallet.is_sla_exempt() and not recipient.is_sla_exempt():
                if not wallet.has_valid_sla():
                    sender_transfers_list = wallet_view_context.authorized_transfers_list(
                        only_appended=False,
                        force_append=True)
                    if len(sender_transfers_list) > settings.SLA_THRESHOLD:
                        raise serializers.ValidationError(
                            detail='', code=ErrorCode.DEBIT_WALLET_EXCEEDED_SLA)
                elif not recipient.has_valid_sla():
                    recipient_transfers_list = recipient_view_context.authorized_transfers_list(
                        only_appended=False,
                        force_append=True)
                    if len(recipient_transfers_list) > settings.SLA_THRESHOLD:
                        raise serializers.ValidationError(
                            detail='', code=ErrorCode.CREDIT_WALLET_EXCEEDED_SLA)

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

            # Ensure transfer consistency
            can_spend, currently_available_funds = wallet_view_context.can_send_transfer(
                current_eon_number=current_eon,
                using_only_appended_funds=False)
            if can_spend is not True:
                raise serializers.ValidationError(
                    detail=can_spend, code=ErrorCode.DEBIT_WALLET_OVERSPENDING)

            # Validate data
            concise_balance_marker_signature_data = validated_data.pop(
                'debit_balance_signature')
            concise_balance_marker_amount = validated_data.pop(
                'debit_balance')

            if concise_balance_marker_amount > currently_available_funds - transfer.amount:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.DEBIT_WALLET_BALANCE_MARKER_EXCEED_BALANCE)

            concise_balance_marker = MinimumAvailableBalanceMarker(
                wallet=wallet,
                eon_number=transfer.eon_number,
                amount=concise_balance_marker_amount)
            concise_balance_marker_checksum = hex_value(
                concise_balance_marker.checksum())
            concise_balance_marker_signature = Signature(
                wallet=transfer.wallet,
                checksum=concise_balance_marker_checksum,
                value=concise_balance_marker_signature_data.get('value'))
            if not concise_balance_marker_signature.is_valid():
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.INVALID_DEBIT_BALANCE_SIGNATURE)

            tx_set_tree = wallet_view_context.optimized_authorized_transfers_tree()
            tx_set_hash = hex_value(tx_set_tree.root_hash())
            transfer_index = tx_set_tree.merkle_tree_nonce_map.get(
                transfer.nonce)
            transfer_proof = tx_set_tree.proof(transfer_index)

            highest_spendings, highest_gains = wallet_view_context.off_chain_actively_sent_received_amounts(
                eon_number=transfer.eon_number,
                only_appended=False)
            active_state = ActiveState(
                wallet=wallet,
                updated_spendings=highest_spendings + transfer.amount,
                updated_gains=highest_gains,
                tx_set_hash=tx_set_hash,
                tx_set_proof_hashes=transfer_proof,
                tx_set_index=transfer_index,
                eon_number=transfer.eon_number)

            checksum = hex_value(active_state.checksum())
            active_state_signature = Signature(
                wallet=transfer.wallet,
                checksum=checksum,
                value=active_state_signature_data.get('value'))
            if not active_state_signature.is_valid():
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.INVALID_DEBIT_SIGNATURE)

            transfer.position = recipient_view_context.off_chain_passively_received_amount(
                eon_number=transfer.eon_number,
                only_appended=False)

            # locking context covers saving the state as well to make sure checkpoint creation is consistent
            with transaction.atomic():
                Signature.objects.bulk_create([
                    concise_balance_marker_signature,
                    active_state_signature
                ])

                concise_balance_marker.signature = concise_balance_marker_signature
                concise_balance_marker.save()

                active_state.wallet_signature = active_state_signature
                active_state.operator_signature = active_state.sign_active_state(
                    settings.HUB_OWNER_ACCOUNT_ADDRESS,
                    settings.HUB_OWNER_ACCOUNT_KEY)
                active_state.save()

                transfer.sender_active_state = active_state
                transfer.sender_balance_marker = concise_balance_marker
                # cache transfer index in sender active set
                transfer.sender_merkle_index = transfer_index
                # transfer.sender_merkle_root_cache = tx_set_hash
                # cache active set merkle mountains height array and hash array for recipient active set
                transfer.sender_merkle_hash_cache, transfer.sender_merkle_height_cache = tx_set_tree.merkle_cache_stacks()
                transfer.complete = True
                transfer.appended = True
                transfer.processed = True
                transfer.save()

        if transfer.appended:
            operator_celery.send_task(
                'auditor.tasks.on_transfer_confirmation', args=[transfer.id])

        return transfer
