import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// base './': the built site works from any folder (GitHub Pages project sites included)
export default defineConfig({ base: './', plugins: [react()] })
