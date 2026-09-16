<template>
  <aside class="layer-panel" :class="{ 'layer-panel--collapsed': collapsed }">
    <!-- Header com botão colapsar -->
    <div class="layer-panel__top">
      <div v-if="!collapsed" class="layer-panel__header-info">
        <AtlasIcon name="layers" :size="16" custom-class="title-icon" />
        <h2 class="layer-panel__title">Camadas</h2>
      </div>

      <button
        class="layer-panel__toggle"
        @click="collapsed = !collapsed"
        :aria-label="collapsed ? 'Expandir painel' : 'Recolher painel'"
        :title="collapsed ? 'Expandir painel' : 'Recolher painel'"
      >
        <AtlasIcon :name="collapsed ? 'chevron-right' : 'chevron-left'" :size="14" />
      </button>
    </div>

    <!-- Conteúdo visível quando não colapsado -->
    <template v-if="!collapsed">
      <div class="layer-panel__body">
        <div
          v-for="layer in layersStore.layers"
          :key="layer.id"
          class="layer-item"
          :class="{ 'layer-item--active': layer.visible }"
        >
          <div class="layer-item__header">
            <button
              class="layer-item__toggle-btn"
              :aria-label="`${layer.visible ? 'Ocultar' : 'Mostrar'} ${layer.label}`"
              @click="layersStore.toggleLayer(layer.id)"
            >
              <div
                class="layer-item__icon-wrapper"
                :style="{ color: layer.color, backgroundColor: `${layer.color}15` }"
              >
                <AtlasIcon :name="getLayerIcon(layer.id)" :size="14" />
              </div>

              <span class="layer-item__label">{{ layer.label }}</span>

              <!-- Switch toggle limpo -->
              <span class="clean-switch" :class="{ 'clean-switch--checked': layer.visible }">
                <span class="clean-switch__thumb" />
              </span>
            </button>
          </div>

          <transition name="slide">
            <div v-if="layer.visible" class="layer-item__controls">
              <div class="layer-item__opacity-row">
                <span class="opacity-label">Opacidade</span>
                <span class="opacity-val">{{ Math.round(layer.opacity * 100) }}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                :value="layer.opacity"
                class="layer-item__slider"
                :aria-label="`Opacidade de ${layer.label}`"
                @input="layersStore.setOpacity(layer.id, +($event.target as HTMLInputElement).value)"
              />
              <div class="layer-item__zoom-hint">
                Disponível a partir do zoom {{ layer.minZoom }}
              </div>
            </div>
          </transition>
        </div>
      </div>

      <footer class="layer-panel__footer">
        <span class="layer-panel__meta">Mato Grosso · 8 Entidades Integradas</span>
      </footer>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useLayersStore } from '@/stores/layersStore'
import type { LayerId } from '@/types/atlas'
import AtlasIcon, { type IconName } from '@/components/AtlasIcon.vue'

const layersStore = useLayersStore()
const collapsed = ref(false)

function getLayerIcon(layerId: LayerId): IconName {
  if (layerId === 'municipios') return 'municipio'
  if (layerId === 'escolas') return 'escola'
  if (layerId === 'setores') return 'setor'
  if (layerId === 'saude') return 'saude'
  if (layerId === 'seguranca') return 'shield'
  if (layerId === 'malha_viaria' || layerId === 'viaria') return 'viaria'
  return 'layers'
}
</script>

<style scoped>
.layer-panel {
  position: absolute;
  top: 4.5rem;
  left: 1rem;
  width: 250px;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(14px);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  color: #0f172a;
  font-family: inherit;
  z-index: 20;
  transition: width 0.25s cubic-bezier(0.16, 1, 0.3, 1), transform 0.25s;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.layer-panel--collapsed {
  width: 44px;
}

.layer-panel__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 0.85rem;
  border-bottom: 1px solid #f1f5f9;
}

.layer-panel__header-info {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.title-icon {
  color: #2563eb;
}

.layer-panel__title {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #334155;
  margin: 0;
}

.layer-panel__toggle {
  width: 26px;
  height: 26px;
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

.layer-panel__toggle:hover {
  background: #f1f5f9;
  color: #0f172a;
  border-color: #cbd5e1;
}

.layer-panel__body {
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  max-height: calc(100vh - 220px);
  overflow-y: auto;
}

.layer-item {
  border-radius: 8px;
  border: 1px solid transparent;
  transition: all 0.15s;
}

.layer-item--active {
  background: #f8fafc;
  border-color: #f1f5f9;
}

.layer-item__header {
  display: flex;
}

.layer-item__toggle-btn {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  padding: 0.5rem 0.65rem;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  text-align: left;
  border-radius: 8px;
  transition: background 0.15s;
}

.layer-item__toggle-btn:hover {
  background: #f1f5f9;
}

.layer-item__icon-wrapper {
  width: 24px;
  height: 24px;
  border-radius: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.layer-item__label {
  flex: 1;
  font-size: 0.8rem;
  font-weight: 600;
  color: #1e293b;
}

/* Switch limpo */
.clean-switch {
  position: relative;
  width: 28px;
  height: 16px;
  background: #cbd5e1;
  border-radius: 9999px;
  transition: background-color 0.2s;
  flex-shrink: 0;
}

.clean-switch__thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  background: #ffffff;
  border-radius: 50%;
  transition: transform 0.2s;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.clean-switch--checked {
  background: #2563eb;
}

.clean-switch--checked .clean-switch__thumb {
  transform: translateX(12px);
}

.layer-item__controls {
  padding: 0 0.65rem 0.65rem 2.4rem;
}

.layer-item__opacity-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.68rem;
  color: #64748b;
  margin-bottom: 0.25rem;
}

.opacity-val {
  font-weight: 600;
  color: #334155;
}

.layer-item__slider {
  width: 100%;
  height: 4px;
  accent-color: #2563eb;
  cursor: pointer;
}

.layer-item__zoom-hint {
  font-size: 0.62rem;
  color: #94a3b8;
  margin-top: 0.2rem;
}

.layer-panel__footer {
  padding: 0.5rem 0.85rem;
  border-top: 1px solid #f1f5f9;
  background: #fafafa;
}

.layer-panel__meta {
  font-size: 0.65rem;
  color: #94a3b8;
  font-weight: 500;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
  max-height: 100px;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
