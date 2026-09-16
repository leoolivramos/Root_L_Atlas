// stores/filtersStore.ts — Filtros analíticos (limiares de acessibilidade, rede e segurança pública SINESP)
import { defineStore } from 'pinia'
import { ref, readonly } from 'vue'
import axios from 'axios'

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type DependenciaRede = 'todas' | 'publica' | 'federal' | 'estadual' | 'municipal' | 'privada'
export type SegurancaMetrica = 'ocorrencias' | 'vitimas'
export type FilterTab = 'seguranca' | 'acessibilidade'

export const useFiltersStore = defineStore('filters', () => {
  // Aba ativa no painel de filtros
  const activeTab = ref<FilterTab>('seguranca')

  // ─── Filtros de Segurança Pública (SINESP Heatmap) ─────────────────────────
  const segurancaMetrica = ref<SegurancaMetrica>('ocorrencias')
  const segurancaAno = ref<number | null>(2024)
  const segurancaTipoCrime = ref<string>('todos')
  const segurancaMes = ref<number | null>(null)

  // Metadados dinâmicos carregados da API
  const disponiveisAnos = ref<number[]>([2024, 2023])
  const disponiveisTiposCrime = ref<string[]>([])
  const disponiveisCrimesTotais = ref<Array<{ tipo_crime: string; total: number }>>([])
  const filtrosLoaded = ref(false)

  // ─── Filtros de Acessibilidade Educacional ──────────────────────────────────
  const accessibilityThresholdKm = ref<number>(10.0)
  const educationNetwork = ref<DependenciaRede>('todas')
  const educationStages = ref<string[]>([])
  const healthFilter = ref<'todos' | 'hospitais' | 'ubs' | 'amb'>('todos')

  function setActiveTab(tab: FilterTab) {
    activeTab.value = tab
  }

  function setSegurancaMetrica(metrica: SegurancaMetrica) {
    segurancaMetrica.value = metrica
  }

  function setSegurancaAno(ano: number | null) {
    segurancaAno.value = ano
  }

  function setSegurancaTipoCrime(crime: string) {
    segurancaTipoCrime.value = crime
  }

  function setSegurancaMes(mes: number | null) {
    segurancaMes.value = mes
  }

  async function fetchSegurancaFiltros() {
    if (filtrosLoaded.value) return
    try {
      const res = await axios.get(`${API}/features/seguranca/filtros`, { timeout: 8000 })
      if (res.data) {
        if (Array.isArray(res.data.anos) && res.data.anos.length > 0) {
          disponiveisAnos.value = res.data.anos
          if (segurancaAno.value && !res.data.anos.includes(segurancaAno.value)) {
            segurancaAno.value = res.data.anos[0]
          }
        }
        if (Array.isArray(res.data.tipos_crime)) {
          disponiveisTiposCrime.value = res.data.tipos_crime
        }
        if (Array.isArray(res.data.crimes_totais)) {
          disponiveisCrimesTotais.value = res.data.crimes_totais
        }
        filtrosLoaded.value = true
      }
    } catch (e) {
      console.warn('Falha ao carregar filtros de segurança:', e)
    }
  }

  function resetSegurancaFilters() {
    segurancaMetrica.value = 'ocorrencias'
    segurancaAno.value = disponiveisAnos.value[0] ?? 2024
    segurancaTipoCrime.value = 'todos'
    segurancaMes.value = null
  }

  function setAccessibilityThreshold(km: number) {
    accessibilityThresholdKm.value = Math.max(1, Math.min(100, km))
  }

  function setEducationNetwork(rede: DependenciaRede) {
    educationNetwork.value = rede
  }

  function toggleEducationStage(stage: string) {
    const idx = educationStages.value.indexOf(stage)
    if (idx >= 0) {
      educationStages.value.splice(idx, 1)
    } else {
      educationStages.value.push(stage)
    }
  }

  function setHealthFilter(filter: typeof healthFilter.value) {
    healthFilter.value = filter
  }

  function resetAll() {
    resetSegurancaFilters()
    accessibilityThresholdKm.value = 10.0
    educationNetwork.value = 'todas'
    educationStages.value = []
    healthFilter.value = 'todos'
  }

  // Expressão MapLibre data-driven para colorir setores por acessibilidade
  function getAccessibilityColorExpression(thresholdKm: number) {
    const half = thresholdKm / 2
    return [
      'case',
      ['<=', ['get', 'dist_escola_km'], half],        '#22c55e',  // verde: < metade do limiar
      ['<=', ['get', 'dist_escola_km'], thresholdKm], '#f59e0b',  // amarelo: entre metade e limiar
      ['>', ['get', 'dist_escola_km'], thresholdKm],  '#ef4444',  // vermelho: acima do limiar
      '#6b7280',  // cinza: sem dado
    ]
  }

  return {
    activeTab,
    segurancaMetrica,
    segurancaAno,
    segurancaTipoCrime,
    segurancaMes,
    disponiveisAnos: readonly(disponiveisAnos),
    disponiveisTiposCrime: readonly(disponiveisTiposCrime),
    disponiveisCrimesTotais: readonly(disponiveisCrimesTotais),
    accessibilityThresholdKm: readonly(accessibilityThresholdKm),
    educationNetwork: readonly(educationNetwork),
    educationStages: readonly(educationStages),
    healthFilter: readonly(healthFilter),
    setActiveTab,
    setSegurancaMetrica,
    setSegurancaAno,
    setSegurancaTipoCrime,
    setSegurancaMes,
    fetchSegurancaFiltros,
    resetSegurancaFilters,
    setAccessibilityThreshold,
    setEducationNetwork,
    toggleEducationStage,
    setHealthFilter,
    resetAll,
    getAccessibilityColorExpression,
  }
})
