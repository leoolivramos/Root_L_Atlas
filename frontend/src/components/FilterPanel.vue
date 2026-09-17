<template>
  <div class="filter-panel" :class="{ 'filter-panel--collapsed': collapsed }">
    <!-- Header: abas de camadas + botão colapsar -->
    <div class="filter-panel__top">
      <div v-if="!collapsed" class="filter-tabs">
        <button
          v-for="tab in availableTabs"
          :key="tab.id"
          class="filter-tab"
          :class="{ 'filter-tab--active': filtersStore.activeTab === tab.id }"
          @click="filtersStore.setActiveTab(tab.id)"
          :title="tab.label"
        >
          <AtlasIcon :name="tab.icon" :size="12" />
          <span class="tab-label">{{ tab.shortLabel }}</span>
        </button>
      </div>

      <button
        class="filter-panel__toggle"
        @click="collapsed = !collapsed"
        :aria-label="collapsed ? 'Expandir filtros' : 'Recolher filtros'"
        :title="collapsed ? 'Expandir filtros' : 'Recolher filtros'"
      >
        <AtlasIcon :name="collapsed ? 'filter' : 'chevron-down'" :size="14" />
      </button>
    </div>

    <!-- Conteúdo por aba -->
    <template v-if="!collapsed">

      <!-- ─── MUNICÍPIOS ─────────────────────────────────────────────────────── -->
      <div v-if="filtersStore.activeTab === 'municipios'" class="filter-panel__body">
        <div class="filter-info-card">
          <AtlasIcon name="municipio" :size="16" custom-class="info-icon" />
          <div>
            <p class="filter-info-card__title">Municípios de MT</p>
            <p class="filter-info-card__desc">
              Exibe os 141 municípios do estado de Mato Grosso com dados populacionais do Censo 2022.
              Clique em qualquer município para ver estatísticas detalhadas.
            </p>
          </div>
        </div>
        <div class="filter-stat-row">
          <div class="filter-stat">
            <span class="filter-stat__num">141</span>
            <span class="filter-stat__label">Municípios</span>
          </div>
          <div class="filter-stat">
            <span class="filter-stat__num">3,6M</span>
            <span class="filter-stat__label">Habitantes</span>
          </div>
          <div class="filter-stat">
            <span class="filter-stat__num">903k</span>
            <span class="filter-stat__label">km²</span>
          </div>
        </div>
      </div>

      <!-- ─── SETORES CENSITÁRIOS ────────────────────────────────────────────── -->
      <div v-if="filtersStore.activeTab === 'setores'" class="filter-panel__body">
        <div class="filter-item">
          <div class="filter-item__header">
            <span class="filter-item__label">Raio máximo de acesso</span>
            <span class="filter-item__value">{{ filtersStore.accessibilityThresholdKm }} km</span>
          </div>
          <input
            type="range"
            min="1"
            max="50"
            step="1"
            :value="filtersStore.accessibilityThresholdKm"
            class="filter-item__slider"
            @input="filtersStore.setAccessibilityThreshold(+($event.target as HTMLInputElement).value)"
          />
          <div class="filter-item__legend">
            <div class="legend-item">
              <span class="legend-dot legend-dot--green" />
              <span>≤ {{ Math.round(filtersStore.accessibilityThresholdKm / 2) }}km</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot legend-dot--yellow" />
              <span>≤ {{ filtersStore.accessibilityThresholdKm }}km</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot legend-dot--red" />
              <span>&gt; {{ filtersStore.accessibilityThresholdKm }}km</span>
            </div>
          </div>
        </div>

        <div class="filter-info-card filter-info-card--small">
          <p class="filter-info-card__desc">
            Coloração dos setores pela distância euclidiana à escola mais próxima.
            Ajuste o limiar para visualizar diferentes níveis de acesso.
          </p>
        </div>
      </div>

      <!-- ─── ESCOLAS ─────────────────────────────────────────────────────────── -->
      <div v-if="filtersStore.activeTab === 'escolas'" class="filter-panel__body">
        <div class="filter-item">
          <span class="filter-item__label">Rede de Ensino</span>
          <div class="filter-chip-group">
            <button
              v-for="opt in dependenciaOpts"
              :key="opt.value"
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.educationNetwork === opt.value }"
              @click="filtersStore.setEducationNetwork(opt.value)"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div class="filter-item">
          <span class="filter-item__label">Etapa de Ensino</span>
          <div class="filter-chip-group">
            <button
              v-for="stage in etapasOpts"
              :key="stage.value"
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.educationStages.includes(stage.value) }"
              @click="filtersStore.toggleEducationStage(stage.value)"
            >
              {{ stage.label }}
            </button>
          </div>
          <p class="filter-hint">Selecione uma ou mais etapas para filtrar</p>
        </div>

        <div class="filter-legend-bar">
          <div class="legend-bar-item" style="background: #d97706;" />
          <span>Escolas do Censo Escolar INEP (Mato Grosso)</span>
        </div>
      </div>

      <!-- ─── SAÚDE ───────────────────────────────────────────────────────────── -->
      <div v-if="filtersStore.activeTab === 'saude'" class="filter-panel__body">
        <div class="filter-item">
          <span class="filter-item__label">Tipo de Estabelecimento</span>
          <div class="filter-chip-group">
            <button
              v-for="opt in healthOpts"
              :key="opt.value"
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.healthType === opt.value }"
              @click="filtersStore.setHealthType(opt.value)"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div class="filter-legend-bar">
          <div class="legend-bar-item" style="background: #ef4444;" />
          <span>Estabelecimentos de Saúde (CNES / DATASUS)</span>
        </div>
      </div>

      <!-- ─── MALHA VIÁRIA ────────────────────────────────────────────────────── -->
      <div v-if="filtersStore.activeTab === 'malha_viaria'" class="filter-panel__body">
        <div class="filter-item">
          <span class="filter-item__label">Classe de Via</span>
          <div class="filter-chip-group">
            <button
              v-for="opt in roadOpts"
              :key="opt.value"
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.roadType === opt.value }"
              @click="filtersStore.setRoadType(opt.value)"
            >
              <span class="road-dot" :style="{ background: opt.color }" />
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div class="filter-item">
          <span class="filter-item__label">Legenda de Cores</span>
          <div class="road-legend">
            <div v-for="opt in roadOpts.filter(o => o.value !== 'todos')" :key="opt.value" class="road-legend-item">
              <span class="road-legend-line" :style="{ background: opt.color }" />
              <span>{{ opt.label }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── SEGURANÇA ───────────────────────────────────────────────────────── -->
      <div v-if="filtersStore.activeTab === 'seguranca'" class="filter-panel__body">
        <!-- Ano -->
        <div class="filter-item">
          <div class="filter-item__header">
            <span class="filter-item__label">Ano de Referência</span>
            <span class="filter-item__value">{{ filtersStore.segurancaAno ?? 'Todos' }}</span>
          </div>
          <div class="filter-chip-group">
            <button
              v-for="ano in filtersStore.disponiveisAnos"
              :key="ano"
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.segurancaAno === ano }"
              @click="filtersStore.setSegurancaAno(ano)"
            >{{ ano }}</button>
            <button
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.segurancaAno === null }"
              @click="filtersStore.setSegurancaAno(null)"
            >Todos</button>
          </div>
        </div>

        <!-- Tipo de Crime -->
        <div class="filter-item">
          <span class="filter-item__label">Tipo de Ocorrência</span>
          <select
            class="filter-select"
            :value="filtersStore.segurancaTipoCrime"
            @change="filtersStore.setSegurancaTipoCrime(($event.target as HTMLSelectElement).value)"
          >
            <option value="todos">Todos os crimes (Geral)</option>
            <option
              v-for="crime in crimesList"
              :key="crime.tipo_crime"
              :value="crime.tipo_crime"
            >
              {{ crime.tipo_crime }} ({{ Number(crime.total).toLocaleString('pt-BR') }})
            </option>
          </select>
        </div>

        <!-- Mês -->
        <div class="filter-item">
          <div class="filter-item__header">
            <span class="filter-item__label">Mês</span>
            <span class="filter-item__value">{{ currentMesLabel }}</span>
          </div>
          <select
            class="filter-select"
            :value="filtersStore.segurancaMes ?? ''"
            @change="handleMesChange"
          >
            <option value="">O ano todo (Consolidado)</option>
            <option v-for="(mNome, idx) in mesesList" :key="idx" :value="idx + 1">
              {{ idx + 1 }} — {{ mNome }}
            </option>
          </select>
        </div>

        <!-- Legenda choropleth -->
        <div class="choropleth-legend-card">
          <div class="choropleth-legend-card__header">
            <span class="choropleth-legend-card__title">Intensidade Municipal</span>
            <span class="choropleth-legend-card__metric">
              {{ filtersStore.segurancaMetrica === 'ocorrencias' ? 'Ocorrências' : 'Vítimas' }}
            </span>
          </div>
          <div class="choropleth-legend-bar" />
          <div class="choropleth-legend-labels">
            <span>Baixa</span>
            <span>Média</span>
            <span>Alta</span>
          </div>
        </div>

        <div class="filter-panel__footer-inline">
          <button class="filter-reset__btn" @click="filtersStore.resetSegurancaFilters()">
            Redefinir Filtros
          </button>
        </div>
      </div>

      <!-- ─── QUEIMADAS (INPE BDQUEIMADAS) ─────────────────────────────────── -->
      <div v-if="filtersStore.activeTab === 'queimadas'" class="filter-panel__body">
        <div class="filter-info-card">
          <AtlasIcon name="flame" :size="16" custom-class="info-icon info-icon--fire" />
          <div>
            <p class="filter-info-card__title">Focos de Queimadas — INPE</p>
            <p class="filter-info-card__desc">
              Monitoramento geoespacial de focos de calor com satélites orbitais e geoestacionários.
            </p>
          </div>
        </div>

        <!-- Métrica de Análise -->
        <div class="filter-item">
          <span class="filter-item__label">Métrica de Visualização</span>
          <div class="filter-chip-group">
            <button
              v-for="metrica in queimadasMetricasOpts"
              :key="metrica.value"
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.queimadasMetrica === metrica.value }"
              @click="filtersStore.setQueimadasMetrica(metrica.value)"
            >
              {{ metrica.label }}
            </button>
          </div>
        </div>

        <!-- Ano -->
        <div class="filter-item">
          <div class="filter-item__header">
            <span class="filter-item__label">Ano</span>
            <span class="filter-item__value">{{ filtersStore.queimadasAno ?? 'Todos' }}</span>
          </div>
          <div class="filter-chip-group">
            <button
              v-for="ano in filtersStore.disponiveisAnosQueimadas"
              :key="ano"
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.queimadasAno === ano }"
              @click="filtersStore.setQueimadasAno(ano)"
            >{{ ano }}</button>
            <button
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.queimadasAno === null }"
              @click="filtersStore.setQueimadasAno(null)"
            >Todos</button>
          </div>
        </div>

        <!-- Bioma -->
        <div class="filter-item">
          <span class="filter-item__label">Bioma em MT</span>
          <div class="filter-chip-group">
            <button
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.queimadasBioma === 'todos' }"
              @click="filtersStore.setQueimadasBioma('todos')"
            >Todos</button>
            <button
              v-for="b in filtersStore.disponiveisBiomas"
              :key="b"
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.queimadasBioma === b }"
              @click="filtersStore.setQueimadasBioma(b)"
            >{{ b }}</button>
          </div>
        </div>

        <!-- Mês -->
        <div class="filter-item">
          <div class="filter-item__header">
            <span class="filter-item__label">Mês</span>
            <span class="filter-item__value">{{ currentMesQueimadasLabel }}</span>
          </div>
          <select
            class="filter-select"
            :value="filtersStore.queimadasMes ?? ''"
            @change="handleQueimadasMesChange"
          >
            <option value="">O ano todo (Consolidado)</option>
            <option v-for="(mNome, idx) in mesesList" :key="idx" :value="idx + 1">
              {{ idx + 1 }} — {{ mNome }}
            </option>
          </select>
        </div>

        <!-- Satélite de Referência -->
        <div class="filter-item">
          <label class="filter-checkbox-label">
            <input
              type="checkbox"
              :checked="filtersStore.queimadasApenasReferencia"
              @change="filtersStore.toggleQueimadasReferencia()"
            />
            <span>Apenas Satélite de Referência (AQUA/MODIS)</span>
          </label>
        </div>

        <!-- Legenda de Calor -->
        <div class="choropleth-legend-card">
          <div class="choropleth-legend-card__header">
            <span class="choropleth-legend-card__title">Intensidade Térmica</span>
            <span class="choropleth-legend-card__metric choropleth-legend-card__metric--fire">
              {{ queimadasMetricaLabel }}
            </span>
          </div>
          <div class="choropleth-legend-bar choropleth-legend-bar--fire" />
          <div class="choropleth-legend-labels">
            <span>Baixa</span>
            <span>Média</span>
            <span>Alta / Crítica</span>
          </div>
        </div>

        <div class="filter-panel__footer-inline">
          <button class="filter-reset__btn" @click="filtersStore.resetQueimadasFilters()">
            Redefinir Filtros
          </button>
        </div>
      </div>

    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useFiltersStore, type DependenciaRede, type HealthType, type RoadType } from '@/stores/filtersStore'
import AtlasIcon, { type IconName } from '@/components/AtlasIcon.vue'

const filtersStore = useFiltersStore()
const collapsed = ref(false)

onMounted(() => {
  filtersStore.fetchSegurancaFiltros()
  filtersStore.fetchQueimadasFiltros()
})

// ─── Definição das abas disponíveis ─────────────────────────────────────────
const availableTabs: {
  id: typeof filtersStore.activeTab
  label: string
  shortLabel: string
  icon: IconName
}[] = [
  { id: 'municipios',   label: 'Municípios',          shortLabel: 'Mun.',     icon: 'municipio' },
  { id: 'setores',      label: 'Setores Censitários',  shortLabel: 'Setores',  icon: 'setor' },
  { id: 'escolas',      label: 'Escolas (INEP)',        shortLabel: 'Escolas',  icon: 'escola' },
  { id: 'saude',        label: 'Saúde (CNES)',          shortLabel: 'Saúde',    icon: 'saude' },
  { id: 'malha_viaria', label: 'Malha Viária (OSM)',    shortLabel: 'Viária',   icon: 'viaria' },
  { id: 'seguranca',    label: 'Segurança (SINESP)',    shortLabel: 'Seg.',     icon: 'shield' },
  { id: 'queimadas',    label: 'Queimadas (INPE)',      shortLabel: 'Fogo',     icon: 'flame' },
]

// ─── Queimadas ───────────────────────────────────────────────────────────────
const queimadasMetricasOpts: { value: 'focos' | 'frp_medio' | 'risco_medio'; label: string }[] = [
  { value: 'focos', label: 'Focos' },
  { value: 'frp_medio', label: 'FRP (MW)' },
  { value: 'risco_medio', label: 'Risco Fogo' },
]

const currentMesQueimadasLabel = computed(() => {
  if (filtersStore.queimadasMes === null) return 'Ano Todo'
  return mesesList[filtersStore.queimadasMes - 1] ?? 'Ano Todo'
})

function handleQueimadasMesChange(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  filtersStore.setQueimadasMes(val ? Number(val) : null)
}

const queimadasMetricaLabel = computed(() => {
  if (filtersStore.queimadasMetrica === 'frp_medio') return 'FRP Médio (MW)'
  if (filtersStore.queimadasMetrica === 'risco_medio') return 'Risco Médio'
  return 'Densidade de Focos'
})

// ─── Segurança ───────────────────────────────────────────────────────────────
const mesesList = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
]

const currentMesLabel = computed(() => {
  if (filtersStore.segurancaMes === null) return 'Ano Todo'
  return mesesList[filtersStore.segurancaMes - 1] ?? 'Ano Todo'
})

function handleMesChange(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  filtersStore.setSegurancaMes(val ? Number(val) : null)
}

const crimesList = computed(() => {
  if (filtersStore.disponiveisCrimesTotais.length > 0) {
    return filtersStore.disponiveisCrimesTotais
  }
  return filtersStore.disponiveisTiposCrime.map((c) => ({ tipo_crime: c, total: 0 }))
})

// ─── Escolas ─────────────────────────────────────────────────────────────────
const dependenciaOpts: { value: DependenciaRede; label: string }[] = [
  { value: 'todas',     label: 'Todas' },
  { value: 'publica',   label: 'Pública' },
  { value: 'estadual',  label: 'Estadual' },
  { value: 'municipal', label: 'Municipal' },
  { value: 'federal',   label: 'Federal' },
  { value: 'privada',   label: 'Privada' },
]

const etapasOpts = [
  { value: 'creche',     label: 'Creche' },
  { value: 'pre_escola', label: 'Pré-escola' },
  { value: 'fund_ai',    label: 'Fund. I' },
  { value: 'fund_af',    label: 'Fund. II' },
  { value: 'medio',      label: 'Médio' },
  { value: 'eja',        label: 'EJA' },
]

// ─── Saúde ───────────────────────────────────────────────────────────────────
const healthOpts: { value: HealthType; label: string }[] = [
  { value: 'todos',         label: 'Todos' },
  { value: 'hospital',      label: 'Hospital' },
  { value: 'ubs',           label: 'UBS / Posto' },
  { value: 'policlinica',   label: 'Policlínica' },
  { value: 'pronto_socorro', label: 'Pronto-Socorro' },
  { value: 'consultorio',   label: 'Consultório' },
]

// ─── Malha Viária ─────────────────────────────────────────────────────────────
const roadOpts: { value: RoadType; label: string; color: string }[] = [
  { value: 'todos',     label: 'Todas',     color: '#94a3b8' },
  { value: 'motorway',  label: 'Rodovia',   color: '#dc2626' },
  { value: 'trunk',     label: 'Troncal',   color: '#ea580c' },
  { value: 'primary',   label: 'Principal', color: '#f59e0b' },
  { value: 'secondary', label: 'Secundária',color: '#10b981' },
  { value: 'tertiary',  label: 'Terciária', color: '#06b6d4' },
]
</script>

<style scoped>
.filter-panel {
  width: 290px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(14px);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  color: #0f172a;
  font-family: inherit;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.filter-panel--collapsed {
  width: auto;
  min-width: 44px;
}

/* Header */
.filter-panel__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.45rem 0.55rem;
  border-bottom: 1px solid #f1f5f9;
  background: #f8fafc;
  gap: 0.4rem;
}

/* Abas de camadas */
.filter-tabs {
  display: flex;
  gap: 2px;
  flex: 1;
  overflow-x: auto;
  scrollbar-width: none;
}
.filter-tabs::-webkit-scrollbar { display: none; }

.filter-tab {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  padding: 0.3rem 0.4rem;
  border: 1px solid transparent;
  background: transparent;
  color: #64748b;
  font-size: 0.68rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}

.filter-tab:hover:not(.filter-tab--active) {
  background: #f1f5f9;
  color: #334155;
}

.filter-tab--active {
  background: #eff6ff;
  color: #2563eb;
  border-color: #bfdbfe;
}

.tab-label {
  display: inline;
}

.filter-panel__toggle {
  width: 26px;
  height: 26px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}

.filter-panel__toggle:hover {
  background: #f1f5f9;
  color: #0f172a;
  border-color: #cbd5e1;
}

/* Corpo dos filtros */
.filter-panel__body {
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  max-height: 420px;
  overflow-y: auto;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.filter-item__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.filter-item__label {
  font-size: 0.7rem;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.filter-item__value {
  font-size: 0.78rem;
  font-weight: 700;
  color: #2563eb;
}

/* Info Card (Municípios) */
.filter-info-card {
  display: flex;
  gap: 0.6rem;
  padding: 0.65rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  align-items: flex-start;
}

.filter-info-card--small {
  padding: 0.5rem 0.6rem;
}

.info-icon {
  color: #2563eb;
  flex-shrink: 0;
  margin-top: 2px;
}

.filter-info-card__title {
  font-size: 0.78rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 0.2rem;
}

.filter-info-card__desc {
  font-size: 0.68rem;
  color: #64748b;
  line-height: 1.45;
  margin: 0;
}

/* Stats */
.filter-stat-row {
  display: flex;
  gap: 0.4rem;
}

.filter-stat {
  flex: 1;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.5rem 0.4rem;
  text-align: center;
}

.filter-stat__num {
  display: block;
  font-size: 0.95rem;
  font-weight: 800;
  color: #2563eb;
  line-height: 1.1;
}

.filter-stat__label {
  display: block;
  font-size: 0.62rem;
  color: #64748b;
  margin-top: 0.15rem;
}

/* Slider */
.filter-item__slider {
  width: 100%;
  height: 4px;
  accent-color: #2563eb;
  cursor: pointer;
}

/* Legenda de acessibilidade */
.filter-item__legend {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.15rem;
  font-size: 0.63rem;
  color: #64748b;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.2rem;
}

.legend-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.legend-dot--green  { background: #16a34a; }
.legend-dot--yellow { background: #d97706; }
.legend-dot--red    { background: #dc2626; }

/* Chips */
.filter-chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.28rem;
  margin-top: 0.05rem;
}

.filter-chip {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.22rem 0.5rem;
  border-radius: 99px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  font-size: 0.68rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.12s;
}

.filter-chip--active {
  background: #eff6ff;
  border-color: #2563eb;
  color: #2563eb;
  font-weight: 600;
}

.filter-chip:hover:not(.filter-chip--active) {
  background: #f1f5f9;
  color: #0f172a;
}

.filter-hint {
  font-size: 0.62rem;
  color: #94a3b8;
  margin: 0;
}

/* Barra de legenda colorida */
.filter-legend-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.65rem;
  color: #64748b;
}

.legend-bar-item {
  width: 28px;
  height: 8px;
  border-radius: 4px;
  flex-shrink: 0;
}

/* Malha Viária */
.road-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.road-legend {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.road-legend-item {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.68rem;
  color: #475569;
}

.road-legend-line {
  display: inline-block;
  width: 20px;
  height: 3px;
  border-radius: 2px;
  flex-shrink: 0;
}

/* Segmented Control */
.segmented-control {
  display: flex;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 2px;
  gap: 2px;
}

.segmented-btn {
  flex: 1;
  padding: 0.32rem 0.5rem;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 0.72rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.12s;
}

.segmented-btn--active {
  background: #ffffff;
  color: #ef4444;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* Select */
.filter-select {
  width: 100%;
  padding: 0.4rem 0.55rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #1e293b;
  font-size: 0.73rem;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  transition: border-color 0.15s;
}

.filter-select:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}

/* Choropleth legend */
.choropleth-legend-card {
  padding: 0.55rem 0.7rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.choropleth-legend-card__header {
  display: flex;
  justify-content: space-between;
  font-size: 0.67rem;
  color: #64748b;
  font-weight: 600;
}

.choropleth-legend-card__metric {
  color: #ef4444;
  text-transform: capitalize;
}

.choropleth-legend-bar {
  height: 8px;
  border-radius: 4px;
  background: linear-gradient(
    to right,
    #bfdbfe,
    #60a5fa,
    #f59e0b,
    #ef4444,
    #7f1d1d
  );
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.08);
}

.choropleth-legend-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.6rem;
  color: #94a3b8;
  font-weight: 500;
}

/* Footer reset inline */
.filter-panel__footer-inline {
  padding-top: 0.1rem;
}

.filter-reset__btn {
  width: 100%;
  padding: 0.32rem 0.5rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #64748b;
  font-size: 0.7rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.filter-reset__btn:hover {
  background: #fee2e2;
  color: #dc2626;
  border-color: #fca5a5;
}

.info-icon--fire {
  color: #ea580c !important;
}

.choropleth-legend-card__metric--fire {
  color: #ea580c !important;
}

.choropleth-legend-bar--fire {
  background: linear-gradient(
    to right,
    #fef08a,
    #f59e0b,
    #ea580c,
    #dc2626,
    #7f1d1d
  ) !important;
}

.filter-checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.7rem;
  color: #334155;
  cursor: pointer;
  padding: 0.15rem 0;
  user-select: none;
}

.filter-checkbox-label input[type="checkbox"] {
  accent-color: #ea580c;
  cursor: pointer;
  width: 14px;
  height: 14px;
}
</style>
