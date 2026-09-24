import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import './shared/estilos.css'
import './shared/interfaz.css'

import App from './App.jsx'

createRoot(document.getElementById('raiz')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
