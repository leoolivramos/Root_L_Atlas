<template>
  <div class="app-container">
    <!-- Barra Superior Flutuante (Header + Busca + Controles Rápidos) -->
    <header class="app-topbar">
      <!-- Identidade da Plataforma -->
      <div class="app-brand" @click="resetViewport" title="Resetar visualização para Mato Grosso">
        <div class="app-brand__logo">
          <AtlasIcon name="map" :size="18" />
        </div>
        <div class="app-brand__text">
          <span class="app-brand__title">ROOTL ATLAS</span>
          <span class="app-brand__subtitle">Mato Grosso</span>
        </div>
      </div>

      <!-- Barra de Busca Centralizada -->
      <div class="app-search-area">
        <SearchBar @select="handleSearchSelect" />
      </div>

      <!-- Ações e Controles Utilitários -->
      <div class="app-actions">
        <!-- Seletor de Basemap (Claro / Escuro / OSM) -->
        <div class="basemap-selector" title="Estilo do mapa base">
          <button
            v-for="b in basemapsList"
            :key="b.id"
            class="basemap-btn"
            :class="{ 'basemap-btn--active': mapStore.activeBasemap === b.id }"
            @click="mapStore.setBasemap(b.id)"
          >
            {{ b.label }}
          </button>
        </div>

        <!-- Toggle 3D / 2D -->
        <button
          class="top-btn"
          :class="{ 'top-btn--active': mapStore.is3D }"
          @click="mapStore.toggle3D"
          :title="mapStore.is3D ? 'Alternar para visão 2D plana' : 'Alternar para visão 3D inclinada'"
        >
          <AtlasIcon name="cube" :size="15" />
          <span>{{ mapStore.is3D ? '3D' : '2D' }}</span>
        </button>

        <!-- Centralizar Mato Grosso -->
        <button
          class="top-btn"
          @click="resetViewport"
          title="Centralizar mapa em Mato Grosso"
          aria-label="Centralizar mapa"
        >
          <AtlasIcon name="target" :size="16" />
        </button>

        <!-- Toggle Painel de Filtros -->
        <button
          class="top-btn"
          :class="{ 'top-btn--active': mapStore.showFilters }"
          @click="mapStore.toggleFilters"
          title="Alternar painel de filtros de acessibilidade"
        >
          <AtlasIcon name="filter" :size="15" />
          <span class="btn-text-desktop">Filtros</span>
        </button>
      </div>
    </header>

    <!-- Canvas do Mapa Principal -->
    <MapCanvas
      class="map-area"
      @feature-click="handleFeatureClick"
      @map-click="handleMapClick"
    >
      <!-- Painel de Camadas (Lateral Esquerda Flutuante) -->
      <LayerPanel v-if="mapStore.showLayers" />

      <!-- Painel de Filtros (Lateral Direita Inferior Flutuante) -->
      <transition name="slide-up">
        <div v-if="mapStore.showFilters" class="app-filter-wrapper">
          <FilterPanel />
        </div>
      </transition>

      <!-- Barra de Carregamento Global -->
      <transition name="fade">
        <div v-if="requestsStore.isAnyLoading" class="global-loading">
          <div class="global-loading__bar" />
        </div>
      </transition>
    </MapCanvas>

    <!-- Painel Lateral de Detalhes da Feição Selecionada -->
    <FeatureDetail
      :feature="selectedFeature"
      @close="selectedFeature = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import MapCanvas from '@/components/MapCanvas.vue'
import LayerPanel from '@/components/LayerPanel.vue'
import FilterPanel from '@/components/FilterPanel.vue'
import FeatureDetail from '@/components/FeatureDetail.vue'
import SearchBar from '@/components/SearchBar.vue'
import AtlasIcon from '@/components/AtlasIcon.vue'
import { useMapStore, type BasemapId } from '@/stores/mapStore'
import { useRequestsStore } from '@/stores/requestsStore'
import type { SelectedFeature, LayerId, SearchResult } from '@/types/atlas'
import type maplibregl from 'maplibre-gl'

const mapStore = useMapStore()
const requestsStore = useRequestsStore()

const selectedFeature = ref<SelectedFeature | null>(null)

const basemapsList: { id: BasemapId; label: string }[] = [
  { id: 'light', label: 'Claro' },
  { id: 'dark', label: 'Escuro' },
  { id: 'osm', label: 'Natural' },
  { id: 'satellite', label: 'Satélite' },
]

function handleFeatureClick(
  layer: LayerId,
  id: string | number,
  properties: Record<string, unknown>
) {
  selectedFeature.value = {
    layer,
    id,
    properties,
    lineage: {
      fonte_id: (properties['fonte_id'] as string) ?? '',
      data_extracao: properties['data_extracao'] as string,
      url_origem: properties['url_origem'] as string,
      versao_processamento: properties['versao_processamento'] as string,
    },
  }
}

function handleMapClick(_lngLat: maplibregl.LngLat) {
  if (selectedFeature.value) {
    selectedFeature.value = null
  }
}

function handleSearchSelect(_result: SearchResult) {
  // A busca já realiza o ajuste de câmera via mapStore
}

function resetViewport() {
  mapStore.resetViewport()
}
</script>

<style>
/* Reset Global */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  height: 100%;
  width: 100%;
  overflow: hidden;
  background: #f8fafc;
  color: #0f172a;
  -webkit-font-smoothing: antialiased;
}

#app {
  height: 100%;
  width: 100%;
}

/* Scrollbars Clean */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
</style>

<style scoped>
.app-container {
  position: relative;
  width: 100vw;
  height: 100vh;
  display: flex;
  overflow: hidden;
  font-family: 'Inter', system-ui, sans-serif;
}

.map-area {
  flex: 1;
  position: relative;
  width: 100%;
  height: 100%;
}

/* Barra Superior Flutuante */
.app-topbar {
  position: absolute;
  top: 0.75rem;
  left: 0.75rem;
  right: 0.75rem;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  z-index: 30;
  pointer-events: none; /* Permite cliques no mapa através de áreas vazias */
}

.app-topbar > * {
  pointer-events: auto; /* Reativa cliques nos componentes filhos */
}

/* Marca / Logo */
.app-brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(12px);
  border: 1px solid #e2e8f0;
  border-radius: 9999px;
  padding: 0.45rem 1rem 0.45rem 0.5rem;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  user-select: none;
  transition: all 0.15s;
}

.app-brand:hover {
  background: #ffffff;
  border-color: #cbd5e1;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08);
}

.app-brand__logo {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #2563eb;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.3);
}

.app-brand__text {
  display: flex;
  flex-direction: column;
}

.app-brand__title {
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #0f172a;
  line-height: 1.1;
}

.app-brand__subtitle {
  font-size: 0.65rem;
  font-weight: 600;
  color: #64748b;
  letter-spacing: 0.02em;
}

/* Área de Busca */
.app-search-area {
  display: flex;
  justify-content: center;
}

/* Controles e Botões Utilitários */
.app-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Seletor de Basemap */
.basemap-selector {
  display: flex;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(12px);
  border: 1px solid #e2e8f0;
  border-radius: 9999px;
  padding: 3px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
}

.basemap-btn {
  padding: 0.3rem 0.75rem;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 9999px;
  cursor: pointer;
  transition: all 0.15s;
}

.basemap-btn:hover:not(.basemap-btn--active) {
  color: #0f172a;
}

.basemap-btn--active {
  background: #2563eb;
  color: #ffffff;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);
}

/* Botões Topbar */
.top-btn {
  height: 38px;
  min-width: 38px;
  padding: 0 0.75rem;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(12px);
  border: 1px solid #e2e8f0;
  border-radius: 9999px;
  color: #475569;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
  transition: all 0.15s;
}

.top-btn:hover {
  background: #ffffff;
  color: #0f172a;
  border-color: #cbd5e1;
}

.top-btn--active {
  background: #eff6ff;
  color: #2563eb;
  border-color: #93c5fd;
}

@media (max-width: 768px) {
  .btn-text-desktop {
    display: none;
  }
}

/* Filtros Flutuantes */
.app-filter-wrapper {
  position: absolute;
  bottom: 2rem;
  right: 1rem;
  z-index: 20;
}

/* Linha de Loading */
.global-loading {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  z-index: 100;
  overflow: hidden;
}

.global-loading__bar {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #6366f1, #3b82f6);
  background-size: 200% 100%;
  animation: loading-bar 1.2s linear infinite;
}

@keyframes loading-bar {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.25s;
}
.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(16px);
  opacity: 0;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
