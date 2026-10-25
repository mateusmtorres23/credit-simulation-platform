import { useState } from 'react'
import { createSimulation } from './api'
import { BankResultCard } from './components/BankResultCard'
import { SimulationForm } from './components/SimulationForm'
import type { SimulationFormValues, SimulationResponse } from './types'
import './App.css'

function App() {
  const [results, setResults] = useState<SimulationResponse | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [operationError, setOperationError] = useState<string | null>(null)

  async function handleSubmit(values: SimulationFormValues) {
    setIsSubmitting(true)
    setResults(null)
    setOperationError(null)

    try {
      const response = await createSimulation(values)
      setResults(response)
    } catch (error) {
      setOperationError(
        error instanceof Error
          ? error.message
          : 'Não foi possível concluir a simulação. Tente novamente.',
      )
      throw error
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="Octafin, página inicial">
          <span className="brand-mark" aria-hidden="true">O</span>
          <span>octafin</span>
        </a>
        <nav aria-label="Navegação principal">
          <a className="nav-link active" href="#simular">Simular</a>
          <span className="nav-link disabled" aria-disabled="true">
            Histórico <span className="nav-badge">indisponível</span>
          </span>
        </nav>
      </header>

      <main id="simular" className="page-content">
        <section className="intro" aria-labelledby="page-title">
          <p className="eyebrow">Simulação de consignado</p>
          <h1 id="page-title">Encontre as condições para o seu empréstimo</h1>
          <p className="intro-text">
            Preencha seus dados para consultar as duas instituições em uma única solicitação.
          </p>
        </section>

        <div className="notice" role="note">
          <span aria-hidden="true">ⓘ</span>
          <p>Use exclusivamente dados fictícios nesta demonstração.</p>
        </div>

        <SimulationForm
          isSubmitting={isSubmitting}
          operationError={operationError}
          onSubmit={handleSubmit}
        />

        {isSubmitting && (
          <p className="status-message" role="status" aria-live="polite">
            <span className="spinner" aria-hidden="true" />
            Consultando as instituições e salvando sua simulação. Aguarde...
          </p>
        )}

        {results && !isSubmitting && (
          <section className="results-section" aria-labelledby="results-title">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Resposta consolidada</p>
                <h2 id="results-title">Resultado da sua simulação</h2>
              </div>
              <p className="history-hint">
                Esta simulação fica disponível no histórico deste navegador por até sete dias.
              </p>
            </div>
            <div className="results-grid">
              {results.results.map((result) => (
                <BankResultCard key={result.bank} result={result} />
              ))}
            </div>
          </section>
        )}
      </main>

      <footer className="site-footer">
        <p>Octafin · Simulação demonstrativa</p>
      </footer>
    </div>
  )
}

export default App
