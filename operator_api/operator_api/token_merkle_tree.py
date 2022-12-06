from operator_api import crypto
from operator_api.crypto import hex_value
from operator_api.merkle_tree import normalize_size, calculate_merkle_proof
from operator_api.util import ZERO_CHECKSUM


class TokenMerkleTree:
    def __init__(self, token_commitments):
        self.tokens = normalize_tokens(token_commitments)
        self.merkle_tree_leaf_map = {}
        self.merkle_tree_nonce_map = {}
        self.root = calculate_token_merkle_tree(
            self.tokens, self.merkle_tree_leaf_map, self.merkle_tree_nonce_map, 0)

    def root_hash(self):
        return self.root.get('hash')

    def proof(self, index):
        result = calculate_merkle_proof(
            index, self.merkle_tree_leaf_map[index])
        return ''.join([hex_value(node.get('hash')) for node in result])


def normalize_tokens(transactions):
    return normalize_size(transactions, {
        'left': 0,
        'merkle_root': '0x0000000000000000000000000000000000000000',
        'right': 0,
        'hash': crypto.decode_hex(ZERO_CHECKSUM)
    })


def calculate_token_merkle_tree(leaves, leaf_map, nonce_map, index):
    n = len(leaves)
    if n == 1:
        result = {
            'node': leaves[0],
            'hash': leaves[0].get('hash'),
            'index': index,
            'height': 0
        }
        leaf_map[index] = result
        nonce_map[leaves[0].get('nonce')] = index
        return result

    mid = n//2
    left = leaves[0:mid]
    right = leaves[mid:n]
    left_child = calculate_token_merkle_tree(
        left, leaf_map, nonce_map, 2 * index)
    right_child = calculate_token_merkle_tree(
        right, leaf_map, nonce_map, 2 * index + 1)
    internal_node = {
        'left_child': left_child,
        'right_child': right_child,
    }
    result = {
        'node': internal_node,
        'hash': internal_node_hash(internal_node),
        'height': left_child.get('height') + 1
    }
    left_child['parent'] = result
    right_child['parent'] = result

    return result


def internal_node_hash(internal_node):
    representation = [
        crypto.uint32(internal_node.get('left_child').get('height')),
        internal_node.get('left_child').get('hash'),
        internal_node.get('right_child').get('hash')
    ]
    return crypto.hash_array(representation)
