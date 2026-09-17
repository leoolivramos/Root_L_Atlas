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
  'seguranca-choropleth',  // camada principal do choropleth de segurança
  'queimadas-circle',      // pontos MVT individuais de focos de queimada
  'queimadas-choropleth',  // polígono municipal agregado de queimadas
]

// ─── Inicialização do mapa ───────────────────────────────────────────────────

onMounted(async () => {
  if (!mapContainer.value) return

  const initialBasemap = BASEMAPS[mapStore.activeBasemap] || BASEMAPS.osm

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

    // Registra eventos de click e hover APÓS as layers serem criadas pelo addAllLayers()
    CLICKABLE_LAYERS.forEach((layerId) => {
      map!.on('click', layerId, handleLayerClick)
      map!.on('mouseenter', layerId, () => {
        if (map) map.getCanvas().style.cursor = 'pointer'
      })
      map!.on('mouseleave', layerId, () => {
        if (map) map.getCanvas().style.cursor = ''
      })
    })
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

// ——— Segurança: Choropleth Municipal —————————————————————————————————————

async function updateSegurancaChoropleth() {
  if (!map || !mapStore.mapReady) return
  const segCfg = layersStore.getLayer('seguranca')
  if (!segCfg?.visible) return

  try {
    const params: Record<string, string | number> = {
      metrica: filtersStore.segurancaMetrica,
    }
    if (filtersStore.segurancaAno !== null) params.ano = filtersStore.segurancaAno
    if (filtersStore.segurancaTipoCrime && filtersStore.segurancaTipoCrime !== 'todos') {
      params.tipo_crime = filtersStore.segurancaTipoCrime
    }
    if (filtersStore.segurancaMes !== null) params.mes = filtersStore.segurancaMes

    const res = await axios.get(`${API}/features/seguranca/heatmap`, { params })
    const source = map.getSource('source-seguranca') as maplibregl.GeoJSONSource
    if (source && res.data) {
      source.setData(res.data)
    }
  } catch (e) {
    console.warn('Erro ao atualizar choropleth de segurança:', e)
  }
}

function addSegurancaChoroplethLayer(cfg: LayerConfig) {
  if (!map) return

  const sourceId = 'source-seguranca'
  const choroplethId = 'seguranca-choropleth'   // fill de polígono municipal
  const strokeId = 'seguranca-stroke'            // borda dos municípios

  if (!map.getSource(sourceId)) {
    map.addSource(sourceId, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  }

  // Fill: polígono municipal colorido por intensidade
  if (!map.getLayer(choroplethId)) {
    map.addLayer({
      id: choroplethId,
      type: 'fill',
      source: sourceId,
      paint: {
        'fill-color': [
          'interpolate', ['linear'], ['get', 'weight'],
          0,   'rgba(240, 249, 255, 0.1)',
          0.1, '#bfdbfe',
          0.3, '#60a5fa',
          0.5, '#f59e0b',
          0.7, '#ef4444',
          1.0, '#7f1d1d',
        ],
        'fill-opacity': [
          'case',
          ['>', ['get', 'weight'], 0], cfg.opacity * 0.82,
          0.05,
        ],
      },
      layout: { visibility: cfg.visible ? 'visible' : 'none' },
    })
  }

  // Borda dos municípios
  if (!map.getLayer(strokeId)) {
    map.addLayer({
      id: strokeId,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': [
          'interpolate', ['linear'], ['get', 'weight'],
          0,   '#94a3b8',
          0.5, '#f87171',
          1.0, '#7f1d1d',
        ],
        'line-width': [
          'interpolate', ['linear'], ['zoom'],
          4, 0.5,
          8, 1.0,
          12, 1.5,
        ],
        'line-opacity': 0.7,
      },
      layout: { visibility: cfg.visible ? 'visible' : 'none' },
    })
  }

  if (cfg.visible) {
    updateSegurancaChoropleth()
  }
}

// ——— Queimadas: Choropleth Municipal + Pontos MVT ——————————————————————————

async function updateQueimadasChoropleth() {
  if (!map || !mapStore.mapReady) return
  const qCfg = layersStore.getLayer('queimadas')
  if (!qCfg?.visible) return

  try {
    const params: Record<string, string | number | boolean> = {
      metrica: filtersStore.queimadasMetrica,
    }
    if (filtersStore.queimadasAno !== null) params.ano = filtersStore.queimadasAno
    if (filtersStore.queimadasMes !== null) params.mes = filtersStore.queimadasMes
    if (filtersStore.queimadasBioma && filtersStore.queimadasBioma !== 'todos') {
      params.bioma = filtersStore.queimadasBioma
    }
    if (filtersStore.queimadasApenasReferencia) {
      params.apenas_referencia = true
    }

    const res = await axios.get(`${API}/features/queimadas/heatmap`, { params })
    const source = map.getSource('source-queimadas-choropleth') as maplibregl.GeoJSONSource
    if (source && res.data) {
      source.setData(res.data)
    }
  } catch (e) {
    console.warn('Erro ao atualizar choropleth de queimadas:', e)
  }
}

function updateQueimadasPointsFilter() {
  if (!map || !mapStore.mapReady) return
  const circleId = 'queimadas-circle'
  if (!map.getLayer(circleId)) return

  const conditions: any[] = ['all']

  if (filtersStore.queimadasBioma && filtersStore.queimadasBioma !== 'todos') {
    conditions.push(['==', ['get', 'bioma'], filtersStore.queimadasBioma])
  }
  if (filtersStore.queimadasApenasReferencia) {
    conditions.push(['==', ['get', 'is_referencia'], true])
  }
  if (filtersStore.queimadasAno !== null) {
    conditions.push(['==', ['to-number', ['get', 'ano']], filtersStore.queimadasAno])
  }
  if (filtersStore.queimadasMes !== null) {
    conditions.push(['==', ['to-number', ['get', 'mes']], filtersStore.queimadasMes])
  }

  if (conditions.length > 1) {
    map.setFilter(circleId, conditions as any)
  } else {
    map.setFilter(circleId, null)
  }
}

function addQueimadasLayers(cfg: LayerConfig) {
  if (!map) return

  // 1. Camada de Choropleth Municipal (GeoJSON)
  const choroplethSourceId = 'source-queimadas-choropleth'
  const choroplethId = 'queimadas-choropleth'
  const strokeId = 'queimadas-stroke'

  if (!map.getSource(choroplethSourceId)) {
    map.addSource(choroplethSourceId, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  }

  if (!map.getLayer(choroplethId)) {
    map.addLayer({
      id: choroplethId,
      type: 'fill',
      source: choroplethSourceId,
      maxzoom: 12,
      paint: {
        'fill-color': [
          'interpolate', ['linear'], ['get', 'weight'],
          0,    'rgba(254, 240, 138, 0.04)',
          0.15, '#fef08a',
          0.35, '#f59e0b',
          0.6,  '#ea580c',
          0.85, '#dc2626',
          1.0,  '#7f1d1d',
        ],
        'fill-opacity': [
          'case',
          ['>', ['get', 'weight'], 0], cfg.opacity * 0.72,
          0.04,
        ],
      },
      layout: { visibility: cfg.visible ? 'visible' : 'none' },
    })
  }

  if (!map.getLayer(strokeId)) {
    map.addLayer({
      id: strokeId,
      type: 'line',
      source: choroplethSourceId,
      maxzoom: 12,
      paint: {
        'line-color': [
          'interpolate', ['linear'], ['get', 'weight'],
          0,   '#cbd5e1',
          0.5, '#ea580c',
          1.0, '#7f1d1d',
        ],
        'line-width': [
          'interpolate', ['linear'], ['zoom'],
          4, 0.5,
          8, 1.0,
          12, 1.5,
        ],
        'line-opacity': 0.65,
      },
      layout: { visibility: cfg.visible ? 'visible' : 'none' },
    })
  }

  // 2. Camada MVT de Pontos Individuais de Focos
  const mvtSourceId = `source-${cfg.id}`
  const circleId = `${cfg.id}-circle`

  if (!map.getSource(mvtSourceId)) {
    map.addSource(mvtSourceId, {
      type: 'vector',
      tiles: [cfg.tileUrl],
      scheme: 'xyz',
      minzoom: cfg.minZoom,
      maxzoom: cfg.maxZoom,
    })
  }

  if (!map.getLayer(circleId)) {
    map.addLayer({
      id: circleId,
      type: 'circle',
      source: mvtSourceId,
      'source-layer': 'queimadas',
      minzoom: cfg.minZoom,
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          5, 2.5,
          8, 4.2,
          11, 6.5,
          14, 9.5,
          18, 14.0,
        ],
        'circle-color': [
          'interpolate', ['linear'], ['coalesce', ['to-number', ['get', 'frp']], 15],
          0,   '#fef08a',
          25,  '#f59e0b',
          60,  '#ea580c',
          120, '#dc2626',
          300, '#7f1d1d',
        ],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': [
          'interpolate', ['linear'], ['zoom'],
          5, 0.4,
          8, 0.8,
          12, 1.5,
        ],
        'circle-opacity': cfg.opacity,
      },
      layout: { visibility: cfg.visible ? 'visible' : 'none' },
    })
  }

  if (cfg.visible) {
    updateQueimadasChoropleth()
    updateQueimadasPointsFilter()
  }
}

function addVectorLayer(cfg: LayerConfig) {
  if (!map) return

  if (cfg.id === 'seguranca') {
    addSegurancaChoroplethLayer(cfg)
    return
  }

  if (cfg.id === 'queimadas') {
    addQueimadasLayers(cfg)
    return
  }

  const sourceId = `source-${cfg.id}`
  const fillLayerId = `${cfg.id}-fill`
  const lineLayerId = `${cfg.id}-line`
  const circleLayerId = `${cfg.id}-circle`

  // Adiciona source MVT se não existir
  if (!map.getSource(sourceId)) {
    map.addSource(sourceId, {
      type: 'vector',
      tiles: [cfg.tileUrl],
      scheme: 'xyz',
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

  // Malha viária (linhas) — source-layer 'malha_viaria' conforme ST_AsMVT
  if (cfg.id === 'malha_viaria') {
    if (!map.getLayer(lineLayerId)) {
      map.addLayer({
        id: lineLayerId,
        type: 'line',
        source: sourceId,
        'source-layer': 'malha_viaria',
        minzoom: cfg.minZoom,
        paint: {
          'line-color': [
            'match', ['get', 'highway'],
            'motorway', '#dc2626',
            'trunk', '#ea580c',
            'primary', '#f59e0b',
            'secondary', '#10b981',
            'tertiary', '#06b6d4',
            '#94a3b8'
          ],
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            5, 0.8,
            7, 1.2,
            10, 2.0,
            12, 2.8,
            15, 4.0
          ],
          'line-opacity': [
            'interpolate', ['linear'], ['zoom'],
            5, 0.65,
            7, 0.8,
            10, 0.9,
            13, cfg.opacity,
          ],
        },
        layout: {
          visibility: cfg.visible ? 'visible' : 'none',
          'line-cap': 'round',
          'line-join': 'round',
        },
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
          <div class="clean-popup__row">
            <span>Domicílios</span>
            <strong>${Number(props['domicilios_total'] ?? 0).toLocaleString('pt-BR')}</strong>
          </div>
          ${props['renda_media_domicilio'] != null ? `
          <div class="clean-popup__row">
            <span>Renda Média</span>
            <strong>R$ ${Number(props['renda_media_domicilio']).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
          </div>` : ''}
          ${props['area_km2'] != null ? `
          <div class="clean-popup__row">
            <span>Área</span>
            <strong>${Number(props['area_km2']).toFixed(2)} km²</strong>
          </div>` : ''}
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
    const nome = (props['no_fantasia'] && String(props['no_fantasia']).trim())
      || (props['no_razao_social'] && String(props['no_razao_social']).trim())
      || 'Unidade de Saúde'
    return `
      <div class="clean-popup">
        <div class="clean-popup__badge" style="background: rgba(239, 68, 68, 0.12); color: #ef4444;">Saúde (CNES)</div>
        <h4 class="clean-popup__title">${nome}</h4>
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
            <span>Município</span>
            <strong>${props['no_municipio'] ?? '—'}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Leitos</span>
            <strong>${props['qt_leitos_total'] ?? 0}</strong>
          </div>
          ${props['qt_leitos_sus'] != null ? `
          <div class="clean-popup__row">
            <span>Leitos SUS</span>
            <strong>${props['qt_leitos_sus']}</strong>
          </div>` : ''}
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

  if (layer === 'seguranca') {
    const metricLabel = filtersStore.segurancaMetrica === 'ocorrencias' ? 'Ocorrências' : 'Vítimas'
    const crimeLabel = filtersStore.segurancaTipoCrime === 'todos' ? 'Todos os crimes' : filtersStore.segurancaTipoCrime
    const val = Number(props['val'] ?? props['qtd_ocorrencias'] ?? 0).toLocaleString('pt-BR')
    const vitimas = Number(props['qtd_vitimas'] ?? 0).toLocaleString('pt-BR')
    const taxa = props['taxa_100k'] != null ? Number(props['taxa_100k']).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) : '—'
    const periodo = filtersStore.segurancaAno ? `${filtersStore.segurancaAno}` : 'Todos os anos'
    const mesTxt = filtersStore.segurancaMes ? ` · Mês ${filtersStore.segurancaMes}` : ''

    return `
      <div class="clean-popup">
        <div class="clean-popup__badge" style="background: rgba(239, 68, 68, 0.12); color: #ef4444;">Segurança Pública (SINESP)</div>
        <h4 class="clean-popup__title">${props['nm_municipio'] ?? 'Município'}</h4>
        <div class="clean-popup__rows">
          <div class="clean-popup__row">
            <span>${metricLabel}</span>
            <strong style="color: #ef4444; font-size: 0.95rem;">${val}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Taxa (por 100k hab.)</span>
            <strong>${taxa}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Tipo de Crime</span>
            <strong style="max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${crimeLabel}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Período</span>
            <strong>${periodo}${mesTxt}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Total de Vítimas</span>
            <strong>${vitimas}</strong>
          </div>
        </div>
      </div>
    `
  }

  if (layer === 'queimadas') {
    // Se for ponto individual (possui satélite)
    if (props['satelite']) {
      const isRef = props['is_referencia'] === true || props['is_referencia'] === 'true'
      const frpVal = props['frp'] != null && props['frp'] !== '' ? `${Number(props['frp']).toFixed(1)} MW` : '—'
      const riscoVal = props['risco_fogo'] != null && props['risco_fogo'] !== '' ? Number(props['risco_fogo']).toFixed(2) : '—'
      const diasChuva = props['numero_dias_sem_chuva'] != null && Number(props['numero_dias_sem_chuva']) >= 0
        ? `${props['numero_dias_sem_chuva']} dias`
        : '—'
      const dataHora = props['data_hora_gmt']
        ? String(props['data_hora_gmt']).replace('T', ' ').slice(0, 19)
        : '—'

      return `
        <div class="clean-popup">
          <div class="clean-popup__badge" style="background: rgba(234, 88, 12, 0.12); color: #ea580c;">Foco de Calor (INPE)</div>
          <h4 class="clean-popup__title">${props['municipio'] ?? 'Mato Grosso'}</h4>
          <div class="clean-popup__rows">
            <div class="clean-popup__row">
              <span>Satélite</span>
              <strong>${props['satelite']}${isRef ? ' (Ref.)' : ''}</strong>
            </div>
            <div class="clean-popup__row">
              <span>Data / Hora (GMT)</span>
              <strong>${dataHora}</strong>
            </div>
            <div class="clean-popup__row">
              <span>Bioma</span>
              <strong>${props['bioma'] ?? '—'}</strong>
            </div>
            <div class="clean-popup__row">
              <span>Potência (FRP)</span>
              <strong style="color: #ea580c;">${frpVal}</strong>
            </div>
            <div class="clean-popup__row">
              <span>Risco de Fogo</span>
              <strong>${riscoVal}</strong>
            </div>
            <div class="clean-popup__row">
              <span>Sem Chuva</span>
              <strong>${diasChuva}</strong>
            </div>
          </div>
        </div>
      `
    }

    // Se for choropleth municipal
    const metricaLabels: Record<string, string> = {
      focos: 'Total de Focos',
      frp_medio: 'FRP Médio',
      risco_medio: 'Risco Médio',
    }
    const mLabel = metricaLabels[filtersStore.queimadasMetrica] || 'Total de Focos'
    const focosTot = Number(props['val'] ?? props['total_focos'] ?? 0).toLocaleString('pt-BR')
    const focosRef = Number(props['focos_referencia'] ?? 0).toLocaleString('pt-BR')
    const frpMed = props['frp_medio'] != null ? `${Number(props['frp_medio']).toFixed(1)} MW` : '—'
    const riscoMed = props['risco_fogo_medio'] != null ? Number(props['risco_fogo_medio']).toFixed(2) : '—'
    const anoTxt = filtersStore.queimadasAno ? `${filtersStore.queimadasAno}` : 'Todos os anos'
    const mesTxt = filtersStore.queimadasMes ? ` · Mês ${filtersStore.queimadasMes}` : ''

    return `
      <div class="clean-popup">
        <div class="clean-popup__badge" style="background: rgba(234, 88, 12, 0.12); color: #ea580c;">Queimadas no Município</div>
        <h4 class="clean-popup__title">${props['nm_municipio'] ?? 'Município'}</h4>
        <div class="clean-popup__rows">
          <div class="clean-popup__row">
            <span>${mLabel}</span>
            <strong style="color: #ea580c; font-size: 0.95rem;">${focosTot}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Satélite Referência</span>
            <strong>${focosRef}</strong>
          </div>
          <div class="clean-popup__row">
            <span>FRP Médio</span>
            <strong>${frpMed}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Risco de Fogo Médio</span>
            <strong>${riscoMed}</strong>
          </div>
          <div class="clean-popup__row">
            <span>Período</span>
            <strong>${anoTxt}${mesTxt}</strong>
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

    // Insere o basemap atrás de todas as camadas existentes
    const layers = map.getStyle().layers || []
    let firstVectorLayerId: string | undefined
    for (const l of layers) {
      if (
        l.id.includes('-fill') ||
        l.id.includes('-line') ||
        l.id.includes('-circle') ||
        l.id.includes('-heat') ||
        l.id.includes('-point')
      ) {
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
      if (cfg.id === 'seguranca') {
        const choroplethId = 'seguranca-choropleth'
        const strokeId = 'seguranca-stroke'
        const vis = cfg.visible ? 'visible' : 'none'
        if (map!.getLayer(choroplethId)) {
          map!.setLayoutProperty(choroplethId, 'visibility', vis)
          map!.setPaintProperty(choroplethId, 'fill-opacity', [
            'case',
            ['>', ['get', 'weight'], 0], cfg.opacity * 0.82,
            0.05,
          ])
        }
        if (map!.getLayer(strokeId)) {
          map!.setLayoutProperty(strokeId, 'visibility', vis)
        }
        if (cfg.visible) {
          updateSegurancaChoropleth()
        }
        return
      }

      if (cfg.id === 'queimadas') {
        const choroplethId = 'queimadas-choropleth'
        const strokeId = 'queimadas-stroke'
        const circleId = 'queimadas-circle'
        const vis = cfg.visible ? 'visible' : 'none'
        if (map!.getLayer(choroplethId)) {
          map!.setLayoutProperty(choroplethId, 'visibility', vis)
          map!.setPaintProperty(choroplethId, 'fill-opacity', [
            'case',
            ['>', ['get', 'weight'], 0], cfg.opacity * 0.72,
            0.04,
          ])
        }
        if (map!.getLayer(strokeId)) {
          map!.setLayoutProperty(strokeId, 'visibility', vis)
        }
        if (map!.getLayer(circleId)) {
          map!.setLayoutProperty(circleId, 'visibility', vis)
          map!.setPaintProperty(circleId, 'circle-opacity', cfg.opacity)
        }
        if (cfg.visible) {
          updateQueimadasChoropleth()
          updateQueimadasPointsFilter()
        }
        return
      }

      const fillId = `${cfg.id}-fill`
      const lineId = `${cfg.id}-line`
      const circleId = `${cfg.id}-circle`

      const vis = cfg.visible ? 'visible' : 'none'

      // Polígonos (fill)
      if (map!.getLayer(fillId)) {
        map!.setLayoutProperty(fillId, 'visibility', vis)
        if (cfg.id !== 'municipios') {
          map!.setPaintProperty(fillId, 'fill-opacity', cfg.opacity)
          if (cfg.id === 'setores') {
            map!.setPaintProperty(
              fillId,
              'fill-color',
              filtersStore.getAccessibilityColorExpression(filtersStore.accessibilityThresholdKm)
            )
          }
        }
      }

      // Linhas (malha viária, contornos de municípios e setores)
      if (map!.getLayer(lineId)) {
        map!.setLayoutProperty(lineId, 'visibility', vis)
        if (cfg.id === 'malha_viaria') {
          map!.setPaintProperty(lineId, 'line-opacity', [
            'interpolate', ['linear'], ['zoom'],
            5, 0.65 * cfg.opacity,
            7, 0.8 * cfg.opacity,
            10, 0.9 * cfg.opacity,
            13, cfg.opacity,
          ])
        }
      }

      // Círculos (pontos de escolas, saúde)
      if (map!.getLayer(circleId)) {
        map!.setLayoutProperty(circleId, 'visibility', vis)
        map!.setPaintProperty(circleId, 'circle-opacity', cfg.opacity)
      }
    })
  },
  { deep: true }
)

// Filtros de segurança SINESP → atualiza dados do choropleth
watch(
  [
    () => filtersStore.segurancaMetrica,
    () => filtersStore.segurancaAno,
    () => filtersStore.segurancaTipoCrime,
    () => filtersStore.segurancaMes,
  ],
  () => {
    if (!mapStore.mapReady) return
    updateSegurancaChoropleth()
  }
)

// Filtros de queimadas INPE → atualiza choropleth e pontos
watch(
  [
    () => filtersStore.queimadasMetrica,
    () => filtersStore.queimadasAno,
    () => filtersStore.queimadasMes,
    () => filtersStore.queimadasBioma,
    () => filtersStore.queimadasApenasReferencia,
  ],
  () => {
    if (!mapStore.mapReady) return
    updateQueimadasChoropleth()
    updateQueimadasPointsFilter()
  }
)

// ─── Filtros de Escolas (Rede + Etapas de Ensino) ───────────────────────────
function updateEscolasFilter() {
  if (!map || !mapStore.mapReady) return
  const circleId = 'escolas-circle'
  if (!map.getLayer(circleId)) return

  const conditions: any[] = ['all']

  // 1. Rede de ensino
  const rede = filtersStore.educationNetwork
  const depMap: Record<string, number[]> = {
    todas: [1, 2, 3, 4],
    publica: [1, 2, 3],
    federal: [1],
    estadual: [2],
    municipal: [3],
    privada: [4],
  }
  const deps = depMap[rede] ?? [1, 2, 3, 4]
  if (deps.length < 4) {
    conditions.push(['in', ['to-number', ['get', 'tp_dependencia']], ['literal', deps]])
  }

  // 2. Etapas de ensino (booleanos da tabela de escolas)
  const stages = filtersStore.educationStages
  if (stages.length > 0) {
    const stageConditions: any[] = ['any']
    stages.forEach((stage) => {
      if (stage === 'creche') {
        stageConditions.push(['==', ['get', 'in_inf_creche'], true])
      } else if (stage === 'pre_escola') {
        stageConditions.push(['==', ['get', 'in_inf_pre_escola'], true])
      } else if (stage === 'fund_ai') {
        stageConditions.push(['==', ['get', 'in_fund_anos_iniciais'], true])
      } else if (stage === 'fund_af') {
        stageConditions.push(['==', ['get', 'in_fund_anos_finais'], true])
      } else if (stage === 'medio') {
        stageConditions.push(['any', ['==', ['get', 'in_medio_regular'], true], ['==', ['get', 'in_medio_integrado'], true]])
      } else if (stage === 'eja') {
        stageConditions.push(['==', ['get', 'in_eja'], true])
      }
    })
    conditions.push(stageConditions)
  }

  if (conditions.length > 1) {
    map.setFilter(circleId, conditions as any)
  } else {
    map.setFilter(circleId, null)
  }
}

watch(
  [() => filtersStore.educationNetwork, () => filtersStore.educationStages],
  () => {
    updateEscolasFilter()
  },
  { deep: true }
)

// Filtro de tipo de unidade de saúde → aplica filter MapLibre na camada de saúde
watch(
  () => filtersStore.healthType,
  (tipo) => {
    if (!map || !mapStore.mapReady) return
    const circleId = 'saude-circle'
    if (!map.getLayer(circleId)) return

    // Mapeamento de HealthType para tp_unidade (códigos CNES)
    const tipoMap: Record<string, number[]> = {
      todos: [],
      hospital: [5, 7, 15],           // Hospital Geral, Especializado, Misto
      ubs: [1, 2],                    // Posto de Saúde, Centro/UBS
      policlinica: [4, 36],           // Policlínica, Clínica Especializada
      pronto_socorro: [20, 21, 73],   // Pronto Socorro, Pronto Atendimento (UPA)
      consultorio: [22],              // Consultório
    }
    const tipos = tipoMap[tipo] ?? []
    if (tipos.length === 0) {
      map.setFilter(circleId, null)
    } else {
      map.setFilter(circleId, [
        'any',
        ['in', ['to-number', ['get', 'tp_unidade']], ['literal', tipos]],
        ['in', ['get', 'tp_unidade'], ['literal', tipos]],
      ])
    }
  }
)

// Filtro de tipo de via → aplica filter MapLibre na camada de malha viária
watch(
  () => filtersStore.roadType,
  (tipo) => {
    if (!map || !mapStore.mapReady) return
    const lineId = 'malha_viaria-line'
    if (!map.getLayer(lineId)) return

    if (tipo === 'todos') {
      map.setFilter(lineId, null)
    } else {
      // Inclui links da mesma classe (ex: motorway_link para motorway)
      map.setFilter(lineId, ['in', ['get', 'highway'], ['literal', [tipo, `${tipo}_link`]]])
    }
  }
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
