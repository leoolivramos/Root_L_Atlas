// stores/layersStore.ts — Camadas ativas, opacidade, estilo data-driven
import { defineStore } from 'pinia'
import { ref, computed, readonly } from 'vue'
import type { LayerConfig, LayerId } from '@/types/atlas'

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const DEFAULT_LAYERS: LayerConfig[] = [
  {
    id: 'municipios',
    label: 'Municípios',
    tileUrl: `${API}/tiles/municipios/{z}/{x}/{y}`,
    minZoom: 4,
    maxZoom: 18,
    visible: true,
    opacity: 0.18,
    color: '#2563eb',
  },
  {
    id: 'setores',
    label: 'Setores Censitários',
    tileUrl: `${API}/tiles/setores/{z}/{x}/{y}`,
    minZoom: 4,
    maxZoom: 18,
    visible: false,
    opacity: 0.4,
    color: '#8b5cf6',
  },
  {
    id: 'escolas',
    label: 'Escolas (INEP)',
    tileUrl: `${API}/tiles/escolas/{z}/{x}/{y}`,
    minZoom: 8,
    maxZoom: 18,
    visible: false,
    opacity: 1.0,
    color: '#d97706',
  },
  {
    id: 'saude',
    label: 'Saúde (CNES)',
    tileUrl: `${API}/tiles/saude/{z}/{x}/{y}`,
    minZoom: 8,
    maxZoom: 18,
    visible: false,
    opacity: 1.0,
    color: '#ef4444',
  },
  {
    id: 'malha_viaria',
    label: 'Malha Viária (OSM)',
    tileUrl: `${API}/tiles/malha_viaria/{z}/{x}/{y}`,
    minZoom: 5,
    maxZoom: 18,
    visible: false,
    opacity: 0.75,
    color: '#10b981',
  },
  {
    id: 'seguranca',
    label: 'Segurança (SINESP)',
    tileUrl: '',
    minZoom: 4,
    maxZoom: 18,
    visible: false,
    opacity: 0.85,
    color: '#ef4444',
  },
  {
    id: 'queimadas',
    label: 'Queimadas (INPE)',
    tileUrl: `${API}/tiles/queimadas/{z}/{x}/{y}`,
    minZoom: 5,
    maxZoom: 18,
    visible: false,
    opacity: 0.9,
    color: '#f97316',
  },
]

export const useLayersStore = defineStore('layers', () => {
  const layers = ref<LayerConfig[]>(structuredClone(DEFAULT_LAYERS))

  const visibleLayers = computed(() => layers.value.filter((l) => l.visible))

  function toggleLayer(id: LayerId) {
    const layer = layers.value.find((l) => l.id === id)
    if (layer) layer.visible = !layer.visible
  }

  function setOpacity(id: LayerId, opacity: number) {
    const layer = layers.value.find((l) => l.id === id)
    if (layer) layer.opacity = Math.max(0, Math.min(1, opacity))
  }

  function setLayerColor(id: LayerId, color: string) {
    const layer = layers.value.find((l) => l.id === id)
    if (layer) layer.color = color
  }

  function getLayer(id: LayerId): LayerConfig | undefined {
    return layers.value.find((l) => l.id === id)
  }

  return {
    layers: readonly(layers),
    visibleLayers,
    toggleLayer,
    setOpacity,
    setLayerColor,
    getLayer,
  }
})
