import React, { useState } from 'react'
import { CopyToClipboard } from 'react-copy-to-clipboard'
import i18n from '../i18n'
import { useButtonStyle } from '../contexts/Theme'

const QRCode = require('qrcode.react')
const { toWei } = require('web3-utils')
const qs = require('query-string')

export default (props) => {
  const buttonStyle = useButtonStyle()
  const [amount, setAmount] = useState('')
  const canRequest = amount > 0

  const [requested, setRequested] = useState(false)

  const { address, changeAlert, token, networkId } = props
  if (requested) {
    const invoice = {
      network: networkId,
      publicKey: address,
      tokenAddress: token.tokenAddress,
      amount: toWei(amount, 'ether')
    }

    const deeplinkRoot = 'lqdnet://send?'
    const qrValue = deeplinkRoot + qs.stringify(invoice)
    console.log('Request Link:', qrValue)

    const qrSize = Math.min(document.documentElement.clientWidth, 512) - 90

    return (
      <div>
        <CopyToClipboard
          text={qrValue} onCopy={() => {
            changeAlert({ type: 'success', message: 'Request link copied to clipboard' })
          }}
        >
          <div style={{ width: '100%', textAlign: 'center' }}>
            <div style={{ fontSize: 30, cursor: 'pointer', textAlign: 'center', width: '100%' }}>
              {'f' + token.shortName + ' ' + amount}
            </div>

            <div style={{ cursor: 'pointer', textAlign: 'center', width: '100%' }}>
              <QRCode value={qrValue} size={qrSize} />
            </div>

            <div className='input-group'>
              <input type='text' className='form-control' value={qrValue} disabled />
              <div className='input-group-append'>
                <span className='input-group-text'><i className='fas fa-copy' /></span>
              </div>
            </div>

          </div>
        </CopyToClipboard>
      </div>
    )
  } else {
    return (
      <div>
        <div className='content row'>
          <div className='form-group w-100'>
            <label htmlFor='amount_input'>{i18n.t('request_funds.amount')}</label>
            <div className='input-group'>
              <div className='input-group-prepend'>
                <div className='input-group-text'>{token ? 'f' + token.shortName : i18n.t('loading')}</div>
              </div>
              <input
                type='number' className='form-control' placeholder='0.00' value={amount}
                onChange={event => setAmount(event.target.value)}
              />
            </div>
          </div>
        </div>
        <button
          name='theVeryBottom'
          style={buttonStyle.primary}
          className={`btn btn-lg w-100 ${canRequest ? '' : 'disabled'}`}
          onClick={() => {
            if (canRequest) {
              setRequested(true)
            } else {
              props.changeAlert({ type: 'warning', message: 'Please enter a valid amount' })
            }
          }}
        >
          {i18n.t('request_funds.button')}
        </button>
      </div>
    )
  }
}
