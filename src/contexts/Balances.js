import React, { createContext, useContext, useReducer, useMemo, useCallback, useEffect } from 'react'

import { safeAccess } from '../utils'
import { isAddress, fromWei, toBN } from 'web3-utils'
import { useNocustClient, useEraNumber } from './Nocust'
//import { toBigNumber } from 'nocust-client'

import { createNocustManager } from '../services/nocustManager'
import { nocust } from 'nocust-client'
import Web3 from 'web3'

const UPDATE = 'UPDATE'
const UPDATE_ONCHAIN = 'UPDATE_ONCHAIN'
const UPDATE_OFFCHAIN = 'UPDATE_OFFCHAIN'

const ZERO_BALANCE = { offchainBalance: toBN('0'), OnChainBalance: toBN('0') }

const BalanceContext = createContext()

function useBalanceContext () {
  return useContext(BalanceContext)
}

function reducer (state, { type, payload }) {
  switch (type) {
    case UPDATE: {
      const { address, tokenAddress, tokenBalance } = payload
      return {
        ...state,
        [address]: {
          ...(safeAccess(state, [address]) || {}),
          [tokenAddress]: tokenBalance
        }
      }
    }
    case UPDATE_ONCHAIN: {
      const { address, tokenAddress, OnChainBalance } = payload
      return {
        ...state,
        [address]: {
          ...(safeAccess(state, [address]) || {}),
          [tokenAddress]: {
            ...(safeAccess(state, [address, tokenAddress]) || {}),
            OnChainBalance
          }
        }
      }
    }
    case UPDATE_OFFCHAIN: {
      const { address, tokenAddress, offchainBalance } = payload
      return {
        ...state,
        [address]: {
          ...(safeAccess(state, [address]) || {}),
          [tokenAddress]: {
            ...(safeAccess(state, [address, tokenAddress]) || {}),
            offchainBalance
          }
        }
      }
    }
    default: {
      throw Error(`Unexpected action type in BalancesContext reducer: '${type}'.`)
    }
  }
}

export default function Provider ({ children }) {
  const [state, dispatch] = useReducer(reducer, {})

  const update = useCallback((address, tokenAddress, tokenBalance) => {
    dispatch({ type: UPDATE, payload: { address, tokenAddress, tokenBalance } })
  }, [])

  const updateOnchain = useCallback((address, tokenAddress, OnChainBalance) => {
    dispatch({ type: UPDATE_ONCHAIN, payload: { address, tokenAddress, OnChainBalance } })
  }, [])

  const updateOffchain = useCallback((address, tokenAddress, offchainBalance) => {
    dispatch({ type: UPDATE_OFFCHAIN, payload: { address, tokenAddress, offchainBalance } })
  }, [])

  return (
    <BalanceContext.Provider value={useMemo(() => [state, { update, updateOnchain, updateOffchain }], [state, update, updateOnchain, updateOffchain])}>
      {children}
    </BalanceContext.Provider>
  )
}

export function useOffchainAddressBalance (address, tokenAddress, privateKey) {
  //const nocust = useNocustClient()
  useEffect(() => {
    (async () => {
      await createNocustManager(process.env.REACT_APP_WEB3_PROVIDER, process.env.REACT_APP_HUB_CONTRACT_ADDRESS, process.env.REACT_APP_HUB_API_URL, privateKey)
    })();
    
    return () => {
      // this now gets called when the component unmounts
    };
  }, []);

  //const eraNumber = useEraNumber()

  const [state, { updateOffchain }] = useBalanceContext()
  const { offchainBalance } = safeAccess(state, [address, tokenAddress]) || ZERO_BALANCE

  useEffect(() => {
    if (
      isAddress(address) &&
      isAddress(tokenAddress)
    ) {
      console.log('Getting offchain balance')

      async function getOffchainBalance() {
        try {
          const offChainBalance = await nocust.getBalance(address, tokenAddress)
          updateOffchain(address, tokenAddress, offChainBalance)
        } catch (err) {
          console.error(err)
          updateOffchain(address, tokenAddress, ZERO_BALANCE)
      }

      }
      getOffchainBalance()
    }
  }, [address, tokenAddress])

  return offchainBalance
}

export function useOnchainAddressBalance (address, tokenAddress, privateKey) {
  //const nocust = useNocustClient()
  useEffect(() => {
    (async () => {
      await createNocustManager(process.env.REACT_APP_WEB3_PROVIDER, process.env.REACT_APP_HUB_CONTRACT_ADDRESS, process.env.REACT_APP_HUB_API_URL, privateKey)
    })();
    
    return () => {
      // this now gets called when the component unmounts
    };
  }, []);

  //const eraNumber = useEraNumber()

  const [state, { updateOnchain }] = useBalanceContext()
  const { OnChainBalance } = safeAccess(state, [address, tokenAddress]) || ZERO_BALANCE

  useEffect(() => {
    console.log('getting OnChain balances for', tokenAddress)
    if (!!address && !!tokenAddress) {
     async function getParentChainBalance() {
        try {
          const parentChainBalance = await nocust.getParentChainBalance(address, tokenAddress)
          updateOnchain(address, tokenAddress, parentChainBalance)
         } catch (err) {
          updateOnchain(address, tokenAddress, ZERO_BALANCE)
         }
      }

      getParentChainBalance()
    }
  }, [address, tokenAddress])

  return OnChainBalance
}

export function getDisplayValue (value, decimals = 4) {
  const displayVal = Web3.utils.fromWei(value.toString(10), 'ether')
  if (displayVal.indexOf('.') >= 0) {
    if (displayVal.charAt(0) === '0') {
      return displayVal.substr(0, displayVal.search(/[1-9]/) + decimals + 1)
    } else {
      return displayVal.substr(0, displayVal.indexOf('.') + decimals + 1)
    }
  }
  const balance = Number(displayVal)
  return balance
}

export function useAddressBalance (address, tokenAddress, privateKey) {

  //const eraNumber = useEraNumber()
  const [state, { update }] = useBalanceContext()
  const tokenBalance = safeAccess(state, [address, tokenAddress]) || ZERO_BALANCE

  useEffect(() => {
    console.log('getting balances for', tokenAddress)
    if (!!address && !!tokenAddress) {
      const getWalletBalance = async () => {

        await nocust.init({
          contractAddress: process.env.REACT_APP_HUB_CONTRACT_ADDRESS,
          rpcUrl: process.env.REACT_APP_WEB3_PROVIDER,
          operatorUrl: process.env.REACT_APP_HUB_API_URL
        });
      
        await nocust.addPrivateKey(privateKey);
        //console.log("Private key added");
      
        const OnChainBalance = await nocust.getParentChainBalance(address, tokenAddress)
        const OffchainBalance = await nocust.getBalance(address, tokenAddress)
        const walletBalance = Promise.all([OnChainBalance, OffchainBalance])
        walletBalance.then(([OnChainBalance, OffchainBalance]) => {
          update(address, tokenAddress, { OnChainBalance, OffchainBalance })
        })
        .catch(err => {
          console.error(err)
          update(address, tokenAddress, ZERO_BALANCE)
        })
      };
      
      getWalletBalance();
    }
  }, [address, tokenAddress])

  //console.log('tokenBalance4', tokenBalance)
  return tokenBalance
}

export function useAllTokenBalances (address) {
  const [state] = useBalanceContext()
  const tokenDetails = safeAccess(state, [address]) || {}
  return tokenDetails
}
