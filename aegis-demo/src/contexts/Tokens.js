import React, { createContext, useContext, useReducer, useMemo, useCallback, useEffect } from 'react'

import { useEraNumber } from './Nocust'

import ethImg from '../images/ethereum.png'
import daiImg from '../images/dai.jpg'
import lqdImg from '../images/liquidity.png'

import { nocust } from 'nocust-client'
import Web3 from 'web3'

const UPDATE = 'UPDATE'

export const TokensContext = createContext()

export function useTokensContext () {
  return useContext(TokensContext)
}

function reducer (state, { type, payload }) {
  switch (type) {
    case UPDATE: {
      const { tokens } = payload
      return {
        ...state,
        tokens
      }
    }
    default: {
      throw Error(`Unexpected action type in TokensContext reducer: '${type}'.`)
    }
  }
}

export default function Provider ({ children }) {
  const [state, dispatch] = useReducer(reducer, {})

  const update = useCallback((tokens) => {
    dispatch({ type: UPDATE, payload: { tokens } })
  }, [])

  return (
    <TokensContext.Provider value={useMemo(() => [state, { update }], [state, update])}>
      {children}
    </TokensContext.Provider>
  )
}

function buildTokenDict (tokenList) {
  var tokens = tokenList.reduce((accumulator, pilot) => {
    return { ...accumulator, [pilot.shortName]: { name: pilot.name, shortName: pilot.shortName, tokenAddress: pilot.address } }
  }, {})

  if (tokens.ETH) tokens.ETH.image = ethImg
  if (tokens.DAI) tokens.DAI.image = daiImg
  if (tokens.LQD) tokens.LQD.image = lqdImg

  return tokens
}

export function useTokens (privateKey) {

  //onst eraNumber = useEraNumber()

  const [state, { update }] = useTokensContext()
  const { tokens } = state

  useEffect(() => {
    const fetchTokens = async () => {
      await nocust.init({
        contractAddress: process.env.REACT_APP_HUB_CONTRACT_ADDRESS,
        rpcUrl: process.env.REACT_APP_WEB3_PROVIDER,
        operatorUrl: process.env.REACT_APP_HUB_API_URL
      });
    
      await nocust.addPrivateKey(privateKey);
      //console.log("Private key added");

      try {
        const tokenList = await nocust.getSupportedTokens()
        const tokens = buildTokenDict(tokenList)
        update(tokens)
      } catch (e) {
        console.log('fetch tokens error', e)
        update({})
      }
    }

    fetchTokens()

  }, [])

  return tokens
}

export function registerTokens (address, privateKey) {
  //const nocust = useNocustClient()
  const tokens = useTokens(privateKey)

  useEffect(() => {
    if (tokens) {
      Object.values(tokens).map(async token => {
        const addressRegistered = await nocust.isWalletRegistered(address, token.tokenAddress)
        // explicitly test for false-ness as endpoint returns undefined for true
        console.log('addressRegistered', addressRegistered)
        if (addressRegistered === false) {
          return registerToken(address, token.tokenAddress, privateKey)
        }
        return null
      })
    }
  }, [nocust, address, tokens])
}

async function registerToken (address, tokenAddress, privateKey) {

  const registerTokenAndApprove = async () => {

    await nocust.init({
      contractAddress: process.env.REACT_APP_HUB_CONTRACT_ADDRESS,
      rpcUrl: process.env.REACT_APP_WEB3_PROVIDER,
      operatorUrl: process.env.REACT_APP_HUB_API_URL
    });
  
    await nocust.addPrivateKey(privateKey);
    //console.log("Private key added");
  
    console.log('Registering token:', tokenAddress)
    try {
      return nocust.registerWallet(address, tokenAddress)
    } catch (e) {
      console.log('Error registering', e)
    }

    console.log('Approving deposits:', address)
    const gasPriceVal = 20.0
    const gasPrice = Web3.utils.toWei(gasPriceVal.toString(),'gwei');
    try {
      return nocust.approveDeposits(address, gasPrice, tokenAddress)
    } catch (e) {
      console.log('Error registering', e)
    }
  };
  
  registerTokenAndApprove();
}

export function isValidToken (tokens, tokenShortName) {
  if (!tokens) return false
  return Object.keys(tokens).includes(tokenShortName)
}

export function lookupTokenAddress (tokens, tokenAddress) {
  if (!tokens) return false
  return Object.values(tokens).find((token) => {
    return tokenAddress === token.tokenAddress
  })
}

export function lookupTokenName (tokenName, privateKey) {
  const tokens = useTokens()
  if (!tokens) return false
  return Object.values(tokens).find((token) => {
    return tokenName === token.shortName
  })
}
