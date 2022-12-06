import argparse

import rlp
from ecdsa import SigningKey, SECP256k1
from eth_utils import keccak, decode_hex, encode_hex
from web3 import Web3, HTTPProvider


parser = argparse.ArgumentParser()
parser.add_argument('binary', help='path to binary to deploy')
parser.add_argument('key', help='hex encoded wallet private key')
parser.add_argument('rpc', help='ethereum rpc node url')
parser.add_argument('--publish', dest='publish', help='publish contract to rpc node', action='store_true', required=False)
parser.set_defaults(publish=False)
args = parser.parse_args()

if not args.publish:
    print('Doing demo run. No code will be published.')

web3 = Web3(HTTPProvider(args.rpc))

private_key = SigningKey.from_string(string=decode_hex(args.key), curve=SECP256k1)
public_key = private_key.get_verifying_key().to_string()
wallet_address = web3.toChecksumAddress(keccak(public_key).hex()[24:])

web3.eth.defaultAccount = wallet_address

print('Deploying from wallet: {}'.format(wallet_address))

with open(args.binary) as f:
    bytecode = f.readline().lstrip().rstrip()

contract_class = web3.eth.contract(bytecode=bytecode, abi=[])

deployment_transaction = contract_class.constructor().buildTransaction({
    'gasPrice': web3.toWei('25', 'gwei'),
})
print('Gas Cost: {}'.format(deployment_transaction.get('gas')))
nonce = web3.eth.getTransactionCount(wallet_address)
deployment_transaction['nonce'] = nonce
deployment_transaction['to'] = ''


print('Nonce: {}'.format(nonce))

#web3.eth.enable_unaudited_features()
signed_transaction = web3.eth.account.signTransaction(deployment_transaction, private_key=args.key)

contract_address = keccak(rlp.encode([decode_hex(wallet_address), nonce]))[12:]
print('Contract address: {}'.format(web3.toChecksumAddress(contract_address)))

if args.publish:
    print('Publishing contract to rpc')
    transaction_hash = web3.eth.sendRawTransaction(signed_transaction.rawTransaction)
    print('Transaction Hash: {}'.format(encode_hex(transaction_hash)))
