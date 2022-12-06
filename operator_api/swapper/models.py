from ledger.models.transfer import Transfer


class Swap(Transfer):
    class Meta:
        proxy = True
