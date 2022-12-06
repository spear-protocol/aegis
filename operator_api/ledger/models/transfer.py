from decimal import Decimal
import uuid
from django.apps import apps
from django.core.validators import MinValueValidator
from django.db import models
from .transaction import Transaction
from eth_utils import keccak
from operator_api import crypto
from django.db import transaction


# Off-chain Transfer
class Transfer(Transaction):
    sender_balance_marker = models.ForeignKey(
        to='MinimumAvailableBalanceMarker',
        on_delete=models.PROTECT,
        related_name='transfer_sender_balance_marker')
    sender_active_state = models.ForeignKey(
        to='ActiveState',
        on_delete=models.PROTECT,
        related_name='sender_active_state')
    recipient = models.ForeignKey(
        to='Wallet',
        on_delete=models.PROTECT,
        related_name="transfer_recipient_wallet")
    recipient_active_state = models.ForeignKey(
        to='ActiveState',
        on_delete=models.PROTECT,
        related_name='recipient_active_state',
        blank=True,
        null=True)
    nonce = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        blank=True,
        null=True,
        db_index=True)
    passive = models.BooleanField(
        default=False,
        db_index=True)
    position = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        blank=True,
        null=True,
        db_index=True)
    sender_finalization_active_state = models.ForeignKey(
        to='ActiveState',
        on_delete=models.PROTECT,
        related_name='sender_finalization_active_state',
        blank=True,
        null=True)
    processed = models.BooleanField(
        default=False,
        db_index=True)
    complete = models.BooleanField(
        default=False,
        db_index=True)
    cancelled = models.BooleanField(
        default=False,
        db_index=True)
    voided = models.BooleanField(
        default=False,
        db_index=True)
    appended = models.BooleanField(
        default=False,
        db_index=True)
    swap = models.BooleanField(
        default=False,
        db_index=True)
    final_receipt_hashes = models.CharField(
        max_length=64 * 32,
        blank=True,
        null=True)
    final_receipt_values = models.CharField(
        max_length=80 * 32,
        blank=True,
        null=True)
    final_receipt_index = models.BigIntegerField(
        blank=True,
        null=True)
    amount_swapped = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('1'))],
        blank=True,
        null=True)
    recipient_fulfillment_active_state = models.ForeignKey(
        to='ActiveState',
        on_delete=models.PROTECT,
        related_name='recipient_fulfillment_active_state',
        blank=True,
        null=True)
    recipient_finalization_active_state = models.ForeignKey(
        to='ActiveState',
        on_delete=models.PROTECT,
        related_name='recipient_finalization_active_state',
        blank=True,
        null=True)
    swap_freezing_signature = models.ForeignKey(
        to='Signature',
        on_delete=models.PROTECT,
        related_name='swap_freezing_signature',
        blank=True,
        null=True)
    sender_cancellation_active_state = models.ForeignKey(
        to='ActiveState',
        on_delete=models.PROTECT,
        related_name='sender_cancellation_active_state',
        blank=True,
        null=True)
    recipient_cancellation_active_state = models.ForeignKey(
        to='ActiveState',
        on_delete=models.PROTECT,
        related_name='recipient_cancellation_active_state',
        blank=True,
        null=True)
    sender_merkle_hash_cache = models.CharField(
        max_length=65 * 32,
        blank=True,
        null=True)
    sender_merkle_height_cache = models.CharField(
        max_length=4 * 32,
        blank=True,
        null=True)
    sender_merkle_index = models.BigIntegerField(
        blank=True,
        null=True)
    # sender_merkle_root_cache = models.CharField(
    #     max_length=65,
    #     blank=True,
    #     null=True)
    recipient_merkle_hash_cache = models.CharField(
        max_length=65 * 32,
        blank=True,
        null=True)
    recipient_merkle_height_cache = models.CharField(
        max_length=4 * 32,
        blank=True,
        null=True)
    recipient_merkle_index = models.BigIntegerField(
        blank=True,
        null=True)
    # recipient_merkle_root_cache = models.CharField(
    #     max_length=65,
    #     blank=True,
    #     null=True)
    tx_id = models.UUIDField(
        default=uuid.uuid4,
        blank=True,
        null=True,
        db_index=True)
    sender_starting_balance = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        blank=True,
        null=True)
    recipient_starting_balance = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        blank=True,
        null=True)
    sell_order = models.BooleanField(
        default=True)

    class Meta:
        unique_together = (
            ('eon_number', 'recipient', 'nonce'),
            ('eon_number', 'wallet', 'nonce'),
            ('eon_number', 'tx_id'))

    def checksum(self, wallet_transfer_context, is_last_transfer=False, starting_balance=None, assume_active_state_exists=False):
        if not self.is_swap():
            nonce = int(self.nonce)

            if self.passive:
                if self.position is None or is_last_transfer and self.sender_finalization_active_state is None:
                    hash_position = 2 ** 256 - 1
                else:
                    hash_position = self.position
                # nonce is hash(position || nonce)
                hash_values = [
                    crypto.uint256(int(hash_position)),
                    crypto.uint256(int(self.nonce)),
                ]
                nonce = crypto.big_endian_to_int(
                    crypto.hash_array(hash_values))

            representation = [
                keccak(crypto.address(self.recipient.address if self.wallet ==
                                      wallet_transfer_context.wallet else self.wallet.address)),
                crypto.uint256(int(self.amount)),
                crypto.uint64(int(self.recipient.trail_identifier)),
                crypto.uint256(nonce),
            ]
        else:
            if starting_balance is None:
                starting_balance = int(
                    wallet_transfer_context.starting_balance_in_eon(self.eon_number))

            is_cancelled = self.cancelled and (
                assume_active_state_exists or self.recipient_cancellation_active_state is not None)

            if self.recipient == wallet_transfer_context.wallet and (self.complete or is_cancelled):
                starting_balance = 2 ** 256 - 1

            representation = [
                keccak(crypto.address(self.wallet.token.address)),
                keccak(crypto.address(self.recipient.token.address)),
                crypto.uint64(int(self.recipient.trail_identifier)),
                crypto.uint256(int(self.amount)),
                crypto.uint256(int(self.amount_swapped)),
                crypto.uint256(starting_balance),
                crypto.uint256(int(self.nonce)),
            ]
        return crypto.hash_array(representation)

    def swap_cancellation_message_checksum(self):
        representation = [
            keccak(crypto.address(self.wallet.token.address)),
            keccak(crypto.address(self.recipient.token.address)),
            crypto.uint256(int(self.nonce)),
        ]
        return crypto.hash_array(representation)

    # return dict of passive transfer
    # to be used as leaf when constructing passive transfer augmented merkle tree
    def passive_shorthand(self, wallet_transfer_context, index=None, index_map=None):
        if index_map is not None:
            index_map[int(self.nonce)] = index

        return {
            'wallet': self.recipient.address,
            'left': int(self.position),
            'right': int(self.position + self.amount),
            'nonce': self.nonce,
            'hash': self.checksum(wallet_transfer_context)
        }

    def shorthand(self, wallet_transfer_context, index=None, index_map=None, is_last_transfer=False, starting_balance=None, assume_active_state_exists=False):
        if index_map is not None:
            index_map[int(self.nonce)] = index

        return {
            'wallet': self.recipient.address if self.wallet == wallet_transfer_context.wallet else self.wallet.address,
            'token': self.wallet.token.address,
            'amount': int(self.amount),
            'recipient_trail_identifier': int(self.recipient.trail_identifier),
            'nonce': self.nonce,
            'hash': self.checksum(wallet_transfer_context, is_last_transfer=is_last_transfer, starting_balance=starting_balance, assume_active_state_exists=assume_active_state_exists),
            'processed': self.processed,
            'complete': self.complete,
        }

    def is_pending_recipient_approval(self):
        return self.recipient_active_state is None

    def is_signed_by_operator(self):
        return self.appended \
            and self.sender_active_state.operator_signature is not None \
            and self.recipient_active_state.operator_signature is not None

    def is_timed_out_transfer(self):
        return self.is_transfer() and self.processed and not self.complete and self.is_pending_recipient_approval() and self.voided

    def is_transfer(self):
        return not self.is_swap()

    def is_swap(self):
        return self.swap

    def matched_amounts(self, all_eons=False):
        Matching = apps.get_model('ledger', 'Matching')

        if all_eons:
            as_left = Matching.objects.filter(left_order_tx_id=self.tx_id)
            as_right = Matching.objects.filter(right_order_tx_id=self.tx_id)
        else:
            as_left = Matching.objects.filter(
                left_order_tx_id=self.tx_id, eon_number=self.eon_number)
            as_right = Matching.objects.filter(
                right_order_tx_id=self.tx_id, eon_number=self.eon_number)

        as_left = as_left.aggregate(models.Sum('left_deducted_right_granted_amount'), models.Sum(
            'right_deducted_left_granted_amount'))
        as_right = as_right.aggregate(models.Sum(
            'left_deducted_right_granted_amount'), models.Sum('right_deducted_left_granted_amount'))

        matched_out = (as_left['left_deducted_right_granted_amount__sum'] or 0) + \
            (as_right['right_deducted_left_granted_amount__sum'] or 0)
        matched_in = (as_left['right_deducted_left_granted_amount__sum'] or 0) + \
            (as_right['left_deducted_right_granted_amount__sum'] or 0)

        return matched_out, matched_in

    def is_open_swap(self):
        return self.is_swap() and not self.processed

    def is_fulfilled_swap(self):
        return self.is_swap() and self.complete

    def retire_swap(self):
        if not self.is_open_swap():
            return
        self.close(
            appended=self.is_signed_by_operator(),
            voided=not self.is_signed_by_operator() and not self.complete,
            complete=self.complete)

    def sign_swap(self, address, private_key):
        if self.is_swap() \
                and not self.processed \
                and not self.is_signed_by_operator() \
                and not self.voided \
                and not self.cancelled \
                and not self.complete:
            self.sender_active_state.operator_signature = self.sender_active_state.sign_active_state(
                address, private_key)
            self.sender_active_state.operator_signature.save()
            self.sender_active_state.save()
            self.recipient_active_state.operator_signature = self.recipient_active_state.sign_active_state(
                address, private_key)
            self.recipient_active_state.operator_signature.save()
            self.recipient_active_state.save()
            self.appended = True
            self.save()

    def sign_swap_fulfillment(self, address, private_key):
        if self.is_swap() \
                and not self.processed \
                and self.is_signed_by_operator() \
                and self.complete \
                and self.recipient_fulfillment_active_state.operator_signature is None:
            self.recipient_fulfillment_active_state.operator_signature = self.recipient_fulfillment_active_state.sign_active_state(
                address, private_key)
            self.recipient_fulfillment_active_state.operator_signature.save()
            self.recipient_fulfillment_active_state.save()
            self.save()

    def sign_swap_finalization(self, address, private_key):
        if self.is_swap() \
                and not self.processed\
                and self.is_signed_by_operator()\
                and self.complete \
                and self.recipient_finalization_active_state is not None\
                and self.recipient_finalization_active_state.operator_signature is None:
            self.recipient_finalization_active_state.operator_signature = self.recipient_finalization_active_state.sign_active_state(
                address, private_key)
            self.recipient_finalization_active_state.operator_signature.save()
            self.recipient_finalization_active_state.save()
            self.save()

    def sign_swap_cancellation(self, address, private_key):
        if self.is_swap() \
                and not self.processed\
                and self.is_signed_by_operator()\
                and self.cancelled \
                and self.sender_cancellation_active_state is not None \
                and self.recipient_cancellation_active_state is not None \
                and self.sender_cancellation_active_state.operator_signature is None \
                and self.recipient_cancellation_active_state.operator_signature is None:
            self.sender_cancellation_active_state.operator_signature = self.sender_cancellation_active_state.sign_active_state(
                address, private_key)
            self.sender_cancellation_active_state.operator_signature.save()
            self.sender_cancellation_active_state.save()
            self.recipient_cancellation_active_state.operator_signature = self.recipient_cancellation_active_state.sign_active_state(
                address, private_key)
            self.recipient_cancellation_active_state.operator_signature.save()
            self.recipient_cancellation_active_state.save()
            self.save()

    def change_state(self, processed=False, complete=False, cancelled=False, appended=False, voided=False):
        with transaction.atomic():
            self.processed = processed
            self.complete = complete
            self.cancelled = cancelled
            self.appended = appended
            self.voided = voided
            self.save()
            if self.complete or self.cancelled or self.voided:
                Transfer.objects.filter(tx_id=self.tx_id, eon_number__gt=self.eon_number, swap=True, voided=False).update(
                    processed=True, appended=False, voided=True)

    def close(self, complete=False, cancelled=False, appended=False, voided=False):
        self.change_state(
            processed=True,
            complete=complete,
            cancelled=cancelled,
            appended=appended,
            voided=voided)
