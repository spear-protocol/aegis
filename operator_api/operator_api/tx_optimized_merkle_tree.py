from operator_api import crypto
from operator_api.zero_merkle_root_cache import NODE_CACHE


class OptimizedTransactionMerkleTree:
    def __init__(self, merkle_hash_cache=None, merkle_height_cache=None, transaction=None, transactions=None):
        self.stack = []
        self.root = NODE_CACHE[0]
        self.paths = {}
        self.merkle_tree_nonce_map = {}

        if transaction is not None:
            self.stack, self.root, tx_path = append_tx_to_set(
                build_stack_from_cache(merkle_hash_cache, merkle_height_cache),
                transaction
            )
            tx_index = self.last_tx_index()
            self.merkle_tree_nonce_map[int(
                transaction.get('nonce'))] = tx_index
            self.paths[tx_index] = tx_path
        elif transactions is not None:
            index = 0
            for tx in transactions:
                self.merkle_tree_nonce_map[tx.get('nonce')] = index
                self.stack, self.root, tx_path = append_tx_to_set(
                    self.stack,
                    tx
                )
                self.paths[index] = tx_path
                index += 1

    def root_hash(self):
        return self.root.get('hash')

    def merkle_cache_stacks(self):
        merkle_hash_stack = [crypto.hex_value(
            node.get('hash')) for node in self.stack]
        merkle_height_stack = [str(node.get('height')) for node in self.stack]
        return (
            ','.join(merkle_hash_stack),
            ','.join(merkle_height_stack)
        )

    def last_tx_index(self):
        index = 0
        for item in self.stack:
            index += 2**item.get('height')
        return index - 1

    def proof(self, index):
        return ''.join([crypto.hex_value(node_hash) for node_hash in self.paths[index]])

    def last_tx_proof(self):
        return self.proof(self.last_tx_index())


def build_stack_from_cache(merkle_hash_cache, merkle_height_cache):
    if merkle_hash_cache == '' or merkle_hash_cache is None:
        return []

    merkle_hash_stack = merkle_hash_cache.split(',')
    merkle_height_stack = merkle_height_cache.split(',')

    assert(len(merkle_hash_stack) == len(merkle_height_stack))

    merkle_hash_stack = [crypto.decode_hex(item) for item in merkle_hash_stack]
    merkle_height_stack = [int(item) for item in merkle_height_stack]

    return [
        {'hash': hash_value, 'height': height_value}
        for hash_value, height_value in zip(merkle_hash_stack, merkle_height_stack)
    ]


def get_zero_tree_root(height):
    if height > len(NODE_CACHE):
        return None

    return NODE_CACHE[height]


def combine_hash(left_node, right_node):
    representation = [
        crypto.uint32(left_node.get('height')),
        left_node.get('hash'),
        right_node.get('hash')
    ]
    return crypto.hash_array(representation)


def append_tx_to_set(stack, tx):
    last_tx_path = []

    stack.append({
        'height': 0,
        'hash': tx.get('hash')
    })

    if len(stack) == 1:
        return (
            stack,
            stack[0],
            last_tx_path
        )

    while len(stack) > 1 and stack[-1].get('height') == stack[-2].get('height'):
        right_node = stack.pop()
        left_node = stack.pop()
        parent_node = {
            'hash': combine_hash(left_node, right_node),
            'height': right_node.get('height') + 1
        }
        stack.append(parent_node)
        last_tx_path.append(left_node.get('hash'))

    pointer_to_last_node_on_path = len(stack) - 1

    if len(stack) == 1:
        return (
            stack,
            stack[0],
            last_tx_path
        )
    else:
        padded_stack = [node for node in stack]
        while len(padded_stack) > 1:
            last_stack_index = len(padded_stack)-1
            if padded_stack[-1].get('height') == padded_stack[-2].get('height'):
                right_node = padded_stack.pop()
                left_node = padded_stack.pop()
                parent_node = {
                    'hash': combine_hash(left_node, right_node),
                    'height': right_node.get('height') + 1
                }
                padded_stack.append(parent_node)

                # is right node
                if pointer_to_last_node_on_path == last_stack_index:
                    last_tx_path.append(left_node.get('hash'))
                    pointer_to_last_node_on_path = last_stack_index-1
                # is left node
                elif pointer_to_last_node_on_path == last_stack_index-1:
                    last_tx_path.append(right_node.get('hash'))
                    pointer_to_last_node_on_path = last_stack_index-1

            else:
                sibling_node = get_zero_tree_root(
                    padded_stack[-1].get('height'))
                padded_stack.append(
                    sibling_node
                )
        return (
            stack,
            padded_stack[0],
            last_tx_path
        )
