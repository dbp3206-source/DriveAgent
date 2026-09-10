import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import '@fontsource/be-vietnam-pro/400.css'
import '@fontsource/be-vietnam-pro/500.css'
import '@fontsource/be-vietnam-pro/600.css'
import './workspace.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
