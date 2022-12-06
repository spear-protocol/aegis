from operator_api import crypto
from operator_api.merkle_tree import MerkleTree, normalize_size, calculate_merkle_tree
from operator_api.util import ZERO_CHECKSUM


# Default hasher for passive_transfers
def passive_transfer_leaf_inner_hash(leaf):
    return leaf.get('hash')  # leaves are prehashed


# Merkelized-Augmented-Interval tree
class PassiveDeliveryMerkleTree(MerkleTree):
    def __init__(self, transfers, upper_bound, leaf_inner_hash=passive_transfer_leaf_inner_hash):
        self.transfers = normalize_transfers(transfers, upper_bound)
        self.upper_bound = upper_bound
        self.merkle_tree_leaf_map = {}
        self.root = calculate_merkle_tree(
            leaf_inner_hash, self.transfers, self.merkle_tree_leaf_map, 0)


# make number of leaves a power of 2
def normalize_transfers(transfers, upper_bound):
    return normalize_size(transfers, {
        'wallet': '0x0000000000000000000000000000000000000000',
        'left': int(upper_bound),
        'right': int(upper_bound),
        'nonce': 0,
        'hash': crypto.decode_hex(ZERO_CHECKSUM)
    })
