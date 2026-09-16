<template>
  <div ref="mapContainer" class="map-container" :class="{ 'map-3d': mapStore.is3D }">
    <!-- Loading overlay -->
    <transition name="fade">
      <div v-if="!mapStore.mapReady" class="map-loading">
        <div class="map-loading__spinner" />
        <p class="map-loading__text">Carregando mapa de Mato Grosso...</p>
      </div>
    </transition>

    <!-- Slot para controles sobrepostos -->
    <slot />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import axios from 'axios'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useMapStore, BASEMAPS, type BasemapId } from '@/stores/mapStore'
import { useLayersStore } from '@/stores/layersStore'
import { useFiltersStore } from '@/stores/filtersStore'
import type { LayerConfig, LayerId } from '@/types/atlas'

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const emit = defineEmits<{
  'feature-click': [layer: LayerId, id: string | number, properties: Record<string, unknown>]
  'map-click': [lngLat: maplibregl.LngLat]
}>()

const mapContainer = ref<HTMLDivElement | null>(null)
const mapStore = useMapStore()
const layersStore = useLayersStore()
const filtersStore = useFiltersStore()

let map: maplibregl.Map | null = null
let popup: maplibregl.Popup | null = null

const CLICKABLE_LAYERS = [
  'setores-fill',
  'escolas-circle',
  'municipios-fill',
  'saude-circle',
  'malha_viaria-line',
  'seguranca-point',
]

// ─── Inicialização do mapa ───────────────────────────────────────────────────

onMounted(async () => {
  if (!mapContainer.value) return

  const initialBasemap = BASEMAPS[mapStore.activeBasemap] || BASEMAPS.light

  map = new maplibregl.Map({
    container: mapContainer.value,
    style: {
      version: 8,
      name: 'RootL Atlas Clean Base',
      sources: {
        'basemap-tiles': {
          type: 'raster',
          tiles: [initialBasemap.url],
          tileSize: 256,
          attribution: initialBasemap.attribution,
          maxzoom: 19,
        },
      },
      layers: [
        {
          id: 'basemap-layer',
          type: 'raster',
          source: 'basemap-tiles',
          paint: {
            'raster-opacity': 1.0,
            'raster-fade-duration': 200,
          },
        },
      ],
    },
    center: [mapStore.viewport.center[0], mapStore.viewport.center[1]],
    zoom: mapStore.viewport.zoom,
    bearing: mapStore.viewport.bearing,
    pitch: mapStore.viewport.pitch,
    attributionControl: false,
    antialias: true,
  })

  // Controles MapLibre nativos limpos e discretos
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true, showCompass: true }), 'bottom-right')
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-left')
  map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left')

  map.on('load', () => {
    mapStore.setMapReady(true)
    addAllLayers()
  })

  // Sincroniza viewport → store
  map.on('moveend', () => {
    if (!map) return
    const c = map.getCenter()
    mapStore.setViewport({
      center: [c.lng, c.lat],
      zoom: map.getZoom(),
      bearing: map.getBearing(),
      pitch: map.getPitch(),
    })
  })

  // Eventos de hover e clique nas camadas
  CLICKABLE_LAYERS.forEach((layerId) => {
    map!.on('click', layerId, handleLayerClick)
    map!.on('mouseenter', layerId, () => {
      if (map) map.getCanvas().style.cursor = 'pointer'
    })
    map!.on('mouseleave', layerId, () => {
      if (map) map.getCanvas().style.cursor = ''
    })
  })

  // Clique no mapa (fora de feição)
  map.on('click', (e) => {
    emit('map-click', e.lngLat)
  })
})

onUnmounted(() => {
  map?.remove()
  map = null
})

// ─── Adição de camadas MVT ───────────────────────────────────────────────────

function addAllLayers() {
  if (!map) return
  layersStore.layers.forEach((layer) => {
    addVectorLayer(layer)
  })
}

function addVectorLayer(cfg: LayerConfig) {
  if (!map) return

  const sourceId = `source-${cfg.id}`
  const fillLayerId = `${cfg.id}-fill`
  const lineLayerId = `${cfg.id}-line`
  const circleLayerId = `${cfg.id}-circle`

  // Adiciona source MVT se não existir
  if (!map.getSource(sourceId)) {
    map.addSource(sourceId, {
      type: 'vector',
      tiles: [cfg.tileUrl],
      minzoom: cfg.minZoom,
      maxzoom: cfg.maxZoom,
    })
  }

  // Pontos (escolas, saúde)
  if (cfg.id === 'escolas' || cfg.id === 'saude') {
    if (!map.getLayer(circleLayerId)) {
      map.addLayer({
        id: circleLayerId,
        type: 'circle',
        source: sourceId,
        'source-layer': cfg.id,
        minzoom: cfg.minZoom,
        paint: {
          'circle-radius': [
            'interpolate', ['linear'], ['zoom'],
            8, 4.0,
            10, 6.0,
            14, 9.0,
            18, 14.0,
          ],
          'circle-color': cfg.color,
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 2,
          'circle-opacity': cfg.opacity,
        },
        layout: { visibility: cfg.visible ? 'visible' : 'none' },
      })
    }
    return
  }

  // Malha viária (linhas)
  if (cfg.id === 'malha_viaria') {
    if (!map.getLayer(lineLayerId)) {
      map.addLayer({
        id: lineLayerId,
        type: 'line',
        source: sourceId,
        'source-layer': 'malha_viaria',
        minzoom: cfg.minZoom,
        maxzoom: cfg.maxZoom,
        paint: {
          'line-color': [
            'match', ['get', 'highway'],
            'motorway', '#dc2626',
            'trunk', '#ea580c',
            'primary', '#f59e0b',
            'secondary', '#10b981',
            'tertiary', '#06b6d4',
            '#64748b'
          ],
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            7, 1.0,
            11, 2.0,
            15, 3.5
          ],
          'line-opacity': cfg.opacity,
        },
        layout: { visibility: cfg.visible ? 'visible' : 'none' },
      })
    }
    return
  }

  // Polígonos (setores, municípios)
  const colorExpr = cfg.id === 'setores'
    ? filtersStore.getAccessibilityColorExpression(filtersStore.accessibilityThresholdKm)
    : cfg.color

  if (!map.getLayer(fillLayerId)) {
    map.addLayer({
      id: fillLayerId,
      type: 'fill',
      source: sourceId,
      'source-layer': cfg.id === 'municipios' ? 'municipios' : 'setores_censitarios',
      minzoom: cfg.minZoom,
      maxzoom: cfg.maxZoom,
      paint: {
        'fill-color': colorExpr as string,
        'fill-opacity': cfg.id === 'municipios'
          ? 0.12
          : ['interpolate', ['linear'], ['zoom'], cfg.minZoom, 0.4, cfg.minZoom + 1, cfg.opacity],
      },
      layout: { visibility: cfg.visible ? 'visible' : 'none' },
    })
  }

  if (!map.getLayer(lineLayerId)) {
    map.addLayer({
      id: lineLayerId,
      type: 'line',
      source: sourceId,
      'source-layer': cfg.id === 'municipios' ? 'municipios' : 'setores_censitarios',
      minzoom: cfg.minZoom,
      paint: {
        'line-color': cfg.id === 'municipios' ? '#2563eb' : '#475569',
        'line-width': cfg.id === 'municipios'
          ? ['interpolate', ['linear'], ['zoom'], 4, 1.5, 8, 2.2, 14, 3.0]
          : ['interpolate', ['linear'], ['zoom'], cfg.minZoom, 0.5, 14, 1.2],
        'line-opacity': cfg.id === 'municipios' ? 0.95 : 0.7,
      },
      layout: { visibility: cfg.visible ? 'visible' : 'none' },
    })
  }
}

// ─── Evento de clique em feição ──────────────────────────────────────────────

function handleLayerClick(e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) {
  if (!e.features || e.features.length === 0) return
  const feat = e.features[0]
  const layerIdParts = feat.layer.id.split('-')
  const layerId = layerIdParts.slice(0, -1).join('-') as LayerId
  const props = feat.properties ?? {}

  const featureId: string | number =
    props['cd_setor'] ??
    props['co_entidade'] ??
    props['co_cnes'] ??
    props['osm_id'] ??
    props['cd_municipio'] ??
    feat.id ??
    ''

  // Popup limpo e direto no mapa
  popup?.remove()
  popup = new maplibregl.Popup({
    closeButton: true,
    closeOnClick: true,
    maxWidth: '280px',
    offset: 12,
  })
    .setLngLat(e.lngLat)
    .setHTML(buildPopupHTML(layerId, props))
    .addTo(map!)

  emit('feature-click', layerId, featureId, props)
}

function buildPopupHTML(layer: string, props: Record<string, unknown>): string {
  if (layer === 'municipios') {
    return `
      <div class="clean-popup">
        <div class="clean-popup__badge">Município</div>
        <h4 class="clean-popup__title">${props['nm_municipio'] ?? 'Município'}</h4>
        <div class="clean-popup__rows">
          <div class="clean-popup__row">
            <span>Código IBGE</span>
            <strong>${props['cd_municipio'] ?? ''}</strong>
          </div>
          <div class="clean-popup__row">
            <span>População (2022)</span>
            <strong>${props['populacao_2022'] ? Number(props['populacao_2022']).toLocaleString('pt-BR') : '—'}</strong>
          </div>
          ${props['area_km2'] ? `
          <div class="clean-popup__row">
            <span>Área territorial</span>
            <strong>${Number(props['area_km2']).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} km²</strong>
          </div>` : ''}
        </div>
      </div>
    `
  }

  if (layer === 'setores') {
    return `
      <div class="clean-popup">
        <div class="clean-popup__badge">Setor Censitário</div>
        <h4 class="clean-popup__title">${props['nm_municipio'] ?? 'Setor'}</h4>
        <div class="clean-popup__rows">
          <div class="clean-popup__row">
            <span>Código</span>
            <strong>${props['cd_setor'] ?? ''}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Tipologia</span>
            <strong>${props['nm_tipo_setor'] ?? 'Urbano/Rural'}</strong>
          </div>
          <div class="clean-popup__row">
            <span>População</span>
            <strong>${Number(props['pop_total'] ?? 0).toLocaleString('pt-BR')}</strong>
          </div>
          ${props['dist_escola_km'] != null ? `
          <div class="clean-popup__row">
            <span>Escola mais próxima</span>
            <strong>${Number(props['dist_escola_km']).toFixed(1)} km</strong>
          </div>` : ''}
        </div>
      </div>
    `
  }

  if (layer === 'escolas') {
    return `
      <div class="clean-popup">
        <div class="clean-popup__badge">Escola</div>
        <h4 class="clean-popup__title">${props['no_entidade'] ?? 'Escola'}</h4>
        <div class="clean-popup__rows">
          <div class="clean-popup__row">
            <span>Rede</span>
            <strong>${props['nm_dependencia'] ?? '—'}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Município</span>
            <strong>${props['no_municipio'] ?? '—'}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Matrículas</span>
            <strong>${Number(props['qt_mat_bas'] ?? 0).toLocaleString('pt-BR')}</strong>
          </div>
        </div>
      </div>
    `
  }

  if (layer === 'saude') {
    return `
      <div class="clean-popup">
        <div class="clean-popup__badge" style="background: rgba(239, 68, 68, 0.12); color: #ef4444;">Saúde (CNES)</div>
        <h4 class="clean-popup__title">${props['no_fantasia'] ?? 'Unidade de Saúde'}</h4>
        <div class="clean-popup__rows">
          <div class="clean-popup__row">
            <span>Tipo</span>
            <strong>${props['nm_tp_unidade'] ?? '—'}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Gestão</span>
            <strong>${props['tp_gestao'] ?? '—'}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Leitos</span>
            <strong>${props['qt_leitos_total'] ?? 0}</strong>
          </div>
        </div>
      </div>
    `
  }

  if (layer === 'malha_viaria') {
    return `
      <div class="clean-popup">
        <div class="clean-popup__badge" style="background: rgba(16, 185, 129, 0.12); color: #10b981;">Malha Viária (OSM)</div>
        <h4 class="clean-popup__title">${props['name'] || props['highway'] || 'Via'}</h4>
        <div class="clean-popup__rows">
          <div class="clean-popup__row">
            <span>Tipo</span>
            <strong>${props['highway'] ?? '—'}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Sentido Único</span>
            <strong>${props['oneway'] ? 'Sim' : 'Não'}</strong>
          </div>
        </div>
      </div>
    `
  }

  return `<div class="clean-popup"><h4 class="clean-popup__title">${layer}</h4></div>`
}

// ─── Watchers: sincroniza store → mapa ──────────────────────────────────────

// Troca de Basemap (Claro / Escuro / OSM)
watch(
  () => mapStore.activeBasemap,
  (newBasemapId: BasemapId) => {
    if (!map || !mapStore.mapReady) return
    const cfg = BASEMAPS[newBasemapId]
    if (!cfg) return

    // Atualiza raster tiles do basemap
    if (map.getLayer('basemap-layer')) map.removeLayer('basemap-layer')
    if (map.getSource('basemap-tiles')) map.removeSource('basemap-tiles')

    map.addSource('basemap-tiles', {
      type: 'raster',
      tiles: [cfg.url],
      tileSize: 256,
      attribution: cfg.attribution,
      maxzoom: 19,
    })

    // Insere o basemap atrás de todas as camadas vetoriais existentes
    const layers = map.getStyle().layers || []
    let firstVectorLayerId: string | undefined
    for (const l of layers) {
      if (l.id.includes('-fill') || l.id.includes('-line') || l.id.includes('-circle')) {
        firstVectorLayerId = l.id
        break
      }
    }

    map.addLayer(
      {
        id: 'basemap-layer',
        type: 'raster',
        source: 'basemap-tiles',
        paint: {
          'raster-opacity': 1.0,
          'raster-fade-duration': 150,
        },
      },
      firstVectorLayerId
    )
  }
)

// Visibilidade e opacidade das camadas
watch(
  () => layersStore.layers,
  (layers) => {
    if (!map || !mapStore.mapReady) return
    layers.forEach((cfg) => {
      const fillId = `${cfg.id}-fill`
      const lineId = `${cfg.id}-line`
      const circleId = `${cfg.id}-circle`

      const vis = cfg.visible ? 'visible' : 'none'
      if (map!.getLayer(fillId)) {
        map!.setLayoutProperty(fillId, 'visibility', vis)
        map!.setLayoutProperty(lineId, 'visibility', vis)
        if (cfg.id !== 'municipios') {
          map!.setPaintProperty(fillId, 'fill-opacity', cfg.opacity)
        }
      }
      if (map!.getLayer(circleId)) {
        map!.setLayoutProperty(circleId, 'visibility', vis)
        map!.setPaintProperty(circleId, 'circle-opacity', cfg.opacity)
      }
    })
  },
  { deep: true }
)

// Limiar de acessibilidade → atualiza cor dos setores instantaneamente
watch(
  () => filtersStore.accessibilityThresholdKm,
  (km) => {
    if (!map || !mapStore.mapReady) return
    const fillId = 'setores-fill'
    if (map.getLayer(fillId)) {
      map.setPaintProperty(
        fillId,
        'fill-color',
        filtersStore.getAccessibilityColorExpression(km)
      )
    }
  }
)

// Viewport externo → fly-to
watch(
  () => mapStore.viewport,
  (v) => {
    if (!map) return
    const curr = map.getCenter()
    if (
      Math.abs(curr.lng - v.center[0]) > 0.001 ||
      Math.abs(curr.lat - v.center[1]) > 0.001
    ) {
      map.flyTo({ center: [v.center[0], v.center[1]], zoom: v.zoom, pitch: v.pitch, bearing: v.bearing })
    }
  },
  { deep: true }
)
</script>

<style scoped>
.map-container {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #f8fafc;
}

.map-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(248, 250, 252, 0.9);
  backdrop-filter: blur(8px);
  z-index: 100;
  gap: 0.75rem;
}

.map-loading__spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.map-loading__text {
  color: #475569;
  font-size: 0.85rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

<style>
/* Popups MapLibre — Design Minimalista e Limpo */
.maplibregl-popup-content {
  background: rgba(255, 255, 255, 0.98) !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 10px !important;
  color: #0f172a !important;
  padding: 0 !important;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1) !important;
}

.maplibregl-popup-close-button {
  font-size: 16px !important;
  color: #94a3b8 !important;
  padding: 4px 8px !important;
}
.maplibregl-popup-close-button:hover {
  color: #0f172a !important;
  background: none !important;
}

.maplibregl-popup-tip {
  border-top-color: rgba(255, 255, 255, 0.98) !important;
}

.clean-popup {
  padding: 0.85rem 1rem;
}

.clean-popup__badge {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #2563eb;
  background: #eff6ff;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  margin-bottom: 0.35rem;
}

.clean-popup__title {
  font-size: 0.9rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 0.5rem;
  line-height: 1.3;
}

.clean-popup__rows {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  border-top: 1px solid #f1f5f9;
  padding-top: 0.4rem;
}

.clean-popup__row {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #64748b;
}

.clean-popup__row strong {
  color: #1e293b;
  font-weight: 600;
  text-align: right;
  margin-left: 0.5rem;
}
</style>
