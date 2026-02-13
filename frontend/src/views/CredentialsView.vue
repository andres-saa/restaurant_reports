<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Divider from 'primevue/divider'

const API = import.meta.env.VITE_API_URL ?? ''

interface Credentials {
  usuario_nick?: string
  usuario_clave?: string
  usuario_recordar?: string
  local_id?: string
  turno_id?: string
  caja_id?: string
  app?: string
}

const credentials = ref<Credentials>({})
const loading = ref(false)
const error = ref('')
const loginLog = ref<Array<{ step: string; message: string; success?: boolean; time: string }>>([])
const updating = ref(false)

function formatTime() {
  return new Date().toLocaleTimeString('es', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

async function loadCredentials() {
  loading.value = true
  error.value = ''
  try {
    const r = await fetch(`${API}/credentials`)
    const contentType = r.headers.get('content-type') || ''
    if (!contentType.includes('application/json')) {
      const text = await r.text()
      if (text.trimStart().startsWith('<!') || text.trimStart().startsWith('<')) {
        throw new Error('El servidor devolvió HTML en lugar de JSON. ¿Está el backend en marcha (uvicorn)? Configura el proxy en vite.config para /credentials.')
      }
      throw new Error(r.statusText || 'Respuesta no JSON')
    }
    if (!r.ok) throw new Error(r.statusText)
    const data = await r.json()
    credentials.value = data
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No se pudieron cargar las credenciales'
    credentials.value = {}
  } finally {
    loading.value = false
  }
}

const form = ref<Credentials>({
  usuario_nick: '',
  usuario_clave: '',
  usuario_recordar: '1',
  local_id: '1',
  turno_id: '1',
  caja_id: '29',
  app: 'Web',
})

function fillFormFromCurrent() {
  if (credentials.value.usuario_nick) form.value.usuario_nick = credentials.value.usuario_nick
  if (credentials.value.usuario_recordar) form.value.usuario_recordar = credentials.value.usuario_recordar
  if (credentials.value.local_id) form.value.local_id = credentials.value.local_id
  if (credentials.value.turno_id) form.value.turno_id = credentials.value.turno_id
  if (credentials.value.caja_id) form.value.caja_id = credentials.value.caja_id
  if (credentials.value.app) form.value.app = credentials.value.app
  form.value.usuario_clave = ''
}

/** Guarda credenciales y hace login por formulario (navegador). */
async function updateAndLoginByForm() {
  const payload: Credentials = {}
  if (form.value.usuario_nick) payload.usuario_nick = form.value.usuario_nick
  if (form.value.usuario_clave) payload.usuario_clave = form.value.usuario_clave
  if (form.value.usuario_recordar) payload.usuario_recordar = form.value.usuario_recordar
  if (form.value.local_id) payload.local_id = form.value.local_id
  if (form.value.turno_id) payload.turno_id = form.value.turno_id
  if (form.value.caja_id) payload.caja_id = form.value.caja_id
  if (form.value.app) payload.app = form.value.app
  if (!Object.keys(payload).length) {
    error.value = 'Indica al menos usuario y clave.'
    return
  }
  error.value = ''
  loginLog.value = []
  updating.value = true
  loginLog.value.push({
    step: 'info',
    message: 'Guardando credenciales...',
    time: formatTime(),
  })
  try {
    const putRes = await fetch(`${API}/credentials`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const putOk = putRes.ok
    if (!putOk) {
      const putData = await putRes.json().catch(() => ({}))
      throw new Error((putData.detail as string) || putRes.statusText)
    }
    loginLog.value.push({
      step: 'info',
      message: 'Credenciales guardadas. Iniciando login por formulario (navegador)...',
      time: formatTime(),
    })
    const r = await fetch(`${API}/login?method=form`, { method: 'POST' })
    const contentType = r.headers.get('content-type') || ''
    let data: Record<string, unknown> = {}
    if (contentType.includes('application/json')) {
      data = await r.json().catch(() => ({}))
    }
    const success = data.success === true && !(data as { _is_error?: boolean })._is_error
    const msg = (data.message as string) || (r.ok ? 'Listo' : r.statusText)
    loginLog.value.push({
      step: success ? 'done' : 'error',
      message: msg,
      success,
      time: formatTime(),
    })
    if (success) await loadCredentials()
    if (!success) error.value = msg
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Error'
    error.value = msg
    loginLog.value.push({ step: 'error', message: msg, success: false, time: formatTime() })
  } finally {
    updating.value = false
  }
}

onMounted(() => {
  loadCredentials().then(() => fillFormFromCurrent())
})
</script>

<template>
  <div class="credentials-page">
    <div class="credentials-header">
      <h1 class="credentials-page-title">Credenciales de acceso</h1>
      <p class="credentials-page-subtitle">
        Actualiza usuario y clave; al guardar se hará login por formulario (navegador en segundo plano).
      </p>
    </div>

    <Message v-if="error" severity="error" class="credentials-error" @close="error = ''">
      {{ error }}
    </Message>

    <!-- Credenciales actuales -->
    <Card v-if="credentials.usuario_nick || loading" class="credentials-block credentials-current">
      <template #title>
        <span class="block-title">
          <i class="pi pi-lock block-title-icon"></i>
          Credenciales actuales
        </span>
      </template>
      <template #content>
        <div v-if="loading" class="credentials-loading">
          <ProgressSpinner style="width: 1.75rem; height: 1.75rem" strokeWidth="4" />
          <span>Cargando credenciales...</span>
        </div>
        <div v-else-if="credentials.usuario_nick" class="credentials-readonly">
          <div class="cred-row">
            <span class="cred-label">Usuario</span>
            <span class="cred-value">{{ credentials.usuario_nick }}</span>
          </div>
          <div class="cred-row">
            <span class="cred-label">Clave</span>
            <span class="cred-value cred-masked">{{ credentials.usuario_clave || '********' }}</span>
          </div>
          <div class="cred-row cred-row-minor">
            <span class="cred-label">Recordar</span>
            <span class="cred-value">{{ credentials.usuario_recordar ?? '—' }}</span>
          </div>
          <div class="cred-row cred-row-minor">
            <span class="cred-label">Local ID</span>
            <span class="cred-value">{{ credentials.local_id ?? '—' }}</span>
          </div>
          <div class="cred-row cred-row-minor">
            <span class="cred-label">Turno ID</span>
            <span class="cred-value">{{ credentials.turno_id ?? '—' }}</span>
          </div>
          <div class="cred-row cred-row-minor">
            <span class="cred-label">Caja ID</span>
            <span class="cred-value">{{ credentials.caja_id ?? '—' }}</span>
          </div>
          <div class="cred-row cred-row-minor">
            <span class="cred-label">App</span>
            <span class="cred-value">{{ credentials.app ?? '—' }}</span>
          </div>
        </div>
        <p v-else class="cred-empty-hint">Aún no hay credenciales guardadas. Usa el formulario de abajo.</p>
      </template>
    </Card>

    <!-- Formulario para actualizar -->
    <Card class="credentials-block credentials-form">
      <template #title>
        <span class="block-title">
          <i class="pi pi-pencil block-title-icon"></i>
          Actualizar credenciales
        </span>
      </template>
      <template #content>
        <div class="form-grid">
          <div class="field field-main">
            <label for="usuario_nick">Usuario</label>
            <InputText
              id="usuario_nick"
              v-model="form.usuario_nick"
              placeholder="ej. usuario@correo.com"
              autocomplete="off"
            />
          </div>
          <div class="field field-main">
            <label for="usuario_clave">Clave <span class="field-hint">(dejar en blanco para no cambiar)</span></label>
            <InputText
              id="usuario_clave"
              v-model="form.usuario_clave"
              type="password"
              placeholder="••••••••"
              autocomplete="new-password"
            />
          </div>
          <Divider align="left" type="dashed" class="form-divider">
            <span class="text-sm text-color-secondary">Opcionales</span>
          </Divider>
          <div class="field field-opt">
            <label for="local_id">Local ID</label>
            <InputText id="local_id" v-model="form.local_id" placeholder="1" />
          </div>
          <div class="field field-opt">
            <label for="turno_id">Turno ID</label>
            <InputText id="turno_id" v-model="form.turno_id" placeholder="1" />
          </div>
          <div class="field field-opt">
            <label for="caja_id">Caja ID</label>
            <InputText id="caja_id" v-model="form.caja_id" placeholder="29" />
          </div>
        </div>
        <div class="form-actions">
          <Button
            label="Actualizar credenciales y probar login"
            icon="pi pi-refresh"
            iconPos="left"
            :loading="updating"
            :disabled="updating"
            class="btn-update"
            @click="updateAndLoginByForm"
          />
        </div>
      </template>
    </Card>

    <!-- Log en tiempo real -->
    <Card class="credentials-block login-log">
      <template #title>
        <span class="block-title">
          <i class="pi pi-list block-title-icon"></i>
          Resultado del login
        </span>
      </template>
      <template #content>
        <div class="log-list">
          <div v-if="!loginLog.length" class="log-empty">
            <i class="pi pi-info-circle"></i>
            Al pulsar «Actualizar credenciales y probar login» aquí aparecerá el progreso.
          </div>
          <div
            v-for="(entry, i) in loginLog"
            :key="i"
            class="log-entry"
            :class="{
              'log-entry-success': entry.success === true,
              'log-entry-error': entry.success === false,
            }"
          >
            <span class="log-time">{{ entry.time }}</span>
            <span class="log-message">{{ entry.message }}</span>
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.credentials-page {
  padding: 1.25rem 1rem 2rem;
  max-width: 560px;
  margin: 0 auto;
}

.credentials-header {
  margin-bottom: 1.5rem;
}

.credentials-page-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 0.35rem 0;
  color: var(--p-text-color);
  letter-spacing: -0.02em;
}

.credentials-page-subtitle {
  font-size: 0.9375rem;
  color: var(--p-text-muted-color);
  margin: 0;
  line-height: 1.45;
}

.credentials-error {
  margin-bottom: 1.25rem;
}

.credentials-block {
  margin-bottom: 1.25rem;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
}

.credentials-block :deep(.p-card-title) {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
}

.credentials-block :deep(.p-card-content) {
  padding-top: 0.5rem;
}

.block-title {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.block-title-icon {
  font-size: 1rem;
  color: var(--p-primary-color);
  opacity: 0.9;
}

/* Credenciales actuales (solo lectura) */
.credentials-current :deep(.p-card-header) {
  background: linear-gradient(to bottom, var(--p-content-surface-100), var(--p-content-surface-50));
  border-bottom: 1px solid var(--p-content-border-color);
}

.credentials-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0;
  color: var(--p-text-muted-color);
  font-size: 0.9375rem;
}

.credentials-readonly {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.cred-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  margin-bottom: 0.25rem;
  background: var(--p-content-surface-50);
  border: 1px solid var(--p-content-border-color);
}

.cred-row:last-of-type {
  margin-bottom: 0;
}

.cred-row-minor {
  background: transparent;
  padding: 0.4rem 0.75rem;
  border-color: transparent;
}

.cred-label {
  flex: 0 0 100px;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--p-text-muted-color);
}

.cred-value {
  flex: 1;
  font-size: 0.9375rem;
  color: var(--p-text-color);
  word-break: break-all;
}

.cred-masked {
  font-family: ui-monospace, monospace;
  letter-spacing: 0.08em;
}

.cred-empty-hint {
  color: var(--p-text-muted-color);
  font-size: 0.9375rem;
  margin: 0;
  padding: 0.5rem 0;
}

/* Formulario */
.credentials-form .form-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-divider {
  margin: 0.5rem 0 0.75rem;
}

.form-divider :deep(.p-divider-content) {
  background: var(--p-content-background);
}

.field label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: 0.35rem;
  color: var(--p-text-color);
}

.field-hint {
  font-weight: 400;
  color: var(--p-text-muted-color);
}

.field-main {
  width: 100%;
  max-width: 100%;
}

.credentials-form .field-main :deep(.p-inputtext) {
  width: 100%;
  box-sizing: border-box;
}

.field-opt {
  max-width: 160px;
}

.form-actions {
  margin-top: 1.25rem;
  padding-top: 0.25rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.btn-update {
  min-width: 220px;
}

/* Log */
.log-list {
  max-height: 240px;
  overflow-y: auto;
  border-radius: 10px;
  padding: 0.5rem;
  background: var(--p-content-surface-100);
  border: 1px solid var(--p-content-border-color);
  font-family: ui-monospace, 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.8125rem;
}

.log-empty {
  color: var(--p-text-muted-color);
  padding: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.log-empty .pi {
  flex-shrink: 0;
  opacity: 0.7;
}

.log-entry {
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  display: flex;
  gap: 0.75rem;
  align-items: baseline;
  margin-bottom: 0.2rem;
  transition: background 0.15s ease;
}

.log-entry:last-child {
  margin-bottom: 0;
}

.log-time {
  flex-shrink: 0;
  color: var(--p-text-muted-color);
  font-variant-numeric: tabular-nums;
}

.log-message {
  flex: 1;
  word-break: break-word;
}

.log-entry-success {
  background: rgba(34, 197, 94, 0.12);
  color: var(--p-green-800);
}

.app-dark .log-entry-success {
  background: rgba(34, 197, 94, 0.18);
  color: var(--p-green-300);
}

.log-entry-error {
  background: rgba(239, 68, 68, 0.12);
  color: var(--p-red-800);
}

.app-dark .log-entry-error {
  background: rgba(239, 68, 68, 0.18);
  color: var(--p-red-300);
}

@media (min-width: 480px) {
  .credentials-form .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem 1.25rem;
  }
  .field-main {
    grid-column: 1 / -1;
  }
  .form-divider {
    grid-column: 1 / -1;
  }
  .field-opt {
    max-width: none;
  }
}
</style>
