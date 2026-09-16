// src/types/atlas.ts
// Tipos TypeScript globais do RootL Atlas

export interface MapViewport {
  center: [number, number]  // [lon, lat]
  zoom: number
  bearing: number
  pitch: number
}

export type LayerId = 'municipios' | 'setores' | 'escolas' | 'saude' | 'viaria' | 'malha_viaria' | 'seguranca'

export interface LayerConfig {
  id: LayerId
  label: string
  tileUrl: string
  minZoom: number
  maxZoom: number
  visible: boolean
  opacity: number
  color: string
  style?: Record<string, unknown>
}

export type RequestStatus = 'idle' | 'loading' | 'success' | 'error'

export interface RequestState {
  status: RequestStatus
  error?: string
  timestamp?: number
}

export interface SelectedFeature {
  layer: LayerId
  id: string | number
  properties: Record<string, unknown>
  geometry?: GeoJSON.Geometry
  lineage?: DataLineage
}

export interface DataLineage {
  fonte_id: string
  data_extracao?: string
  url_origem?: string
  versao_processamento?: string
  resolucao_original?: string
  nota_metodologica?: string
}

export interface AccessibilityMetrics {
  cd_setor: string
  metodo: string
  nota_metodologica: string
  raio_busca_km: number
  metricas: {
    escola_mais_proxima: {
      co_entidade?: number
      no_entidade?: string
      rede?: string
      distancia_eucl_km?: number
      geometry?: GeoJSON.Geometry
    }
    escola_fundamental_publica_mais_proxima: {
      co_entidade?: number
      distancia_eucl_km?: number
    }
    contagem_no_raio: Record<string, number>
  }
}

export interface SearchResult {
  tipo: string
  id: string
  nome: string
  xmin: number
  ymin: number
  xmax: number
  ymax: number
  score?: number
  municipio?: string
  rede?: string
}

export interface MunicipalityAccessibilitySummary {
  cd_municipio: string
  metodo: string
  nota_metodologica: string
  limiar_acesso_km: number
  resumo: {
    total_setores: number
    populacao_total: number
    pop_com_acesso_fund_pub: number
    pop_sem_acesso_fund_pub: number
    pct_pop_com_acesso: number
    setores_com_acesso: number
    setores_sem_acesso: number
  }
  distancias: {
    media_escola_km: number
    media_escola_fund_pub_km: number
    min_km: number
    max_km: number
  }
}
