import React from 'react'
import { Blockie, Scaler } from 'dapparatus'

import { CopyToClipboard } from 'react-copy-to-clipboard'
import i18n from '../i18n'
import { useTokenTransactions } from '../contexts/Transactions'

const { fromWei } = require('web3-utils')
const humanizeDuration = require('humanize-duration')

const TransactionEntry = ({ tx, changeAlert, token }) => {
  const txAge = humanizeDuration(Date.now() - tx.timestamp, { largest: 2, round: true })

  const transactionAmount = (
    <span>
      <span style={{ opacity: 0.33 }}>-</span>{fromWei(tx.amount.toString(10), 'ether')} f{token.shortName}<span style={{ opacity: 0.33 }}>{'->'}</span>
    </span>
  )

  const fromBlockie = (
    <CopyToClipboard
      text={tx.wallet.address} onCopy={() => {
        changeAlert({ type: 'success', message: i18n.t('receive.address_copied') + ': ' + tx.wallet.address })
      }}
    >
      <div style={{ cursor: 'pointer' }}>
        <Blockie
          address={tx.wallet.address}
          config={{ size: 4 }}
        />
      </div>
    </CopyToClipboard>
  )

  const toBlockie = (
    <CopyToClipboard
      text={tx.recipient.address} onCopy={() => {
        changeAlert({ type: 'success', message: i18n.t('receive.address_copied') + ': ' + tx.recipient.address })
      }}
    >
      <div style={{ cursor: 'pointer' }}>
        <Blockie
          address={tx.recipient.address}
          config={{ size: 4 }}
        />
      </div>
    </CopyToClipboard>
  )

  return (
    <div style={{ position: 'relative' }} className='content bridge row'>
      <div className='col-3 p-1' style={{ textAlign: 'center' }}>
        {fromBlockie}
      </div>
      <div className='col-3 p-1' style={{ textAlign: 'center', whiteSpace: 'nowrap', letterSpacing: -1 }}>
        <Scaler config={{ startZoomAt: 600, origin: '25% 50%', adjustedZoom: 1 }}>
          {transactionAmount}
        </Scaler>
      </div>
      <div className='col-3 p-1' style={{ textAlign: 'center', whiteSpace: 'nowrap', letterSpacing: -1 }}>
        {toBlockie}
      </div>
      <div className='col-2 p-1' style={{ textAlign: 'center', whiteSpace: 'nowrap', letterSpacing: -1 }}>
        <Scaler config={{ startZoomAt: 600, origin: '25% 50%', adjustedZoom: 1 }}>
          <span style={{ marginLeft: 5, marginTop: -5, opacity: 0.4, fontSize: 12 }}>{txAge} ago</span>
        </Scaler>
      </div>

    </div>
  )
}

export default ({ max, address, changeAlert, token }) => {
  const transactions = useTokenTransactions(address, token.address)

  const txns = []
  let count = 0
  if (!max) max = 9999
  for (const r in transactions) { // eslint-disable-line no-unused-vars
    if (count++ < max) {
      txns.push(<hr key={'ruler' + transactions[r].tx_id} style={{ color: '#DFDFDF', marginTop: 0, marginBottom: 7 }} />)
      txns.push(<TransactionEntry key={transactions[r].tx_id} tx={transactions[r]} changeAlert={changeAlert} token={token} />)
    }
  }
  if (txns.length > 0) {
    return (
      <div style={{ marginTop: 30 }}>
        {txns}
      </div>
    )
  } else {
    return (
      <span />
    )
  }
}
