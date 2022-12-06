from django.test import TestCase
from operator_api import crypto
from operator_api.tx_merkle_tree import TransactionMerkleTree
from operator_api.tx_optimized_merkle_tree import OptimizedTransactionMerkleTree


class OperatorTests(TestCase):
    def setUp(self):
        self.transactions_1 = []
        self.transactions_2 = []

        for i in range(3001):
            node = {
                'hash': crypto.hash_message(crypto.unsigned_int_to_bytes(i)),
                'nonce': i
            }
            self.transactions_1.append(node)
            self.transactions_2.append(node)

    def test_correct_root_calculation(self):
        reference_tree = TransactionMerkleTree(self.transactions_1)

        merkle_hash_cache, merkle_height_cache = '', ''
        root_hash = ''

        for tx in self.transactions_2:
            optimized_tree = OptimizedTransactionMerkleTree(
                merkle_hash_cache,
                merkle_height_cache,
                tx
            )
            root_hash = optimized_tree.root_hash()
            merkle_hash_cache, merkle_height_cache = optimized_tree.merkle_cache_stacks()

        self.assertEqual(root_hash, reference_tree.root_hash())

    def test_correct_root_calculation_at_zero(self):
        reference_tree = TransactionMerkleTree([])

        merkle_hash_cache, merkle_height_cache = '', ''
        root_hash = ''

        optimized_tree = OptimizedTransactionMerkleTree(
            merkle_hash_cache,
            merkle_height_cache
        )

        root_hash = optimized_tree.root_hash()
        merkle_hash_cache, merkle_height_cache = optimized_tree.merkle_cache_stacks()

        self.assertEqual(root_hash, reference_tree.root_hash())

    def test_correct_root_calculation_at_one(self):
        reference_tree = TransactionMerkleTree(self.transactions_1[:1])

        merkle_hash_cache, merkle_height_cache = '', ''
        root_hash = ''

        for tx in self.transactions_2[:1]:
            optimized_tree = OptimizedTransactionMerkleTree(
                merkle_hash_cache,
                merkle_height_cache,
                tx
            )
            root_hash = optimized_tree.root_hash()
            merkle_hash_cache, merkle_height_cache = optimized_tree.merkle_cache_stacks()

        self.assertEqual(root_hash, reference_tree.root_hash())

    def test_last_transfer_index(self):
        reference_tree = TransactionMerkleTree(self.transactions_1)

        merkle_hash_cache, merkle_height_cache = '', ''
        optimized_tree = None

        for tx in self.transactions_2:
            optimized_tree = OptimizedTransactionMerkleTree(
                merkle_hash_cache,
                merkle_height_cache,
                tx
            )
            merkle_hash_cache, merkle_height_cache = optimized_tree.merkle_cache_stacks()

        self.assertEqual(optimized_tree.root_hash(),
                         reference_tree.root_hash())
        self.assertEqual(
            optimized_tree.last_tx_index(),
            reference_tree.merkle_tree_nonce_map.get(
                self.transactions_2[-1].get('nonce'))
        )

    def test_last_transfer_index_at_one(self):
        reference_tree = TransactionMerkleTree(self.transactions_1[:1])

        merkle_hash_cache, merkle_height_cache = '', ''
        optimized_tree = None

        for tx in self.transactions_2[:1]:
            optimized_tree = OptimizedTransactionMerkleTree(
                merkle_hash_cache,
                merkle_height_cache,
                tx
            )
            merkle_hash_cache, merkle_height_cache = optimized_tree.merkle_cache_stacks()

        self.assertEqual(optimized_tree.root_hash(),
                         reference_tree.root_hash())
        self.assertEqual(
            optimized_tree.last_tx_index(),
            reference_tree.merkle_tree_nonce_map.get(
                self.transactions_2[0].get('nonce'))
        )

    def test_last_transfer_path(self):
        reference_tree = TransactionMerkleTree(self.transactions_1)

        merkle_hash_cache, merkle_height_cache = '', ''
        optimized_tree = None

        self
        for tx in self.transactions_2:
            optimized_tree = OptimizedTransactionMerkleTree(
                merkle_hash_cache,
                merkle_height_cache,
                tx
            )
            merkle_hash_cache, merkle_height_cache = optimized_tree.merkle_cache_stacks()

        last_tx_index = optimized_tree.last_tx_index()

        self.assertEqual(optimized_tree.root_hash(),
                         reference_tree.root_hash())
        self.assertEqual(
            last_tx_index,
            reference_tree.merkle_tree_nonce_map.get(
                self.transactions_2[-1].get('nonce'))
        )
        self.assertEqual(
            optimized_tree.merkle_tree_nonce_map.get(
                self.transactions_2[-1].get('nonce')),
            reference_tree.merkle_tree_nonce_map.get(
                self.transactions_2[-1].get('nonce'))
        )
        self.assertEqual(
            optimized_tree.last_tx_proof(),
            reference_tree.proof(last_tx_index)
        )

    def test_last_transfer_path_at_one(self):
        reference_tree = TransactionMerkleTree(self.transactions_1[:1])

        merkle_hash_cache, merkle_height_cache = '', ''
        optimized_tree = None

        for tx in self.transactions_2[:1]:
            optimized_tree = OptimizedTransactionMerkleTree(
                merkle_hash_cache,
                merkle_height_cache,
                tx
            )
            merkle_hash_cache, merkle_height_cache = optimized_tree.merkle_cache_stacks()

        last_tx_index = optimized_tree.last_tx_index()

        self.assertEqual(optimized_tree.root_hash(),
                         reference_tree.root_hash())
        self.assertEqual(
            last_tx_index,
            reference_tree.merkle_tree_nonce_map.get(
                self.transactions_2[0].get('nonce'))
        )
        self.assertEqual(
            optimized_tree.merkle_tree_nonce_map.get(
                self.transactions_2[0].get('nonce')),
            reference_tree.merkle_tree_nonce_map.get(
                self.transactions_2[0].get('nonce'))
        )
        self.assertEqual(
            optimized_tree.last_tx_proof(),
            reference_tree.proof(last_tx_index)
        )

    def test_correct_root_calculation_batch_create(self):
        reference_tree = TransactionMerkleTree(self.transactions_1)

        merkle_hash_cache, merkle_height_cache = '', ''
        root_hash = ''

        optimized_tree = OptimizedTransactionMerkleTree(
            merkle_hash_cache,
            merkle_height_cache,
            transactions=self.transactions_2
        )

        root_hash = optimized_tree.root_hash()
        merkle_hash_cache, merkle_height_cache = optimized_tree.merkle_cache_stacks()

        self.assertEqual(root_hash, reference_tree.root_hash())

    def test_correct_root_calculation_batch_create_at_zero(self):
        reference_tree = TransactionMerkleTree([])

        merkle_hash_cache, merkle_height_cache = '', ''
        root_hash = ''

        optimized_tree = OptimizedTransactionMerkleTree(
            merkle_hash_cache,
            merkle_height_cache,
            transactions=[]
        )

        root_hash = optimized_tree.root_hash()
        merkle_hash_cache, merkle_height_cache = optimized_tree.merkle_cache_stacks()

        self.assertEqual(root_hash, reference_tree.root_hash())

    def test_correct_root_calculation_batch_create_at_one(self):
        reference_tree = TransactionMerkleTree(self.transactions_1[:1])

        merkle_hash_cache, merkle_height_cache = '', ''
        root_hash = ''

        optimized_tree = OptimizedTransactionMerkleTree(
            merkle_hash_cache,
            merkle_height_cache,
            transactions=self.transactions_2[:1]
        )

        root_hash = optimized_tree.root_hash()
        merkle_hash_cache, merkle_height_cache = optimized_tree.merkle_cache_stacks()

        self.assertEqual(root_hash, reference_tree.root_hash())
