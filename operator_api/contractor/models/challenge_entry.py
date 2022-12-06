class ChallengeEntry(object):
    def __init__(self, arr):
        self.challengeStage = arr[0]
        self.block = arr[1]
        self.initialStateEon = arr[2]
        self.initialStateBalance = arr[3]
        self.deltaHighestSpendings = arr[4]
        self.deltaHighestGains = arr[5]
        self.finalStateBalance = arr[6]
        self.deliveredTxNonce = arr[7]
