import React from 'react'
import { useHistory, useLocation, Link } from 'react-router-dom'
import { Blockie } from 'dapparatus'
import { useMainStyle } from '../contexts/Theme'
// import burnerloader from '../burnerloader.gif';

export default ({ network, total, ens, balance, address }) => {
  const history = useHistory()
  const location = useLocation()
  const mainStyle = useMainStyle()

  let name = ens
  if (!name) {
    name = address.substring(2, 8)
  }

  const moneyDisplay = (
    <div style={{ opacity: 0.4, fontSize: 22, paddingTop: 18 }}>
      {network}
    </div>
  )

  const blockieDisplay = (
    <Blockie
      address={address}
      config={{ size: 6 }}
    />
  )

  const sendButtonOpacity = 1.0

  const scanButtonStyle = {
    opacity: sendButtonOpacity,
    position: 'fixed',
    right: 20,
    bottom: 20,
    zIndex: 2,
    cursor: 'pointer'
  }

  const bottomRight = (
    <Link to={{ pathname: '/scanner', search: location.search }} style={scanButtonStyle}>
      <div style={{ position: 'relative', backgroundImage: 'linear-gradient(' + mainStyle.mainColorAlt + ',' + mainStyle.mainColor + ')', backgroundColor: mainStyle.mainColor, borderRadius: '50%', width: 89, height: 89, boxShadow: '0.5px 0.5px 5px #000000' }}>
        <div style={{ color: '#FFFFFF', position: 'absolute', left: 30, top: 28 }}>
          <i className='fas fa-qrcode' />
        </div>
      </div>
    </Link>
  )

  let topLeft
  let opacity = 0.5

  if (location.pathname !== '/liquidity/receive') {
    opacity = 1.0
    topLeft = (
      <div style={{ position: 'absolute', left: 16, top: 4, zIndex: 1, cursor: 'pointer' }} onClick={() => history.push('/liquidity/receive')}>
        {blockieDisplay} <div style={{ position: 'absolute', left: 60, top: 15, fontSize: 14 }}>{name}</div>
      </div>
    )
  } else {
    topLeft = (
      <div style={{ position: 'absolute', left: 16, top: 4, zIndex: 1, cursor: 'pointer' }} onClick={() => history.goBack()}>
        {blockieDisplay} <div style={{ position: 'absolute', left: 60, top: 15, fontSize: 14 }}>{name}</div>
      </div>
    )
  }

  const topRight = (
    <div style={{ position: 'absolute', right: 28, top: -4, zIndex: 1, fontSize: 46, opacity: 0.9 }}>
      {moneyDisplay}
    </div>
  )

  const lossWarning = ''
  /*
  let context = document.getElementById("context").innerHTML
  console.log("context",context,"balance",balance)
  if(context=="INCOGNITO" && balance>0){
    lossWarning =  (
      <div style={{marginTop:50, fontSize:28}}>
        WARNING: If you close this window you will lose these funds.
      </div>
    )
  } */

  return (
    <div className='header' style={{ opacity }}>
      {topLeft}
      {topRight}
      {lossWarning}
      {bottomRight}
    </div>
  )
}
