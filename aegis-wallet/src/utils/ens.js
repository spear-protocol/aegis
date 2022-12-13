import Web3 from 'web3'
import namehash from 'eth-ens-namehash'

export async function ensLookup (name) {
  const hash = namehash.hash(name)
  console.log('namehash', name, hash)

  const { Contract } = new Web3(new Web3.providers.HttpProvider(process.env.REACT_APP_MAINNET_WEB3_PROVIDER)).eth

  const ensContract = new Contract(require('../contracts/ENS.abi.js'), require('../contracts/ENS.address.js'))
  const resolver = await ensContract.methods.resolver(hash).call()
  if (resolver === '0x0000000000000000000000000000000000000000') return '0x0000000000000000000000000000000000000000'
  console.log('resolver address', resolver)

  const ensResolver = new Contract(require('../contracts/ENSResolver.abi.js'), resolver)
  console.log('ensResolver:', ensResolver)

  return ensResolver.methods.addr(hash).call()
}

export async function reverseEnsLookup (address) {
  const hash = namehash.hash(address.toLowerCase().substr(2) + '.addr.reverse')

  const { Contract } = new Web3(new Web3.providers.HttpProvider(process.env.REACT_APP_MAINNET_WEB3_PROVIDER)).eth

  const ensContract = new Contract(require('../contracts/ENS.abi.js'), require('../contracts/ENS.address.js'))
  const resolver = await ensContract.methods.resolver(hash).call()
  if (resolver === '0x0000000000000000000000000000000000000000') return null

  const ensResolver = new Contract(require('../contracts/ENSResolver.abi.js'), resolver)

  return ensResolver.methods.name(hash).call()
}
