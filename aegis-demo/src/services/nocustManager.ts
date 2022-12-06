import { nocust } from 'nocust-client'
import { StorageEngine } from 'nocust-client/dist/services/storage'
import Web3 from 'web3'

class NocustManagerStorageService implements StorageEngine {
  storage = {}

  async get(key: string): Promise<string> {
    return this.storage[key] || ''
  }

  async set(key: string, value: string): Promise<boolean> {
    this.storage[key] = value
    return true
  }

  async delete(key: string): Promise<boolean> {
    delete this.storage[key]
    return true
  }
}

let web3: Web3

export const createNocustManager = async (
  providerUrl: string,
  contractAddress: string,
  operatorUrl: string,
  privateKey: string
) => {
  try {
    await nocust.init({
      contractAddress: contractAddress,
      rpcUrl: providerUrl,
      operatorUrl: operatorUrl,
      storageEngine: new NocustManagerStorageService(),
    })
    console.log("Nocust initialized")
    addNocustPrivateKey(providerUrl, privateKey)
  } catch (e) {
    console.log('createNocustManager', e)
  }
}

export const addNocustPrivateKey = async (
  providerUrl: string,
  privateKey: string,
)=> {
  try {
    await nocust.addPrivateKey(privateKey)
    web3 = new Web3(new Web3.providers.HttpProvider(providerUrl))
    web3.eth.accounts.wallet.clear()
    web3.eth.accounts.wallet.add(privateKey)
    console.log("privateKey added")
  } catch (e) {
    console.log('addNocustPrivateKey', e)
  }
}

export { web3 }