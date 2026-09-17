// stores/mapStore.ts — Estado do mapa (viewport, modo, basemap, painéis)
import { defineStore } from 'pinia'
import { ref, readonly } from 'vue'
import type { MapViewport } from '@/types/atlas'

export type BasemapId = 'osm' | 'light' | 'dark' | 'satellite'

export interface BasemapConfig {
  id: BasemapId
  label: string
  url: string
  attribution: string
}

export const BASEMAPS: Record<BasemapId, BasemapConfig> = {
  osm: {
    id: 'osm',
    label: 'Natural (OSM)',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors',
  },
  light: {
    id: 'light',
    label: 'Claro',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles © Esri — Esri, DeLorme, NAVTEQ',
  },
  dark: {
    id: 'dark',
    label: 'Escuro',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles © Esri — Esri, DeLorme, NAVTEQ',
  },
  satellite: {
    id: 'satellite',
    label: 'Satélite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles © Esri, Maxar, Earthstar Geographics',
  },
}

export const useMapStore = defineStore('map', () => {
  // Mato Grosso — centro aproximado
  const viewport = ref<MapViewport>({
    center: [-55.9, -12.6],
    zoom: 6,
    bearing: 0,
    pitch: 0,
  })

  const mapReady = ref(false)
  const is3D = ref(false)
  const activeBasemap = ref<BasemapId>('osm')

  // Painéis flutuantes (para manter o mapa limpo e desobstruído)
  const showLayers = ref(true)
  const showFilters = ref(false)

  function setViewport(v: Partial<MapViewport>) {
    viewport.value = { ...viewport.value, ...v }
  }

  function flyTo(center: [number, number], zoom?: number) {
    viewport.value = {
      ...viewport.value,
      center,
      zoom: zoom ?? viewport.value.zoom,
    }
  }

  function fitBounds(bounds: [number, number, number, number]) {
    const centerLon = (bounds[0] + bounds[2]) / 2
    const centerLat = (bounds[1] + bounds[3]) / 2
    viewport.value = { ...viewport.value, center: [centerLon, centerLat] }
  }

  function setMapReady(ready: boolean) {
    mapReady.value = ready
  }

  function toggle3D() {
    is3D.value = !is3D.value
    viewport.value = { ...viewport.value, pitch: is3D.value ? 45 : 0 }
  }

  function setBasemap(id: BasemapId) {
    activeBasemap.value = id
  }

  function toggleLayers() {
    showLayers.value = !showLayers.value
  }

  function toggleFilters() {
    showFilters.value = !showFilters.value
  }

  function resetViewport() {
    flyTo([-55.9, -12.6], 6)
    viewport.value = { ...viewport.value, pitch: 0, bearing: 0 }
    is3D.value = false
  }

  return {
    viewport: readonly(viewport),
    mapReady: readonly(mapReady),
    is3D: readonly(is3D),
    activeBasemap: readonly(activeBasemap),
    showLayers,
    showFilters,
    setViewport,
    flyTo,
    fitBounds,
    setMapReady,
    toggle3D,
    setBasemap,
    toggleLayers,
    toggleFilters,
    resetViewport,
  }
})
