import React from 'react'
import { Link, useLocation } from 'react-router-dom'

const preventSpaces = (event) => {
  const keyPressed = event.key

  if (/\s/g.test(keyPressed)) {
    event.preventDefault()
  }
}

const AddressBar = (props) => {
  const location = useLocation()

  return (
    <div className='input-group'>
      <input
        type='text' className='form-control' placeholder='0x...' value={props.toAddress || ''}
        ref={(input) => { if (typeof props.addressInput === 'function') { props.addressInput(input) } }}
        onKeyPress={preventSpaces}
        onChange={event => { props.setToAddress(event.target.value.replace(/\s/g, '')) }}
      />
      {props.openScanner &&
        <div className='input-group-append'>
          <div className='input-group-text' id='basic-addon2' style={props.buttonStyle.primary}>
            <Link to={{ pathname: '/scanner', search: location.search }}>
              <i style={{ color: '#FFFFFF' }} className='fas fa-qrcode' />
            </Link>
          </div>
        </div>}
    </div>
  )
}

export default AddressBar
