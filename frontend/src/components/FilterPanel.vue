<template>
  <div class="filter-panel" :class="{ 'filter-panel--collapsed': collapsed }">
    <!-- Header com abas e botão colapsar -->
    <div class="filter-panel__top">
      <div v-if="!collapsed" class="filter-tabs">
        <button
          class="filter-tab"
          :class="{ 'filter-tab--active': filtersStore.activeTab === 'seguranca' }"
          @click="filtersStore.setActiveTab('seguranca')"
        >
          <AtlasIcon name="shield" :size="13" />
          <span>Segurança</span>
        </button>
        <button
          class="filter-tab"
          :class="{ 'filter-tab--active': filtersStore.activeTab === 'acessibilidade' }"
          @click="filtersStore.setActiveTab('acessibilidade')"
        >
          <AtlasIcon name="escola" :size="13" />
          <span>Educação</span>
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

    <!-- Conteúdo dos Filtros -->
    <template v-if="!collapsed">
      <!-- ─── ABA SEGURANÇA PÚBLICA (HEATMAP SINESP) ─────────────────────────── -->
      <div v-if="filtersStore.activeTab === 'seguranca'" class="filter-panel__body">
        <!-- Métrica (Ocorrências vs Vítimas) -->
        <div class="filter-item">
          <span class="filter-item__label">Métrica de Análise</span>
          <div class="segmented-control">
            <button
              class="segmented-btn"
              :class="{ 'segmented-btn--active': filtersStore.segurancaMetrica === 'ocorrencias' }"
              @click="filtersStore.setSegurancaMetrica('ocorrencias')"
            >
              Ocorrências
            </button>
            <button
              class="segmented-btn"
              :class="{ 'segmented-btn--active': filtersStore.segurancaMetrica === 'vitimas' }"
              @click="filtersStore.setSegurancaMetrica('vitimas')"
            >
              Vítimas
            </button>
          </div>
        </div>

        <!-- Ano de Referência -->
        <div class="filter-item">
          <div class="filter-item__header">
            <span class="filter-item__label">Ano</span>
            <span class="filter-item__value">{{ filtersStore.segurancaAno ?? 'Todos' }}</span>
          </div>
          <div class="filter-chip-group">
            <button
              v-for="ano in filtersStore.disponiveisAnos"
              :key="ano"
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.segurancaAno === ano }"
              @click="filtersStore.setSegurancaAno(ano)"
            >
              {{ ano }}
            </button>
            <button
              class="filter-chip"
              :class="{ 'filter-chip--active': filtersStore.segurancaAno === null }"
              @click="filtersStore.setSegurancaAno(null)"
            >
              Todos
            </button>
          </div>
        </div>

        <!-- Tipo de Crime -->
        <div class="filter-item">
          <span class="filter-item__label">Tipo de Ocorrência Criminal</span>
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
            <span class="filter-item__label">Mês de Referência</span>
            <span class="filter-item__value">{{ currentMesLabel }}</span>
          </div>
          <select
            class="filter-select"
            :value="filtersStore.segurancaMes ?? ''"
            @change="handleMesChange"
          >
            <option value="">O ano todo (Consolidado)</option>
            <option v-for="(mNome, idx) in mesesList" :key="idx" :value="idx + 1">
              {{ idx + 1 }} - {{ mNome }}
            </option>
          </select>
        </div>

        <!-- Legenda do Mapa de Calor -->
        <div class="heatmap-legend-card">
          <div class="heatmap-legend-card__header">
            <span class="heatmap-legend-card__title">Intensidade do Calor</span>
            <span class="heatmap-legend-card__metric">{{ filtersStore.segurancaMetrica === 'ocorrencias' ? 'Ocorrências' : 'Vítimas' }}</span>
          </div>
          <div class="heatmap-legend-bar" />
          <div class="heatmap-legend-labels">
            <span>Baixa</span>
            <span>Média</span>
            <span>Alta Densidade</span>
          </div>
        </div>
      </div>

      <!-- ─── ABA ACESSIBILIDADE EDUCACIONAL ─────────────────────────────────── -->
      <div v-else class="filter-panel__body">
        <div class="filter-item">
          <div class="filter-item__header">
            <span class="filter-item__label">Raio máximo à escola</span>
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

        <div class="filter-item">
          <span class="filter-item__label">Rede de ensino</span>
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
      </div>

      <!-- Rodapé / Reset -->
      <div class="filter-panel__footer">
        <button
          v-if="filtersStore.activeTab === 'seguranca'"
          class="filter-reset__btn"
          @click="filtersStore.resetSegurancaFilters"
        >
          Redefinir Filtros de Segurança
        </button>
        <button
          v-else
          class="filter-reset__btn"
          @click="filtersStore.resetAll"
        >
          Redefinir Filtros de Educação
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useFiltersStore, type DependenciaRede } from '@/stores/filtersStore'
import AtlasIcon from '@/components/AtlasIcon.vue'

const filtersStore = useFiltersStore()
const collapsed = ref(false)

onMounted(() => {
  filtersStore.fetchSegurancaFiltros()
})

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

const dependenciaOpts: { value: DependenciaRede; label: string }[] = [
  { value: 'todas', label: 'Todas' },
  { value: 'publica', label: 'Pública' },
  { value: 'estadual', label: 'Estadual' },
  { value: 'municipal', label: 'Municipal' },
  { value: 'federal', label: 'Federal' },
  { value: 'privada', label: 'Privada' },
]
</script>

<style scoped>
.filter-panel {
  width: 275px;
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

.filter-panel__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.65rem;
  border-bottom: 1px solid #f1f5f9;
  background: #f8fafc;
  gap: 0.5rem;
}

/* Abas */
.filter-tabs {
  display: flex;
  background: #e2e8f0;
  padding: 2px;
  border-radius: 8px;
  flex: 1;
  gap: 2px;
}

.filter-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  padding: 0.35rem 0.45rem;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 0.72rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.filter-tab--active {
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
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

.filter-panel__body {
  padding: 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 480px;
  overflow-y: auto;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.filter-item__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.filter-item__label {
  font-size: 0.72rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.filter-item__value {
  font-size: 0.78rem;
  font-weight: 700;
  color: #2563eb;
}

/* Segmented Control (Ocorrências / Vítimas) */
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
  padding: 0.35rem 0.5rem;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 0.74rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.segmented-btn--active {
  background: #ffffff;
  color: #ef4444;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* Custom Select */
.filter-select {
  width: 100%;
  padding: 0.45rem 0.6rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #1e293b;
  font-size: 0.76rem;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  transition: border-color 0.15s;
}

.filter-select:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}

/* Slider */
.filter-item__slider {
  width: 100%;
  height: 4px;
  accent-color: #2563eb;
  cursor: pointer;
}

/* Legenda da Acessibilidade */
.filter-item__legend {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.2rem;
  font-size: 0.65rem;
  color: #64748b;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.legend-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.legend-dot--green { background: #16a34a; }
.legend-dot--yellow { background: #d97706; }
.legend-dot--red { background: #dc2626; }

/* Chips */
.filter-chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.1rem;
}

.filter-chip {
  padding: 0.25rem 0.55rem;
  border-radius: 99px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  font-size: 0.7rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
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

/* Card de Legenda do Heatmap */
.heatmap-legend-card {
  margin-top: 0.2rem;
  padding: 0.6rem 0.75rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.heatmap-legend-card__header {
  display: flex;
  justify-content: space-between;
  font-size: 0.68rem;
  color: #64748b;
  font-weight: 600;
}

.heatmap-legend-card__metric {
  color: #ef4444;
  text-transform: capitalize;
}

.heatmap-legend-bar {
  height: 8px;
  border-radius: 4px;
  background: linear-gradient(
    to right,
    rgba(33, 102, 172, 0.4),
    rgb(103, 169, 207),
    rgb(209, 229, 240),
    rgb(253, 219, 199),
    rgb(239, 138, 98),
    rgb(178, 24, 43)
  );
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.1);
}

.heatmap-legend-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.62rem;
  color: #94a3b8;
  font-weight: 500;
}

.filter-panel__footer {
  padding: 0.55rem 0.8rem;
  border-top: 1px solid #f1f5f9;
  background: #fafafa;
}

.filter-reset__btn {
  width: 100%;
  padding: 0.35rem 0.5rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #64748b;
  font-size: 0.72rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.filter-reset__btn:hover {
  background: #fee2e2;
  color: #dc2626;
  border-color: #fca5a5;
}
</style>
