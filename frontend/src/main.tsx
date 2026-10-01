import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './legacy-surface-recovery.css'
import './styles.css'
import '@fontsource/be-vietnam-pro/400.css'
import '@fontsource/be-vietnam-pro/500.css'
import '@fontsource/be-vietnam-pro/600.css'
import './workspace.css'
import './mascot-restore.css'
import './theme-polish.css'
import './release-canvas.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
