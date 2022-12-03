import React, { Component } from 'react'
import { Redirect } from 'react-router-dom'
import i18n from '../i18n'
import { Reader, LegacyReader } from '../components/SendByScan'
const qs = require('query-string')

export default class ScannerPage extends Component {
  constructor (props) {
    super(props)
    let defaultToLegacyMode = false
    if (!navigator || !navigator.mediaDevices) {
      defaultToLegacyMode = true
    }
    this.state = {
      legacyMode: defaultToLegacyMode,
      scanFail: false
    }
  }

  handleError = error => {
    console.log('SCAN ERROR')
    console.error(error)
    this.setState({ legacyMode: true })
    this.props.onError(error)
  }

  handleFailure = (scanFail) => {
    this.setState({ scanFail })
    setTimeout(() => { this.setState({ scanFail: false }) }, 3500)
  }

  render () {
    const { legacyMode, scanFail, scanData } = this.state

    if (scanData) {
      return <Redirect to={{ pathname: '/liquidity/send/' + scanData.toAddress, search: qs.stringify({ ...qs.parse(this.props.search), ...scanData.search }) }} />
    }

    let failMessage = ''
    if (scanFail) {
      failMessage = (
        <div style={{ position: 'absolute', left: 0, top: 0, zIndex: 99, fontSize: 24, color: '#FF0000', backgroundColor: '#333333', opacity: 0.9, width: '100%', height: '100%', fontWeight: 'bold' }}>
          <div style={{ textAlign: 'center', paddingTop: '15%' }}>
            <div style={{ marginBottom: 20 }}><i className='fas fa-ban' /></div>
          </div>
          <div style={{ textAlign: 'center', paddingTop: '25%' }}>
            <div>{i18n.t('send_by_scan.try_again')}</div>

          </div>
          <div style={{ textAlign: 'center', padding: '10%', paddingTop: '15%', fontSize: 16 }}>
            <div>{scanFail}</div>
          </div>
        </div>
      )
    }

    return (
      <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 5, margin: '0 auto !important', background: '#000000' }}>
        <div style={{ position: 'absolute', zIndex: 256, top: 20, right: 20, fontSize: 80, paddingRight: 20, color: '#FFFFFF', cursor: 'pointer' }} onClick={() => this.props.goBack()}>
          <i className='fa fa-times' aria-hidden='true' />
        </div>
        {legacyMode ? <LegacyReader onSuccess={(scanData) => { this.setState({ scanData }) }} onFail={(scanFail) => { this.handleFailure(scanFail) }} />
          : <Reader onError={this.handleError} onSuccess={(scanData) => { this.setState({ scanData }) }} onFail={(scanFail) => { this.handleFailure(scanFail) }} />}
        <div style={{ position: 'absolute', zIndex: 11, bottom: 20, fontSize: 12, left: 20, color: '#FFFFFF', opacity: 0.333 }}>
          {navigator.userAgent} - {JSON.stringify(navigator.mediaDevices)}
        </div>
        {failMessage}
      </div>
    )
  }
}
