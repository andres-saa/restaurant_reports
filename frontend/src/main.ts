import 'primeicons/primeicons.css'
import 'primeflex/primeflex.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

import App from './App.vue'
import router from './router'

const PRIMARY = 'rgb(255, 98, 0)'
// Paleta completa para que light y dark usen naranja (Aura en dark usa primary.400, primary.300, etc.)
const primaryPalette = {
  50: 'rgb(255, 247, 237)',
  100: 'rgb(255, 237, 213)',
  200: 'rgb(254, 215, 170)',
  300: 'rgb(253, 186, 116)',
  400: 'rgb(251, 146, 60)',
  500: PRIMARY,
  600: 'rgb(230, 88, 0)',
  700: 'rgb(204, 78, 0)',
  800: 'rgb(166, 62, 0)',
  900: 'rgb(127, 47, 0)',
  950: 'rgb(69, 26, 0)'
}

const themePreset = definePreset(Aura, {
  semantic: {
    primary: primaryPalette
  }
})

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ConfirmationService)
app.use(PrimeVue, {
  theme: {
    preset: themePreset,
    options: {
      darkModeSelector: '.app-dark'
    }
  }
})

app.mount('#app')
