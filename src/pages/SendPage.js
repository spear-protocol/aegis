import React, { useEffect } from 'react'

import Ruler from '../components/Ruler'
import i18n from '../i18n'

import NavCard from '../components/NavCard'
import SendToAddress from '../components/SendToAddress'
import Balance from '../components/Balance'
import Transactions from '../components/Transactions'

import { useOffchainAddressBalance } from '../contexts/Balances'
import { lookupTokenAddress } from '../contexts/Tokens'
import { createNocustManager } from '../services/nocustManager'
import { nocust } from 'nocust-client'

import { safeAccess } from '../utils'
import { isAddress, fromWei } from 'web3-utils'
import { useNocustClient } from '../contexts/Nocust'
import { useButtonStyle } from '../contexts/Theme'

const qs = require('query-string')

export default (props) => {
  const buttonStyle = useButtonStyle()
  //const nocust = useNocustClient()
  useEffect(() => {
    (async () => {
      await createNocustManager(process.env.REACT_APP_WEB3_PROVIDER, process.env.REACT_APP_HUB_CONTRACT_ADDRESS, process.env.REACT_APP_HUB_API_URL, props.privateKey)
    })();
    
    return () => {
      // this now gets called when the component unmounts
    };
  }, []);

  const query = qs.parse(props.location.search)

  // First look up token address.
  // May have been given the token's shortname so perform lookup if that fails
  // Finally default to main token.
  let token
  if (isAddress(query.token)) {
    token = lookupTokenAddress(props.tokens, query.token)
  } else {
    token = safeAccess(props.tokens, [query.token]) || safeAccess(props.tokens, [process.env.REACT_APP_TOKEN]) || {}
  }

  const tokenBalance = useOffchainAddressBalance(props.address, token.tokenAddress, props.privateKey)
  const toAddress = typeof props.location.state !== 'undefined' ? props.location.state.toAddress : undefined
  const tokenAmount = typeof query.amount === 'string' ? fromWei(query.amount, 'ether') : undefined

  console.log('SendPage token', token)
  console.log('SendPage tokenBalance', tokenBalance)
  console.log('SendPage toAddress', toAddress)

  return (
    <div>
      <div className='send-to-address card w-100' style={{ zIndex: 1 }}>

        <NavCard title={i18n.t('send_to_address.title') + ' f' + token.shortName} />
        <Balance
          token={token}
          offchain
          selected
          address={props.address}
          privateKey={props.privateKey}
        />
        <Ruler />
        <SendToAddress
          token={token}
          sendTransaction={(tx) => nocust.transfer(tx)}
          toAddress={toAddress}
          amount={tokenAmount}
          ensLookup={props.ensLookup}
          buttonStyle={buttonStyle}
          offchainBalance={tokenBalance}
          address={props.address}
          privateKey={props.privateKey}
          changeAlert={props.changeAlert}
          onSend={async (txhash) => {
            props.history.push(`${props.url}/sending`)
            const tx = await nocust.getTransfer(await txhash)
            console.log(tx)
          }}
        />
        <Transactions
          changeAlert={props.changeAlert}
          address={props.address}
          token={token}
          max={5}
        />
      </div>
      {props.backButton}
    </div>
  )
}
