import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { applyBrand } from './config/brand'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { installGlobalErrorHandlers } from './utils/errorReporting'

applyBrand()
installGlobalErrorHandlers()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary fullPage>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
