import React from 'react'
import { CopyToClipboard } from 'react-copy-to-clipboard'
import i18n from '../i18n'

import NavCard from '../components/NavCard'

const QRCode = require('qrcode.react')

export default (props) => {
  const { address, network, changeAlert } = props

  const qrSize = Math.min(document.documentElement.clientWidth, 512) - 90
  return (
    <div>
      <div className='main-card card w-100' style={{ zIndex: 1 }}>

        <NavCard title={i18n.t('receive_title')} />
        <div>
          <div className='send-to-address w-100'>
            <CopyToClipboard
              text={address} onCopy={() => {
                changeAlert({ type: 'success', message: i18n.t('receive.address_copied') })
              }}
            >
              <div className='content qr row' style={{ cursor: 'pointer' }}>
                <QRCode value={address} size={qrSize} />
                <div className='input-group'>
                  <input type='text' className='form-control' style={{ color: '#999999' }} value={address} disabled />
                  <div className='input-group-append'>
                    <span className='input-group-text'><i style={{ color: '#999999' }} className='fas fa-copy' /></span>
                  </div>
                </div>
              </div>
            </CopyToClipboard>
            <div style={{ width: '100%', textAlign: 'center', padding: 20 }}>
              <a href={'https://explorer.liquidity.network/details/' + network + '/' + address} target='_blank' rel='noopener noreferrer'>
                View on Explorer
              </a>
            </div>
          </div>
        </div>
      </div>
      {props.backButton}
    </div>
  )
}
