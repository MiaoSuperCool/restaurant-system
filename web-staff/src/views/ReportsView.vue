<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getReportOverview } from '@/api/reports'
import type { ReportOverview } from '@/api/reports'
import { getStoreOptions } from '@/api/stores'
import type { StoreOption } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { formatPrice } from '@/utils/format'

const authStore = useAuthStore()

/**
 * 能选门店的人就是「全部范围」的账号
 *
 * 店长只有一个数据范围，给他一个只有一家店的下拉框是添乱。
 * （后端那边照样会拦——这只是体验层）
 */
const canPickStore = computed(() => authStore.data_scope === 'all')

const RANGES = [
  { days: 1, label: '今天' },
  { days: 7, label: '近 7 天' },
  { days: 30, label: '近 30 天' },
]

const days = ref(7)
const storeId = ref<number | null>(null)
const stores = ref<StoreOption[]>([])
const data = ref<ReportOverview | null>(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    data.value = await getReportOverview({
      days: days.value,
      store_id: storeId.value ?? undefined,
    })
  } catch {
    // 拦截器已提示（没权限码、看了别家店都是 403）
  } finally {
    loading.value = false
  }
}

/**
 * 柱/条的长度：`base` 撑满，其余按比例（**不按固定刻度**，不然几毛钱的单看不出来）
 *
 * 两个细节：
 * - 有值但很小时给个 4% 的底——「卖了 1 块钱」和「压根没卖」在图上是两回事
 * - **真的为 0 就不画**。空着那一格才说明「这天没生意」，
 *   画一根小柱子反而像是有营业额
 */
function barLength(value: number, base: number): string {
  if (base <= 0) return '0%'
  return `${Math.max((value / base) * 100, value > 0 ? 4 : 0)}%`
}

/**
 * 刻度怎么写
 *
 * 柱子少（两周以内）写具体日期——「09-12」比「1」直观得多。
 * 柱子多就写**序号**（第几天）：30 天每根摊到 22px，而「09-12」要 35px，
 * 写日期会被挤到溢出（`white-space: nowrap` + flex 默认的 `min-width: auto`），
 * 只能抽稀——抽稀就会出现「有的柱子有标签、有的没有」，看着乱。
 * 序号只要 14px，30 个排得下，还整齐。
 *
 * 具体的日期和金额在 tooltip 里，鼠标放上去就有——**柱子本身只负责看趋势**。
 */
const compactTicks = computed(() => (data.value?.trend.length ?? 0) > 14)

function tickText(row: { date: string }, index: number): string {
  return compactTicks.value ? String(index + 1) : row.date.slice(5)
}

const trendMax = computed(() =>
  Math.max(...(data.value?.trend.map((row) => row.revenue) ?? [0]))
)
const hourMax = computed(() =>
  Math.max(...(data.value?.by_hour.map((row) => row.order_count) ?? [0]))
)
const dishMax = computed(() =>
  Math.max(...(data.value?.top_dishes.map((row) => row.quantity) ?? [0]))
)
const methodTotal = computed(() =>
  (data.value?.by_method ?? []).reduce((sum, row) => sum + row.amount, 0)
)
/** 某一笔支付占总额的百分比 */
function methodPercent(amount: number): string {
  if (methodTotal.value <= 0) return '0'
  return ((amount / methodTotal.value) * 100).toFixed(0)
}

const storeMax = computed(() =>
  Math.max(...(data.value?.by_store.map((row) => row.revenue) ?? [0]))
)

/** 门店对比只在有两家以上时才有意义——店长看到的就是一行，那张卡片是废话 */
const showStoreCompare = computed(() => (data.value?.by_store.length ?? 0) > 1)

onMounted(async () => {
  if (canPickStore.value) {
    try {
      stores.value = (await getStoreOptions()).stores
    } catch {
      // 拦截器已提示
    }
  }
  load()
})
</script>

<template>
  <div class="reports">
    <div class="toolbar">
      <!-- v-model 和 @change 一起用时，**@change 触发的那一刻 v-model 已经赋好值了**。
           所以这儿只能直接调 load，不能写「值没变就不请求」那种判断——
           写了的话永远成立，切换一次都不生效（这个 bug 就是这么来的） -->
      <el-radio-group v-model="days" @change="load">
        <el-radio-button v-for="item in RANGES" :key="item.days" :value="item.days">
          {{ item.label }}
        </el-radio-button>
      </el-radio-group>

      <el-select
        v-if="canPickStore"
        v-model="storeId"
        placeholder="全部门店"
        clearable
        class="store-select"
        @change="load"
      >
        <el-option v-for="store in stores" :key="store.id" :label="store.name" :value="store.id" />
      </el-select>

      <span v-if="data" class="range-hint">
        {{ data.range.start }} ~ {{ data.range.end }}（{{ data.range.days }} 天）
      </span>
    </div>

    <p class="hint">
      <strong>口径</strong>：营业额 = 已收 − 已退，<strong>排除已取消的单</strong>；
      营业日按<strong>下单时间</strong>算（和订单号里的日期、日结对账是同一个口径），
      不是按收款时间。时段按本地时间分——「几点最忙」问的是店里墙上那个钟。
    </p>

    <div v-loading="loading" class="body">
      <!-- ---------- 四个数 ---------- -->
      <div class="cards">
        <div class="card primary">
          <span class="card-label">营业额</span>
          <span class="card-value">{{ formatPrice(data?.summary.revenue ?? 0) }}</span>
        </div>
        <div class="card">
          <span class="card-label">单量</span>
          <span class="card-value">{{ data?.summary.order_count ?? 0 }}</span>
        </div>
        <div class="card">
          <span class="card-label">客单价</span>
          <span class="card-value">{{ formatPrice(data?.summary.avg_order_amount ?? 0) }}</span>
        </div>
        <div class="card">
          <span class="card-label">退款 / 取消</span>
          <span class="card-value">
            {{ formatPrice(data?.summary.refund_amount ?? 0) }}
            <span class="card-sub">{{ data?.summary.cancelled_count ?? 0 }} 单取消</span>
          </span>
        </div>
      </div>

      <!-- ---------- 趋势 ---------- -->
      <div class="panel">
        <h2>营业额趋势</h2>
        <div class="bars">
          <!-- 每根柱子自己带 tooltip：**具体日期和金额都在这儿**，
               柱子上不再标数字——30 根柱子那点宽度标不下，
               硬标就得抽稀，一抽稀就有标有不标、柱子顶端参差不齐

               **营业额为 0 的那几根不出 tooltip**：没有柱子就说明是 0，
               日期看下面的刻度也知道，再弹一个「¥0.00」纯属噪音 -->
          <el-tooltip
            v-for="(row, index) in data?.trend ?? []"
            :key="row.date"
            :content="`${row.date} · 营业额 ${formatPrice(row.revenue)}`"
            placement="top"
            :show-after="0"
            :disabled="row.revenue <= 0"
          >
            <div class="bar-col">
              <div class="bar-track">
                <div class="bar" :style="{ height: barLength(row.revenue, trendMax) }" />
              </div>
              <span class="bar-label">{{ tickText(row, index) }}</span>
            </div>
          </el-tooltip>
        </div>
      </div>

      <div class="two-col">
        <!-- ---------- 支付方式 ---------- -->
        <div class="panel">
          <h2>支付方式</h2>
          <div v-if="!(data?.by_method ?? []).length" class="empty">这段时间没有收款</div>
          <div
            v-for="row in data?.by_method ?? []"
            :key="row.method"
            class="hbar-row"
          >
            <span class="hbar-label">{{ row.method_label }}</span>
            <div class="hbar-track">
              <div
                class="hbar-fill"
                :style="{ width: barLength(row.amount, methodTotal) }"
              />
            </div>
            <span class="hbar-value">
              {{ formatPrice(row.amount) }}
              <!-- 这一组是**构成**（各占总额多少），所以条长按总额算；
                   不写百分比的话，「微信 ¥656 只占一半」看着像少画了。
                   下面那两组是**排行**（谁多谁少），按最大值撑满 -->
              <span class="hbar-sub">
                {{ row.count }} 笔 · {{ methodPercent(row.amount) }}%
              </span>
            </span>
          </div>
        </div>

        <!-- ---------- 菜品排行 ---------- -->
        <div class="panel">
          <h2>热销菜品（按份数）</h2>
          <div v-if="!(data?.top_dishes ?? []).length" class="empty">这段时间没有卖出东西</div>
          <div
            v-for="row in data?.top_dishes ?? []"
            :key="row.dish_id"
            class="hbar-row"
          >
            <span class="hbar-label">{{ row.dish_name }}</span>
            <div class="hbar-track">
              <div class="hbar-fill" :style="{ width: barLength(row.quantity, dishMax) }" />
            </div>
            <span class="hbar-value">
              {{ row.quantity }} 份
              <span class="hbar-sub">{{ formatPrice(row.amount) }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- ---------- 时段 ---------- -->
      <div class="panel">
        <h2>时段分布</h2>
        <p class="panel-hint">这一块是给排班用的：哪个小时单最多，一眼看得出来</p>
        <div v-if="!(data?.by_hour ?? []).length" class="empty">这段时间没有订单</div>
        <div v-else class="bars">
          <div v-for="row in data?.by_hour ?? []" :key="row.hour" class="bar-col">
            <span class="bar-value">{{ row.order_count }}</span>
            <div class="bar-track">
              <div class="bar" :style="{ height: barLength(row.order_count, hourMax) }" />
            </div>
            <span class="bar-label">{{ row.hour }} 点</span>
          </div>
        </div>
      </div>

      <!-- ---------- 门店对比 ---------- -->
      <div v-if="showStoreCompare" class="panel">
        <h2>门店对比</h2>
        <div v-for="row in data?.by_store ?? []" :key="row.store_id" class="hbar-row">
          <span class="hbar-label">{{ row.store_name }}</span>
          <div class="hbar-track">
            <div class="hbar-fill" :style="{ width: barLength(row.revenue, storeMax) }" />
          </div>
          <span class="hbar-value">
            {{ formatPrice(row.revenue) }}
            <span class="hbar-sub">{{ row.order_count }} 单</span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reports {
  padding: 32px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.store-select {
  width: 160px;
}

.range-hint {
  font-size: 13px;
  color: #a0a0a0;
}

.hint {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.7;
  margin-bottom: 20px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.card {
  padding: 20px;
  background: #f5f5f5;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
}

/* 营业额是主指标，给个黑底——一眼看到的就是它 */
.card.primary {
  background: #1f1f1f;
  border-color: #1f1f1f;
}

.card-label {
  display: block;
  font-size: 13px;
  color: #8a8a8a;
  margin-bottom: 8px;
}

.card.primary .card-label {
  color: #b0b0b0;
}

.card-value {
  display: block;
  font-size: 26px;
  font-weight: 600;
  color: #1f1f1f;
  line-height: 1.2;
}

.card.primary .card-value {
  color: #fff;
}

.card-sub {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  font-weight: 400;
  color: #a0a0a0;
}

.panel {
  padding: 20px;
  margin-bottom: 16px;
  background: #f5f5f5;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
}

.panel h2 {
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 16px;
}

.panel-hint {
  font-size: 12px;
  color: #a0a0a0;
  margin: -10px 0 16px;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.two-col .panel {
  margin-bottom: 16px;
}

/* ---------- 柱状图（纯 CSS，没引图表库） ---------- */

.bars {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 180px;
}

.bar-col {
  flex: 1;
  /* **不写这条的话 flex 默认 min-width: auto**，列会被里面的文字撑开
     （标签是 nowrap），一列撑宽、整排跟着溢出容器 */
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}

.bar-track {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
}

.bar {
  width: 100%;
  background: #1f1f1f;
  border-radius: 4px 4px 0 0;
  transition: height 0.2s;
}

.bar-label {
  margin-top: 8px;
  font-size: 11px;
  color: #a0a0a0;
  white-space: nowrap;
}

/* ---------- 横条 ---------- */

.hbar-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.hbar-label {
  width: 96px;
  flex-shrink: 0;
  font-size: 13px;
  color: #1f1f1f;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hbar-track {
  flex: 1;
  height: 14px;
  background: #e8e8e8;
  border-radius: 7px;
  overflow: hidden;
}

.hbar-fill {
  height: 100%;
  background: #1f1f1f;
  border-radius: 7px;
  transition: width 0.2s;
}

.hbar-value {
  width: 120px;
  flex-shrink: 0;
  text-align: right;
  font-size: 13px;
  color: #1f1f1f;
}

.hbar-sub {
  display: block;
  font-size: 11px;
  color: #a0a0a0;
}

.empty {
  padding: 24px 0;
  text-align: center;
  font-size: 13px;
  color: #a0a0a0;
}
</style>