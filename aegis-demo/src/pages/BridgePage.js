import React from 'react'

import { Scaler } from 'dapparatus'
import i18n from '../i18n'

import Ruler from '../components/Ruler'
import NavCard from '../components/NavCard'
import Bridge from '../components/Bridge'

import { useWithdrawalFee } from '../contexts/Withdrawal'

const { toWei, fromWei } = require('web3-utils')

const TOKEN = process.env.REACT_APP_TOKEN

export default ({ address, gwei, changeAlert, backButton, privateKey }) => {
  const withdrawFee = useWithdrawalFee(gwei, privateKey)

  return (
    <div>
      <div className='main-card card w-100' style={{ zIndex: 1 }}>
        <NavCard title={i18n.t('bridge.title')} />
        <div style={{ textAlign: 'center', width: '100%', fontSize: 16, marginTop: 10 }}>
          <Scaler config={{ startZoomAt: 400, origin: '50% 50%', adjustedZoom: 1 }}>
            Withdrawal Fee: {typeof withdrawFee !== 'undefined' ? fromWei(withdrawFee.toString(10), 'ether').toString(10) : 0} ETH
          </Scaler>
        </div>
        <Ruler />
        <Bridge
          address={address}
          token={TOKEN}
          gasPrice={toWei(gwei.toString(20), 'gwei')}
          changeAlert={changeAlert}
          onSend={(txHash) => { console.log(txHash) }}
          privateKey={privateKey}
        />
        <Ruler />
        <Bridge
          address={address}
          token='ETH'
          gasPrice={toWei(gwei.toString(20), 'gwei')}
          changeAlert={changeAlert}
          onSend={(txHash) => { console.log(txHash) }}
          privateKey={privateKey}
        />
      </div>
      {backButton}
    </div>
  )
}
