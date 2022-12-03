import React from 'react'
import { Scaler } from 'dapparatus'

import 'react-input-range/lib/css/index.css'

export default React.forwardRef((props, ref) => {
  const maxButton = (
    <div className='input-group-append' onClick={event => { props.updateValue(props.maxValue) }}>
      <span className='input-group-text' id='basic-addon2' style={props.buttonStyle.secondary}>
          max
      </span>
    </div>
  )

  return (
    <Scaler config={{ startZoomAt: 400, origin: '50% 50%' }}>
      <div className='input-group'>
        <div className='input-group-prepend'>
          <div className='input-group-text'>{props.unit}</div>
        </div>
        <input
          ref={ref}
          type='number'
          step='0.01'
          className='form-control'
          placeholder='0.00'
          value={props.value || ''}
          min={props.minValue}
          max={props.maxValue}
          readOnly={props.readOnly}
          onChange={event => props.updateValue(event.target.value)}
        />
        {typeof props.maxValue !== 'undefined' && maxButton}
      </div>
    </Scaler>
  )
}
)
