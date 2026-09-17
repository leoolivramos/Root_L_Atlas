// stores/filtersStore.ts — Filtros analíticos para todas as camadas do Atlas
import { defineStore } from 'pinia'
import { ref, readonly } from 'vue'
import axios from 'axios'

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type DependenciaRede = 'todas' | 'publica' | 'federal' | 'estadual' | 'municipal' | 'privada'
export type SegurancaMetrica = 'ocorrencias' | 'vitimas'
export type QueimadasMetrica = 'focos' | 'frp_medio' | 'risco_medio'
export type HealthType = 'todos' | 'hospital' | 'ubs' | 'policlinica' | 'pronto_socorro' | 'consultorio'
export type RoadType = 'todos' | 'motorway' | 'trunk' | 'primary' | 'secondary' | 'tertiary'
export type FilterTab = 'municipios' | 'setores' | 'escolas' | 'saude' | 'malha_viaria' | 'seguranca' | 'queimadas'

export const useFiltersStore = defineStore('filters', () => {
  // Aba ativa no painel de filtros
  const activeTab = ref<FilterTab>('seguranca')

  // ─── Filtros de Segurança Pública (SINESP Choropleth) ──────────────────────
  const segurancaMetrica = ref<SegurancaMetrica>('ocorrencias')
  const segurancaAno = ref<number | null>(2024)
  const segurancaTipoCrime = ref<string>('todos')
  const segurancaMes = ref<number | null>(null)

  // Metadados dinâmicos carregados da API
  const disponiveisAnos = ref<number[]>([2024, 2023])
  const disponiveisTiposCrime = ref<string[]>([])
  const disponiveisCrimesTotais = ref<Array<{ tipo_crime: string; total: number }>>([])
  const filtrosLoaded = ref(false)

  // ─── Filtros de Queimadas (INPE BDQueimadas) ────────────────────────────────
  const queimadasMetrica = ref<QueimadasMetrica>('focos')
  const queimadasAno = ref<number | null>(2024)
  const queimadasMes = ref<number | null>(null)
  const queimadasBioma = ref<string>('todos')
  const queimadasApenasReferencia = ref<boolean>(false)

  const disponiveisAnosQueimadas = ref<number[]>([2025, 2024])
  const disponiveisBiomas = ref<string[]>(['Amazônia', 'Cerrado', 'Pantanal'])
  const queimadasFiltrosLoaded = ref(false)

  // ─── Filtros de Acessibilidade (Setores Censitários) ────────────────────────
  const accessibilityThresholdKm = ref<number>(10.0)

  // ─── Filtros de Escolas ─────────────────────────────────────────────────────
  const educationNetwork = ref<DependenciaRede>('todas')
  const educationStages = ref<string[]>([])

  // ─── Filtros de Saúde (CNES) ────────────────────────────────────────────────
  const healthType = ref<HealthType>('todos')

  // ─── Filtros de Malha Viária (OSM) ──────────────────────────────────────────
  const roadType = ref<RoadType>('todos')

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

  // ─── Ações de Filtros de Queimadas ─────────────────────────────────────────
  function setQueimadasMetrica(metrica: QueimadasMetrica) {
    queimadasMetrica.value = metrica
  }

  function setQueimadasAno(ano: number | null) {
    queimadasAno.value = ano
  }

  function setQueimadasMes(mes: number | null) {
    queimadasMes.value = mes
  }

  function setQueimadasBioma(bioma: string) {
    queimadasBioma.value = bioma
  }

  function toggleQueimadasReferencia() {
    queimadasApenasReferencia.value = !queimadasApenasReferencia.value
  }

  async function fetchQueimadasFiltros() {
    if (queimadasFiltrosLoaded.value) return
    try {
      const res = await axios.get(`${API}/features/queimadas/filtros`, { timeout: 8000 })
      if (res.data) {
        if (Array.isArray(res.data.anos) && res.data.anos.length > 0) {
          disponiveisAnosQueimadas.value = res.data.anos
          if (queimadasAno.value && !res.data.anos.includes(queimadasAno.value)) {
            queimadasAno.value = res.data.anos[0]
          }
        }
        if (Array.isArray(res.data.biomas) && res.data.biomas.length > 0) {
          disponiveisBiomas.value = res.data.biomas
        }
        queimadasFiltrosLoaded.value = true
      }
    } catch (e) {
      console.warn('Falha ao carregar filtros de queimadas:', e)
    }
  }

  function resetQueimadasFilters() {
    queimadasMetrica.value = 'focos'
    queimadasAno.value = disponiveisAnosQueimadas.value[0] ?? 2024
    queimadasMes.value = null
    queimadasBioma.value = 'todos'
    queimadasApenasReferencia.value = false
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

  function setHealthType(type: HealthType) {
    healthType.value = type
  }

  function setRoadType(type: RoadType) {
    roadType.value = type
  }

  function resetAll() {
    resetSegurancaFilters()
    resetQueimadasFilters()
    accessibilityThresholdKm.value = 10.0
    educationNetwork.value = 'todas'
    educationStages.value = []
    healthType.value = 'todos'
    roadType.value = 'todos'
  }

  // Expressão MapLibre data-driven para colorir setores por acessibilidade
  function getAccessibilityColorExpression(thresholdKm: number) {
    const half = thresholdKm / 2
    const distVal = ['to-number', ['get', 'dist_escola_km'], -1]
    return [
      'case',
      ['<', distVal, 0],                              '#94a3b8',  // cinza: sem dado (-1)
      ['<=', distVal, half],                          '#16a34a',  // verde: <= metade do limiar
      ['<=', distVal, thresholdKm],                   '#f59e0b',  // amarelo: entre metade e limiar
      ['>', distVal, thresholdKm],                    '#dc2626',  // vermelho: acima do limiar
      '#94a3b8',  // fallback
    ]
  }

  return {
    activeTab,
    // Segurança
    segurancaMetrica,
    segurancaAno,
    segurancaTipoCrime,
    segurancaMes,
    disponiveisAnos: readonly(disponiveisAnos),
    disponiveisTiposCrime: readonly(disponiveisTiposCrime),
    disponiveisCrimesTotais: readonly(disponiveisCrimesTotais),
    // Queimadas
    queimadasMetrica,
    queimadasAno,
    queimadasMes,
    queimadasBioma,
    queimadasApenasReferencia,
    disponiveisAnosQueimadas: readonly(disponiveisAnosQueimadas),
    disponiveisBiomas: readonly(disponiveisBiomas),
    // Demais camadas
    accessibilityThresholdKm: readonly(accessibilityThresholdKm),
    educationNetwork: readonly(educationNetwork),
    educationStages: readonly(educationStages),
    healthType: readonly(healthType),
    roadType: readonly(roadType),
    // Ações
    setActiveTab,
    setSegurancaMetrica,
    setSegurancaAno,
    setSegurancaTipoCrime,
    setSegurancaMes,
    fetchSegurancaFiltros,
    resetSegurancaFilters,
    setQueimadasMetrica,
    setQueimadasAno,
    setQueimadasMes,
    setQueimadasBioma,
    toggleQueimadasReferencia,
    fetchQueimadasFiltros,
    resetQueimadasFilters,
    setAccessibilityThreshold,
    setEducationNetwork,
    toggleEducationStage,
    setHealthType,
    setRoadType,
    resetAll,
    getAccessibilityColorExpression,
  }
})
