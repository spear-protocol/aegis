import argparse

import rlp
from ecdsa import SigningKey, SECP256k1
from eth_utils import keccak, decode_hex, encode_hex, remove_0x_prefix
from eth_abi import encode_abi
from web3 import Web3, HTTPProvider
import json


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
    deployments = json.load(f)

base_nonce = web3.eth.getTransactionCount(wallet_address)

deployed_contracts = {}
for target in deployments:

    print(target.get('name'))

    linked_bytecode = target.get('bytecode')

    for library, address in deployed_contracts.items():
        linked_bytecode = linked_bytecode.replace(library, address)

    parameters = target.get('parameters')

    if parameters:
        types = [param.get('type') for param in parameters]
        values = [param.get('value') for param in parameters]
        linked_bytecode = linked_bytecode + remove_0x_prefix(encode_hex(encode_abi(types, values)))
        for parameter in parameters:
            if parameter["type"] == "address":
                parameter["value"] == wallet_address

    contract_class = web3.eth.contract(bytecode=linked_bytecode, abi=[])

    nonce = base_nonce + len(deployed_contracts)
    print('Nonce: {}'.format(nonce))

    contract_address = keccak(rlp.encode([decode_hex(wallet_address), nonce]))[12:]
    env_contract = web3.toChecksumAddress(contract_address)
    print(f'Contract address: {env_contract}')

    deployed_contracts[target.get('name')] = remove_0x_prefix(web3.toChecksumAddress(contract_address))

    if args.publish:
        deployment_transaction = contract_class.constructor().buildTransaction({
            'gasPrice': web3.toWei('25', 'gwei'),
            'gas': 6553600
        })
        deployment_transaction['nonce'] = nonce
        deployment_transaction['to'] = ''

#        web3.eth.enable_unaudited_features()
        signed_transaction = web3.eth.account.signTransaction(deployment_transaction, private_key=args.key)

        print('Publishing contract to rpc')
        transaction_hash = web3.eth.sendRawTransaction(signed_transaction.rawTransaction)
        print('Transaction Hash: {}'.format(encode_hex(transaction_hash)))
        
#if args.publish:
#    import fileinput
#    with fileinput.input(".env", inplace=True) as env_file:
#        for line in env_file:
#            if "HUB_LQD_CONTRACT_ADDRESS" in line:
#                print(f"HUB_LQD_CONTRACT_ADDRESS={env_contract}")
#            else:
#                print(line)


