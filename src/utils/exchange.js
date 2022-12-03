const { toBN } = require('web3-utils')

export const getMaxOutputs = (orders, amount) => {
  if (!orders.length) {
    return ['0', '0']
  }
  const amountRemaining = (typeof amount !== 'undefined' ? toBN(amount) : toBN('0'))
  const maxIn = toBN('0')
  const maxOut = toBN('0')
  for (var i = 0; i < orders.length; i++) {
    const order = orders[i]

    if (amountRemaining.gte(toBN(order.remaining_in))) {
      maxIn.iadd(toBN(order.remaining_in))
      maxOut.iadd(toBN(order.remaining_out))
    } else {
      maxIn.iadd(toBN(amountRemaining))
      maxOut.iadd((toBN(order.remaining_out).mul(amountRemaining)).div(toBN(order.remaining_in)))
    }

    amountRemaining.isub(toBN(order.remaining_in))
    if (amountRemaining.lte(toBN('0'))) {
      break
    }
  }
  return [maxIn, maxOut]
}

export const getAmountIn = (orders, amountOut) => {
  return getOtherAmount(orders, amountOut, 'out')
}

export const getAmountOut = (orders, amountIn) => {
  return getOtherAmount(orders, amountIn, 'in')
}

const getOtherAmount = (orders, amount, knownQuantity) => {
  let unknownQuantity
  if (knownQuantity === 'in') {
    knownQuantity = 'remaining_in'
    unknownQuantity = 'remaining_out'
  } else {
    knownQuantity = 'remaining_out'
    unknownQuantity = 'remaining_in'
  }

  const amountRemaining = toBN(amount)
  let orderIdx = 0
  const output = toBN('0')
  while (amountRemaining.gt(toBN('0'))) {
    try {
      const order = orders[orderIdx]
      if (amountRemaining.gte(toBN(order[knownQuantity]))) {
        output.iadd(toBN(order[unknownQuantity]))
      } else {
        output.iadd((toBN(order[unknownQuantity]).mul(amountRemaining)).div(toBN(order[knownQuantity])))
      }
      amountRemaining.isub(toBN(order[knownQuantity]))
      orderIdx += 1
    } catch (e) {
      throw new Error('Not enough liquidity on exchange')
    }
  }
  return output
}
