<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="atlas-icon"
    :class="customClass"
    aria-hidden="true"
  >
    <!-- Busca -->
    <template v-if="name === 'search'">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </template>

    <!-- Fechar / Limpar -->
    <template v-else-if="name === 'close'">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </template>

    <!-- Camadas -->
    <template v-else-if="name === 'layers'">
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </template>

    <!-- Filtros / Sliders -->
    <template v-else-if="name === 'filter'">
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </template>

    <!-- Foco / Centralizar / Reset -->
    <template v-else-if="name === 'home' || name === 'reset' || name === 'target'">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="2" x2="12" y2="6" />
      <line x1="12" y1="18" x2="12" y2="22" />
      <line x1="2" y1="12" x2="6" y2="12" />
      <line x1="18" y1="12" x2="22" y2="12" />
      <circle cx="12" cy="12" r="3" />
    </template>

    <!-- 3D / Cubo -->
    <template v-else-if="name === 'cube' || name === '3d'">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </template>

    <!-- Município / Território / Edifício público -->
    <template v-else-if="name === 'municipio' || name === 'landmark'">
      <path d="M3 21h18" />
      <path d="M5 21V9l7-5 7 5v12" />
      <path d="M9 14h6" />
      <path d="M12 11v6" />
    </template>

    <!-- Escola / Educação -->
    <template v-else-if="name === 'escola' || name === 'education'">
      <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
      <path d="M6 12v5c3 3 9 3 12 0v-5" />
    </template>

    <!-- Setor Censitário / Análise / Gráfico -->
    <template v-else-if="name === 'setor' || name === 'chart'">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18" />
      <path d="M9 21V9" />
    </template>

    <!-- Saúde -->
    <template v-else-if="name === 'saude' || name === 'health'">
      <path d="M12 6v12M6 12h12" />
      <circle cx="12" cy="12" r="9" />
    </template>

    <!-- Pin / Localização -->
    <template v-else-if="name === 'pin'">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </template>

    <!-- Link externo -->
    <template v-else-if="name === 'external'">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </template>

    <!-- Mapa / Estilo de Basemap -->
    <template v-else-if="name === 'map'">
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </template>

    <!-- Chevron -->
    <template v-else-if="name === 'chevron-left'">
      <polyline points="15 18 9 12 15 6" />
    </template>
    <template v-else-if="name === 'chevron-right'">
      <polyline points="9 18 15 12 9 6" />
    </template>
    <template v-else-if="name === 'chevron-down'">
      <polyline points="6 9 12 15 18 9" />
    </template>

    <!-- Documento / Linhagem -->
    <template v-else-if="name === 'document' || name === 'lineage'">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </template>

    <!-- Escudo / Segurança -->
    <template v-else-if="name === 'shield'">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </template>

    <!-- Malha Viária / Estrada -->
    <template v-else-if="name === 'viaria' || name === 'road'">
      <line x1="4" y1="21" x2="8" y2="3" />
      <line x1="20" y1="21" x2="16" y2="3" />
      <line x1="12" y1="5" x2="12" y2="9" />
      <line x1="12" y1="13" x2="12" y2="17" />
    </template>

    <!-- Fallback -->
    <template v-else>
      <circle cx="12" cy="12" r="8" />
    </template>
  </svg>
</template>

<script setup lang="ts">
export type IconName =
  | 'search'
  | 'close'
  | 'layers'
  | 'filter'
  | 'home'
  | 'reset'
  | 'target'
  | 'cube'
  | '3d'
  | 'municipio'
  | 'landmark'
  | 'escola'
  | 'education'
  | 'setor'
  | 'chart'
  | 'saude'
  | 'health'
  | 'shield'
  | 'viaria'
  | 'road'
  | 'pin'
  | 'external'
  | 'map'
  | 'chevron-left'
  | 'chevron-right'
  | 'chevron-down'
  | 'document'
  | 'lineage'

withDefaults(
  defineProps<{
    name: IconName
    size?: number | string
    customClass?: string
  }>(),
  {
    size: 16,
    customClass: '',
  }
)
</script>

<style scoped>
.atlas-icon {
  display: inline-block;
  vertical-align: middle;
  flex-shrink: 0;
}
</style>
