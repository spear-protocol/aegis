from eth_utils import keccak
from . import crypto
from .crypto import hex_value


# Default hasher for accounts
def wallet_leaf_inner_hash(leaf):
    representation = [
        keccak(crypto.address(leaf.get('contract'))),
        keccak(crypto.address(leaf.get('token'))),
        keccak(crypto.address(leaf.get('wallet'))),
        crypto.hash_array([
            # merkle root of passive delivery transfer set
            leaf.get('passive_checksum'),
            # total amount received passively
            crypto.uint256(leaf.get('passive_amount')),
            crypto.uint256(leaf.get('passive_marker'))]),  # marker for last outgoing passive transfer location
        leaf.get('active_state_checksum')
    ]
    return crypto.hash_array(representation)


class MerkleTree:
    def __init__(self, balances, upper_bound, leaf_inner_hash=wallet_leaf_inner_hash):
        self.balances = normalize_balance_set(balances, upper_bound)
        self.upper_bound = upper_bound
        self.merkle_tree_leaf_map = {}
        self.root = calculate_merkle_tree(
            leaf_inner_hash, self.balances, self.merkle_tree_leaf_map, 0)

    def proof(self, index):
        result = calculate_merkle_proof(
            index, self.merkle_tree_leaf_map[index])
        return {
            'chain': ''.join([hex_value(node.get('hash')) for node in result]),
            'values': ','.join([str(x) for x in [
                node.get('node').get('left') if (index >> pos) % 2 == 1 else
                node.get('node').get('right') for pos, node in enumerate(result)]])
        }

    def root_hash(self):
        return self.root.get('hash')


def normalize_balance_set(balances, upper_bound):
    return normalize_size(balances, {
        'contract': '0x0000000000000000000000000000000000000000',
        'token': '0x0000000000000000000000000000000000000000',
        'wallet': '0x0000000000000000000000000000000000000000',
        'left': int(upper_bound),
        'right': int(upper_bound),
        'active_state_checksum': b'\0'*32,
        'passive_checksum': b'\0'*32,
        'passive_amount': 0,
        'passive_marker': 0
    })


def normalize_size(list, padding_element):
    n = len(list)
    power_of_two = 1
    while power_of_two < n:
        power_of_two <<= 1
    while len(list) < power_of_two:
        list.append(padding_element)
    return list


def calculate_merkle_tree(leaf_inner_hash, leaves, leaf_map, index):
    n = len(leaves)
    if n == 1:
        result = {
            'node': leaves[0],
            'hash': leaf_hash(leaf_inner_hash, leaves[0]),
            'index': index,
            'height': 0
        }
        leaf_map[index] = result
        return result

    mid = n//2
    left = leaves[0:mid]
    right = leaves[mid:n]
    left_child = calculate_merkle_tree(
        leaf_inner_hash, left, leaf_map, 2 * index)
    right_child = calculate_merkle_tree(
        leaf_inner_hash, right, leaf_map, 2 * index + 1)
    internal_node = {
        'left': int(leaves[0].get('left')),
        'left_child': left_child,
        'mid': int(leaves[mid].get('left')),
        'right_child': right_child,
        'right': int(leaves[n - 1].get('right')),
    }
    result = {
        'node': internal_node,
        'hash': internal_node_hash(internal_node),
        'height': left_child.get('height') + 1
    }
    left_child['parent'] = result
    right_child['parent'] = result

    return result


def calculate_merkle_proof(index, leaf):
    result = []
    index = index if index is not None else leaf.get('index')
    node = leaf
    while node.get('parent') is not None:
        node_left = index % 2 == 0  # is the current node in the left of the link

        if node_left:
            result.append(node.get('parent').get('node').get('right_child'))
        else:
            result.append(node.get('parent').get('node').get('left_child'))

        node = node.get('parent')
        index >>= 1

    return result


def leaf_hash(leaf_inner_hasher, leaf):
    representation = [
        crypto.uint256(leaf.get('left')),
        leaf_inner_hasher(leaf),
        crypto.uint256(leaf.get('right'))
    ]
    return crypto.hash_array(representation)


def internal_node_inner_hash(internal_node):
    representation = [
        internal_node.get('left_child').get('hash'),
        crypto.uint256(internal_node.get('mid')),
        internal_node.get('right_child').get('hash')
    ]
    return crypto.hash_array(representation)


def internal_node_hash(internal_node):
    representation = [
        crypto.uint32(internal_node.get('left_child').get('height')),
        crypto.uint256(internal_node.get('left')),
        internal_node_inner_hash(internal_node),
        crypto.uint256(internal_node.get('right'))
    ]
    return crypto.hash_array(representation)
