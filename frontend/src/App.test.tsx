import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const approved = (bank: 'bank_a' | 'bank_b') => ({
  bank, status: 'approved', offer: {
    amount_cents: 100000, term_months: 12, monthly_interest_rate_bps: 199,
    installment_cents: 9500,
  },
})

const baseResponse = {
  id: 'id-1', created_at: '2026-10-25T15:00:00Z',
  results: [approved('bank_a'), approved('bank_b')],
}

afterEach(() => vi.restoreAllMocks())

async function fillForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Nome completo'), 'Pessoa Fictícia')
  await user.type(screen.getByLabelText('E-mail'), 'pessoa@exemplo.com')
  await user.type(screen.getByLabelText('CPF'), '12345678901')
  await user.type(screen.getByLabelText('Renda mensal'), '3.000,00')
  await user.type(screen.getByLabelText('CNPJ do empregador'), '12345678000190')
  await user.type(screen.getByLabelText('Valor solicitado'), '1.000,00')
  await user.type(screen.getByLabelText('Prazo'), '12')
}

describe('simulação', () => {
  it('impede chamada para entrada inválida', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText('Informe seu nome.')).toBeInTheDocument()
  })

  it('valida os limites de nome e e-mail sem restringir caracteres internacionais', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    render(<App />)
    await user.type(screen.getByLabelText('Nome completo'), 'a'.repeat(151))
    await user.type(screen.getByLabelText('E-mail'), 'usuário@exemplo.рф')
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText('O nome deve ter no máximo 150 caracteres.')).toBeInTheDocument()
    expect(screen.queryByText('Informe um e-mail válido.')).not.toBeInTheDocument()
  })

  it('envia e apresenta aprovação na ordem Banco A e Banco B', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(baseResponse), { status: 201 }))
    render(<App />)
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(await screen.findByRole('heading', { name: 'Resultado da sua simulação' })).toBeInTheDocument()
    const headings = screen.getAllByRole('heading', { level: 3 })
    expect(headings.map((heading) => heading.textContent)).toEqual(['Banco A', 'Banco B'])
    expect(screen.getAllByText('R$ 1.000,00')).toHaveLength(2)
    expect(screen.getAllByText('1,99% ao mês')).toHaveLength(2)
  })

  it('apresenta reprovação com mensagem da API, falha parcial e falha total', async () => {
    const user = userEvent.setup()
    const rejected = { bank: 'bank_a', status: 'rejected', reasons: [{ code: 'CUSTOM', message: 'Mensagem normalizada do banco.' }] }
    const failed = { bank: 'bank_b', status: 'failed', error: { code: 'TIMEOUT', message: 'A instituição demorou para responder.' } }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      ...baseResponse, results: [rejected, failed],
    }), { status: 201 }))
    render(<App />)
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(await screen.findByText('Mensagem normalizada do banco.')).toBeInTheDocument()
    expect(screen.getByText('Falha técnica')).toBeInTheDocument()
    expect(screen.getByText('Isso não representa uma reprovação de crédito.')).toBeInTheDocument()
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      ...baseResponse, results: [
        { ...failed, bank: 'bank_a' },
        { ...failed, bank: 'bank_b' },
      ],
    }), { status: 201 }))
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(await screen.findAllByText('Falha técnica')).toHaveLength(2)
  })

  it('impede duplicação por clique e teclado durante o carregamento', async () => {
    const user = userEvent.setup()
    let resolveRequest: (response: Response) => void = () => undefined
    const pending = new Promise<Response>((resolve) => { resolveRequest = resolve })
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(pending)
    render(<App />)
    await fillForm(user)
    const button = screen.getByRole('button', { name: 'Simular empréstimo' })
    await user.click(button)
    expect(screen.getByRole('status')).toHaveTextContent('Consultando')
    await user.click(button)
    await user.click(screen.getByLabelText('Prazo'))
    await user.keyboard('{Enter}')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    resolveRequest(new Response(JSON.stringify(baseResponse), { status: 201 }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Resultado da sua simulação' })).toBeInTheDocument())
  })

  it('remove resultados na nova tentativa e preserva valores e erros de campo', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(baseResponse), { status: 201 }))
    render(<App />)
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(await screen.findByText('Resultado da sua simulação')).toBeInTheDocument()
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({
      error: {
        code: 'VALIDATION_ERROR', message: 'Revise os campos informados.',
        fields: [{ field: 'email', code: 'INVALID_VALUE', message: 'E-mail inválido.' }],
      },
    }), { status: 422 }))
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(screen.queryByText('Resultado da sua simulação')).not.toBeInTheDocument()
    expect(await screen.findByText('E-mail inválido.')).toBeInTheDocument()
    expect(screen.getByLabelText('E-mail')).toHaveValue('pessoa@exemplo.com')
  })
})
