<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createMember, getBalanceTxns, getMembers, rechargeBalance } from '@/api/members'
import type { BalanceTxn, Member } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { formatPrice, formatTime } from '@/utils/format'

const authStore = useAuthStore()

// 会员这块的权限码分三段，别混：
//   member:manage            改会员资料（建档）
//   member:balance:recharge  充值——**钱的入口**，单独一个码
//   member:balance:view      看余额 + 流水
const canManage = computed(() => authStore.hasPermission('member:manage'))
const canRecharge = computed(() => authStore.hasPermission('member:balance:recharge'))
const canSeeBalance = computed(() => authStore.hasPermission('member:balance:view'))

const members = ref<Member[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const loading = ref(false)

async function loadMembers() {
  loading.value = true
  try {
    const data = await getMembers({ search: search.value, page: page.value })
    members.value = data.members
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadMembers()
}

// ---------- 建档 ----------

const createVisible = ref(false)
const creating = ref(false)
const form = ref({ mobile: '', nickname: '' })

function openCreate() {
  form.value = { mobile: '', nickname: '' }
  createVisible.value = true
}

async function handleCreate() {
  if (!form.value.mobile.trim()) {
    ElMessage.warning('手机号必填——它是会员的身份标识')
    return
  }
  creating.value = true
  try {
    await createMember({
      mobile: form.value.mobile.trim(),
      nickname: form.value.nickname.trim(),
    })
    ElMessage.success('已建档')
    createVisible.value = false
    handleSearch()
  } catch {
    // 拦截器已提示（手机号重复等）
  } finally {
    creating.value = false
  }
}

// ---------- 充值 ----------

const rechargeVisible = ref(false)
const recharging = ref(false)
const current = ref<Member | null>(null)
const rechargeForm = ref({ principal: 100, bonus: 0, remark: '' })

/** 充完之后账上会有多少——收银员要当场报给顾客听 */
const afterRecharge = computed(() => {
  const now = current.value?.balance?.total ?? 0
  return now + (rechargeForm.value.principal || 0) + (rechargeForm.value.bonus || 0)
})

function openRecharge(row: Member) {
  current.value = row
  rechargeForm.value = { principal: 100, bonus: 0, remark: '' }
  rechargeVisible.value = true
}

async function handleRecharge() {
  if (!current.value) return
  if (rechargeForm.value.principal <= 0 && rechargeForm.value.bonus <= 0) {
    ElMessage.warning('本金和赠送不能都是 0')
    return
  }
  recharging.value = true
  try {
    await rechargeBalance(current.value.id, {
      principal: rechargeForm.value.principal || 0,
      bonus: rechargeForm.value.bonus || 0,
      remark: rechargeForm.value.remark.trim(),
    })
    ElMessage.success('充值成功')
    rechargeVisible.value = false
    loadMembers()
  } catch {
    // 拦截器已提示（会员停用、金额为负等）
  } finally {
    recharging.value = false
  }
}

// ---------- 流水 ----------

const txnVisible = ref(false)
const txns = ref<BalanceTxn[]>([])
const txnLoading = ref(false)
const txnMember = ref<Member | null>(null)

async function openTxns(row: Member) {
  txnMember.value = row
  txnVisible.value = true
  txnLoading.value = true
  try {
    const data = await getBalanceTxns(row.id)
    txns.value = data.txns
  } catch {
    txns.value = []
  } finally {
    txnLoading.value = false
  }
}

onMounted(loadMembers)
</script>

<template>
  <div class="members">
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索手机号或昵称"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button @click="handleSearch">搜索</el-button>
      <p class="hint">顾客报手机号，这里搜出来就能看余额——收银台常用</p>
      <el-button
        v-if="canManage"
        type="primary"
        class="ml-auto add-btn"
        title="新会员"
        @click="openCreate"
      >
        +
      </el-button>
    </div>

    <div class="table-card">
      <el-table v-loading="loading" :data="members">
        <el-table-column label="手机号" width="140">
          <template #default="{ row }">
            <span v-if="row.mobile">{{ row.mobile }}</span>
            <span v-else class="muted">—（微信会员）</span>
          </template>
        </el-table-column>
        <el-table-column prop="nickname" label="昵称" min-width="120" />
        <el-table-column v-if="canSeeBalance" label="储值余额" width="200">
          <template #default="{ row }">
            <template v-if="row.balance">
              <span class="balance-total">{{ formatPrice(row.balance.total) }}</span>
              <span class="balance-detail">
                本金 {{ formatPrice(row.balance.principal) }}
                · 赠送 {{ formatPrice(row.balance.bonus) }}
              </span>
            </template>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success" size="small" disable-transitions>
              正常
            </el-tag>
            <el-tag v-else type="info" size="small" disable-transitions>已停用</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="建档时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canRecharge"
              size="small"
              :disabled="!row.is_active"
              @click="openRecharge(row)"
            >
              充值
            </el-button>
            <el-button v-if="canSeeBalance" size="small" link @click="openTxns(row)">
              流水
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
        @current-change="loadMembers"
      />
    </div>

    <!-- 建档 -->
    <el-dialog v-model="createVisible" title="新会员" width="380px">
      <el-form label-width="70px">
        <el-form-item label="手机号">
          <el-input v-model="form.mobile" placeholder="会员的身份标识，必填" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" placeholder="可以不填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">建档</el-button>
      </template>
    </el-dialog>

    <!-- 充值 -->
    <el-dialog v-model="rechargeVisible" title="储值充值" width="440px">
      <div v-if="current" class="recharge-body">
        <p class="recharge-who">
          {{ current.nickname || '未命名' }}
          <span v-if="current.mobile" class="muted">{{ current.mobile }}</span>
        </p>
        <p class="recharge-now">
          当前余额 <strong>{{ formatPrice(current.balance?.total ?? 0) }}</strong>
          <span class="balance-detail">
            本金 {{ formatPrice(current.balance?.principal ?? 0) }}
            · 赠送 {{ formatPrice(current.balance?.bonus ?? 0) }}
          </span>
        </p>

        <el-form label-width="90px" class="recharge-form">
          <el-form-item label="本金">
            <el-input-number v-model="rechargeForm.principal" :min="0" :precision="2" />
            <span class="field-hint">顾客真掏的钱，<strong>能退</strong></span>
          </el-form-item>
          <el-form-item label="赠送">
            <el-input-number v-model="rechargeForm.bonus" :min="0" :precision="2" />
            <span class="field-hint">充多少送多少就填这儿，<strong>不退</strong></span>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="rechargeForm.remark" placeholder="选填" />
          </el-form-item>
        </el-form>

        <p class="after">
          充完账上会有 <strong>{{ formatPrice(afterRecharge) }}</strong>
        </p>
      </div>
      <template #footer>
        <el-button @click="rechargeVisible = false">取消</el-button>
        <el-button type="primary" :loading="recharging" @click="handleRecharge">
          确认充值
        </el-button>
      </template>
    </el-dialog>

    <!-- 流水 -->
    <el-dialog v-model="txnVisible" title="余额流水" width="620px">
      <p class="txn-who">
        {{ txnMember?.nickname || '未命名' }}
        <span v-if="txnMember?.mobile" class="muted">{{ txnMember.mobile }}</span>
      </p>
      <el-table v-loading="txnLoading" :data="txns" size="small">
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="type_label" label="类型" width="110" />
        <el-table-column label="变动" width="100">
          <template #default="{ row }">
            <span :class="row.amount >= 0 ? 'gain' : 'spend'">
              {{ row.amount >= 0 ? '+' : '' }}{{ formatPrice(row.amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="本金 / 赠送" width="150">
          <template #default="{ row }">
            {{ formatPrice(row.principal_delta) }} / {{ formatPrice(row.bonus_delta) }}
          </template>
        </el-table-column>
        <el-table-column label="变动后余额" min-width="130">
          <template #default="{ row }">{{ formatPrice(row.principal_after + row.bonus_after) }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="120" />
      </el-table>
      <p class="txn-hint">
        储值分<strong>本金</strong>（能退）和<strong>赠送</strong>（不退）。扣款时先扣赠送——先花掉不能退的那部分。
      </p>
    </el-dialog>
  </div>
</template>

<style scoped>
.members {
  padding: 32px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.search-input {
  width: 260px;
}

.hint {
  font-size: 13px;
  color: #a0a0a0;
}

.add-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  font-size: 20px;
}

.ml-auto {
  margin-left: auto;
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

.balance-total {
  display: block;
  font-weight: 600;
  color: #1f1f1f;
}

.balance-detail {
  display: block;
  font-size: 12px;
  color: #a0a0a0;
}

.muted {
  color: #c0c0c0;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.recharge-who {
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 4px;
}

.recharge-now {
  font-size: 14px;
  color: #1f1f1f;
  margin-bottom: 16px;
}

.recharge-form {
  margin-top: 8px;
}

.field-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #a0a0a0;
}

.after {
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid #e5e5e5;
  font-size: 14px;
  color: #1f1f1f;
}

.txn-who {
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 12px;
}

.gain {
  color: #2f855a;
}

.spend {
  color: #c45656;
}

.txn-hint {
  margin-top: 12px;
  font-size: 12px;
  color: #a0a0a0;
}
</style>