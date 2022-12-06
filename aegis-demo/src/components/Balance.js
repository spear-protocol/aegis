import React from 'react'
import i18n from '../i18n'

import { Scaler } from 'dapparatus'
import { toBN } from 'web3-utils'
import { getDisplayValue, useAddressBalance } from '../contexts/Balances'
import Web3 from 'web3'

export default ({ address, token, selected, offchain, privateKey }) => {
  let opacity = 0.65
  if (selected) {
    opacity = 0.95
  }
  const tokenBalance = useAddressBalance(address, token ? token.tokenAddress : undefined, privateKey)
  //const balance = offchain ? tokenBalance.offchainBalance : tokenBalance.onChainBalance
  const balance = offchain ? tokenBalance.OffchainBalance : tokenBalance.OnChainBalance
  var amount = balance ? getDisplayValue(balance) : i18n.t('loading')

  if (isNaN(amount) || typeof amount === 'undefined') {
    amount = 0.00
    opacity = 0.25
  }

  if (opacity < 0.9 && parseFloat(amount) <= 0.0) {
    opacity = 0.05
  }

  let iconDisplay
  let tokenName

  if (token && typeof token.image === 'string' && token.image.length < 8) {
    iconDisplay = (
      <div style={{ width: 50, height: 50, fontSize: 42, paddingTop: 13 }}>
        {token.image}
      </div>
    )
  } else {
    iconDisplay = <img src={token && token.image} alt='' style={{ maxWidth: 50, maxHeight: 50 }} />
  }

  if (token && token.shortName) {
    tokenName = (
      <div style={{ position: 'absolute', left: 60, top: 12, fontSize: 14, opacity: 0.77, whiteSpace: 'nowrap' }}>
        {offchain ? 'f' + token.shortName : token.shortName}
      </div>
    )
  } else {
    tokenName = (
      <div style={{ position: 'absolute', left: 60, top: 12, fontSize: 14, opacity: 0.77, whiteSpace: 'nowrap' }}>
        {i18n.t('loading')}
      </div>
    )
  }

  const balanceDisplay = (
    <Scaler config={{ startZoomAt: 400, origin: '200px 30px', adjustedZoom: 1 }}>
      <div style={{ fontSize: 40, letterSpacing: -2 }}>
        {amount}
      </div>
    </Scaler>
  )

  return (
    <div className='balance row' style={{ opacity, paddingBottom: 0, paddingLeft: 20 }}>
      <div className='avatar col p-0'>
        {iconDisplay}
        {tokenName}
      </div>
      <div style={{ position: 'absolute', right: 25, marginTop: 15 }}>
        {balanceDisplay}
      </div>
    </div>
  )
}
