import { ref } from 'vue'
import { defineStore } from 'pinia'

export type Role = 'user' | 'admin'

/** Rol solo en memoria; se toma siempre de la URL en cada navegación (no se persiste). */
export const useRoleStore = defineStore('role', () => {
  const role = ref<Role | null>(null)

  function setRole(r: Role | null) {
    role.value = r
  }

  const isUser = () => role.value === 'user'
  const isAdmin = () => role.value === 'admin'
  const hasRole = () => role.value !== null

  return { role, setRole, isUser, isAdmin, hasRole }
})
