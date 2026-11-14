import { Component } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/inter'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App.jsx'

// Whatever goes wrong in the page, the reader gets a way back instead of a blank screen.
class Guard extends Component {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? (
      <main className="page">
        <p className="error" role="alert">
          This view could not be shown.{' '}
          <a
            className="link"
            href="./"
            onClick={() => {
              location.hash = ''
            }}
          >
            Back to the world
          </a>
        </p>
      </main>
    ) : (
      this.props.children
    )
  }
}

createRoot(document.getElementById('root')).render(
  <Guard>
    <App />
  </Guard>,
)
