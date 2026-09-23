import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import './shared/estilos.css'

import Lectura from './lectura/Lectura.jsx'

createRoot(document.getElementById('raiz')).render(
  <StrictMode>
    <Lectura />
  </StrictMode>,
)
