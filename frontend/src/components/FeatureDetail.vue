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

        <!-- Queimadas INPE (municípios ou ponto de queimadas) -->
        <div v-if="(feature.layer === 'municipios' || feature.layer === 'queimadas') && munQueimadas" class="accessibility-card">
          <div class="accessibility-card__header">
            <div class="accessibility-card__title">
              <AtlasIcon name="flame" :size="14" custom-class="acc-icon acc-icon--fire" />
              <span>Focos de Queimadas (INPE)</span>
            </div>
            <span class="accessibility-card__method">{{ munQueimadas.ano ?? 'Consolidado' }}</span>
          </div>
          <div class="accessibility-card__body">
            <div class="accessibility-card__row">
              <span>Total de Focos</span>
              <strong style="color: #ea580c;">{{ fmtNum(munQueimadas.total_focos) }}</strong>
            </div>
            <div class="accessibility-card__row">
              <span>Satélite de Referência</span>
              <strong>{{ fmtNum(munQueimadas.focos_referencia) }}</strong>
            </div>
            <div class="accessibility-card__row">
              <span>FRP Médio</span>
              <strong>{{ munQueimadas.frp_medio != null ? `${Number(munQueimadas.frp_medio).toFixed(1)} MW` : '—' }}</strong>
            </div>
            <div class="accessibility-card__row">
              <span>Risco de Fogo Médio</span>
              <strong>{{ munQueimadas.risco_fogo_medio != null ? Number(munQueimadas.risco_fogo_medio).toFixed(2) : '—' }}</strong>
            </div>
            <div class="accessibility-card__row">
              <span>Dias sem Chuva (Médio)</span>
              <strong>{{ munQueimadas.dias_sem_chuva_medio != null ? `${Number(munQueimadas.dias_sem_chuva_medio).toFixed(0)} dias` : '—' }}</strong>
            </div>
          </div>
        </div>

        <!-- Linhagem e Metadados Canônicos -->
        <details class="feature-lineage" open>
          <summary class="feature-lineage__summary">
            <div class="summary-left">
              <AtlasIcon name="document" :size="13" />
              <span>Linhagem e Metadados Oficiais</span>
            </div>
            <AtlasIcon name="chevron-down" :size="13" />
          </summary>

          <div class="lineage-wrapper">
            <!-- Badges de autoridade e domínio -->
            <div class="lineage-pills">
              <span class="lineage-pill lineage-pill--agency">{{ activeMeta.orgao_curto }}</span>
              <span class="lineage-pill lineage-pill--domain">{{ activeMeta.dominio }}</span>
              <span class="lineage-pill lineage-pill--res">{{ activeMeta.resolucao_espacial }}</span>
            </div>

            <!-- Lista estruturada de metadados -->
            <dl class="lineage-list">
              <div class="lineage-row">
                <dt>Órgão Emissor</dt>
                <dd><strong>{{ activeMeta.orgao }}</strong></dd>
              </div>

              <div class="lineage-row">
                <dt>Base Canônica</dt>
                <dd>{{ activeMeta.nome }}</dd>
              </div>

              <div v-if="formattedExtracaoDate" class="lineage-row">
                <dt>Data de Extração</dt>
                <dd>{{ formattedExtracaoDate }}</dd>
              </div>

              <div v-if="activeVersao" class="lineage-row">
                <dt>Versão do Processamento</dt>
                <dd><span class="version-tag">{{ activeVersao }}</span></dd>
              </div>

              <div v-if="activeMeta.frequencia_atualizacao" class="lineage-row">
                <dt>Frequência</dt>
                <dd>{{ activeMeta.frequencia_atualizacao }}</dd>
              </div>

              <div v-if="activeMeta.licenca" class="lineage-row">
                <dt>Licença</dt>
                <dd>{{ activeMeta.licenca }}</dd>
              </div>
            </dl>

            <!-- Nota metodológica oficial -->
            <div v-if="activeMeta.metodologia" class="lineage-methodology">
              <p class="lineage-methodology__title">Nota Metodológica Oficial:</p>
              <p class="lineage-methodology__text">{{ activeMeta.metodologia }}</p>
            </div>

            <!-- Ações e Links Oficiais -->
            <div class="lineage-actions">
              <a
                v-if="activeSourceUrl"
                :href="activeSourceUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="lineage-btn lineage-btn--primary"
                title="Acessar repositório original de dados abertos"
              >
                <span>Baixar Fonte Original</span>
                <AtlasIcon name="external" :size="11" />
              </a>

              <a
                v-if="activeMeta.url_portal"
                :href="activeMeta.url_portal"
                target="_blank"
                rel="noopener noreferrer"
                class="lineage-btn lineage-btn--secondary"
                title="Visitar portal oficial do órgão emissor"
              >
                <span>Portal Oficial</span>
                <AtlasIcon name="external" :size="11" />
              </a>
            </div>
          </div>
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
const munQueimadas = ref<{ total_focos: number; focos_referencia: number; frp_medio: number; risco_fogo_medio: number; dias_sem_chuva_medio: number; ano?: number } | null>(null)

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const LAYER_ICON_MAP: Record<string, IconName> = {
  setores: 'setor',
  municipios: 'municipio',
  escolas: 'escola',
  saude: 'saude',
  malha_viaria: 'viaria',
  seguranca: 'shield',
  queimadas: 'flame',
}

const LAYER_LABELS: Record<string, string> = {
  setores: 'Setor Censitário',
  municipios: 'Município',
  escolas: 'Escola (INEP)',
  saude: 'Saúde (CNES)',
  malha_viaria: 'Malha Viária (OSM)',
  seguranca: 'Segurança (SINESP)',
  queimadas: 'Queimadas (INPE)',
}

interface LayerMetaInfo {
  fonte_id: string
  nome: string
  orgao: string
  orgao_curto: string
  dominio: string
  resolucao_espacial: string
  frequencia_atualizacao: string
  url_origem: string
  url_portal?: string
  licenca: string
  metodologia: string
}

const FALLBACK_METAS: Record<string, LayerMetaInfo> = {
  setores: {
    fonte_id: 'ibge_censo_2022_agregados_setores',
    nome: 'Censo Demográfico 2022 — Agregados por Setores Censitários',
    orgao: 'IBGE — Instituto Brasileiro de Geografia e Estatística',
    orgao_curto: 'IBGE',
    dominio: 'Demografia & Território',
    resolucao_espacial: 'Setor Censitário (intramunicipal)',
    frequencia_atualizacao: 'Decenal (Censo 2022)',
    url_origem: 'https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/malha_com_atributos/setores/csv/BR_setores_CD2022.csv',
    url_portal: 'https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html',
    licenca: 'Dados Abertos Governamentais (CC-BY 4.0)',
    metodologia: 'Agregados oficiais do Censo 2022: contagem de população residente, total de domicílios, domicílios ocupados e divisão por sexo.',
  },
  municipios: {
    fonte_id: 'ibge_censo_2022_populacao',
    nome: 'População Residente Municipal — Censo Demográfico 2022',
    orgao: 'IBGE — Instituto Brasileiro de Geografia e Estatística',
    orgao_curto: 'IBGE',
    dominio: 'Demografia & Território',
    resolucao_espacial: 'Municipal (141 municípios de MT)',
    frequencia_atualizacao: 'Decenal / Estimativas Anuais',
    url_origem: 'https://apisidra.ibge.gov.br/values/t/4709/n6/in%20n3%2051/v/93/p/2022',
    url_portal: 'https://sidra.ibge.gov.br/tabela/4709',
    licenca: 'Dados Abertos Governamentais (Domínio Público)',
    metodologia: 'População oficial do Censo 2022 obtida via API SIDRA (Tabela 4709) consolidada com geometria vetorial para cálculo de densidade demográfica (hab/km²).',
  },
  escolas: {
    fonte_id: 'inep_censo_escolar_2025',
    nome: 'Censo da Educação Básica — Microdados Georreferenciados',
    orgao: 'INEP — Ministério da Educação',
    orgao_curto: 'INEP',
    dominio: 'Educação Básica',
    resolucao_espacial: 'Ponto (Escola)',
    frequencia_atualizacao: 'Anual',
    url_origem: 'https://download.inep.gov.br/microdados/microdados_educacao_basica_2024.zip',
    url_portal: 'https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar',
    licenca: 'Dados Abertos Governamentais (Domínio Público)',
    metodologia: 'Censo Escolar anual com dependência administrativa, modalidades de ensino ofertadas, instalações físicas, salas e matrículas.',
  },
  saude: {
    fonte_id: 'datasus_cnes_estab',
    nome: 'Cadastro Nacional de Estabelecimentos de Saúde (CNES)',
    orgao: 'DATASUS / Ministério da Saúde',
    orgao_curto: 'DATASUS',
    dominio: 'Saúde Pública',
    resolucao_espacial: 'Ponto (Estabelecimento)',
    frequencia_atualizacao: 'Mensal',
    url_origem: 'ftp://ftp.datasus.gov.br/dissemin/publicos/CNES/200508_/Dados/ST/',
    url_portal: 'http://cnes.datasus.gov.br/',
    licenca: 'Dados Abertos Governamentais (Domínio Público)',
    metodologia: 'Cadastro oficial de estabelecimentos de saúde, tipologia assistencial, leitos totais e leitos SUS, esfera administrativa e gestora.',
  },
  malha_viaria: {
    fonte_id: 'osm_mt_pbf',
    nome: 'OpenStreetMap — Extrato Regional da Rede Viária (Mato Grosso)',
    orgao: 'OpenStreetMap Contributors / Geofabrik',
    orgao_curto: 'OSM',
    dominio: 'Infraestrutura Viária',
    resolucao_espacial: 'Segmento Viário (LineString)',
    frequencia_atualizacao: 'Semanal / Contínua',
    url_origem: 'https://download.geofabrik.de/south-america/brazil/centro-oeste-latest.osm.pbf',
    url_portal: 'https://www.openstreetmap.org/',
    licenca: 'Open Database License (ODbL 1.0)',
    metodologia: 'Malha viária colaborativa filtrada para rodovias federais e estaduais, vias arteriais e coletoras de Mato Grosso.',
  },
  seguranca: {
    fonte_id: 'sinesp_vde_mun',
    nome: 'Sistema Nacional de Informações de Segurança Pública (SINESP)',
    orgao: 'Ministério da Justiça e Segurança Pública (MJSP)',
    orgao_curto: 'SINESP / MJSP',
    dominio: 'Segurança Pública',
    resolucao_espacial: 'Municipal (Mato Grosso)',
    frequencia_atualizacao: 'Mensal',
    url_origem: 'https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/sinesp-1/dados-abertos-sinesp',
    url_portal: 'https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/sinesp-1',
    licenca: 'Dados Abertos Governamentais (Domínio Público)',
    metodologia: 'Registros mensais de ocorrências policiais e vítimas por tipologia criminal. Resolução máxima é MUNICIPAL (sem extrapolação para bairros).',
  },
  queimadas: {
    fonte_id: 'inpe_bdqueimadas_mensal',
    nome: 'BDQueimadas — Programa Queimadas (INPE)',
    orgao: 'INPE — Instituto Nacional de Pesquisas Espaciais',
    orgao_curto: 'INPE',
    dominio: 'Meio Ambiente & Clima',
    resolucao_espacial: 'Ponto (Sensor Ótico)',
    frequencia_atualizacao: 'Tempo Real / Mensal Consolidado',
    url_origem: 'https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/',
    url_portal: 'https://terrabrasilis.dpi.inpe.br/queimadas/bdqueimadas/',
    licenca: 'Dados Abertos Governamentais (Domínio Público)',
    metodologia: 'Detecção termal de calor a partir de satélites ópticos (Aqua, Terra, NOAA). Contém potência radiativa do fogo (FRP) e risco de fogo.',
  },
}

const layerMetaRemote = ref<Record<string, any> | null>(null)

const activeMeta = computed<LayerMetaInfo>(() => {
  const layer = props.feature?.layer ?? 'setores'
  const fallback = FALLBACK_METAS[layer] ?? FALLBACK_METAS.setores
  const remote = layerMetaRemote.value

  if (!remote) return fallback

  return {
    fonte_id: remote.fonte_id || fallback.fonte_id,
    nome: remote.nome || fallback.nome,
    orgao: remote.orgao || fallback.orgao,
    orgao_curto: fallback.orgao_curto,
    dominio: remote.dominio || fallback.dominio,
    resolucao_espacial: remote.resolucao_espacial || fallback.resolucao_espacial,
    frequencia_atualizacao: remote.frequencia_atualizacao || fallback.frequencia_atualizacao,
    url_origem: remote.url_origem || fallback.url_origem,
    url_portal: remote.url_portal || fallback.url_portal,
    licenca: remote.licenca || fallback.licenca,
    metodologia: remote.metodologia || fallback.metodologia,
  }
})

const activeSourceUrl = computed(() => {
  return (
    props.feature?.lineage?.url_origem ||
    (props.feature?.properties?.['url_origem'] as string) ||
    activeMeta.value.url_origem
  )
})

const activeVersao = computed(() => {
  return (
    props.feature?.lineage?.versao_processamento ||
    (props.feature?.properties?.['versao_processamento'] as string) ||
    '1.0.0'
  )
})

const formattedExtracaoDate = computed(() => {
  const raw =
    props.feature?.lineage?.data_extracao ||
    (props.feature?.properties?.['data_extracao'] as string)
  if (!raw) return 'Consolidado Oficial 2022–2026'
  try {
    const d = new Date(raw)
    if (isNaN(d.getTime())) return String(raw)
    return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return String(raw)
  }
})

const layerIconName = computed<IconName>(() => LAYER_ICON_MAP[props.feature?.layer ?? ''] ?? 'pin')
const layerLabel = computed(() => LAYER_LABELS[props.feature?.layer ?? ''] ?? 'Feição')

const primaryName = computed(() => {
  const p = props.feature?.properties
  if (props.feature?.layer === 'setores') {
    return (
      (p?.['nm_bairro'] as string) ||
      (p?.['nm_distrito'] as string) ||
      `Setor ${p?.['cd_setor'] ?? props.feature?.id ?? ''}`
    )
  }
  if (props.feature?.layer === 'municipios') {
    return (p?.['nm_municipio'] as string) ?? (p?.['municipio'] as string) ?? 'Município'
  }
  return (
    p?.['no_entidade'] ??
    p?.['no_fantasia'] ??
    p?.['nm_municipio'] ??
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
  if (props.feature?.layer === 'setores') {
    const parts = [
      p?.['nm_municipio'],
      p?.['nm_tipo_setor'] || 'Setor Censitário'
    ].filter(Boolean)
    return parts.join(' · ')
  }
  if (props.feature?.layer === 'municipios') {
    return `Mato Grosso · IBGE ${p?.['cd_municipio'] || props.feature?.id || ''}`
  }
  if (props.feature?.layer === 'saude') return p?.['nm_tp_unidade'] as string
  if (props.feature?.layer === 'malha_viaria') return (p?.['highway'] as string)?.toUpperCase()
  if (props.feature?.layer === 'seguranca') return `Ocorrências SINESP · ${p?.['nm_municipio'] || ''}`
  if (props.feature?.layer === 'queimadas') return `Foco · ${p?.['bioma'] || ''} · Satélite ${p?.['satelite'] || ''}`
  return null
})

// Métricas rápidas por camada
const quickMetrics = computed(() => {
  const p = props.feature?.properties
  if (!p) return []

  if (props.feature?.layer === 'setores') {
    const metrics = [
      { label: 'População', value: fmtNum(p['pop_total'] as number) },
      { label: 'Domicílios', value: fmtNum(p['domicilios_total'] as number) },
    ]
    if (p['domicilios_ocupados'] != null && Number(p['domicilios_ocupados']) > 0) {
      metrics.push({ label: 'Ocupados', value: fmtNum(p['domicilios_ocupados'] as number) })
    }
    if (p['pop_homens'] != null && p['pop_mulheres'] != null && Number(p['pop_homens']) > 0) {
      metrics.push({ label: 'Homens / Mulheres', value: `${fmtNum(p['pop_homens'] as number)} / ${fmtNum(p['pop_mulheres'] as number)}` })
    }
    if (p['area_km2'] != null) {
      metrics.push({ label: 'Área (km²)', value: fmtNum(p['area_km2'] as number, 2) })
    }
    if (p['dist_escola_km'] != null && Number(p['dist_escola_km']) >= 0) {
      metrics.push({ label: 'Escola Próxima', value: `${Number(p['dist_escola_km']).toFixed(1)} km` })
    }
    return metrics
  }

  if (props.feature?.layer === 'municipios') {
    const metrics = [
      { label: 'Pop. (Censo 2022)', value: fmtNum(p['populacao_2022'] as number) },
    ]
    if (p['densidade_demografica'] != null) {
      metrics.push({ label: 'Densidade', value: `${fmtNum(p['densidade_demografica'] as number, 1)} hab/km²` })
    }
    if (p['domicilios_total'] != null || p['qt_domicilios'] != null) {
      metrics.push({ label: 'Domicílios', value: fmtNum((p['domicilios_total'] ?? p['qt_domicilios']) as number) })
    }
    if (p['qt_setores'] != null) {
      metrics.push({ label: 'Setores IBGE', value: fmtNum(p['qt_setores'] as number) })
    }
    if (p['qt_escolas'] != null || p['qt_escolas_total'] != null) {
      metrics.push({ label: 'Escolas', value: fmtNum((p['qt_escolas'] ?? p['qt_escolas_total']) as number) })
    }
    if (p['qt_estabelecimentos_saude'] != null) {
      metrics.push({ label: 'Saúde', value: fmtNum(p['qt_estabelecimentos_saude'] as number) })
    }
    if (p['area_km2'] != null) {
      metrics.push({ label: 'Área (km²)', value: fmtNum(p['area_km2'] as number, 1) })
    }
    return metrics
  }

  if (props.feature?.layer === 'escolas') {
    return [
      { label: 'Matrículas', value: fmtNum(p['qt_mat_bas'] as number) },
      { label: 'Salas', value: p['qt_salas_utilizadas'] ?? '—' },
      { label: 'Rede', value: p['nm_dependencia'] ?? '—' },
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
      { label: 'Taxa / 100k hab.', value: p['taxa_100k'] != null ? fmtNum(Number(p['taxa_100k']), 1) : '—' },
      { label: 'População', value: p['populacao_2022'] ? fmtNum(Number(p['populacao_2022'])) : '—' },
      { label: 'Ocorrências', value: fmtNum((p['qtd_ocorrencias'] ?? p['val'] ?? 0) as number) },
      { label: 'Vítimas', value: fmtNum((p['qtd_vitimas'] ?? 0) as number) },
      { label: 'Índice Relativo', value: p['weight'] != null ? `${Math.round(Number(p['weight']) * 100)}%` : '—' },
    ]
  }
  if (props.feature?.layer === 'queimadas') {
    return [
      { label: 'Satélite', value: (p['satelite'] as string) || '—' },
      { label: 'FRP (MW)', value: p['frp'] != null ? `${Number(p['frp']).toFixed(1)} MW` : '—' },
      { label: 'Risco Fogo', value: p['risco_fogo'] != null ? Number(p['risco_fogo']).toFixed(2) : '—' },
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

// Carrega dados contextuais e metadados quando uma feição é selecionada
watch(
  () => props.feature,
  async (feat) => {
    accessMetrics.value = null
    munSeguranca.value = null
    munCobertura.value = null
    munQueimadas.value = null
    layerMetaRemote.value = null

    if (!feat) return

    // Busca metadados da camada
    axios
      .get(`${API}/metadata/layer/${feat.layer}`)
      .then((res) => {
        if (res.data?.metadata) {
          layerMetaRemote.value = res.data.metadata
        }
      })
      .catch(() => {
        layerMetaRemote.value = null
      })

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
    } else if (feat.layer === 'municipios' || feat.layer === 'seguranca' || feat.layer === 'queimadas') {
      try {
        const munId = feat.properties?.['cd_municipio'] || feat.properties?.['municipio_id'] || feat.id
        const [resSeg, resCob, resQueim, resMun] = await Promise.all([
          axios.get(`${API}/features/municipio/${munId}/seguranca`).catch(() => null),
          axios.get(`${API}/features/municipio/${munId}/cobertura_solo`).catch(() => null),
          axios.get(`${API}/features/municipio/${munId}/queimadas`).catch(() => null),
          feat.layer === 'municipios' ? axios.get(`${API}/features/municipio/${munId}`).catch(() => null) : Promise.resolve(null),
        ])
        if (resSeg?.data) munSeguranca.value = resSeg.data
        if (resCob?.data) munCobertura.value = resCob.data
        if (resQueim?.data) munQueimadas.value = resQueim.data
        if (resMun?.data?.properties) {
          Object.assign(feat.properties, resMun.data.properties)
        }
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

.feature-attrs__list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem 0.75rem;
  padding: 0.6rem 0.75rem;
  background: #ffffff;
}

.lineage-wrapper {
  padding: 0.75rem;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.lineage-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.lineage-pill {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  letter-spacing: 0.02em;
}

.lineage-pill--agency {
  background: #dbeafe;
  color: #1e40af;
}

.lineage-pill--domain {
  background: #f1f5f9;
  color: #475569;
}

.lineage-pill--res {
  background: #fef3c7;
  color: #92400e;
}

.lineage-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0;
}

.lineage-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  border-bottom: 1px dashed #f1f5f9;
  padding-bottom: 0.3rem;
}

.lineage-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.lineage-row dt {
  font-size: 0.7rem;
  color: #64748b;
  font-weight: 500;
  min-width: 95px;
  text-transform: none;
}

.lineage-row dd {
  font-size: 0.72rem;
  color: #0f172a;
  text-align: right;
  word-break: break-word;
  margin: 0;
}

.version-tag {
  display: inline-block;
  font-family: monospace;
  font-size: 0.68rem;
  background: #f1f5f9;
  color: #0f172a;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
}

.lineage-methodology {
  background: #f8fafc;
  border-left: 3px solid #2563eb;
  padding: 0.45rem 0.6rem;
  border-radius: 0 4px 4px 0;
}

.lineage-methodology__title {
  font-size: 0.68rem;
  font-weight: 600;
  color: #334155;
  margin: 0 0 0.15rem;
}

.lineage-methodology__text {
  font-size: 0.68rem;
  color: #64748b;
  margin: 0;
  line-height: 1.35;
}

.lineage-actions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.2rem;
}

.lineage-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  text-decoration: none;
  transition: all 0.15s ease;
}

.lineage-btn--primary {
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
}

.lineage-btn--primary:hover {
  background: #dbeafe;
  border-color: #93c5fd;
}

.lineage-btn--secondary {
  background: #f8fafc;
  color: #475569;
  border: 1px solid #e2e8f0;
}

.lineage-btn--secondary:hover {
  background: #f1f5f9;
  color: #0f172a;
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

.acc-icon--fire {
  color: #ea580c !important;
}
</style>
