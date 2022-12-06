from typing import Union, Tuple

from django.db.models import Q, QuerySet, Max, Sum, F, Case, When

from operator_api.tx_merkle_tree import TransactionMerkleTree
from operator_api.tx_optimized_merkle_tree import OptimizedTransactionMerkleTree
from operator_api.passive_delivery_merkle_tree import PassiveDeliveryMerkleTree
from ledger.models import Wallet, Transfer, RootCommitment, Deposit, WithdrawalRequest, ExclusiveBalanceAllotment, MinimumAvailableBalanceMarker, \
    ActiveState


class WalletTransferContext:
    def __init__(self, wallet: Wallet, transfer: Union[Transfer, None]):
        self.wallet = wallet
        self.transfer = transfer

    def filter_transfers_by_transfer_id(self, transfers: QuerySet):
        # If this context has no transfer, or its transfer has no receipt, do nothing as there's no receipt id
        if self.transfer is None or self.transfer.id is None:
            return transfers
        # Filter out transfers approved by their recipients after this context's transfer
        return transfers.filter(id__lte=self.transfer.id)

    def filter_transfers_by_transfer_set_index(self, transfers: QuerySet):
        # If this context has no transfer, or its transfer has no id, do nothing as there's no index to filter with
        if self.transfer is None:
            return transfers

        if self.transfer.id is None:
            return transfers

        # Find transfer in set, where index field is added
        try:
            transfer = transfers.get(id=self.transfer.id)
        except Transfer.DoesNotExist:
            return transfers

        return transfers.filter(index__lte=transfer.index)

    def filter_transfers_by_recipient_active_state_id(self, transfers: QuerySet):
        # If this context has no transfer, or its transfer has no receipt, do nothing as there's no receipt id
        if self.transfer is None or self.transfer.recipient_active_state_id is None:
            return transfers
        # If this context is for an incoming tx pending a receipt, do nothing as there's no receipt id
        # TODO: remove potential redundancy
        if self.wallet == self.transfer.recipient and self.transfer.is_pending_recipient_approval():
            return transfers
        # Filter out transfers approved by their recipients after this context's transfer
        return transfers.filter(recipient_active_state_id__lte=self.transfer.recipient_active_state_id)

    def filter_transfers_by_position(self, transfers: QuerySet):
        if self.transfer is None or not self.transfer.passive:
            return transfers
        return transfers.filter(position__lte=self.transfer.position)

    def filter_transactions_by_time(self, transactions: QuerySet):
        # If context has no transfer or its transfer is not yet in the database, do nothing
        if self.transfer is None or self.transfer.id is None:
            return transactions
        # If this context is for an incoming tx pending a receipt, do nothing
        if self.wallet == self.transfer.recipient and self.transfer.is_pending_recipient_approval():
            return transactions
        # Filter out transfers started after this context's transfer
        if self.transfer.passive:
            return transactions.filter(time__lte=self.transfer.time)
        return transactions.filter(time__lte=self.transfer.recipient_active_state.time)

    def can_schedule_transfer(self):
        if not self.wallet.is_admitted():
            return 'Wallet has not yet been admitted to commit chain.'
        if self.transfer.wallet == self.wallet:  # This context is for an outgoing transfer
            if self.latest_touched_active_transfer_eon_number() > self.transfer.eon_number:
                return 'A newer eon has already been touched by the sender wallet.'
            pending_tx = self.outgoing_transfer_pending_receipt()
            if pending_tx is not None and pending_tx.id != self.transfer.id:
                return '{}: Outgoing transfer {} is pending receipt for the sender wallet.'.format(self.transfer.id, pending_tx.id)
            pending_swap = self.swap_in_progress(self.transfer.eon_number)
            if pending_swap is not None and pending_swap.id != self.transfer.id:
                return '{}: Swap {} is in progress for the sender wallet.'.format(self.transfer.id, pending_swap.id)
        else:  # This context is for an incoming transfer
            if not self.transfer.is_pending_recipient_approval():
                if not self.transfer.passive and self.latest_touched_active_transfer_eon_number() > self.transfer.eon_number:
                    return 'A newer eon has already been touched by the recipient wallet.'
                pending_tx = self.outgoing_transfer_pending_receipt()
                if pending_tx is not None:
                    return 'Outgoing transfer {} is pending receipt for the recipient wallet.'.format(pending_tx.id)
            # should block receiving transfer if this account has a pending multi eon swap
            pending_swap = self.swap_in_progress(self.transfer.eon_number)
            if pending_swap is not None and pending_swap.id != self.transfer.id:
                return '{}: Swap {} is in progress for the recipient wallet.'.format(self.transfer.id, pending_swap.id)
        return True

    def can_append_transfer(self):
        can_schedule = self.can_schedule_transfer()
        if can_schedule is not True:
            return can_schedule

        return True

    def can_send_transfer(self, current_eon_number, using_only_appended_funds):
        is_checkpoint_created = RootCommitment.objects.filter(
            eon_number=current_eon_number).exists()

        # Ensure loose sync sanity
        if is_checkpoint_created and self.transfer.eon_number < current_eon_number:
            return 'Outdated transfer eon number', None

        spendable = self.loosely_available_funds_at_eon(
            eon_number=self.transfer.eon_number,
            current_eon_number=current_eon_number,
            is_checkpoint_created=is_checkpoint_created,
            only_appended=using_only_appended_funds)

        if self.transfer.amount > spendable:
            return 'Amount too high: {} > {}'.format(self.transfer.amount, spendable), None
        elif self.transfer.amount < 0:
            return 'Negative transfer amount.', None

        return True, spendable

    def get_passive_values(self, eon_number):
        passive_marker = 0
        passive_amount = 0
        passive_checksum = b'\0' * 32

        last_appended_transfer, _ = self.last_appended_active_transfer(
            eon_number=eon_number)
        last_appended_incoming_passive_transfer = self.last_appended_incoming_passive_transfer(
            eon_number=eon_number)

        if last_appended_transfer is not None and last_appended_transfer.passive and last_appended_transfer.sender_finalization_active_state is None:
            passive_marker = last_appended_transfer.position

        if last_appended_incoming_passive_transfer is not None:
            passive_checksum = self.incoming_passive_transfers_tree_root(
                only_appended=True,
                force_append=False,
                eon_number=eon_number)
            passive_amount = self.off_chain_passively_received_amount(
                eon_number=eon_number,
                only_appended=True)

        return passive_checksum, int(passive_amount), int(passive_marker)

    # Return transfer set ordered by index in active set tree
    def get_ordered_tx_set(self, eon_number=None):
        is_sender = Q(
            wallet=self.wallet
        )
        is_active_recipient = Q(
            recipient=self.wallet,
            recipient_active_state__isnull=False,
            passive=False
        )
        is_in_tx_set = is_sender | is_active_recipient

        if eon_number is None and self.transfer:
            eon_number = self.transfer.eon_number

        transfers = Transfer.objects \
            .filter(
                is_in_tx_set,
                eon_number=eon_number,
                voided=False
            ).annotate(
                # avoid expensive joins by using cached index
                # index=Case(
                #     When(is_sender, then=F('sender_active_state__tx_set_index')),
                #     When(is_active_recipient, then=F('recipient_active_state__tx_set_index'))
                # ),
                # add index field to eleminate field heterogeneity
                index=Case(
                    When(is_sender, then=F('sender_merkle_index')),
                    When(is_active_recipient, then=F('recipient_merkle_index'))
                ),
                # order by new index field
            ).order_by('index')

        return transfers

    # Return last two cached transactions
    # ordered by index in active set tree
    def get_last_two_cached_transactions(self, only_appended, force_append, eon_number=None):
        is_sender = Q(
            wallet=self.wallet,
            sender_merkle_hash_cache__isnull=False,
            sender_merkle_height_cache__isnull=False
        )
        is_active_recipient = Q(
            recipient=self.wallet,
            recipient_active_state__isnull=False,
            passive=False,
            recipient_merkle_hash_cache__isnull=False,
            recipient_merkle_height_cache__isnull=False
        )
        is_in_tx_set = is_sender | is_active_recipient

        transfers = Transfer.objects \
            .filter(
                is_in_tx_set,
                eon_number=eon_number or self.transfer.eon_number,
                voided=False
            ).annotate(
                # avoid expensive joins by using cached index
                # index=Case(
                #     When(is_sender, then=F('sender_active_state__tx_set_index')),
                #     When(is_active_recipient, then=F('recipient_active_state__tx_set_index'))
                # ),
                # add index field to eleminate field heterogeneity
                index=Case(
                    When(is_sender, then=F('sender_merkle_index')),
                    When(is_active_recipient, then=F('recipient_merkle_index'))
                ),
                # add index field to eleminate field heterogeneity
                height_cache=Case(
                    When(is_sender, then=F('sender_merkle_height_cache')),
                    When(is_active_recipient, then=F(
                        'recipient_merkle_height_cache'))
                ),
                # add index field to eleminate field heterogeneity
                hash_cache=Case(
                    When(is_sender, then=F('sender_merkle_hash_cache')),
                    When(is_active_recipient, then=F(
                        'recipient_merkle_hash_cache'))
                ),
                # order by new index field
                # in descending order, since last 2 transactions are those of interest
            )

        if only_appended:
            transfers.filter(appended=True)

        if not force_append:
            transfers = self.filter_transfers_by_transfer_set_index(transfers)

        transfers = transfers.order_by('-index')[:2]

        if transfers.count() == 2:
            return transfers[0], transfers[1]

        if transfers.count() == 1:
            return transfers[0], None

        return None, None

    # get list of passive transfers
    # taking wallet-transfer context into consideration
    def incoming_passive_transfers_list(self, only_appended, force_append, eon_number=None):
        if self.transfer is not None and eon_number is None:
            eon_number = self.transfer.eon_number

        transfers = Transfer.objects \
            .filter(
                recipient=self.wallet,
                recipient_active_state__isnull=True,
                passive=True,
                eon_number=eon_number,
                voided=False) \
            .order_by('id')

        if self.transfer is not None and self.transfer.passive:
            transfers = self.filter_transfers_by_position(transfers)

        if only_appended:
            transfers = transfers.exclude(appended=False)

        transfers_list = [tx for tx in transfers]

        if force_append is True and self.transfer is not None and not self.transfer.appended:
            if self.transfer.recipient_id == self.wallet.id and self.transfer.passive:
                transfers_list.append(self.transfer)
                assert (len(transfers_list) > 0)
        return transfers_list

    # get a list of leaves or incoming passive transfers
    def incoming_passive_transfers_list_shorthand(self, only_appended, force_append, eon_number=None):
        return [tx.passive_shorthand(wallet_transfer_context=self) for tx in self.incoming_passive_transfers_list(
            only_appended=only_appended,
            force_append=force_append,
            eon_number=eon_number)]

    # get augmented merkelized interval tree of passive transfers
    def incoming_passive_transfers_tree(self, only_appended, force_append, eon_number=None) -> PassiveDeliveryMerkleTree:
        transfers = self.incoming_passive_transfers_list_shorthand(
            only_appended=only_appended,
            force_append=force_append,
            eon_number=eon_number)
        if len(transfers) > 0:
            upper_bound = transfers[-1]['right']
        else:
            upper_bound = 0
        return PassiveDeliveryMerkleTree(transfers, upper_bound)

    # get augmented merkelized interval tree root hash of passive transfers
    def incoming_passive_transfers_tree_root(self, only_appended, force_append, eon_number=None):
        return self.incoming_passive_transfers_tree(
            only_appended=only_appended,
            force_append=force_append,
            eon_number=eon_number) \
            .root_hash()

    # get augmented merkelized interval tree upper bound of passive transfers
    def incoming_passive_transfers_tree_upper_bound(self, only_appended, force_append, eon_number=None):
        return self.incoming_passive_transfers_tree(
            only_appended=only_appended,
            force_append=force_append,
            eon_number=eon_number)\
            .upper_bound

    def authorized_transfers_list(self, only_appended, force_append, eon_number=None):
        # retrieve transfers ordered by active tx set index
        transfers = self.get_ordered_tx_set(eon_number=eon_number)

        if only_appended:
            transfers = transfers.exclude(appended=False)

        transfers_list = [tx for tx in transfers]

        if force_append is True and self.transfer is not None and not self.transfer.appended:
            # Only append this as an active transfer if it is outgoing, or not an incoming passive transfer.
            if self.transfer.wallet_id == self.wallet.id or not self.transfer.passive:
                transfers_list.append(self.transfer)

        # The transfers list must be non empty, unless the context transfer is not appended
        if force_append and self.transfer is not None:
            assert (len(transfers_list) > 0 or (
                self.transfer.recipient_id == self.wallet.id and self.transfer.passive))

        return transfers_list

    def authorized_transfers_list_shorthand(self, only_appended, force_append, eon_number=None, last_transfer_is_finalized=True, index_map=None, assume_active_state_exists=False, starting_balance=None):
        txs = [tx for tx in self.authorized_transfers_list(
            only_appended=only_appended,
            force_append=force_append,
            eon_number=eon_number)]

        for i in range(len(txs)):
            if not last_transfer_is_finalized and i == len(txs)-1:
                txs[i] = txs[i].shorthand(
                    wallet_transfer_context=self,
                    index=i,
                    index_map=index_map,
                    is_last_transfer=True,
                    starting_balance=starting_balance,
                    assume_active_state_exists=assume_active_state_exists)
            else:
                txs[i] = txs[i].shorthand(
                    wallet_transfer_context=self,
                    index=i,
                    index_map=index_map,
                    starting_balance=starting_balance,
                    assume_active_state_exists=assume_active_state_exists)

        return txs

    def authorized_transfers_tree(self, only_appended, force_append, last_transfer_is_finalized=True, assume_active_state_exists=False) -> TransactionMerkleTree:
        return TransactionMerkleTree(self.authorized_transfers_list_shorthand(
            only_appended=only_appended,
            force_append=force_append,
            last_transfer_is_finalized=last_transfer_is_finalized,
            assume_active_state_exists=assume_active_state_exists))

    @classmethod
    def authorized_transfers_tree_from_list(cls, transfers_list) -> TransactionMerkleTree:
        return TransactionMerkleTree(transfers_list)

    @classmethod
    def optimized_authorized_transfers_tree_from_list(cls, transfers_list) -> OptimizedTransactionMerkleTree:
        return OptimizedTransactionMerkleTree(
            merkle_hash_cache=None,
            merkle_height_cache=None,
            transactions=transfers_list
        )

    def authorized_transfers_tree_root(self, only_appended, force_append, last_transfer_is_finalized=True):
        return self.authorized_transfers_tree(
            only_appended=only_appended,
            force_append=force_append,
            last_transfer_is_finalized=last_transfer_is_finalized) \
            .root_hash()

    # Optimized alternative to authorized_transfers_tree
    def optimized_authorized_transfers_tree(self, force_append=True, only_appended=False, starting_balance=None, assume_active_state_exists=False) -> OptimizedTransactionMerkleTree:

        # fetch last 2 transfers in active set transfers, with cache values
        last_cached_transfer, before_last_cached_transfer = self.get_last_two_cached_transactions(
            only_appended, force_append)

        is_adding_new_transaction = self.transfer is not None and not self.transfer.appended and (
            self.transfer.wallet_id == self.wallet.id or not self.transfer.passive)
        is_fetching_complete_set = not force_append
        is_fetching_appended_set = force_append and only_appended and self.transfer is not None and self.transfer.id is not None

        # if the last cache entry exists
        if last_cached_transfer is not None:

            # fetching complete transaction set
            if is_fetching_complete_set:
                # need second last cache item to construct tree
                if before_last_cached_transfer is not None:
                    return OptimizedTransactionMerkleTree(
                        before_last_cached_transfer.hash_cache,
                        before_last_cached_transfer.height_cache,
                        transaction=last_cached_transfer.shorthand(
                            wallet_transfer_context=self,
                            is_last_transfer=True,
                            starting_balance=starting_balance,
                            assume_active_state_exists=assume_active_state_exists
                        )
                    )
                # if it does not exist, fallback to recalculating entire tree

            # fetch only appended transaction set
            elif is_fetching_appended_set:

                # if last cached transaction is context transaction
                if last_cached_transfer.id == self.transfer.id:
                    # need second last cache item to construct tree
                    if before_last_cached_transfer is not None:
                        return OptimizedTransactionMerkleTree(
                            before_last_cached_transfer.hash_cache,
                            before_last_cached_transfer.height_cache,
                            transaction=self.transfer.shorthand(
                                wallet_transfer_context=self,
                                is_last_transfer=True,
                                starting_balance=starting_balance,
                                assume_active_state_exists=assume_active_state_exists
                            )
                        )
                    # if it does not exist, fallback to recalculating entire tree

                # if last cached transaction is not context transaction
                # use last cached item and context transaction to calculate tree
                else:
                    return OptimizedTransactionMerkleTree(
                        last_cached_transfer.hash_cache,
                        last_cached_transfer.height_cache,
                        transaction=self.transfer.shorthand(
                            wallet_transfer_context=self,
                            is_last_transfer=True,
                            starting_balance=starting_balance,
                            assume_active_state_exists=assume_active_state_exists
                        )
                    )

            # adding new transaction to set
            elif is_adding_new_transaction:
                # get last cached items
                merkle_hash_cache = last_cached_transfer.hash_cache
                merkle_height_cache = last_cached_transfer.height_cache

                # is this context transaction a fullfilled or cancelled swap
                # need to reconstruct for the sender as well
                # a partially matched swap in a previous eon will result in a different starting balance (from that of sender state tx set)
                # if multi eon swap is cancelled, since starting balance changed this tx_set_tree should be reconstructed
                is_fulfilled_or_cancelled_swap = last_cached_transfer.is_swap() and (
                    last_cached_transfer.complete or last_cached_transfer.cancelled)

                # is this context transaction passive
                is_passive = last_cached_transfer.passive

                # reconstruct tree using existing tx set, excluding context transaction
                # to make sure swap or passive transfer is finalized
                should_reconstruct_old_tree = is_fulfilled_or_cancelled_swap or is_passive

                if should_reconstruct_old_tree:
                    # for backward compatibility
                    # if tree before last tree is not cached, re-calculate entire tree
                    if before_last_cached_transfer is None:
                        old_set = self.authorized_transfers_list(
                            only_appended=False,
                            force_append=False,
                        )
                        reconstructed_old_tree = OptimizedTransactionMerkleTree(
                            merkle_hash_cache=None,
                            merkle_height_cache=None,
                            transactions=[
                                tx.shorthand(
                                    wallet_transfer_context=self,
                                    starting_balance=starting_balance,
                                    assume_active_state_exists=assume_active_state_exists) for tx in old_set if tx.index <= last_cached_transfer.index
                            ]
                        )

                    # if tree before last tree is cached, use cache to re-construct last tree
                    else:
                        reconstructed_old_tree = OptimizedTransactionMerkleTree(
                            before_last_cached_transfer.hash_cache,
                            before_last_cached_transfer.height_cache,
                            transaction=last_cached_transfer.shorthand(
                                wallet_transfer_context=self,
                                is_last_transfer=False,
                                starting_balance=starting_balance,
                                assume_active_state_exists=assume_active_state_exists
                            )
                        )

                    # update last cache item after finalizing included transactions
                    merkle_hash_cache, merkle_height_cache = reconstructed_old_tree.merkle_cache_stacks()
                    # if context wallet is sender
                    if self.wallet == last_cached_transfer.wallet:
                        last_cached_transfer.sender_merkle_hash_cache = merkle_hash_cache
                        last_cached_transfer.sender_merkle_height_cache = merkle_height_cache
                    # if context wallet is recipient and is_fulfilled_or_cancelled_swap
                    elif self.wallet == last_cached_transfer.recipient and is_fulfilled_or_cancelled_swap:
                        last_cached_transfer.recipient_merkle_hash_cache = merkle_hash_cache
                        last_cached_transfer.recipient_merkle_height_cache = merkle_height_cache
                    last_cached_transfer.save()

                # use last cached item to construct new tree
                return OptimizedTransactionMerkleTree(
                    merkle_hash_cache,
                    merkle_height_cache,
                    transaction=self.transfer.shorthand(
                        wallet_transfer_context=self,
                        starting_balance=starting_balance,
                        assume_active_state_exists=assume_active_state_exists
                    )
                )

        # for backward compatibility
        # fallback to re-calculating the whole tree
        return OptimizedTransactionMerkleTree(
            merkle_hash_cache=None,
            merkle_height_cache=None,
            transactions=self.authorized_transfers_list_shorthand(
                only_appended=only_appended,
                force_append=force_append,
                last_transfer_is_finalized=not (
                    is_fetching_appended_set or is_adding_new_transaction),
                starting_balance=starting_balance,
                assume_active_state_exists=assume_active_state_exists
            )
        )

    def last_outgoing_passive_transfer(self, eon_number):
        return self.filter_transfers_by_transfer_id(Transfer.objects.filter(
            wallet=self.wallet,
            passive=True,
            eon_number=eon_number)) \
            .order_by('id') \
            .last()

    def last_appended_outgoing_passive_transfer(self, eon_number):
        return self.filter_transfers_by_transfer_id(Transfer.objects.filter(
            wallet=self.wallet,
            passive=True,
            eon_number=eon_number,
            appended=True)) \
            .order_by('id') \
            .last()

    def last_appended_outgoing_active_transfer(self, eon_number):
        return self.filter_transfers_by_recipient_active_state_id(Transfer.objects.filter(
            wallet=self.wallet,
            passive=False,
            eon_number=eon_number,
            appended=True)) \
            .order_by('id') \
            .last()

    def last_appended_incoming_active_transfer(self, eon_number):
        return self.filter_transfers_by_recipient_active_state_id(Transfer.objects.filter(
            recipient=self.wallet,
            recipient_active_state__isnull=False,
            passive=False,
            eon_number=eon_number,
            appended=True)) \
            .order_by('id') \
            .last()

    def last_appended_active_transfer(self, eon_number) -> Tuple[Transfer, bool]:
        transfer = self.get_ordered_tx_set(
            eon_number=eon_number).filter(appended=True).last()
        return transfer, transfer is not None and transfer.wallet == self.wallet

    def last_appended_incoming_passive_transfer(self, eon_number) -> Transfer:
        if self.transfer is not None and self.transfer.passive and self.transfer.recipient == self.wallet:
            return self.filter_transfers_by_position(Transfer.objects.filter(
                recipient=self.wallet,
                # TODO add db constraint that passive -> recipient_active_state__isnull
                recipient_active_state__isnull=True,
                passive=True,
                eon_number=eon_number,
                appended=True)) \
                .order_by('position', 'id') \
                .last()

        return self.filter_transfers_by_transfer_id(Transfer.objects.filter(
            recipient=self.wallet,
            # TODO add db constraint that passive -> recipient_active_state__isnull
            recipient_active_state__isnull=True,
            passive=True,
            eon_number=eon_number,
            appended=True)) \
            .order_by('position', 'id') \
            .last()

    @staticmethod
    def appropriate_transfer_active_state(transfer: Transfer, is_outgoing: bool) -> Union[ActiveState, None]:
        if transfer is None:
            return None
        elif transfer.is_swap():
            if transfer.processed:
                if is_outgoing:
                    return transfer.sender_cancellation_active_state if transfer.cancelled \
                        else transfer.sender_active_state
                else:
                    if transfer.recipient_finalization_active_state is not None:
                        return transfer.recipient_finalization_active_state
                    elif transfer.cancelled:
                        return transfer.recipient_cancellation_active_state
                    elif transfer.complete:
                        return transfer.recipient_fulfillment_active_state
                    return transfer.recipient_active_state
            else:
                if is_outgoing:
                    return transfer.sender_active_state
                else:
                    if transfer.complete:
                        return transfer.recipient_fulfillment_active_state
                    return transfer.recipient_active_state
        else:
            if is_outgoing:  # TODO return passive outgoing finalization active state update
                return transfer.sender_cancellation_active_state if transfer.cancelled \
                    else transfer.sender_active_state
            elif not transfer.passive:
                return transfer.recipient_cancellation_active_state if transfer.cancelled \
                    else transfer.recipient_active_state
            else:
                return None

    def last_appended_active_state(self, eon_number) -> Union[ActiveState, None]:
        last_tx, last_tx_is_outgoing = self.last_appended_active_transfer(
            eon_number=eon_number)

        return WalletTransferContext.appropriate_transfer_active_state(last_tx, last_tx_is_outgoing)

    def last_scheduled_transfer(self, eon_number) -> Tuple[Transfer, bool]:
        transfer = self.filter_transfers_by_recipient_active_state_id(Transfer.objects.filter(
            Q(wallet=self.wallet) |
            Q(recipient=self.wallet,
              recipient_active_state__isnull=False, passive=False),
            eon_number=eon_number,
            voided=False)) \
            .order_by('id') \
            .last()

        # transfer = self.filter_transfers_by_recipient_active_state_id(
        #     self.get_ordered_tx_set(eon_number=eon_number)
        # ).last()
        return transfer, transfer is not None and transfer.wallet == self.wallet

    def off_chain_actively_sent_received_amounts(self, eon_number, only_appended):
        # Calculate Off-chain Transfers
        if only_appended:
            last_tx, last_tx_is_outgoing = self.last_appended_active_transfer(
                eon_number=eon_number)
        else:
            last_tx, last_tx_is_outgoing = self.last_scheduled_transfer(
                eon_number=eon_number)

        if last_tx is None:
            return 0, 0

        # take this eon's matched amounts into consideration if
        # swap is complete but not finalized or partially matched or not matched at all
        # swap is not voided
        # swap is not cancelled
        # swap is appended
        elif last_tx.is_swap() and last_tx.recipient_finalization_active_state is None and not last_tx.cancelled and not last_tx.voided and last_tx.appended:
            matched_out, matched_in = last_tx.matched_amounts()

            if last_tx_is_outgoing:
                return last_tx.sender_active_state.updated_spendings, \
                    last_tx.sender_active_state.updated_gains + last_tx.amount - matched_out
            else:
                return last_tx.recipient_active_state.updated_spendings, \
                    last_tx.recipient_active_state.updated_gains + matched_in
        else:
            last_tx_active_state = WalletTransferContext.appropriate_transfer_active_state(
                last_tx, last_tx_is_outgoing)

            updated_spendings = last_tx_active_state.updated_spendings
            updated_gains = last_tx_active_state.updated_gains

            if last_tx.is_swap():
                current_eon_matched_out, current_eon_matched_in = last_tx.matched_amounts()

                # if swap is complete and outgoing
                # matched out amount is added in twice
                if last_tx.complete and last_tx_is_outgoing:
                    total_matched_out, _ = last_tx.matched_amounts(
                        all_eons=True)
                    # remove matched amount from previous eons
                    updated_gains += total_matched_out - current_eon_matched_out
                # if swap was partially matched this eon then cancelled
                # recipient should be credited when creating cancellation active state
                # last_tx.recipient_cancellation_active_state is None makes sure that recipient is not credited twice
                if last_tx.cancelled and last_tx.recipient_cancellation_active_state is None and not last_tx_is_outgoing:
                    # add matched in amount
                    updated_gains += current_eon_matched_in
            return updated_spendings, updated_gains

    def off_chain_passively_received_amount(self, eon_number, only_appended):
        if only_appended:
            last_passive_incoming = self.last_appended_incoming_passive_transfer(
                eon_number=eon_number)
            if last_passive_incoming:
                return last_passive_incoming.position + last_passive_incoming.amount
            else:
                return 0

        return self.filter_transfers_by_transfer_id(Transfer.objects.filter(
            recipient=self.wallet,
            # TODO add db constraint that passive -> recipient_active_state__isnull
            recipient_active_state__isnull=True,
            passive=True,
            voided=False,
            cancelled=False,
            eon_number=eon_number)) \
            .aggregate(Sum('amount')) \
            .get('amount__sum') or 0

    def available_funds_at_eon(self, eon_number, only_appended):
        # Saved Balance
        total = self.balance_amount_as_of_eon(eon_number)
        # Deposits
        deposits = self.filter_transactions_by_time(Deposit.objects.filter(
            wallet=self.wallet,
            eon_number=eon_number))
        total += sum([deposit.amount for deposit in deposits])
        # Active Transfers
        highest_spend, highest_gain = self.off_chain_actively_sent_received_amounts(
            eon_number=eon_number,
            only_appended=only_appended)
        total += highest_gain - highest_spend
        # Passive Transfers
        passively_received = self.off_chain_passively_received_amount(
            eon_number=eon_number,
            only_appended=only_appended)
        total += passively_received
        # Withdrawals
        withdrawals = self.filter_transactions_by_time(WithdrawalRequest.objects.filter(
            wallet=self.wallet,
            eon_number=eon_number,
            slashed=False))
        total -= sum([withdrawal.amount for withdrawal in withdrawals])

        return int(total)

    def loosely_available_funds_at_eon(self, eon_number, current_eon_number, is_checkpoint_created, only_appended):
        loose_funds = 0
        if (not is_checkpoint_created) and eon_number == current_eon_number:
            loose_funds = self.available_funds_at_eon(
                eon_number=eon_number - 1,
                only_appended=only_appended)
        loose_funds += self.available_funds_at_eon(
            eon_number=eon_number,
            only_appended=only_appended)
        return loose_funds

    def transfers_appended_by_operator_in_eon(self, eon_number):
        return self.filter_transfers_by_recipient_active_state_id(Transfer.objects.filter(
            Q(wallet=self.wallet) |
            Q(recipient=self.wallet, recipient_active_state__isnull=False, passive=False) |
            Q(recipient=self.wallet, passive=True),
            eon_number=eon_number,
            appended=True)) \
            .order_by('id')

    def transfers_pending_operator_processing_in_eon(self, eon_number):
        return self.filter_transfers_by_recipient_active_state_id(Transfer.objects.filter(
            Q(wallet=self.wallet) |
            Q(recipient=self.wallet),
            eon_number=eon_number,
            processed=False)) \
            .order_by('id')

    def outgoing_transfer_pending_receipt(self):
        return self.filter_transfers_by_recipient_active_state_id(Transfer.objects.filter(
            wallet=self.wallet,
            recipient_active_state__isnull=True,
            processed=False,
            passive=False)) \
            .order_by('id') \
            .first()

    def last_approved_incoming_active_transfer_pending_operator_confirmation(self, eon_number):
        return self.filter_transfers_by_recipient_active_state_id(Transfer.objects.filter(
            recipient=self.wallet,
            recipient_active_state__isnull=False,
            eon_number=eon_number,
            processed=False)) \
            .order_by('id') \
            .last()

    def swap_in_progress(self, eon_number):
        return self.filter_transfers_by_recipient_active_state_id(Transfer.objects.filter(
            Q(wallet=self.wallet) |
            Q(recipient=self.wallet, recipient_active_state__isnull=False),
            swap=True,
            eon_number=eon_number,
            processed=False)) \
            .order_by('id') \
            .first()

    def on_chain_deposited_withdrawn(self, eon_number):
        # Calculate On-chain transactions
        deposit, withdrawal = 0, 0
        deposits = self.filter_transactions_by_time(Deposit.objects.filter(
            wallet=self.wallet,
            eon_number=eon_number)) \
            .order_by('pk')
        withdrawals = self.filter_transactions_by_time(WithdrawalRequest.objects.filter(
            wallet=self.wallet,
            eon_number=eon_number,
            slashed=False)) \
            .order_by('pk')

        if deposits:
            deposit = sum([dep.amount for dep in deposits])
        if withdrawals:
            withdrawal = sum([withdrawal.amount for withdrawal in withdrawals])
        return deposit, withdrawal

    def balance_as_of_eon(self, eon_number):
        try:
            return ExclusiveBalanceAllotment.objects.get(wallet=self.wallet, eon_number=eon_number)
        except ExclusiveBalanceAllotment.DoesNotExist:
            return None

    def balance_amount_as_of_eon(self, eon_number):
        balance = self.balance_as_of_eon(eon_number=eon_number)
        return 0 if balance is None else balance.amount()

    def starting_balance_in_eon(self, eon_number):
        balance = self.balance_as_of_eon(eon_number=eon_number)
        if balance is None:
            return self.available_funds_at_eon(
                eon_number=eon_number - 1,
                only_appended=False)
        else:
            return balance.amount()

    def minimum_balance_since_eon(self, eon_number):
        return MinimumAvailableBalanceMarker.objects \
            .filter(wallet=self.wallet, eon_number__gte=eon_number) \
            .order_by('amount') \
            .first()

    def latest_touched_active_transfer_eon_number(self):
        max_transfer_eon_number = self.filter_transfers_by_recipient_active_state_id(
            Transfer.objects.filter(
                Q(wallet=self.wallet) | Q(recipient=self.wallet,
                                          recipient_active_state__isnull=False,
                                          passive=False),
                voided=False
            )).aggregate(Max('eon_number')).get('eon_number__max')

        return max_transfer_eon_number if max_transfer_eon_number is not None else 0
