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


class SwapFinalizationSerializer(serializers.ModelSerializer):
    finalization_signature = SignatureSerializer(write_only=True, many=True)

    recipient_finalization_active_state = ActiveStateSerializer(read_only=True)

    class Meta:
        model = Transfer
        fields = ('id', 'tx_id', 'finalization_signature',
                  'recipient_finalization_active_state')
        read_only_fields = (
            'id', 'tx_id', 'recipient_finalization_active_state',)
        error_codes = [
            ErrorCode.SWAP_NOT_FULFILLED,
            ErrorCode.SWAP_ALREADY_FROZEN,
            ErrorCode.SWAP_ALREADY_VOIDED,
            ErrorCode.SWAP_ALREADY_CLOSED,
            ErrorCode.SWAP_ALREADY_FINALIZED,
            ErrorCode.WRONG_NUMBER_OF_CREDIT_SIGNATURES,
            ErrorCode.INVALID_CREDIT_SIGNATURE,
            ErrorCode.INVALID_FUTURE_CREDIT_SIGNATURE,
        ]

    def update(self, swap, validated_data):
        current_swap = None
        is_swap_finalized = False
        with transaction.atomic():
            current_eon = LocalViewInterface.latest().eon_number()
            swap_set = Transfer.objects.select_for_update().filter(
                tx_id=swap.tx_id, eon_number__gte=current_eon, swap=True).order_by('eon_number')

            current_swap = swap_set[0]

            if not current_swap.complete:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_NOT_FULFILLED)
            elif current_swap.cancelled:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_ALREADY_FROZEN)
            elif current_swap.voided:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_ALREADY_VOIDED)
            elif current_swap.processed:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_ALREADY_CLOSED)
            elif current_swap.recipient_finalization_active_state is not None:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_ALREADY_FINALIZED)

            finalization_signatures = validated_data.pop(
                'finalization_signature')

            # state to save
            finalization_active_state_signature_records = []
            finalization_active_state_records = []

            if swap_set.count() != len(finalization_signatures):
                raise serializers.ValidationError(detail='Wrong number of finalization signatures, expected {} but got {}'.format(
                    swap_set.count(), len(finalization_signatures)), code=ErrorCode.WRONG_NUMBER_OF_CREDIT_SIGNATURES)

            recipient_view_context = WalletTransferContext(
                wallet=current_swap.recipient, transfer=current_swap)

            tx_set_tree = recipient_view_context.optimized_authorized_transfers_tree()
            tx_set_hash = crypto.hex_value(tx_set_tree.root_hash())
            transfer_index = tx_set_tree.merkle_tree_nonce_map.get(
                current_swap.nonce)
            transfer_proof = tx_set_tree.proof(transfer_index)

            highest_spendings, highest_gains = recipient_view_context.off_chain_actively_sent_received_amounts(
                eon_number=current_swap.eon_number,
                only_appended=False)

            finalization_active_state = ActiveState(
                wallet=current_swap.recipient,
                updated_spendings=highest_spendings + current_swap.amount_swapped,
                updated_gains=highest_gains + current_swap.amount_swapped,
                tx_set_hash=tx_set_hash,
                tx_set_proof_hashes=transfer_proof,
                tx_set_index=transfer_index,
                eon_number=current_swap.eon_number)

            finalization_active_state_signature_data = finalization_signatures[0]
            finalization_active_state_checksum = crypto.hex_value(
                finalization_active_state.checksum())
            finalization_active_state_signature = Signature(
                wallet=current_swap.recipient,
                checksum=finalization_active_state_checksum,
                value=finalization_active_state_signature_data.get('value'))

            if not finalization_active_state_signature.is_valid():
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.INVALID_CREDIT_SIGNATURE)

            finalization_active_state_signature_records.append(
                finalization_active_state_signature)
            finalization_active_state_records.append(finalization_active_state)

            # calculate future spent, gained, empty tx set
            future_spent_gained = max(
                highest_spendings, highest_gains) + swap.amount_swapped + 1
            empty_tx_set_hash = crypto.hex_value(NODE_CACHE[0]['hash'])

            for index in range(1, len(swap_set)):
                future_swap = swap_set[index]
                finalization_active_state = ActiveState(
                    wallet=future_swap.recipient,
                    updated_spendings=future_spent_gained,
                    updated_gains=future_spent_gained,
                    tx_set_hash=empty_tx_set_hash,
                    # any dummy value
                    tx_set_proof_hashes='',
                    # any dummy value
                    tx_set_index=0,
                    eon_number=future_swap.eon_number)

                finalization_active_state_checksum = crypto.hex_value(
                    finalization_active_state.checksum())
                finalization_active_state_signature = Signature(
                    wallet=swap.recipient,
                    checksum=finalization_active_state_checksum,
                    value=finalization_signatures[index].get('value'))

                if not finalization_active_state_signature.is_valid():
                    raise serializers.ValidationError(
                        detail='', code=ErrorCode.INVALID_FUTURE_CREDIT_SIGNATURE)

                finalization_active_state_signature_records.append(
                    finalization_active_state_signature)
                finalization_active_state_records.append(
                    finalization_active_state)

            Signature.objects.bulk_create(
                finalization_active_state_signature_records
            )

            with current_swap.lock(auto_renewal=False), current_swap.wallet.lock(auto_renewal=False), current_swap.recipient.lock(auto_renewal=False):
                for index in range(len(finalization_active_state_records)):
                    finalization_active_state_records[index].wallet_signature = finalization_active_state_signature_records[index]

                ActiveState.objects.bulk_create(
                    finalization_active_state_records
                )

                for index in range(len(swap_set)):
                    swap_set[index].recipient_finalization_active_state = finalization_active_state_records[index]
                    if index > 0:
                        swap_set[index].voided = True
                        swap_set[index].appended = False
                        swap_set[index].processed = True

                Transfer.objects.bulk_update(swap_set, [
                                             'recipient_finalization_active_state', 'voided', 'appended', 'processed'])

                swap_set[0].sign_swap_finalization(
                    settings.HUB_OWNER_ACCOUNT_ADDRESS,
                    settings.HUB_OWNER_ACCOUNT_KEY)
                swap_set[0].close(complete=True, appended=True)

                current_swap = swap_set[0]
                is_swap_finalized = True

        if is_swap_finalized:
            operator_celery.send_task(
                'auditor.tasks.on_swap_finalization', args=[current_swap.id])
        return current_swap
