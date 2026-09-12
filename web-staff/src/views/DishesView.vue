<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCategoryOptions } from '@/api/categories'
import { deleteDish, getDishes } from '@/api/dishes'
import type { CategoryOption, Dish } from '@/api/types'
import DishFormDialog from '@/components/DishFormDialog.vue'
import { DISH_STATUS_TAG } from '@/constants/menu'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 菜品基础是全公司数据，改动还要求「全部」数据范围（后端会拦）。
// 本店范围的店长进得来但只能看——他调本店菜单要走「门店菜品」，那是下一步做的。
const canManage = computed(() => authStore.data_scope === 'all')
const canCreate = computed(() => canManage.value && authStore.hasPermission('menu:create'))
const canUpdate = computed(() => canManage.value && authStore.hasPermission('menu:update'))
const canDelete = computed(() => canManage.value && authStore.hasPermission('menu:delete'))

const dishes = ref<Dish[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const categoryFilter = ref<number | null>(null)
const categoryOptions = ref<CategoryOption[]>([])
const loading = ref(false)

const dialogVisible = ref(false)
const editingDish = ref<Dish | null>(null)

async function loadCategoryOptions() {
  try {
    const data = await getCategoryOptions()
    categoryOptions.value = data.categories
  } catch {
    // 拦截器已提示
  }
}

async function loadDishes() {
  loading.value = true
  try {
    const data = await getDishes({
      search: search.value,
      page: page.value,
      category_id: categoryFilter.value ?? undefined,
    })
    dishes.value = data.dishes
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadDishes()
}

function openCreate() {
  editingDish.value = null
  dialogVisible.value = true
}

function openEdit(dish: Dish) {
  editingDish.value = dish
  dialogVisible.value = true
}

async function handleDelete(dish: Dish) {
  try {
    await ElMessageBox.confirm(
      `确定删除菜品「${dish.name}」吗？\n还在门店菜单里挂着或已被订单引用时无法删除，那种情况请改成「已停售」。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteDish(dish.id)
    ElMessage.success('删除成功')
    if (dishes.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    loadDishes()
  } catch {
    // 拦截器已提示
  }
}

function handleDialogSuccess() {
  dialogVisible.value = false
  loadDishes()
}

function formatPrice(value: number): string {
  return `¥${value.toFixed(2)}`
}

onMounted(() => {
  loadCategoryOptions()
  loadDishes()
})
</script>

<template>
  <div class="dishes">
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索菜品名称"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-select
        v-model="categoryFilter"
        placeholder="全部分类"
        clearable
        class="category-filter"
        @change="handleSearch"
      >
        <el-option
          v-for="item in categoryOptions"
          :key="item.id"
          :label="`${item.icon} ${item.name}`.trim()"
          :value="item.id"
        />
      </el-select>
      <el-button @click="handleSearch">搜索</el-button>
      <el-button
        v-if="canCreate"
        type="primary"
        class="ml-auto add-btn"
        title="新增菜品"
        @click="openCreate"
      >
        +
      </el-button>
    </div>

    <div class="table-card">
      <el-table v-loading="loading" :data="dishes">
        <el-table-column prop="name" label="菜品" min-width="140" />
        <el-table-column prop="category_name" label="分类" width="100" />
        <el-table-column label="基础价" width="100">
          <template #default="{ row }">{{ formatPrice(row.base_price) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="DISH_STATUS_TAG[row.status] ?? 'info'" disable-transitions>
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="160" />
        <el-table-column v-if="canManage" label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canUpdate" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button
              v-if="canDelete"
              size="small"
              class="btn-delete"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadDishes"
      />
    </div>

    <DishFormDialog
      v-if="canManage"
      v-model="dialogVisible"
      :dish="editingDish"
      @success="handleDialogSuccess"
    />
  </div>
</template>

<style scoped>
.dishes {
  padding: 32px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.search-input {
  width: 220px;
}

.category-filter {
  width: 160px;
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

.add-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  font-size: 20px;
  line-height: 1;
}

/* 删除按钮：黑边框 + 灰底白字；悬停变黑底白字 */
.btn-delete {
  background: #6b6b6b;
  border-color: #1f1f1f;
  color: #fff;
}

.btn-delete:hover,
.btn-delete:focus {
  background: #1f1f1f;
  border-color: #1f1f1f;
  color: #fff;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>