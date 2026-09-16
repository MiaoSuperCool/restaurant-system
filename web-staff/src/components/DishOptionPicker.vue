<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { StoreMenuRow } from '@/api/types'
import { formatPrice } from '@/utils/format'

/** 选完规格后交给购物车的东西 */
export interface PickedDish {
  dish_id: number
  name: string
  unit_price: number
  quantity: number
  option_ids: number[]
  options_text: string
}

const props = defineProps<{
  modelValue: boolean
  dish: StoreMenuRow | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm', picked: PickedDish): void
}>()

/** 组 id → { 选项 id: 份数 }。加料可以加多份（加蛋 ×2），单选组份数恒为 1 */
const selected = ref<Record<number, Record<number, number>>>({})
const quantity = ref(1)

/** 某个选项选了几份（0 = 没选） */
function countOf(groupId: number, optionId: number): number {
  return selected.value[groupId]?.[optionId] ?? 0
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    quantity.value = 1
    // 必选组默认选第一个——收银员点得最快，不用每次都手动选「标准份」
    const initial: Record<number, Record<number, number>> = {}
    for (const group of props.dish?.option_groups ?? []) {
      initial[group.id] = group.is_required && group.options.length > 0
        ? { [group.options[0].id]: 1 }
        : {}
    }
    selected.value = initial
  }
)

/** 按规格组的顺序铺平选中的选项，带上份数，算加价合计 */
const chosenOptions = computed(() => {
  const result: { id: number; name: string; extra_price: number; count: number }[] = []
  for (const group of props.dish?.option_groups ?? []) {
    for (const option of group.options) {
      const count = countOf(group.id, option.id)
      if (count > 0) {
        result.push({ id: option.id, name: option.name, extra_price: option.extra_price, count })
      }
    }
  }
  return result
})

const unitPrice = computed(() => {
  const base = props.dish?.price ?? 0
  return chosenOptions.value.reduce(
    (sum, option) => sum + option.extra_price * option.count, base
  )
})

const subtotal = computed(() => unitPrice.value * quantity.value)

/** 单选组用 radio——el-radio-group 的 v-model 是单值，这里转一下 */
function singleValue(groupId: number): number | undefined {
  const counts = selected.value[groupId]
  if (!counts) return undefined
  const ids = Object.keys(counts)
  return ids.length > 0 ? Number(ids[0]) : undefined
}

function setSingle(groupId: number, value: number) {
  selected.value = { ...selected.value, [groupId]: { [value]: 1 } }
}

/** 多选组：勾上 = 1 份，取消 = 0 份 */
function toggleMultiple(groupId: number, optionId: number, checked: boolean) {
  const counts = { ...(selected.value[groupId] ?? {}) }
  if (checked) counts[optionId] = counts[optionId] || 1
  else delete counts[optionId]
  selected.value = { ...selected.value, [groupId]: counts }
}

/** 加减份数，减到 0 就是取消这一项 */
function changeCount(groupId: number, optionId: number, delta: number) {
  const counts = { ...(selected.value[groupId] ?? {}) }
  const next = (counts[optionId] ?? 0) + delta
  if (next <= 0) delete counts[optionId]
  else counts[optionId] = next
  selected.value = { ...selected.value, [groupId]: counts }
}

function handleConfirm() {
  const dish = props.dish
  if (!dish) return

  // 和后端同样的校验，错了在这里就说清楚，别等到提交才报 400
  for (const group of dish.option_groups) {
    const counts = selected.value[group.id] ?? {}
    if (group.is_required && Object.keys(counts).length === 0) {
      ElMessage.warning(`请选择「${group.name}」`)
      return
    }
  }

  emit('confirm', {
    dish_id: dish.dish_id,
    name: dish.name,
    unit_price: unitPrice.value,
    quantity: quantity.value,
    // 同一个 id 重复几次就是几份——后端的约定
    option_ids: chosenOptions.value.flatMap((option) => Array(option.count).fill(option.id)),
    options_text: chosenOptions.value
      .map((option) => (option.count > 1 ? `${option.name}×${option.count}` : option.name))
      .join(','),
  })
  emit('update:modelValue', false)
}

function handleClose() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="dish?.name"
    width="460px"
    @close="handleClose"
  >
    <template v-if="dish">
      <p v-if="dish.description" class="dish-desc">{{ dish.description }}</p>

      <div v-for="group in dish.option_groups" :key="group.id" class="group">
        <div class="group-title">
          {{ group.name }}
          <span v-if="group.is_required" class="required">必选</span>
          <span class="group-type">{{ group.selection_type_label }}</span>
        </div>

        <!-- 单选组 -->
        <el-radio-group
          v-if="group.selection_type === 'single'"
          :model-value="singleValue(group.id)"
          @update:model-value="(value: string | number | boolean | undefined) =>
            setSingle(group.id, value as number)"
        >
          <el-radio
            v-for="option in group.options"
            :key="option.id"
            :value="option.id"
            class="option"
          >
            {{ option.name }}
            <span v-if="option.extra_price > 0" class="extra">+{{ option.extra_price }}</span>
          </el-radio>
        </el-radio-group>

        <!-- 多选组：勾上 = 1 份；选中的项右边多一个数量控件，加料可以加多份 -->
        <div v-else class="multi-row">
          <div v-for="option in group.options" :key="option.id" class="multi-item">
            <el-checkbox
              :model-value="countOf(group.id, option.id) > 0"
              class="option"
              @update:model-value="(checked: boolean) =>
                toggleMultiple(group.id, option.id, checked)"
            >
              {{ option.name }}
              <span v-if="option.extra_price > 0" class="extra">+{{ option.extra_price }}</span>
            </el-checkbox>
            <span v-if="countOf(group.id, option.id) > 0" class="stepper">
              <span class="stepper-btn" @click="changeCount(group.id, option.id, -1)">−</span>
              <span class="stepper-num">{{ countOf(group.id, option.id) }}</span>
              <span class="stepper-btn" @click="changeCount(group.id, option.id, 1)">＋</span>
            </span>
          </div>
        </div>
      </div>

      <div class="footer-row">
        <el-input-number v-model="quantity" :min="1" :max="99" />
        <div class="price">
          <span class="price-main">{{ formatPrice(subtotal) }}</span>
          <span class="price-hint">
            单价 {{ formatPrice(unitPrice) }}<template v-if="quantity > 1"> × {{ quantity }}</template>
          </span>
        </div>
      </div>
    </template>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleConfirm">加入点单</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dish-desc {
  font-size: 13px;
  color: #8a8a8a;
  margin-bottom: 16px;
}

.group {
  margin-bottom: 18px;
}

.group-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 8px;
}

.required {
  font-size: 11px;
  font-weight: 400;
  color: #c45656;
  margin-left: 6px;
}

.group-type {
  font-size: 11px;
  font-weight: 400;
  color: #a0a0a0;
  margin-left: 6px;
}

/* 单选和多选都横排：两组行为不一致看起来像出了 bug。
   选项多的时候自然换行，比一列到底省地方 */
.option {
  margin: 0 16px 6px 0;
}

.multi-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

/* 一个选项 + 它的数量控件算一组，换行时不会被拆开 */
.multi-item {
  display: inline-flex;
  align-items: center;
  margin: 0 16px 6px 0;
}

.multi-item .option {
  margin-right: 0;
}

.stepper {
  display: inline-flex;
  align-items: center;
  margin-left: 8px;
}

.stepper-btn {
  width: 20px;
  height: 20px;
  line-height: 18px;
  text-align: center;
  font-size: 14px;
  color: #1f1f1f;
  border: 1px solid #d9d9d9;
  border-radius: 50%;
  cursor: pointer;
  user-select: none;
}

.stepper-btn:hover {
  border-color: #1f1f1f;
}

.stepper-num {
  min-width: 24px;
  text-align: center;
  font-size: 13px;
  color: #1f1f1f;
}

.extra {
  color: #c45656;
  font-size: 12px;
  margin-left: 2px;
}

.footer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #e5e5e5;
}

.price {
  text-align: right;
}

.price-main {
  font-size: 20px;
  font-weight: 600;
  color: #1f1f1f;
}

.price-hint {
  display: block;
  font-size: 12px;
  color: #8a8a8a;
}
</style>
