import { afterEach, describe, expect, it, vi } from 'vitest'
import { createSimulation } from './api'
import type { SimulationFormValues } from './types'

const values: SimulationFormValues = {
  name: 'Pessoa Fictícia', email: 'pessoa@exemplo.com', cpf: '123.456.789-01',
  monthlyIncome: '3.000,00', employerCnpj: '12.345.678/0001-90',
  requestedAmount: '1.234,56', termMonths: '24',
  bankAScenario: 'slow', bankBScenario: 'unavailable',
}

const approved = (bank: 'bank_a' | 'bank_b') => ({
  bank, status: 'approved', offer: {
    amount_cents: 123456, term_months: 24, monthly_interest_rate_bps: 199,
    installment_cents: 6500,
  },
})

const response = { id: 'id-1', created_at: '2026-10-25T15:00:00Z', results: [approved('bank_a'), approved('bank_b')] }

afterEach(() => {
  vi.restoreAllMocks()
})

describe('createSimulation', () => {
  it('envia URL, cenários, payload e credenciais', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(response), { status: 201 }))
    await createSimulation(values)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/simulations?bank_a_scenario=slow&bank_b_scenario=unavailable',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({
          name: 'Pessoa Fictícia', email: 'pessoa@exemplo.com', cpf: '12345678901',
          monthly_income_cents: 300000, employer_cnpj: '12345678000190',
          requested_amount_cents: 123456, term_months: 24,
        }),
      }),
    )
  })

  it('retorna sucesso e trata falha de rede', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(response), { status: 201 }))
    await expect(createSimulation(values)).resolves.toEqual(response)
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('network'))
    await expect(createSimulation(values)).rejects.toThrow('Não foi possível conectar à API')
  })

  it('expõe erros públicos e rejeita fields malformado com mensagem genérica', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'VALIDATION_ERROR', message: 'Revise os campos informados.', fields: [{ field: 'email', code: 'INVALID', message: 'E-mail inválido.' }] },
    }), { status: 422 }))
    await expect(createSimulation(values)).rejects.toMatchObject({
      message: 'Revise os campos informados.',
      fields: [{ field: 'email' }],
    })

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'VALIDATION_ERROR', message: 'Revise os campos informados.', fields: [{ field: 'email' }] },
    }), { status: 422 }))
    await expect(createSimulation(values)).rejects.toEqual(expect.objectContaining({
      message: 'A API não conseguiu concluir a simulação. Revise os dados e tente novamente.',
    }))
  })

  it('trata JSON inválido e resposta de sucesso incompatível', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{', { status: 201 }))
    await expect(createSimulation(values)).rejects.toThrow('resposta inesperada')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      ...response, results: [{ ...approved('bank_a'), offer: { ...approved('bank_a').offer, term_months: 0 } }, approved('bank_b')],
    }), { status: 201 }))
    await expect(createSimulation(values)).rejects.toThrow('resposta inesperada')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      ...response, results: [{ ...approved('bank_a'), offer: { ...approved('bank_a').offer, amount_cents: -1 } }, approved('bank_b')],
    }), { status: 201 }))
    await expect(createSimulation(values)).rejects.toThrow('resposta inesperada')
  })

  it('não aceita payload monetário inválido mesmo fora do formulário', async () => {
    const invalid = { ...values, requestedAmount: '1 2,34' }
    await expect(createSimulation(invalid)).rejects.toThrow('valores monetários válidos')
  })
})
