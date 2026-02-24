<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import Message from 'primevue/message'

const API = import.meta.env.VITE_API_URL ?? ''

interface AppConfig {
  dias_para_apelar: number
}

const config = ref<AppConfig>({ dias_para_apelar: 5 })
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const successMsg = ref('')

async function loadConfig() {
  loading.value = true
  error.value = ''
  try {
    const r = await fetch(`${API}/api/configuracion`)
    if (!r.ok) throw new Error('No se pudo cargar la configuración')
    const data: AppConfig = await r.json()
    config.value = { dias_para_apelar: data.dias_para_apelar ?? 5 }
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  error.value = ''
  successMsg.value = ''
  try {
    const r = await fetch(`${API}/api/configuracion`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dias_para_apelar: config.value.dias_para_apelar })
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error((err as { detail?: string }).detail || 'Error al guardar')
    }
    successMsg.value = 'Configuración guardada correctamente.'
    setTimeout(() => { successMsg.value = '' }, 3000)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

onMounted(loadConfig)
</script>

<template>
  <div class="configuracion-view">
    <Card>
      <template #title>
        <span><i class="pi pi-sliders-h mr-2"></i>Configuración</span>
      </template>
      <template #subtitle>
        Parámetros generales de la aplicación.
      </template>
      <template #content>
        <Message v-if="error" severity="error" class="mb-3">{{ error }}</Message>
        <Message v-if="successMsg" severity="success" class="mb-3">{{ successMsg }}</Message>

        <div v-if="loading" class="flex align-items-center gap-2 text-color-secondary">
          <i class="pi pi-spin pi-spinner"></i> Cargando configuración…
        </div>

        <div v-else class="config-sections">

          <!-- ── Sección: Apelaciones ── -->
          <div class="config-section">
            <h3 class="config-section-title">
              <i class="pi pi-send mr-2"></i>Apelaciones
            </h3>

            <div class="config-row">
              <div class="config-label">
                <span class="font-semibold">Días para apelar</span>
                <p class="config-desc">
                  Número de días que tiene una sede para apelar un pedido desde que el admin lo marca.
                  Pasado este plazo, el pedido pasa automáticamente al apartado
                  <strong>Descuentos</strong> con la etiqueta <em>Plazo vencido</em>
                  y la sede ya no puede apelarlo.
                </p>
              </div>
              <div class="config-input">
                <InputNumber
                  v-model="config.dias_para_apelar"
                  :min="1"
                  :max="60"
                  :show-buttons="true"
                  button-layout="stacked"
                  suffix=" días"
                  class="dias-input"
                />
              </div>
            </div>
          </div>

        </div>

        <div class="mt-4">
          <Button
            label="Guardar configuración"
            icon="pi pi-save"
            :loading="saving"
            :disabled="loading"
            @click="saveConfig"
          />
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.configuracion-view {
  padding: 0.5rem;
  max-width: 700px;
  margin: 0 auto;
}

.config-sections {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.config-section {
  border: 1px solid var(--p-surface-200);
  border-radius: 8px;
  overflow: hidden;
}

.config-section-title {
  margin: 0;
  padding: 0.6rem 1rem;
  font-size: 0.95rem;
  font-weight: 600;
  background: var(--p-surface-50);
  border-bottom: 1px solid var(--p-surface-200);
  color: var(--p-text-color);
}

.config-row {
  display: flex;
  align-items: flex-start;
  gap: 1.5rem;
  padding: 1rem;
  flex-wrap: wrap;
}

.config-label {
  flex: 1;
  min-width: 200px;
}

.config-desc {
  margin: 0.3rem 0 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
  line-height: 1.5;
}

.config-input {
  display: flex;
  align-items: center;
  padding-top: 0.1rem;
  flex-shrink: 0;
}

.dias-input {
  width: 130px;
}

:deep(.dias-input .p-inputnumber-input) {
  width: 100%;
  min-width: 0;
  text-align: center;
}
</style>

<style>
.app-dark .config-section {
  border-color: var(--p-surface-700) !important;
}
.app-dark .config-section-title {
  background: var(--p-surface-800) !important;
  border-color: var(--p-surface-700) !important;
}
</style>
