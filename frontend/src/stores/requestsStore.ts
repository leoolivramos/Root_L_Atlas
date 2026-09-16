// stores/requestsStore.ts — Status de todas as requisições assíncronas
import { defineStore } from 'pinia'
import { ref, computed, readonly } from 'vue'
import type { RequestState } from '@/types/atlas'

type RequestKey =
  | 'feature_detail'
  | 'accessibility'
  | 'search'
  | 'municipio_summary'

export const useRequestsStore = defineStore('requests', () => {
  const states = ref<Record<RequestKey, RequestState>>({
    feature_detail: { status: 'idle' },
    accessibility: { status: 'idle' },
    search: { status: 'idle' },
    municipio_summary: { status: 'idle' },
  })

  const isAnyLoading = computed(() =>
    Object.values(states.value).some((s) => s.status === 'loading')
  )

  const hasAnyError = computed(() =>
    Object.values(states.value).some((s) => s.status === 'error')
  )

  function setLoading(key: RequestKey) {
    states.value[key] = { status: 'loading', timestamp: Date.now() }
  }

  function setSuccess(key: RequestKey) {
    states.value[key] = { status: 'success', timestamp: Date.now() }
  }

  function setError(key: RequestKey, error: string) {
    states.value[key] = { status: 'error', error, timestamp: Date.now() }
  }

  function reset(key: RequestKey) {
    states.value[key] = { status: 'idle' }
  }

  function getState(key: RequestKey): RequestState {
    return states.value[key]
  }

  return {
    states: readonly(states),
    isAnyLoading,
    hasAnyError,
    setLoading,
    setSuccess,
    setError,
    reset,
    getState,
  }
})
