from django.db import models

from .blockchain_transaction import BlockchainTransaction


class Challenge(BlockchainTransaction):
    rebuted = models.BooleanField(
        default=False)

    recipient = models.ForeignKey(
        to='Wallet',
        on_delete=models.PROTECT,
        related_name="challenge_recipient_wallet")

    def tag(self, txid):
        return 'challenge_{}_{}_{}_{}_{}'.format(self.eon_number, self.wallet.token.address, self.wallet.address,
                                                 self.recipient.address, txid)
