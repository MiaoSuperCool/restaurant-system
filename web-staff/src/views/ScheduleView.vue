<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createShift,
  deleteShift,
  getScheduleStores,
  getScheduleWeek,
  getShifts,
  setScheduleDay,
  updateShift,
} from '@/api/schedule'
import type { ScheduleRow, ScheduleStore, ScheduleWeek, Shift } from '@/api/schedule'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

/**
 * 能不能排班
 *
 * 「看」和「排」是两个码：服务员也有 `schedule:view`（他得知道自己哪天来），
 * 但格子对他只是只读的。后端照样拦，这里只是别让人白点。
 */
const canManage = computed(() => authStore.hasPermission('schedule:manage'))

const stores = ref<ScheduleStore[]>([])
const storeId = ref<number | null>(null)
const week = ref<ScheduleWeek | null>(null)
const loading = ref(false)

/** 这一周里的任意一天；undefined = 本周（让后端去算，前端不自己推周一） */
const day = ref<string | undefined>(undefined)

// ---------- 日期小工具 ----------

/**
 * `'2026-09-14'` 加减天数
 *
 * **必须带 `T00:00:00`**：`new Date('2026-09-14')` 按 UTC 午夜解析，
 * 在东八区取回本地日期时会退到 9 月 13 号——翻页会越翻越错一天。
 */
function addDays(iso: string, delta: number): string {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() + delta)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

const rangeText = computed(() => {
  if (!week.value) return ''
  return `${week.value.start.slice(5)} ~ ${week.value.end.slice(5)}`
})

const isThisWeek = computed(() => day.value === undefined)

function goWeek(delta: number) {
  const base = week.value?.start ?? day.value
  if (!base) return
  // 拿「这一周的周一」加减 7 天：周一是后端算的，前端只管翻
  const target = addDays(week.value?.start ?? base, delta)
  day.value = target
  load()
}

// ---------- 加载 ----------

async function loadStores() {
  try {
    // 走排班自己的门店接口：**不能用 /stores/options**——那个要 store:view，
    // 而服务员只有 schedule:view，会弹出「没有门店查看权限」的报错
    const data = await getScheduleStores()
    stores.value = data.stores
    if (storeId.value === null && data.stores.length > 0) {
      // 店长只有一家店：直接选中，省一次点击
      storeId.value = data.stores[0].id
    }
  } catch {
    // 拦截器已提示
  }
}

async function load() {
  if (storeId.value === null) return
  loading.value = true
  try {
    week.value = await getScheduleWeek(storeId.value, day.value)
  } catch {
    week.value = null
  } finally {
    loading.value = false
  }
}

function switchStore() {
  week.value = null
  load()
}

onMounted(async () => {
  await loadStores()
  load()
})

// ---------- 排班（格子） ----------

/** 正在编辑的格子；null = 没打开 */
const editing = ref<{ row: ScheduleRow; index: number; date: string } | null>(null)
const picked = ref<number[]>([])
const saving = ref(false)

function openCell(row: ScheduleRow, index: number) {
  if (!canManage.value || !week.value) return
  editing.value = { row, index, date: week.value.days[index].date }
  picked.value = row.assignments[index].map((a) => a.shift_id)
}

const editingTitle = computed(() => {
  if (!editing.value || !week.value) return ''
  const d = week.value.days[editing.value.index]
  return `${editing.value.row.staff_name} · ${d.date} ${d.weekday}`
})

async function saveCell() {
  if (!editing.value || storeId.value === null) return
  saving.value = true
  try {
    const data = await setScheduleDay(storeId.value, {
      staff_id: editing.value.row.staff_id,
      work_date: editing.value.date,
      shift_ids: picked.value,
    })
    // **用后端返回的结果覆盖那个格子**，不自己猜「我刚才那一下成没成」
    // （同一个班连点两下、或者别处同时改了排班，猜出来的会不一样）
    editing.value.row.assignments[editing.value.index] = data.assignments
    editing.value = null
    ElMessage.success('排班已更新')
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

// ---------- 班次设置 ----------

const showShifts = ref(false)
const shifts = ref<Shift[]>([])
const shiftSaving = ref(false)
/** 正在编辑的班次 id；null = 新增 */
const editingShiftId = ref<number | null>(null)
const form = ref({ name: '', start_time: '09:30', end_time: '14:00' })

async function openShifts() {
  showShifts.value = true
  resetForm()
  try {
    const data = await getShifts(storeId.value as number)
    shifts.value = data.shifts
  } catch {
    shifts.value = []
  }
}

function resetForm() {
  editingShiftId.value = null
  form.value = { name: '', start_time: '09:30', end_time: '14:00' }
}

function editShift(shift: Shift) {
  editingShiftId.value = shift.id
  form.value = {
    name: shift.name,
    start_time: shift.start_time,
    end_time: shift.end_time,
  }
}

async function submitShift() {
  if (!form.value.name.trim()) {
    ElMessage.warning('班次名字不能空着')
    return
  }
  shiftSaving.value = true
  try {
    if (editingShiftId.value === null) {
      await createShift(storeId.value as number, { ...form.value, name: form.value.name.trim() })
      ElMessage.success('班次已添加')
    } else {
      await updateShift(editingShiftId.value, { ...form.value, name: form.value.name.trim() })
      ElMessage.success('班次已更新')
    }
    resetForm()
    await refreshShifts()
    load()
  } catch {
    // 拦截器已提示（重名、时间先后都是 400）
  } finally {
    shiftSaving.value = false
  }
}

async function toggleShift(shift: Shift) {
  try {
    await updateShift(shift.id, { is_active: !shift.is_active })
    await refreshShifts()
    load()
  } catch {
    // 拦截器已提示
  }
}

async function removeShift(shift: Shift) {
  try {
    await ElMessageBox.confirm(
      `删除班次「${shift.name}」？删了之后这个班次就排不了了（已经排出去的班不受影响）。`,
      '确认删除',
      // 按钮文案要自己写：ElementPlus 没配 locale，不写就是英文的 OK / Cancel，
      // 一个中文界面里冒出这两个词很突兀。其它页面也都显式传了
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return // 用户点了取消
  }
  try {
    await deleteShift(shift.id)
    ElMessage.success('班次已删除')
    await refreshShifts()
    load()
  } catch {
    // 拦截器已提示（排过班的班次删不掉，后端会说「请改成停用」）
  }
}

async function refreshShifts() {
  try {
    shifts.value = (await getShifts(storeId.value as number)).shifts
  } catch {
    // 拦截器已提示
  }
}

/**
 * 班次标签的配色：按班次在列表里的**位置**取色，不看名字
 *
 * 按名字判断（「晚班」给橙色）在演示数据里能跑，但店里自己加的班次
 * 一上就叫「夜班」「打烊班」了——按位置取色，加多少个班都分得开。
 */
const CHIP_COLORS = ['#e8f0fe', '#fdf0e0', '#e6f4ea', '#f3e8fd', '#fde8e8', '#e0f2f4']

function chipStyle(shiftId: number) {
  const index = (week.value?.shifts ?? []).findIndex((s) => s.id === shiftId)
  return { background: CHIP_COLORS[index >= 0 ? index % CHIP_COLORS.length : 0] }
}
</script>

<template>
  <div class="schedule">
    <div class="toolbar">
      <el-select
        v-if="stores.length > 1"
        v-model="storeId"
        placeholder="选门店"
        class="store-select"
        @change="switchStore"
      >
        <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <span v-else-if="stores.length === 1" class="store-name">{{ stores[0].name }}</span>

      <el-button-group>
        <el-button :icon="undefined" @click="goWeek(-7)">← 上一周</el-button>
        <el-button :disabled="isThisWeek" @click="day = undefined, load()">本周</el-button>
        <el-button @click="goWeek(7)">下一周 →</el-button>
      </el-button-group>
      <span class="range-hint">{{ rangeText }}</span>

      <el-button v-if="canManage" type="primary" class="shift-btn" @click="openShifts">
        班次设置
      </el-button>
    </div>

    <p class="hint">
      <strong>这是排班，不是考勤。</strong>排班回答的是「下周三谁上早班、谁上晚班」，
      不管几点打的卡。一天可以排两个班（餐饮里的<strong>两头班</strong>：早上来备菜、
      中午歇、晚上再来）——点格子勾选就行，清空 = 那天休息。
    </p>

    <div v-loading="loading">
      <el-table v-if="week?.rows.length" :data="week.rows" border class="grid">
        <el-table-column label="员工" width="150" fixed>
          <template #default="{ row }">
            <div class="staff">
              <span class="staff-name">{{ row.staff_name }}</span>
              <span class="staff-type">{{ row.employment_type_label }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column
          v-for="(d, index) in week.days"
          :key="d.date"
          min-width="120"
        >
          <template #header>
            <span :class="{ 'today-head': d.is_today }">
              {{ d.weekday }} {{ d.date.slice(5) }}
            </span>
          </template>
          <template #default="{ row }">
            <div
              class="cell"
              :class="{ today: d.is_today, editable: canManage }"
              @click="openCell(row, index)"
            >
              <span
                v-for="a in row.assignments[index]"
                :key="a.id"
                class="chip"
                :style="chipStyle(a.shift_id)"
                :title="a.shift_time_range"
              >
                {{ a.shift_name }}
              </span>
              <span v-if="!row.assignments[index].length" class="rest">
                {{ canManage ? '＋' : '休' }}
              </span>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-else-if="!loading"
        :description="storeId === null
          ? '没有可排班的门店'
          : '这家店还没有员工账号——先去「员工」页加人，这里才有得排'"
      />
    </div>

    <!-- ---------- 排一个人一天的班 ---------- -->
    <el-dialog :model-value="editing !== null" :title="editingTitle" width="420px"
               @update:model-value="editing = null">
      <el-checkbox-group v-model="picked" class="shift-picker">
        <el-checkbox v-for="s in week?.shifts ?? []" :key="s.id" :value="s.id">
          {{ s.name }}
          <span class="shift-time">{{ s.time_range }}</span>
        </el-checkbox>
      </el-checkbox-group>
      <p class="dialog-hint">
        <template v-if="!week?.shifts.length">
          这家店还没有班次——先点右上角「班次设置」加几个。
        </template>
        <template v-else>都不勾 = 这天休息。</template>
      </p>
      <template #footer>
        <el-button @click="editing = null">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCell">保存</el-button>
      </template>
    </el-dialog>

    <!-- ---------- 班次设置 ---------- -->
    <el-dialog v-model="showShifts" title="班次设置" width="640px">
      <el-table :data="shifts" size="small" border>
        <el-table-column label="名称" prop="name" />
        <el-table-column label="时间" prop="time_range" width="140" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190">
          <template #default="{ row }">
            <el-button link type="primary" @click="editShift(row)">编辑</el-button>
            <el-button link type="primary" @click="toggleShift(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button link type="danger" @click="removeShift(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="shift-form">
        <el-input v-model="form.name" placeholder="班次名，比如 早班" class="name-input" />
        <el-time-select v-model="form.start_time" start="05:00" step="00:30" end="23:30"
                        placeholder="开始" class="time-input" />
        <span class="dash">—</span>
        <el-time-select v-model="form.end_time" start="05:00" step="00:30" end="23:30"
                        placeholder="结束" class="time-input" />
        <el-button type="primary" :loading="shiftSaving" @click="submitShift">
          {{ editingShiftId === null ? '添加' : '保存修改' }}
        </el-button>
        <el-button v-if="editingShiftId !== null" @click="resetForm">取消</el-button>
      </div>
      <p class="dialog-hint">
        班次是<strong>门店级</strong>的：西溪印象城店 10:30 才开门，它的「早班」和别家不是一个时间。
        <strong>排过班的班次删不掉，只能停用</strong>——已经排出去的记录还得指着它。
      </p>
    </el-dialog>
  </div>
</template>

<style scoped>
.schedule {
  padding: 0 4px 40px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.store-select {
  width: 180px;
}

.store-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
}

.range-hint {
  font-size: 13px;
  color: #8a8a8a;
}

.shift-btn {
  margin-left: auto;
}

.hint {
  margin-bottom: 12px;
  padding: 10px 14px;
  background: #f7f7f7;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.8;
  color: #5a5a5a;
}

.grid {
  width: 100%;
}

.staff {
  display: flex;
  flex-direction: column;
}

.staff-name {
  font-size: 14px;
  color: #1f1f1f;
}

.staff-type {
  font-size: 12px;
  color: #a0a0a0;
}

/* ---------- 格子 ---------- */

.cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  min-height: 40px;
  padding: 4px;
  border-radius: 6px;
}

.cell.editable {
  cursor: pointer;
}

.cell.editable:hover {
  background: #f2f6ff;
}

/* 今天那一列整列浅底：一排 7 格里先看到「今天在哪」 */
.cell.today {
  background: #fafafa;
}

.today-head {
  color: #1f1f1f;
  font-weight: 600;
}

.chip {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  color: #1f1f1f;
  white-space: nowrap;
}

/* 没排班的那一格：可编辑时是个「＋」，只读时写「休」。
   写「休」而不是留白——留白看着像数据没加载出来 */
.rest {
  padding: 2px 8px;
  font-size: 12px;
  color: #c0c0c0;
}

.shift-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.shift-time {
  margin-left: 8px;
  font-size: 12px;
  color: #a0a0a0;
}

.dialog-hint {
  margin-top: 12px;
  font-size: 12px;
  line-height: 1.8;
  color: #8a8a8a;
}

.shift-form {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #eee;
}

.name-input {
  width: 160px;
}

.time-input {
  width: 120px;
}

.dash {
  color: #a0a0a0;
}
</style>