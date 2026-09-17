<template>
  <div class="search-bar" :class="{ 'search-bar--active': focused }">
    <div class="search-bar__input-wrapper">
      <AtlasIcon name="search" :size="16" custom-class="search-bar__search-icon" />

      <input
        ref="inputRef"
        v-model="query"
        type="search"
        placeholder="..."
        class="search-bar__input"
        autocomplete="off"
        @focus="focused = true"
        @blur="handleBlur"
        @input="onInput"
        @keydown.esc="clearSearch"
        @keydown.enter="selectFirst"
        @keydown.down.prevent="navigateDown"
        @keydown.up.prevent="navigateUp"
        :aria-label="'Buscar no mapa'"
        :aria-expanded="showResults"
        aria-haspopup="listbox"
        role="combobox"
      />

      <button
        v-if="query"
        class="search-bar__clear"
        @click="clearSearch"
        aria-label="Limpar busca"
        title="Limpar busca"
      >
        <AtlasIcon name="close" :size="14" />
      </button>

      <!-- Status de carregamento -->
      <div v-if="requestsStore.getState('search').status === 'loading'" class="search-bar__spinner" />
    </div>

    <!-- Resultados -->
    <transition name="dropdown">
      <div v-if="showResults && results.length > 0" class="search-results" role="listbox">
        <div
          v-for="(result, idx) in results"
          :key="`${result.tipo}-${result.id}`"
          class="search-result-item"
          :class="{ 'search-result-item--selected': idx === selectedIdx }"
          role="option"
          :aria-selected="idx === selectedIdx"
          @mousedown.prevent="selectResult(result)"
        >
          <div class="search-result-item__icon-wrapper" :class="`icon--${result.tipo}`">
            <AtlasIcon :name="tipoIcon(result.tipo)" :size="15" />
          </div>

          <div class="search-result-item__info">
            <p class="search-result-item__name">{{ result.nome }}</p>
            <p v-if="result.municipio || result.rede" class="search-result-item__sub">
              {{ result.municipio }}{{ result.municipio && result.rede ? ' · ' : '' }}{{ result.rede }}
            </p>
          </div>

          <span class="search-result-item__tipo-badge" :class="`badge--${result.tipo}`">
            {{ tipoLabel(result.tipo) }}
          </span>
        </div>
      </div>
    </transition>

    <div
      v-if="showResults && query.length >= 2 && results.length === 0 && requestsStore.getState('search').status !== 'loading'"
      class="search-no-results"
    >
      Nenhum resultado encontrado para "{{ query }}"
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import axios from 'axios'
import type { SearchResult } from '@/types/atlas'
import { useMapStore } from '@/stores/mapStore'
import { useRequestsStore } from '@/stores/requestsStore'
import AtlasIcon, { type IconName } from '@/components/AtlasIcon.vue'

const emit = defineEmits<{ select: [result: SearchResult] }>()

const mapStore = useMapStore()
const requestsStore = useRequestsStore()

const inputRef = ref<HTMLInputElement | null>(null)
const query = ref('')
const results = ref<SearchResult[]>([])
const focused = ref(false)
const selectedIdx = ref(-1)

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const showResults = computed(() => focused.value && query.value.length >= 2)

let searchTimer: ReturnType<typeof setTimeout> | null = null

function onInput() {
  selectedIdx.value = -1
  if (searchTimer) clearTimeout(searchTimer)
  if (query.value.length < 2) {
    results.value = []
    return
  }
  searchTimer = setTimeout(doSearch, 300)
}

async function doSearch() {
  requestsStore.setLoading('search')
  try {
    const { data } = await axios.get(`${API}/search`, {
      params: { q: query.value, limit: 12 },
    })
    results.value = data.results ?? []
    requestsStore.setSuccess('search')
  } catch {
    results.value = []
    requestsStore.setError('search', 'Erro na busca')
  }
}

function selectResult(result: SearchResult) {
  query.value = result.nome
  results.value = []
  focused.value = false
  // Ajusta viewport para a área do resultado
  mapStore.fitBounds([result.xmin, result.ymin, result.xmax, result.ymax])
  emit('select', result)
}

function selectFirst() {
  if (results.value.length > 0) {
    const chosen = selectedIdx.value >= 0 ? results.value[selectedIdx.value] : results.value[0]
    selectResult(chosen)
  }
}

function navigateDown() {
  if (results.value.length === 0) return
  selectedIdx.value = (selectedIdx.value + 1) % results.value.length
}

function navigateUp() {
  if (results.value.length === 0) return
  selectedIdx.value = selectedIdx.value <= 0 ? results.value.length - 1 : selectedIdx.value - 1
}

function clearSearch() {
  query.value = ''
  results.value = []
  selectedIdx.value = -1
  inputRef.value?.focus()
}

function handleBlur() {
  setTimeout(() => { focused.value = false }, 180)
}

function tipoIcon(tipo: string): IconName {
  if (tipo === 'municipio') return 'municipio'
  if (tipo === 'escola') return 'escola'
  if (tipo === 'setor') return 'setor'
  if (tipo === 'saude') return 'saude'
  return 'pin'
}

function tipoLabel(tipo: string): string {
  const map: Record<string, string> = {
    municipio: 'Município',
    escola: 'Escola',
    setor: 'Setor Censitário',
    saude: 'Saúde',
  }
  return map[tipo] ?? tipo
}
</script>

<style scoped>
.search-bar {
  position: relative;
  width: 360px;
  max-width: 90vw;
  transition: width 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.search-bar--active {
  width: 440px;
}

.search-bar__input-wrapper {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(12px);
  border: 1px solid #cbd5e1;
  border-radius: 9999px;
  padding: 0.5rem 0.9rem;
  gap: 0.6rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.2s ease;
}

.search-bar--active .search-bar__input-wrapper {
  border-color: #2563eb;
  background: #ffffff;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.15), 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.search-bar__search-icon {
  color: #64748b;
  flex-shrink: 0;
}

.search-bar__input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: #0f172a;
  font-size: 0.875rem;
  font-family: inherit;
  font-weight: 500;
}

.search-bar__input::placeholder {
  color: #94a3b8;
  font-weight: 400;
}

.search-bar__clear {
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  border-radius: 50%;
  transition: color 0.15s;
}

.search-bar__clear:hover {
  color: #0f172a;
}

.search-bar__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

.search-results {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(16px);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  z-index: 50;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.12);
}

.search-result-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0.9rem;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid #f8fafc;
}

.search-result-item:last-child {
  border-bottom: none;
}

.search-result-item:hover,
.search-result-item--selected {
  background: #f1f5f9;
}

.search-result-item__icon-wrapper {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  color: #475569;
  flex-shrink: 0;
}

.icon--municipio { background: #eff6ff; color: #2563eb; }
.icon--escola { background: #fef3c7; color: #d97706; }
.icon--setor { background: #f3e8ff; color: #9333ea; }
.icon--saude { background: #fee2e2; color: #dc2626; }

.search-result-item__info {
  flex: 1;
  min-width: 0;
}

.search-result-item__name {
  font-size: 0.85rem;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.search-result-item__sub {
  font-size: 0.72rem;
  color: #64748b;
  margin: 0.1rem 0 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.search-result-item__tipo-badge {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  flex-shrink: 0;
  background: #f1f5f9;
  color: #475569;
}

.badge--municipio { background: #eff6ff; color: #2563eb; }
.badge--escola { background: #fef3c7; color: #b45309; }
.badge--setor { background: #f3e8ff; color: #7e22ce; }
.badge--saude { background: #fee2e2; color: #b91c1c; }

.search-no-results {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0.85rem 1rem;
  font-size: 0.8rem;
  color: #64748b;
  text-align: center;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08);
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
