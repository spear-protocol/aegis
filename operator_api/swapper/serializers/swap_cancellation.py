from rest_framework import serializers
from django.db import transaction
from django.conf import settings
from operator_api import crypto
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Transfer, Signature, ActiveState
from ledger.serializers import SignatureSerializer
from operator_api.zero_merkle_root_cache import NODE_CACHE
from contractor.interfaces import LocalViewInterface
from operator_api.models import ErrorCode
from auditor.serializers import ActiveStateSerializer
from operator_api.celery import operator_celery


class SwapCancellationSerializer(serializers.ModelSerializer):
    sender_cancellation_signature = SignatureSerializer(
        write_only=True, many=True)
    recipient_cancellation_signature = SignatureSerializer(
        write_only=True, many=True)

    sender_cancellation_active_state = ActiveStateSerializer(read_only=True)
    recipient_cancellation_active_state = ActiveStateSerializer(read_only=True)

    class Meta:
        model = Transfer
        fields = ('id', 'tx_id', 'sender_cancellation_signature', 'recipient_cancellation_signature',
                  'sender_cancellation_active_state', 'recipient_cancellation_active_state')
        read_only_fields = ('id', 'tx_id', 'sender_cancellation_active_state',
                            'recipient_cancellation_active_state')
        error_codes = [
            ErrorCode.WRONG_NUMBER_OF_DEBIT_SIGNATURES,
            ErrorCode.WRONG_NUMBER_OF_CREDIT_SIGNATURES,
            ErrorCode.SWAP_NOT_FROZEN,
            ErrorCode.SWAP_ALREADY_CLOSED,
            ErrorCode.MISSING_FREEZING_SIGNATURE,
            ErrorCode.SWAP_ALREADY_CANCELLED,
            ErrorCode.INVALID_CREDIT_SIGNATURE,
            ErrorCode.INVALID_FUTURE_CREDIT_SIGNATURE,
            ErrorCode.INVALID_DEBIT_SIGNATURE,
            ErrorCode.INVALID_FUTURE_DEBIT_SIGNATURE,
        ]

    def update(self, swap, validated_data):
        current_swap = None
        is_swap_cancelled = False
        with transaction.atomic():
            current_eon = LocalViewInterface.latest().eon_number()
            swap_set = Transfer.objects.select_for_update().filter(
                tx_id=swap.tx_id, eon_number__gte=current_eon, swap=True).order_by('eon_number')

            current_swap = swap_set[0]

            if not current_swap.cancelled:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_NOT_FROZEN)
            elif current_swap.processed:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_ALREADY_CLOSED)
            elif current_swap.swap_freezing_signature is None:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.MISSING_FREEZING_SIGNATURE)
            elif None not in [current_swap.sender_cancellation_active_state, current_swap.recipient_cancellation_active_state]:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_ALREADY_CANCELLED)

            sender_cancellation_signatures = validated_data.get(
                'sender_cancellation_signature')
            recipient_cancellation_signatures = validated_data.get(
                'recipient_cancellation_signature')

            # state to save
            sender_cancellation_active_state_signature_records = []
            sender_cancellation_active_state_records = []
            recipient_cancellation_active_state_signature_records = []
            recipient_cancellation_active_state_records = []

            # make sure appropriate number of signatures was provided
            if swap_set.count() != len(sender_cancellation_signatures):
                raise serializers.ValidationError(detail='Wrong number of sender cancellation signatures, expected {} but got {}'.format(
                    swap_set.count(), len(sender_cancellation_signatures)), code=ErrorCode.WRONG_NUMBER_OF_DEBIT_SIGNATURES)

            if swap_set.count() != len(recipient_cancellation_signatures):
                raise serializers.ValidationError(detail='Wrong number of recipient cancellation signatures, expected {} but got {}'.format(
                    swap_set.count(), len(recipient_cancellation_signatures)), code=ErrorCode.WRONG_NUMBER_OF_CREDIT_SIGNATURES)

            sender_view_context = WalletTransferContext(
                wallet=current_swap.wallet,
                transfer=current_swap)

            debit_tx_set_tree = sender_view_context.optimized_authorized_transfers_tree(
                force_append=False,
                assume_active_state_exists=True)
            tx_set_hash = crypto.hex_value(debit_tx_set_tree.root_hash())
            transfer_index = debit_tx_set_tree.merkle_tree_nonce_map.get(
                current_swap.nonce)
            transfer_proof = debit_tx_set_tree.proof(transfer_index)

            sender_highest_spendings, sender_highest_gains = sender_view_context.off_chain_actively_sent_received_amounts(
                eon_number=current_swap.eon_number,
                only_appended=False)

            matched_out, _ = current_swap.matched_amounts()

            sender_highest_gains += current_swap.amount - matched_out

            sender_cancellation_active_state = ActiveState(
                wallet=current_swap.wallet,
                updated_spendings=sender_highest_spendings,
                updated_gains=sender_highest_gains,
                tx_set_hash=tx_set_hash,
                tx_set_proof_hashes=transfer_proof,
                tx_set_index=transfer_index,
                eon_number=current_swap.eon_number)

            sender_cancellation_active_state_checksum = crypto.hex_value(
                sender_cancellation_active_state.checksum())
            sender_cancellation_active_state_signature = Signature(
                wallet=current_swap.wallet,
                checksum=sender_cancellation_active_state_checksum,
                value=sender_cancellation_signatures[0].get('value'))

            if not sender_cancellation_active_state_signature.is_valid():
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.INVALID_DEBIT_SIGNATURE)

            sender_cancellation_active_state_records.append(
                sender_cancellation_active_state)
            sender_cancellation_active_state_signature_records.append(
                sender_cancellation_active_state_signature)

            recipient_view_context = WalletTransferContext(
                wallet=current_swap.recipient,
                transfer=current_swap)

            credit_tx_set_tree = recipient_view_context.optimized_authorized_transfers_tree(
                force_append=False,
                assume_active_state_exists=True)
            tx_set_hash = crypto.hex_value(credit_tx_set_tree.root_hash())
            transfer_index = credit_tx_set_tree.merkle_tree_nonce_map.get(
                current_swap.nonce)
            transfer_proof = credit_tx_set_tree.proof(transfer_index)

            recipient_highest_spendings, recipient_highest_gains = recipient_view_context.off_chain_actively_sent_received_amounts(
                eon_number=current_swap.eon_number,
                only_appended=False)

            recipient_cancellation_active_state = ActiveState(
                wallet=current_swap.recipient,
                updated_spendings=recipient_highest_spendings + current_swap.amount_swapped,
                updated_gains=recipient_highest_gains + current_swap.amount_swapped,
                tx_set_hash=tx_set_hash,
                tx_set_proof_hashes=transfer_proof,
                tx_set_index=transfer_index,
                eon_number=current_swap.eon_number)

            recipient_cancellation_active_state_checksum = crypto.hex_value(
                recipient_cancellation_active_state.checksum())
            recipient_cancellation_active_state_signature = Signature(
                wallet=current_swap.recipient,
                checksum=recipient_cancellation_active_state_checksum,
                value=recipient_cancellation_signatures[0].get('value'))

            if not recipient_cancellation_active_state_signature.is_valid():
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.INVALID_CREDIT_SIGNATURE)

            recipient_cancellation_active_state_records.append(
                recipient_cancellation_active_state)
            recipient_cancellation_active_state_signature_records.append(
                recipient_cancellation_active_state_signature)

            # calculate future spent, gained, empty tx set
            empty_tx_set_hash = crypto.hex_value(NODE_CACHE[0]['hash'])
            sender_future_spent_gained = max(
                sender_highest_spendings, sender_highest_gains) + 1
            recipient_future_spent_gained = max(
                recipient_highest_spendings, recipient_highest_gains) + current_swap.amount_swapped + 1

            for index in range(1, len(swap_set)):
                future_swap = swap_set[index]
                sender_cancellation_active_state = ActiveState(
                    wallet=future_swap.wallet,
                    updated_spendings=sender_future_spent_gained,
                    updated_gains=sender_future_spent_gained,
                    tx_set_hash=empty_tx_set_hash,
                    # any dummy value
                    tx_set_proof_hashes='',
                    # any dummy value
                    tx_set_index=0,
                    eon_number=future_swap.eon_number)

                sender_cancellation_active_state_checksum = crypto.hex_value(
                    sender_cancellation_active_state.checksum())
                sender_cancellation_active_state_signature = Signature(
                    wallet=future_swap.recipient,
                    checksum=sender_cancellation_active_state_checksum,
                    value=sender_cancellation_signatures[index].get('value'))

                if not sender_cancellation_active_state_signature.is_valid():
                    raise serializers.ValidationError(
                        detail='', code=ErrorCode.INVALID_FUTURE_DEBIT_SIGNATURE)

                sender_cancellation_active_state_signature_records.append(
                    sender_cancellation_active_state_signature)
                sender_cancellation_active_state_records.append(
                    sender_cancellation_active_state)

                recipient_cancellation_active_state = ActiveState(
                    wallet=future_swap.recipient,
                    updated_spendings=recipient_future_spent_gained,
                    updated_gains=recipient_future_spent_gained,
                    tx_set_hash=empty_tx_set_hash,
                    # any dummy value
                    tx_set_proof_hashes='',
                    # any dummy value
                    tx_set_index=0,
                    eon_number=future_swap.eon_number)

                recipient_cancellation_active_state_checksum = crypto.hex_value(
                    recipient_cancellation_active_state.checksum())
                recipient_cancellation_active_state_signature = Signature(
                    wallet=future_swap.recipient,
                    checksum=recipient_cancellation_active_state_checksum,
                    value=recipient_cancellation_signatures[index].get('value'))

                if not recipient_cancellation_active_state_signature.is_valid():
                    raise serializers.ValidationError(
                        detail='', code=ErrorCode.INVALID_FUTURE_CREDIT_SIGNATURE)

                recipient_cancellation_active_state_signature_records.append(
                    recipient_cancellation_active_state_signature)
                recipient_cancellation_active_state_records.append(
                    recipient_cancellation_active_state)

            assert(len(swap_set) == len(
                sender_cancellation_active_state_signature_records))
            assert(len(swap_set) == len(
                recipient_cancellation_active_state_signature_records))

            Signature.objects.bulk_create(
                sender_cancellation_active_state_signature_records
                +
                recipient_cancellation_active_state_signature_records
            )

            with current_swap.lock(auto_renewal=False), current_swap.wallet.lock(auto_renewal=False), current_swap.recipient.lock(auto_renewal=False):
                for index in range(len(swap_set)):
                    sender_cancellation_active_state_records[
                        index].wallet_signature = sender_cancellation_active_state_signature_records[index]
                    recipient_cancellation_active_state_records[
                        index].wallet_signature = recipient_cancellation_active_state_signature_records[index]

                ActiveState.objects.bulk_create(
                    sender_cancellation_active_state_records
                    +
                    recipient_cancellation_active_state_records
                )

                for index in range(len(swap_set)):
                    swap_set[index].sender_cancellation_active_state = sender_cancellation_active_state_records[index]
                    swap_set[index].recipient_cancellation_active_state = recipient_cancellation_active_state_records[index]
                    if index > 0:
                        swap_set[index].voided = True
                        swap_set[index].appended = False
                        swap_set[index].processed = True

                Transfer.objects.bulk_update(swap_set, [
                                             'sender_cancellation_active_state', 'recipient_cancellation_active_state', 'voided', 'appended', 'processed'])

                swap_set[0].sign_swap_cancellation(
                    settings.HUB_OWNER_ACCOUNT_ADDRESS,
                    settings.HUB_OWNER_ACCOUNT_KEY)
                swap_set[0].close(cancelled=True, appended=True)
                current_swap = swap_set[0]
                is_swap_cancelled = True

        if is_swap_cancelled:
            operator_celery.send_task(
                'auditor.tasks.on_swap_cancellation', args=[current_swap.id])
        return current_swap
