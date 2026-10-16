import { FluentProvider, webDarkTheme, webLightTheme } from '@fluentui/react-components'
import { createRoot } from 'react-dom/client'
import { RetentionNotice } from './components/RetentionNotice'
import './workspace.css'

const light = new URLSearchParams(window.location.search).get('theme') === 'light'
document.documentElement.dataset.theme = light ? 'light' : 'dark'

createRoot(document.getElementById('retention-ui-harness')!).render(
  <FluentProvider theme={light ? webLightTheme : webDarkTheme}>
    <RetentionNotice ownerId="qa-synthetic-owner" />
  </FluentProvider>,
)
