<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCategoryOptions } from '@/api/categories'
import { getStoreOptions } from '@/api/stores'
import { getStoreMenu, resetStoreDish, setStoreDish } from '@/api/storeMenu'
import type { StoreDishPayload } from '@/api/storeMenu'
import type { CategoryOption, StoreMenuRow, StoreOption } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { formatPrice } from '@/utils/format'

const authStore = useAuthStore()

// 改价、上下架各自需要专门的权限码，后端会拦；这里禁用输入框只是别让人白填
const canEditPrice = computed(() => authStore.hasPermission('dish:price:edit'))
const canToggleOnline = computed(() => authStore.hasPermission('dish:online'))

const storeOptions = ref<StoreOption[]>([])
const categoryOptions = ref<CategoryOption[]>([])
const selectedStoreId = ref<number | null>(null)
const categoryFilter = ref<number | null>(null)
const search = ref('')

const rows = ref<StoreMenuRow[]>([])
const loading = ref(false)
const saving = ref(false)

async function loadStores() {
  try {
    const data = await getStoreOptions()
    storeOptions.value = data.stores
    // 店长只有一家店：直接选中，省一次点击
    if (selectedStoreId.value === null && data.stores.length > 0) {
      selectedStoreId.value = data.stores[0].id
    }
  } catch {
    // 拦截器已提示
  }
}

async function loadCategories() {
  try {
    const data = await getCategoryOptions()
    categoryOptions.value = data.categories
  } catch {
    // 拦截器已提示
  }
}

async function loadMenu() {
  if (selectedStoreId.value === null) return
  loading.value = true
  try {
    const data = await getStoreMenu(selectedStoreId.value, {
      category_id: categoryFilter.value ?? undefined,
      search: search.value || undefined,
    })
    rows.value = data.dishes
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

function handleStoreChange() {
  loadMenu()
}

/**
 * 改一个字段并存下来
 *
 * 存完重新拉一遍菜单，而不是就地改本地数据：这样 has_override 这类标记
 * 会跟着更新，而且万一保存失败（比如没权限），界面会自动退回服务器上的真实值，
 * 不会留下一个「看着改了其实没改」的假象。
 */
async function saveField(row: StoreMenuRow, patch: StoreDishPayload) {
  if (selectedStoreId.value === null) return
  saving.value = true
  try {
    await setStoreDish(selectedStoreId.value, row.dish_id, patch)
    ElMessage.success('已保存')
  } catch {
    // 拦截器已提示；下面照常重拉，把界面拉回真实值
  } finally {
    await loadMenu()
    saving.value = false
  }
}

async function handleReset(row: StoreMenuRow) {
  if (selectedStoreId.value === null) return
  try {
    await ElMessageBox.confirm(
      `把「${row.name}」在本店的设置恢复成默认？\n价格会变回公司基础价 ¥${row.base_price.toFixed(2)}，并恢复上架、取消限量。`,
      '恢复默认',
      { type: 'warning', confirmButtonText: '恢复', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await resetStoreDish(selectedStoreId.value, row.dish_id)
    ElMessage.success('已恢复默认')
  } catch {
    // 拦截器已提示
  } finally {
    loadMenu()
  }
}

onMounted(async () => {
  await loadStores()
  loadCategories()
  loadMenu()
})
</script>

<template>
  <div class="store-menu">
    <div class="toolbar">
      <el-select
        v-model="selectedStoreId"
        placeholder="选择门店"
        class="store-select"
        @change="handleStoreChange"
      >
        <el-option
          v-for="store in storeOptions"
          :key="store.id"
          :label="`${store.name}（${store.code}）`"
          :value="store.id"
        />
      </el-select>
      <el-select
        v-model="categoryFilter"
        placeholder="全部分类"
        clearable
        class="category-filter"
        @change="loadMenu"
      >
        <el-option
          v-for="item in categoryOptions"
          :key="item.id"
          :label="`${item.icon} ${item.name}`.trim()"
          :value="item.id"
        />
      </el-select>
      <el-input
        v-model="search"
        placeholder="搜索菜品"
        clearable
        class="search-input"
        @keyup.enter="loadMenu"
        @clear="loadMenu"
      />
      <el-button @click="loadMenu">刷新</el-button>
    </div>

    <p class="hint">
      <strong>价格、上架、每日限量直接在格子里改</strong>，改完自动保存，不需要点「编辑」。
      这里的设置只影响选中的这家店，不会动到全公司的基础价；
      没做过特殊设置的菜直接沿用基础价、默认上架、不限量（所以操作列大多是空的）。
    </p>

    <div class="table-card">
      <el-table v-loading="loading || saving" :data="rows">
        <el-table-column prop="name" label="菜品" min-width="140">
          <template #default="{ row }">
            {{ row.name }}
            <!-- 改过的行标一下，一眼能看出这家店对哪些菜做了特殊设置 -->
            <el-tag v-if="row.has_override" size="small" class="override-tag" disable-transitions>
              本店已调整
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category_name" label="分类" width="100" />
        <el-table-column label="基础价" width="100">
          <template #default="{ row }">
            <span :class="{ 'struck': row.has_price_override }">
              {{ formatPrice(row.base_price) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="本店价" width="150">
          <template #default="{ row }">
            <el-input-number
              :model-value="row.price"
              :min="0"
              :precision="2"
              :step="1"
              :controls="false"
              :disabled="!canEditPrice"
              class="price-input"
              @change="(value: number | undefined) => saveField(row, { price: value ?? null })"
            />
          </template>
        </el-table-column>
        <el-table-column label="上架" width="90">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_available"
              :disabled="!canToggleOnline"
              @change="(value: boolean) => saveField(row, { is_available: value })"
            />
          </template>
        </el-table-column>
        <el-table-column label="每日限量" width="140">
          <template #default="{ row }">
            <el-input-number
              :model-value="row.daily_limit ?? undefined"
              :min="1"
              :step="10"
              :controls="false"
              placeholder="不限"
              class="limit-input"
              @change="(value: number | undefined) => saveField(row, { daily_limit: value ?? null })"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <!-- 这一列大多数时候是空的：价格/上架/限量都是直接在格子里改的，
                 不需要「编辑」按钮。只有改过默认值的行才多一个恢复入口。
                 空着不写东西看起来像渲染坏了，所以给个占位符 -->
            <el-button
              v-if="row.has_override"
              size="small"
              link
              @click="handleReset(row)"
            >
              恢复默认
            </el-button>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.store-menu {
  padding: 32px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.store-select {
  width: 220px;
}

.category-filter {
  width: 160px;
}

.search-input {
  width: 180px;
}

.hint {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.7;
  margin-bottom: 16px;
}

.table-card {
  background: #f5f5f5;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  overflow: hidden;
  padding: 20px;
}

.table-card :deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: #ebebeb;
  --el-table-border-color: #e2e2e2;
}

.override-tag {
  margin-left: 6px;
}

.muted {
  color: #c0c0c0;
}

/* 本店价和基础价不同时，把基础价划掉，一眼看出改过 */
.struck {
  text-decoration: line-through;
  color: #a0a0a0;
}

.price-input,
.limit-input {
  width: 100%;
}

.price-input :deep(.el-input__inner),
.limit-input :deep(.el-input__inner) {
  text-align: left;
}
</style>