import { describe, expect, it } from 'vitest'
import { moneyToCents, MAX_SAFE_INTEGER } from './money'

describe('moneyToCents', () => {
  it.each([
    ['1', 100],
    ['1,2', 120],
    ['1,23', 123],
    ['1.234,56', 123456],
    ['123.456.789,01', 12345678901],
    ['  R$ não é aceito', null],
  ])('converte valores brasileiros: %s', (input, expected) => {
    expect(moneyToCents(input)).toBe(expected)
  })

  it('aceita o limite seguro e rejeita o primeiro valor acima', () => {
    expect(moneyToCents('90.071.992.547.409,91')).toBe(MAX_SAFE_INTEGER)
    expect(moneyToCents('90.071.992.547.409,92')).toBeNull()
  })

  it.each(['1 2,34', '1.23', '1,234', '-1,00', '+1,00', '1,,00', '1.2.34,00', '1.000,000'])(
    'rejeita formato inválido: %s',
    (input) => expect(moneyToCents(input)).toBeNull(),
  )

  it('permite apenas espaços externos', () => {
    expect(moneyToCents('  1.234,56  ')).toBe(123456)
  })
})
