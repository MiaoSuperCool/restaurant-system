<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createLegacyMap,
  deleteLegacyMap,
  getLegacyMaps,
  getReconciliations,
  getSyncRecords,
  resolveLegacyId,
  runReconciliation,
} from '@/api/legacy'
import { getStoreOptions } from '@/api/stores'
import type {
  LegacyMap,
  Reconciliation,
  StoreOption,
  SyncRecord,
  SyncSummary,
} from '@/api/types'
import {
  MAP_TARGET_OPTIONS,
  RECONCILIATION_CATEGORY_OPTIONS,
  RECONCILIATION_STATUS_TAG,
  SYNC_CATEGORY_OPTIONS,
  SYNC_DIRECTION_OPTIONS,
  SYNC_STATUS_OPTIONS,
  SYNC_STATUS_TAG,
  detailWho,
} from '@/constants/legacy'
import { formatPrice, formatTime } from '@/utils/format'

const tab = ref<'reconcile' | 'sync' | 'maps'>('reconcile')

const stores = ref<StoreOption[]>([])
const pageSize = 10

// ---------- 对账 ----------

const records = ref<Reconciliation[]>([])
const recordTotal = ref(0)
const recordPage = ref(1)
const category = ref('')
const status = ref('')
const recordsLoading = ref(false)

async function loadRecords() {
  recordsLoading.value = true
  try {
    const data = await getReconciliations({
      // 空字符串要转成 undefined 才会被 axios 丢掉，不然后端按「状态是空串」校验会 422
      category: category.value || undefined,
      status: status.value || undefined,
      page: recordPage.value,
    })
    records.value = data.records
    recordTotal.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    recordsLoading.value = false
  }
}

const runVisible = ref(false)
const running = ref(false)
const runForm = ref({ category: 'balance', store_id: null as number | null, biz_date: '' })

/** 订单对账必须挑门店；储值不挂门店，所以那个下拉只在这时候出现 */
const runNeedsStore = computed(() => runForm.value.category === 'order')

function openRun() {
  const today = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  runForm.value = {
    category: 'balance',
    store_id: stores.value[0]?.id ?? null,
    biz_date: `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`,
  }
  runVisible.value = true
}

async function handleRun() {
  if (runNeedsStore.value && runForm.value.store_id === null) {
    ElMessage.warning('订单对账要先选门店')
    return
  }
  running.value = true
  try {
    const record = await runReconciliation({
      category: runForm.value.category,
      biz_date: runForm.value.biz_date || undefined,
      store_id: runNeedsStore.value ? runForm.value.store_id! : undefined,
    })
    if (record.status === 'matched') {
      ElMessage.success(`${record.biz_date} ${record.store_name} 对得上`)
    } else {
      ElMessage.warning(`${record.mismatch_count} 处对不上，看明细`)
    }
    runVisible.value = false
    recordPage.value = 1
    loadRecords()
  } catch {
    // 拦截器已提示
  } finally {
    running.value = false
  }
}

// 差异明细
const detailVisible = ref(false)
const detailRecord = ref<Reconciliation | null>(null)
const detailRows = ref<Reconciliation['detail']>([])

function openDetail(record: Reconciliation) {
  detailRecord.value = record
  detailRows.value = record.detail ?? []
  detailVisible.value = true
}

// ---------- 同步记录 ----------

const syncRecords = ref<SyncRecord[]>([])
const syncSummary = ref<SyncSummary>({ success: 0, failed: 0, pending: 0, total: 0 })
const syncTotal = ref(0)
const syncPage = ref(1)
const syncFilter = ref({ direction: '', category: '', status: '' })
const syncLoading = ref(false)

async function loadSyncRecords() {
  syncLoading.value = true
  try {
    const data = await getSyncRecords({
      direction: syncFilter.value.direction || undefined,
      category: syncFilter.value.category || undefined,
      status: syncFilter.value.status || undefined,
      page: syncPage.value,
    })
    syncRecords.value = data.records
    syncSummary.value = data.summary
    syncTotal.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    syncLoading.value = false
  }
}

// ---------- ID 映射 ----------

const maps = ref<LegacyMap[]>([])
const mapTotal = ref(0)
const mapPage = ref(1)
const mapSearch = ref('')
const mapsLoading = ref(false)

async function loadMaps() {
  mapsLoading.value = true
  try {
    const data = await getLegacyMaps({ search: mapSearch.value, page: mapPage.value })
    maps.value = data.maps
    mapTotal.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    mapsLoading.value = false
  }
}

// 按老号查——客服拿着老会员号来问的那个动作
const lookupId = ref('')
const lookupResult = ref<string | null>(null)
const lookupLoading = ref(false)

async function handleLookup() {
  const legacyId = lookupId.value.trim()
  if (!legacyId) {
    ElMessage.warning('填一个老系统的号')
    return
  }
  lookupLoading.value = true
  lookupResult.value = null
  try {
    const data = await resolveLegacyId({ legacy_id: legacyId })
    if (!data.found) {
      lookupResult.value = `老系统的号 ${legacyId} 在新系统里没有对应记录（没迁过，或者号填错了）`
      return
    }
    const target = data.target ?? {}
    const who = [target.nickname, target.mobile].filter(Boolean).join(' · ')
    lookupResult.value = `对应新系统 #${target.id} ${who || target.member_id || ''}`
  } catch {
    // 拦截器已提示
  } finally {
    lookupLoading.value = false
  }
}

// 手工补一条映射
const bindVisible = ref(false)
const binding = ref(false)
const bindForm = ref({ target_type: 'member', target_id: 0, legacy_id: '', remark: '' })

function openBind() {
  bindForm.value = { target_type: 'member', target_id: 0, legacy_id: '', remark: '' }
  bindVisible.value = true
}

async function handleBind() {
  if (!bindForm.value.target_id) {
    ElMessage.warning('要填新系统里的 id——先在会员页找到这个人')
    return
  }
  if (!bindForm.value.legacy_id.trim()) {
    ElMessage.warning('要填老系统的号')
    return
  }
  binding.value = true
  try {
    await createLegacyMap({
      target_type: bindForm.value.target_type,
      target_id: bindForm.value.target_id,
      legacy_id: bindForm.value.legacy_id.trim(),
      remark: bindForm.value.remark.trim(),
    })
    ElMessage.success('记好了')
    bindVisible.value = false
    loadMaps()
  } catch {
    // 拦截器已提示（老号重复、对象不存在等）
  } finally {
    binding.value = false
  }
}

async function handleUnbind(map: LegacyMap) {
  try {
    await ElMessageBox.confirm(
      `删掉「${map.legacy_id} → #${map.target_id}」这条对应关系？\n` +
        '删掉之后就没有别的地方能查到这条老数据迁到哪去了，只在该映射录错时才删。',
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteLegacyMap(map.id)
    ElMessage.success('已删除')
    loadMaps()
  } catch {
    // 拦截器已提示
  }
}

function handleTabChange() {
  if (tab.value === 'sync' && syncRecords.value.length === 0) loadSyncRecords()
  if (tab.value === 'maps' && maps.value.length === 0) loadMaps()
}

onMounted(async () => {
  loadRecords()
  try {
    stores.value = (await getStoreOptions()).stores
  } catch {
    // 拦截器已提示
  }
})
</script>

<template>
  <div class="legacy">
    <el-tabs v-model="tab" @tab-change="handleTabChange">
      <!-- ---------------- 对账 ---------------- -->
      <el-tab-pane label="对账" name="reconcile">
        <div class="toolbar">
          <el-select
            v-model="category"
            placeholder="全部类别"
            clearable
            class="filter"
            @change="recordPage = 1; loadRecords()"
          >
            <el-option
              v-for="item in RECONCILIATION_CATEGORY_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-select
            v-model="status"
            placeholder="全部状态"
            clearable
            class="filter"
            @change="recordPage = 1; loadRecords()"
          >
            <el-option label="对得上" value="matched" />
            <el-option label="有差异" value="mismatched" />
          </el-select>
          <el-button @click="loadRecords">刷新</el-button>
          <el-button type="primary" class="ml-auto" @click="openRun">跑一次对账</el-button>
        </div>

        <p class="hint">
          <strong>对的是两边的数</strong>：储值是「账户余额 vs 流水累加」，订单是
          「订单实收 vs 支付流水」。前者按会员一条条比——<strong>总额平了不代表没问题</strong>，
          一个人多 100、一个人少 100，合计正好抵消，所以「处数」这一列比「差异」更该看。
          日结的常态是定时任务在跑（<code>python manage.py reconcile</code>），这里手工点只是查漏。
        </p>

        <div class="table-card">
          <el-table v-loading="recordsLoading" :data="records">
            <el-table-column label="业务日期" width="110">
              <template #default="{ row }">
                <span v-if="row.biz_date">{{ row.biz_date }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="store_name" label="范围" min-width="110" />
            <el-table-column prop="category_label" label="类别" width="70" />
            <el-table-column label="期望（流水）" width="110">
              <template #default="{ row }">{{ formatPrice(row.expected_amount) }}</template>
            </el-table-column>
            <el-table-column label="实际（账上）" width="110">
              <template #default="{ row }">{{ formatPrice(row.actual_amount) }}</template>
            </el-table-column>
            <el-table-column label="差异" width="100">
              <template #default="{ row }">
                <span :class="{ 'text-danger': row.diff_amount !== 0 }">
                  {{ formatPrice(row.diff_amount) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="处数" width="70">
              <template #default="{ row }">
                <span v-if="row.mismatch_count" class="text-danger">
                  {{ row.mismatch_count }}
                </span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag
                  :type="RECONCILIATION_STATUS_TAG[row.status] ?? 'info'"
                  disable-transitions
                >
                  {{ row.status_label }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.mismatch_count"
                  size="small"
                  link
                  @click="openDetail(row)"
                >
                  差异
                </el-button>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="recordPage"
            :page-size="pageSize"
            :total="recordTotal"
            layout="total, prev, pager, next"
            @current-change="loadRecords"
          />
        </div>
      </el-tab-pane>

      <!-- ---------------- 同步记录 ---------------- -->
      <el-tab-pane label="同步记录" name="sync">
        <div class="summary">
          <span class="summary-item">
            一共 <strong>{{ syncSummary.total }}</strong> 条
          </span>
          <span class="summary-item gain">成功 {{ syncSummary.success }}</span>
          <span class="summary-item spend">失败 {{ syncSummary.failed }}</span>
          <span v-if="syncSummary.pending" class="summary-item">
            待重试 {{ syncSummary.pending }}
          </span>
        </div>

        <p class="hint">
          <strong>成功也记</strong>：只记失败的话，「今天到底推没推」没人答得上来——
          没记录既可能是「跑了全成功」，也可能是「压根没跑」。
          失败原因<strong>原样留着不翻译</strong>，排障的时候看的正是原文。
        </p>

        <div class="toolbar">
          <el-select
            v-model="syncFilter.direction"
            placeholder="全部方向"
            clearable
            class="filter"
            @change="syncPage = 1; loadSyncRecords()"
          >
            <el-option
              v-for="item in SYNC_DIRECTION_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-select
            v-model="syncFilter.category"
            placeholder="全部类别"
            clearable
            class="filter"
            @change="syncPage = 1; loadSyncRecords()"
          >
            <el-option
              v-for="item in SYNC_CATEGORY_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-select
            v-model="syncFilter.status"
            placeholder="全部状态"
            clearable
            class="filter"
            @change="syncPage = 1; loadSyncRecords()"
          >
            <el-option
              v-for="item in SYNC_STATUS_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>

        <div class="table-card">
          <el-table v-loading="syncLoading" :data="syncRecords">
            <el-table-column label="时间" width="145">
              <template #default="{ row }">{{ formatTime(row.synced_at, true) }}</template>
            </el-table-column>
            <el-table-column prop="direction_label" label="方向" width="80" />
            <el-table-column label="对象" width="90">
              <template #default="{ row }">{{ row.target_label }} · {{ row.category_label }}</template>
            </el-table-column>
            <el-table-column prop="ref" label="哪一条" min-width="130" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="SYNC_STATUS_TAG[row.status] ?? 'info'" disable-transitions>
                  {{ row.status_label }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="说明" min-width="220">
              <template #default="{ row }">
                <span :class="{ 'text-danger': row.status === 'failed' }">
                  {{ row.message || '—' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="syncPage"
            :page-size="pageSize"
            :total="syncTotal"
            layout="total, prev, pager, next"
            @current-change="loadSyncRecords"
          />
        </div>
      </el-tab-pane>

      <!-- ---------------- ID 映射 ---------------- -->
      <el-tab-pane label="ID 映射" name="maps">
        <p class="hint">
          「老系统里的 M0001001 是新系统的 37 号」。迁移是一次性的动作，但
          <strong>查这个对应关系是长期的事</strong>——客服拿着老会员号来问、
          账对不上要倒查，都得能查回来。所以它不是迁移脚本里的临时表。
        </p>

        <div class="lookup">
          <el-input
            v-model="lookupId"
            placeholder="贴一个老系统的会员号，比如 M0001001"
            clearable
            class="lookup-input"
            @keyup.enter="handleLookup"
          />
          <el-button :loading="lookupLoading" @click="handleLookup">查这是谁</el-button>
          <p v-if="lookupResult" class="lookup-result">{{ lookupResult }}</p>
        </div>

        <div class="toolbar">
          <el-input
            v-model="mapSearch"
            placeholder="搜索老系统的号"
            clearable
            class="search-input"
            @keyup.enter="mapPage = 1; loadMaps()"
            @clear="mapPage = 1; loadMaps()"
          />
          <el-button @click="mapPage = 1; loadMaps()">搜索</el-button>
          <el-button type="primary ml-auto" @click="openBind">手工补一条</el-button>
        </div>

        <div class="table-card">
          <el-table v-loading="mapsLoading" :data="maps">
            <el-table-column prop="legacy_id" label="老系统的号" min-width="140" />
            <el-table-column prop="target_type_label" label="类型" width="100" />
            <el-table-column label="新系统" width="100">
              <template #default="{ row }">#{{ row.target_id }}</template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="180" />
            <el-table-column label="记录时间" width="145">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link class="link-danger" @click="handleUnbind(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="mapPage"
            :page-size="pageSize"
            :total="mapTotal"
            layout="total, prev, pager, next"
            @current-change="loadMaps"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 跑一次对账 -->
    <el-dialog v-model="runVisible" title="跑一次对账" width="440px">
      <el-form label-width="88px">
        <el-form-item label="类别">
          <el-radio-group v-model="runForm.category">
            <el-radio value="balance">储值</el-radio>
            <el-radio value="order">订单</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="runNeedsStore" label="门店">
          <el-select v-model="runForm.store_id" placeholder="选门店" class="full-width">
            <el-option
              v-for="store in stores"
              :key="store.id"
              :label="store.name"
              :value="store.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="业务日期">
          <el-date-picker
            v-model="runForm.biz_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="默认今天"
            class="full-width"
          />
        </el-form-item>
      </el-form>

      <p class="dialog-hint">
        储值对账<strong>只有「此刻」这一种</strong>——余额表存的是现在账上多少，
        没有历史快照，所以传历史日期只是给结论贴个日期标签。
        订单对账按业务日期算，那是「这个营业日收了多少」。
      </p>
      <p class="dialog-hint">
        同一个（日期、门店、类别）重跑会<strong>覆盖</strong>旧结论——对账的语义
        就是重新下一遍。
      </p>

      <template #footer>
        <el-button @click="runVisible = false">取消</el-button>
        <el-button type="primary" :loading="running" @click="handleRun">开始对账</el-button>
      </template>
    </el-dialog>

    <!-- 差异明细 -->
    <el-dialog v-model="detailVisible" title="对不上的明细" width="620px">
      <p v-if="detailRecord" class="dialog-hint">
        {{ detailRecord.biz_date }} · {{ detailRecord.store_name }} ·
        {{ detailRecord.category_label }}：一共 {{ detailRecord.mismatch_count }} 处对不上<template
          v-if="detailRows.length < detailRecord.mismatch_count"
        >（下面只列前 {{ detailRows.length }} 条）</template>
      </p>
      <el-table :data="detailRows" size="small" max-height="320">
        <el-table-column label="是谁" min-width="150">
          <template #default="{ row }">{{ detailWho(row) }}</template>
        </el-table-column>
        <el-table-column label="期望（流水）" width="120">
          <template #default="{ row }">{{ formatPrice(row.expected) }}</template>
        </el-table-column>
        <el-table-column label="实际（账上）" width="120">
          <template #default="{ row }">{{ formatPrice(row.actual) }}</template>
        </el-table-column>
        <el-table-column label="差异" width="100">
          <template #default="{ row }">
            <span class="text-danger">{{ formatPrice(row.diff) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <p class="dialog-hint">
        差异 = 实际 − 期望。正数是账上比流水多出来的钱。
      </p>
    </el-dialog>

    <!-- 手工补一条映射 -->
    <el-dialog v-model="bindVisible" title="补一条 ID 映射" width="460px">
      <el-form label-width="100px">
        <el-form-item label="对象类型">
          <el-radio-group v-model="bindForm.target_type">
            <el-radio
              v-for="item in MAP_TARGET_OPTIONS"
              :key="item.value"
              :value="item.value"
            >
              {{ item.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="新系统 id">
          <el-input-number v-model="bindForm.target_id" :min="1" :controls="false" />
        </el-form-item>
        <el-form-item label="老系统的号">
          <el-input v-model="bindForm.legacy_id" placeholder="如 M0010086" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="bindForm.remark" placeholder="选填，如：迁移时漏掉的" />
        </el-form-item>
      </el-form>
      <p class="dialog-hint">
        一般不用手工补——迁移命令会一条条记下来。这里留给「老系统后来才补录的人」
        和「迁移时漏掉的个别人」。老号和新对象<strong>两个方向都不能重复</strong>，
        重了会直接报错。
      </p>
      <template #footer>
        <el-button @click="bindVisible = false">取消</el-button>
        <el-button type="primary" :loading="binding" @click="handleBind">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.legacy {
  padding: 32px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.filter {
  width: 130px;
}

.search-input {
  width: 220px;
}

.ml-auto {
  margin-left: auto;
}

.hint {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.7;
  margin-bottom: 16px;
}

.hint code {
  background: #f0f0f0;
  padding: 1px 5px;
  border-radius: 3px;
}

.summary {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 16px;
  margin-bottom: 12px;
  background: #f5f5f5;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  font-size: 14px;
  color: #1f1f1f;
}

.summary-item strong {
  font-size: 18px;
}

.gain {
  color: #2f855a;
}

.spend,
.text-danger {
  color: #c45656;
}

.muted {
  color: #c0c0c0;
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

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.lookup {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
  margin-bottom: 16px;
  background: #f5f5f5;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
}

.lookup-input {
  width: 280px;
}

.lookup-result {
  width: 100%;
  font-size: 13px;
  color: #1f1f1f;
}

.full-width {
  width: 100%;
}

.dialog-hint {
  font-size: 12px;
  color: #a0a0a0;
  line-height: 1.7;
  margin-top: 8px;
}

.link-danger {
  color: #c45656;
}
</style>