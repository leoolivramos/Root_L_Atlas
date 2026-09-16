<template>
  <transition name="slide-right">
    <aside v-if="feature" class="feature-detail" role="complementary" aria-label="Detalhes da feição">
      <!-- Header -->
      <header class="feature-detail__header">
        <div class="feature-detail__layer-badge">
          <AtlasIcon :name="layerIconName" :size="13" />
          <span>{{ layerLabel }}</span>
        </div>
        <button class="feature-detail__close" @click="emit('close')" aria-label="Fechar painel" title="Fechar">
          <AtlasIcon name="close" :size="16" />
        </button>
      </header>

      <div class="feature-detail__content">
        <!-- Nome principal -->
        <div class="feature-detail__hero">
          <h2 class="feature-detail__name">{{ primaryName }}</h2>
          <p v-if="secondaryInfo" class="feature-detail__secondary">{{ secondaryInfo }}</p>
        </div>

        <!-- Métricas rápidas -->
        <div v-if="quickMetrics.length" class="feature-metrics">
          <div v-for="m in quickMetrics" :key="m.label" class="metric-card">
            <p class="metric-card__value">{{ m.value }}</p>
            <p class="metric-card__label">{{ m.label }}</p>
          </div>
        </div>

        <!-- Acessibilidade (setores) -->
        <div v-if="feature.layer === 'setores' && accessMetrics" class="accessibility-card">
          <div class="accessibility-card__header">
            <div class="accessibility-card__title">
              <AtlasIcon name="pin" :size="14" custom-class="acc-icon" />
              <span>Acessibilidade Educacional</span>
            </div>
            <span class="accessibility-card__method">{{ accessMetrics.metodo }}</span>
          </div>

          <div class="accessibility-card__body">
            <div class="accessibility-card__row">
              <span>Escola mais próxima</span>
              <strong>{{ accessMetrics.metricas?.escola_mais_proxima?.distancia_eucl_km?.toFixed(1) ?? '—' }} km</strong>
            </div>
            <div class="accessibility-card__row">
              <span>E. Fundamental Pública</span>
              <strong>{{ accessMetrics.metricas?.escola_fundamental_publica_mais_proxima?.distancia_eucl_km?.toFixed(1) ?? '—' }} km</strong>
            </div>
            <div class="accessibility-card__row">
              <span>Escolas em raio de 5km</span>
              <strong>{{ accessMetrics.metricas?.contagem_no_raio?.total_5km ?? '—' }}</strong>
            </div>
          </div>
          <p class="accessibility-card__nota">{{ accessMetrics.nota_metodologica }}</p>
        </div>

        <!-- Segurança Pública SINESP (municípios ou ponto de segurança) -->
        <div v-if="(feature.layer === 'municipios' || feature.layer === 'seguranca') && munSeguranca" class="accessibility-card">
          <div class="accessibility-card__header">
            <div class="accessibility-card__title">
              <AtlasIcon name="shield" :size="14" custom-class="acc-icon" />
              <span>Segurança Pública (SINESP)</span>
            </div>
            <span class="accessibility-card__method">2024</span>
          </div>
          <div class="accessibility-card__body">
            <div class="accessibility-card__row">
              <span>Total de Ocorrências</span>
              <strong>{{ fmtNum(munSeguranca.total_ocorrencias) }}</strong>
            </div>
            <div class="accessibility-card__row">
              <span>Total de Vítimas</span>
              <strong>{{ fmtNum(munSeguranca.total_vitimas) }}</strong>
            </div>
            <div v-for="crime in (munSeguranca.crimes || []).slice(0, 4)" :key="crime.tipo_crime" class="accessibility-card__row">
              <span style="font-size: 0.72rem; color: #64748b;">{{ crime.tipo_crime }}</span>
              <strong style="font-size: 0.78rem;">{{ fmtNum(crime.total_ocorrencias) }}</strong>
            </div>
          </div>
        </div>

        <!-- Cobertura do Solo MapBiomas (municípios) -->
        <div v-if="feature.layer === 'municipios' && munCobertura" class="accessibility-card">
          <div class="accessibility-card__header">
            <div class="accessibility-card__title">
              <AtlasIcon name="layers" :size="14" custom-class="acc-icon" />
              <span>Uso do Solo (MapBiomas)</span>
            </div>
            <span class="accessibility-card__method">Coleção 11</span>
          </div>
          <div class="accessibility-card__body">
            <div class="accessibility-card__row">
              <span>Área Mapeada</span>
              <strong>{{ fmtNum(munCobertura.total_area_ha, 0) }} ha</strong>
            </div>
            <div v-for="cls in (munCobertura.classes || []).slice(0, 4)" :key="cls.classe_mapbiomas" class="accessibility-card__row">
              <span style="font-size: 0.72rem; color: #64748b;">{{ cls.nm_classe }}</span>
              <strong style="font-size: 0.78rem;">{{ fmtNum(cls.area_ha, 0) }} ha</strong>
            </div>
          </div>
        </div>

        <!-- Atributos detalhados -->
        <details class="feature-attrs" open>
          <summary class="feature-attrs__summary">
            <span>Atributos cadastrais</span>
            <AtlasIcon name="chevron-down" :size="13" />
          </summary>
          <dl class="feature-attrs__list">
            <template v-for="(val, key) in filteredProps" :key="key">
              <dt class="feature-attrs__key">{{ formatKey(String(key)) }}</dt>
              <dd class="feature-attrs__val">{{ formatValue(val) }}</dd>
            </template>
          </dl>
        </details>

        <!-- Linhagem de dados -->
        <details v-if="feature.lineage" class="feature-lineage">
          <summary class="feature-lineage__summary">
            <div class="summary-left">
              <AtlasIcon name="document" :size="13" />
              <span>Linhagem e Metadados</span>
            </div>
            <AtlasIcon name="chevron-down" :size="13" />
          </summary>
          <dl class="feature-lineage__list">
            <template v-if="feature.lineage.fonte_id">
              <dt>Fonte</dt>
              <dd>{{ feature.lineage.fonte_id }}</dd>
            </template>
            <template v-if="feature.lineage.data_extracao">
              <dt>Extração</dt>
              <dd>{{ feature.lineage.data_extracao }}</dd>
            </template>
            <template v-if="feature.lineage.url_origem">
              <dt>Origem</dt>
              <dd>
                <a :href="feature.lineage.url_origem" target="_blank" rel="noopener" class="lineage-link">
                  <span>Acessar fonte</span>
                  <AtlasIcon name="external" :size="11" />
                </a>
              </dd>
            </template>
            <template v-if="feature.lineage.resolucao_original">
              <dt>Resolução</dt>
              <dd>{{ feature.lineage.resolucao_original }}</dd>
            </template>
          </dl>
        </details>

        <!-- Estado de carregamento -->
        <div v-if="requestsStore.getState('feature_detail').status === 'loading'" class="feature-detail__loading">
          <div class="spinner" />
          <span>Carregando dados complementares...</span>
        </div>
      </div>
    </aside>
  </transition>
</template>

<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import axios from 'axios'
import type { SelectedFeature, AccessibilityMetrics } from '@/types/atlas'
import { useRequestsStore } from '@/stores/requestsStore'
import AtlasIcon, { type IconName } from '@/components/AtlasIcon.vue'

const props = defineProps<{ feature: SelectedFeature | null }>()
const emit = defineEmits<{ close: [] }>()

const requestsStore = useRequestsStore()
const accessMetrics = ref<AccessibilityMetrics | null>(null)
const munSeguranca = ref<{ total_ocorrencias: number; total_vitimas: number; crimes: Array<{ tipo_crime: string; total_ocorrencias: number }> } | null>(null)
const munCobertura = ref<{ total_area_ha: number; classes: Array<{ nm_classe: string; area_ha: number; classe_mapbiomas: number }> } | null>(null)

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const LAYER_ICON_MAP: Record<string, IconName> = {
  setores: 'setor',
  municipios: 'municipio',
  escolas: 'escola',
  saude: 'saude',
  malha_viaria: 'viaria',
  seguranca: 'shield',
}

const LAYER_LABELS: Record<string, string> = {
  setores: 'Setor Censitário',
  municipios: 'Município',
  escolas: 'Escola (INEP)',
  saude: 'Saúde (CNES)',
  malha_viaria: 'Malha Viária (OSM)',
  seguranca: 'Segurança (SINESP)',
}

const layerIconName = computed<IconName>(() => LAYER_ICON_MAP[props.feature?.layer ?? ''] ?? 'pin')
const layerLabel = computed(() => LAYER_LABELS[props.feature?.layer ?? ''] ?? 'Feição')

const primaryName = computed(() => {
  const p = props.feature?.properties
  return (
    p?.['nm_municipio'] ??
    p?.['no_entidade'] ??
    p?.['no_fantasia'] ??
    p?.['name'] ??
    p?.['highway'] ??
    p?.['cd_setor'] ??
    props.feature?.id ??
    '—'
  )
})

const secondaryInfo = computed(() => {
  const p = props.feature?.properties
  if (props.feature?.layer === 'escolas') return p?.['nm_dependencia'] as string
  if (props.feature?.layer === 'setores') return p?.['nm_tipo_setor'] as string
  if (props.feature?.layer === 'saude') return p?.['nm_tp_unidade'] as string
  if (props.feature?.layer === 'malha_viaria') return (p?.['highway'] as string)?.toUpperCase()
  if (props.feature?.layer === 'seguranca') return `Ocorrências SINESP · ${p?.['nm_municipio'] || ''}`
  return null
})

// Métricas rápidas por camada
const quickMetrics = computed(() => {
  const p = props.feature?.properties
  if (!p) return []

  if (props.feature?.layer === 'setores') {
    return [
      { label: 'População', value: fmtNum(p['pop_total'] as number) },
      { label: 'Domicílios', value: fmtNum(p['domicilios_total'] as number) },
      { label: 'Área (km²)', value: fmtNum(p['area_km2'] as number, 2) },
    ]
  }
  if (props.feature?.layer === 'escolas') {
    return [
      { label: 'Matrículas', value: fmtNum(p['qt_mat_bas'] as number) },
      { label: 'Salas', value: p['qt_salas_utilizadas'] ?? '—' },
      { label: 'Rede', value: p['nm_dependencia'] ?? '—' },
    ]
  }
  if (props.feature?.layer === 'municipios') {
    return [
      { label: 'Pop. (2022)', value: fmtNum(p['populacao_2022'] as number) },
      { label: 'Área (km²)', value: fmtNum(p['area_km2'] as number, 1) },
      { label: 'Saúde', value: p['qt_estabelecimentos_saude'] ?? '—' },
    ]
  }
  if (props.feature?.layer === 'saude') {
    return [
      { label: 'Tipo', value: p['nm_tp_unidade'] || '—' },
      { label: 'Leitos', value: p['qt_leitos_total'] ?? 0 },
      { label: 'Gestão', value: p['tp_gestao'] || '—' },
    ]
  }
  if (props.feature?.layer === 'malha_viaria') {
    return [
      { label: 'Tipo', value: p['highway'] || '—' },
      { label: 'Sentido Único', value: p['oneway'] ? 'Sim' : 'Não' },
      { label: 'Velocidade', value: p['maxspeed'] ? p['maxspeed'] + ' km/h' : '—' },
    ]
  }
  if (props.feature?.layer === 'seguranca') {
    return [
      { label: 'Ocorrências', value: fmtNum((p['qtd_ocorrencias'] ?? p['val'] ?? 0) as number) },
      { label: 'Vítimas', value: fmtNum((p['qtd_vitimas'] ?? 0) as number) },
      { label: 'Índice Relativo', value: p['weight'] != null ? `${Math.round(Number(p['weight']) * 100)}%` : '—' },
    ]
  }
  return []
})

const HIDDEN_PROPS = new Set([
  'geometry', 'geom', 'centroide', 'fonte_id', 'url_origem',
  'data_extracao', 'versao_processamento', 'criado_em', 'atualizado_em',
])

const filteredProps = computed(() => {
  if (!props.feature?.properties) return {}
  return Object.fromEntries(
    Object.entries(props.feature.properties).filter(
      ([k]) => !HIDDEN_PROPS.has(k) && k !== 'geometry'
    )
  )
})

function formatKey(key: string): string {
  return key.replace(/_/g, ' ')
}

function fmtNum(v: number, decimals = 0): string {
  if (v == null || isNaN(v)) return '—'
  return v.toLocaleString('pt-BR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function formatValue(val: unknown): string {
  if (val == null) return '—'
  if (typeof val === 'boolean') return val ? 'Sim' : 'Não'
  if (typeof val === 'number') return fmtNum(val)
  return String(val)
}

// Carrega dados contextuais quando uma feição é selecionada
watch(
  () => props.feature,
  async (feat) => {
    accessMetrics.value = null
    munSeguranca.value = null
    munCobertura.value = null

    if (!feat) return

    if (feat.layer === 'setores') {
      requestsStore.setLoading('accessibility')
      try {
        const { data } = await axios.get(
          `${API}/accessibility/education/sector/${feat.id}`,
          { params: { max_km: 15 } }
        )
        accessMetrics.value = data
        requestsStore.setSuccess('accessibility')
      } catch {
        requestsStore.setError('accessibility', 'Dados de acessibilidade indisponíveis')
      }
    } else if (feat.layer === 'municipios' || feat.layer === 'seguranca') {
      try {
        const munId = feat.properties?.['cd_municipio'] || feat.id
        const [resSeg, resCob] = await Promise.all([
          axios.get(`${API}/features/municipio/${munId}/seguranca`).catch(() => null),
          axios.get(`${API}/features/municipio/${munId}/cobertura_solo`).catch(() => null),
        ])
        if (resSeg?.data) munSeguranca.value = resSeg.data
        if (resCob?.data) munCobertura.value = resCob.data
      } catch {
        // Ignora erros não impeditivos
      }
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.feature-detail {
  position: absolute;
  top: 4.5rem;
  right: 1rem;
  bottom: 1.5rem;
  width: 340px;
  max-width: calc(100vw - 2rem);
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(16px);
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  color: #0f172a;
  font-family: inherit;
  z-index: 30;
  display: flex;
  flex-direction: column;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.12);
  overflow: hidden;
}

.feature-detail__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid #f1f5f9;
  background: #ffffff;
}

.feature-detail__layer-badge {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #2563eb;
  background: #eff6ff;
  padding: 0.2rem 0.55rem;
  border-radius: 6px;
}

.feature-detail__close {
  width: 28px;
  height: 28px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.feature-detail__close:hover {
  background: #f1f5f9;
  color: #0f172a;
  border-color: #cbd5e1;
}

.feature-detail__content {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 1rem;
}

.feature-detail__hero {
  padding: 1rem 1rem 0.5rem;
}

.feature-detail__name {
  font-size: 1.05rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 0.2rem;
  line-height: 1.3;
}

.feature-detail__secondary {
  font-size: 0.78rem;
  color: #2563eb;
  font-weight: 600;
  margin: 0;
}

.feature-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(85px, 1fr));
  gap: 0.5rem;
  padding: 0.5rem 1rem 0.75rem;
}

.metric-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
}

.metric-card__value {
  font-size: 0.95rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
}

.metric-card__label {
  font-size: 0.68rem;
  color: #64748b;
  margin: 0.1rem 0 0;
}

.accessibility-card {
  margin: 0.5rem 1rem;
  background: #f5f3ff;
  border: 1px solid #ddd6fe;
  border-radius: 10px;
  padding: 0.75rem;
}

.accessibility-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.accessibility-card__title {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 700;
  color: #6d28d9;
}

.acc-icon {
  color: #7c3aed;
}

.accessibility-card__method {
  font-size: 0.65rem;
  color: #7c3aed;
  background: #ede9fe;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-weight: 600;
}

.accessibility-card__body {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.accessibility-card__row {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #475569;
  border-bottom: 1px solid #ede9fe;
  padding-bottom: 0.2rem;
}

.accessibility-card__row strong {
  color: #0f172a;
}

.accessibility-card__nota {
  font-size: 0.65rem;
  color: #b45309;
  margin: 0.5rem 0 0;
  line-height: 1.35;
}

.feature-attrs,
.feature-lineage {
  margin: 0.5rem 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.feature-attrs__summary,
.feature-lineage__summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.55rem 0.75rem;
  background: #f8fafc;
  font-size: 0.75rem;
  font-weight: 600;
  color: #334155;
  cursor: pointer;
  user-select: none;
}

.summary-left {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.feature-attrs__list,
.feature-lineage__list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem 0.75rem;
  padding: 0.6rem 0.75rem;
  background: #ffffff;
}

dt {
  font-size: 0.68rem;
  color: #64748b;
  text-transform: capitalize;
}

dd {
  font-size: 0.72rem;
  font-weight: 500;
  color: #0f172a;
  margin: 0;
  text-align: right;
  word-break: break-word;
}

.lineage-link {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  color: #2563eb;
  text-decoration: none;
  font-weight: 600;
}

.lineage-link:hover {
  text-decoration: underline;
}

.feature-detail__loading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  font-size: 0.75rem;
  color: #64748b;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.25s;
}
.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
