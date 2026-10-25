import { describe, expect, it } from 'vitest'
import { formatMoney } from './formatting'

describe('formatMoney', () => {
  it.each([
    [1, 'R$\u00a00,01'],
    [10, 'R$\u00a00,10'],
    [99, 'R$\u00a00,99'],
    [100, 'R$\u00a01,00'],
    [101, 'R$\u00a01,01'],
    [9340, 'R$\u00a093,40'],
    [123456, 'R$\u00a01.234,56'],
    [9007199254740990, 'R$\u00a090.071.992.547.409,90'],
    [9007199254740991, 'R$\u00a090.071.992.547.409,91'],
  ])('formats %s cents without losing precision', (cents, expected) => {
    expect(formatMoney(cents)).toBe(expected)
  })
})
