<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteCategory, getCategories } from '@/api/categories'
import type { Category } from '@/api/types'
import CategoryFormDialog from '@/components/CategoryFormDialog.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 分类的增删改分别是 menu:create / menu:update / menu:delete。
// 店长只有 menu:update（而且只对本店），这里只用 create 判定「能不能管分类」，
// 精确到单个动作的判断交给后端——前端只负责别把明显点不动的按钮画出来。
const canCreate = computed(() => authStore.hasPermission('menu:create'))
const canUpdate = computed(() => authStore.hasPermission('menu:update'))
const canDelete = computed(() => authStore.hasPermission('menu:delete'))
const canManage = computed(() => canCreate.value || canUpdate.value || canDelete.value)

const categories = ref<Category[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const loading = ref(false)

const dialogVisible = ref(false)
const editingCategory = ref<Category | null>(null)

async function loadCategories() {
  loading.value = true
  try {
    const data = await getCategories({ search: search.value, page: page.value })
    categories.value = data.categories
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadCategories()
}

function openCreate() {
  editingCategory.value = null
  dialogVisible.value = true
}

function openEdit(category: Category) {
  editingCategory.value = category
  dialogVisible.value = true
}

async function handleDelete(category: Category) {
  try {
    await ElMessageBox.confirm(
      `确定删除分类「${category.name}」吗？\n分类下面还有菜品时无法删除，需要先把菜品移到别的分类。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteCategory(category.id)
    ElMessage.success('删除成功')
    if (categories.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    loadCategories()
  } catch {
    // 拦截器已提示
  }
}

function handleDialogSuccess() {
  dialogVisible.value = false
  loadCategories()
}

onMounted(loadCategories)
</script>

<template>
  <div class="categories">
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索分类名称"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button @click="handleSearch">搜索</el-button>
      <el-button
        v-if="canCreate"
        type="primary"
        class="ml-auto add-btn"
        title="新增分类"
        @click="openCreate"
      >
        +
      </el-button>
    </div>

    <div class="table-card">
      <el-table v-loading="loading" :data="categories">
        <el-table-column prop="icon" label="图标" width="70" />
        <el-table-column prop="name" label="分类名称" min-width="140" />
        <el-table-column label="适用门店" min-width="180">
          <template #default="{ row }">
            <el-tag v-if="row.is_all_stores" type="info" size="small" disable-transitions>
              全公司通用
            </el-tag>
            <span v-else>{{ row.store_names.join('、') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="显示" width="80">
          <template #default="{ row }">{{ row.is_visible ? '显示' : '隐藏' }}</template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="80" />
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
        @current-change="loadCategories"
      />
    </div>

    <CategoryFormDialog
      v-if="canManage"
      v-model="dialogVisible"
      :category="editingCategory"
      @success="handleDialogSuccess"
    />
  </div>
</template>

<style scoped>
.categories {
  padding: 32px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.search-input {
  width: 260px;
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