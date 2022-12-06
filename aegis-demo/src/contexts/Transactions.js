import React, { createContext, useContext, useReducer, useMemo, useCallback, useEffect } from 'react'

import { safeAccess } from '../utils'
import { isAddress } from 'web3-utils'
import { useNocustClient, useEraNumber } from './Nocust'

import { nocust } from 'nocust-client'

const UPDATE = 'UPDATE'

const TransactionContext = createContext()

function useTransactionContext () {
  return useContext(TransactionContext)
}

function reducer (state, { type, payload }) {
  switch (type) {
    case UPDATE: {
      const { address, tokenAddress, transactions } = payload
      return {
        ...state,
        [address]: {
          ...(safeAccess(state, [address]) || {}),
          [tokenAddress]: transactions

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

  const update = useCallback((address, tokenAddress, transactions) => {
    dispatch({ type: UPDATE, payload: { address, tokenAddress, transactions } })
  }, [])

  return (
    <TransactionContext.Provider value={useMemo(() => [state, { update }], [state, update])}>
      {children}
    </TransactionContext.Provider>
  )
}

export function useTokenTransactions (address, tokenAddress) {
  //const nocust = useNocustClient()
  //const eraNumber = useEraNumber()
  const [state, { update }] = useTransactionContext()
  const transactions = safeAccess(state, [address, tokenAddress]) || []

  useEffect(() => {
    if (isAddress(address) && isAddress(tokenAddress)) {
      console.log('checking transactions')
      const getTokenTransacions = async () => {
        const transactions = await nocust.getTransfers(address, tokenAddress)
        if (transactions.length) {
          transactions = transactions.reverse()
        }
        update(address, tokenAddress, transactions)
      }

      getTokenTransacions()
        .catch(() => {
          update(address, tokenAddress, [])
        })
    }
  }, [address, tokenAddress])

  return transactions
}
