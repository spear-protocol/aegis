from ledger.models import Wallet, Token


class SwapDataRequest(object):
    def __init__(self, left_token: Token, right_token: Token, eon_number):
        if eon_number is not None and eon_number.isnumeric():
            self.eon_number = int(eon_number)
        else:
            self.eon_number = -1
        self.left_token = left_token
        self.right_token = right_token
