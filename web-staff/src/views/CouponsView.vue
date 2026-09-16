<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteCouponTemplate,
  getCouponTemplates,
  updateCouponTemplate,
} from '@/api/coupons'
import type { CouponTemplate } from '@/api/types'
import {
  COUPON_STATUS_TAG,
  COUPON_TEMPLATE_STATUS_OPTIONS,
  couponValueText,
} from '@/constants/coupon'
import CouponFormDialog from '@/components/CouponFormDialog.vue'
import CouponIssueDialog from '@/components/CouponIssueDialog.vue'
import { useAuthStore } from '@/stores/auth'
import { formatLocalTime } from '@/utils/format'

const authStore = useAuthStore()

// 建/改/删模板是 coupon:manage，发券是 coupon:issue——**两个码是分开的**：
// 能设计券的人不一定该能随便发（发出去就是成本）。
// 两个码目前只有运营主管和老板有，所以页面上看不出区别；单独给谁 coupon:issue
// 的时候，这一页（要 coupon:manage）他进不来，得另开一个「发券」入口
const canManage = computed(() => authStore.hasPermission('coupon:manage'))
const canIssue = computed(() => authStore.hasPermission('coupon:issue'))

const templates = ref<CouponTemplate[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const status = ref('')
const loading = ref(false)

const formVisible = ref(false)
const editingTemplate = ref<CouponTemplate | null>(null)
const issueVisible = ref(false)
const issuingTemplate = ref<CouponTemplate | null>(null)

async function loadTemplates() {
  loading.value = true
  try {
    const data = await getCouponTemplates({
      search: search.value,
      // 空字符串要转成 undefined 才会被 axios 丢掉——直接传 '' 后端会当成
      // 「状态是空串」去校验，然后 422（订单页的 status 也是这么处理的）
      status: status.value || undefined,
      page: page.value,
    })
    templates.value = data.templates
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadTemplates()
}

function openCreate() {
  editingTemplate.value = null
  formVisible.value = true
}

function openEdit(template: CouponTemplate) {
  editingTemplate.value = template
  formVisible.value = true
}

function openIssue(template: CouponTemplate) {
  issuingTemplate.value = template
  issueVisible.value = true
}

/** 停用/启用：**只影响还能不能再发**，已经发出去的不受影响 */
async function toggleStatus(template: CouponTemplate) {
  const next = template.status === 'active' ? 'disabled' : 'active'
  const word = next === 'disabled' ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(
      next === 'disabled'
        ? `停用「${template.name}」后不能再发，已经发到顾客手里的 ${template.issued_count} 张照常能用。`
        : `重新启用「${template.name}」？启用后可以继续发给会员。`,
      `${word}确认`,
      { type: 'warning', confirmButtonText: word, cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await updateCouponTemplate(template.id, { status: next })
    ElMessage.success(`${word}成功`)
    loadTemplates()
  } catch {
    // 拦截器已提示
  }
}

async function handleDelete(template: CouponTemplate) {
  try {
    await ElMessageBox.confirm(
      `确定删除券模板「${template.name}」吗？\n` +
        '发出去过的模板删不掉（顾客手里那张券会变成没头没尾的东西），' +
        '不想再发请用「停用」。',
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteCouponTemplate(template.id)
    ElMessage.success('删除成功')
    if (templates.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    loadTemplates()
  } catch {
    // 拦截器已提示（还有券挂在上面）
  }
}

function handleDialogSuccess() {
  formVisible.value = false
  issueVisible.value = false
  loadTemplates()
}

/** 适用门店：全公司通用是常态，门店多的时候只报个数，不然这列会被撑爆 */
function storeText(template: CouponTemplate): string {
  if (template.is_all_stores) return '全公司'
  if (template.store_names.length === 1) return template.store_names[0]
  return `${template.store_names[0]} 等 ${template.store_names.length} 家`
}

onMounted(loadTemplates)
</script>

<template>
  <div class="coupons">
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索券名"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-select
        v-model="status"
        placeholder="全部状态"
        clearable
        class="status-select"
        @change="handleSearch"
      >
        <el-option
          v-for="item in COUPON_TEMPLATE_STATUS_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-button @click="handleSearch">搜索</el-button>
      <el-button v-if="canManage" type="primary" class="ml-auto add-btn" title="新建券" @click="openCreate">
        +
      </el-button>
    </div>

    <p class="hint">
      这里是<strong>券模板</strong>——「满 100 减 20」这条规则，发出去多少张都是它。
      顾客手里那张是<strong>券</strong>，有自己的领取时间和使用记录。
      改模板不影响已经发出去的券，改券也不会动到模板。
    </p>

    <div class="table-card">
      <el-table v-loading="loading" :data="templates">
        <el-table-column label="券名" min-width="155">
          <template #default="{ row }">
            <div class="coupon-name">{{ row.name }}</div>
            <div class="sub">
              {{ row.type_label }} · 已发 {{ row.issued_count }} 张
            </div>
          </template>
        </el-table-column>
        <el-table-column label="优惠" width="125">
          <template #default="{ row }">
            <div class="coupon-value">{{ couponValueText(row) }}</div>
            <div class="sub">
              {{ row.min_amount > 0 ? `满 ¥${row.min_amount.toFixed(0)}` : '无门槛' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="有效期" width="145">
          <template #default="{ row }">
            <div>{{ row.valid_to ? formatLocalTime(row.valid_to) : '长期有效' }}</div>
            <div v-if="row.valid_from" class="sub">
              {{ formatLocalTime(row.valid_from) }} 起
            </div>
          </template>
        </el-table-column>
        <el-table-column label="适用门店" min-width="95">
          <template #default="{ row }">
            <span :title="row.store_names.join('、')">{{ storeText(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="发放量" width="75">
          <template #default="{ row }">
            <span v-if="row.total_quantity">{{ row.issued_count }}/{{ row.total_quantity }}</span>
            <span v-else class="muted">不限</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="75">
          <template #default="{ row }">
            <el-tag :type="COUPON_STATUS_TAG[row.status] ?? 'info'" disable-transitions>
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="canManage || canIssue" label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canIssue"
              size="small"
              :disabled="row.status !== 'active'"
              @click="openIssue(row)"
            >
              发券
            </el-button>
            <template v-if="canManage">
              <el-button size="small" link @click="openEdit(row)">编辑</el-button>
              <el-button size="small" link @click="toggleStatus(row)">
                {{ row.status === 'active' ? '停用' : '启用' }}
              </el-button>
              <el-button size="small" link class="link-danger" @click="handleDelete(row)">
                删除
              </el-button>
            </template>
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
        @current-change="loadTemplates"
      />
    </div>

    <CouponFormDialog
      v-if="canManage"
      v-model="formVisible"
      :template="editingTemplate"
      @success="handleDialogSuccess"
    />
    <CouponIssueDialog
      v-if="canIssue"
      v-model="issueVisible"
      :template="issuingTemplate"
      @success="handleDialogSuccess"
    />
  </div>
</template>

<style scoped>
.coupons {
  padding: 32px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.search-input {
  width: 240px;
}

.status-select {
  width: 130px;
}

.ml-auto {
  margin-left: auto;
}

.add-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  font-size: 20px;
  line-height: 1;
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

.coupon-name {
  font-weight: 600;
  color: #1f1f1f;
  line-height: 1.4;
}

.coupon-value {
  font-weight: 600;
  color: #1f1f1f;
  line-height: 1.4;
}

/* 次要信息做成下面一行小字，和门店页一个路子 */
.sub {
  font-size: 12px;
  color: #a0a0a0;
  line-height: 1.4;
}

.muted {
  color: #c0c0c0;
}

.link-danger {
  color: #c45656;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>