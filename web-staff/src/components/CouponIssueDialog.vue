<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { issueCoupons } from '@/api/coupons'
import { getMembers } from '@/api/members'
import type { CouponTemplate, Member } from '@/api/types'
import { describeCoupon } from '@/constants/coupon'

const props = defineProps<{
  modelValue: boolean
  template: CouponTemplate | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}>()

const issuing = ref(false)
const searching = ref(false)
const memberIds = ref<number[]>([])
const candidates = ref<Member[]>([])
const chosen = ref<Member[]>([])
const count = ref(1)
const remark = ref('')

/**
 * 下拉里能看到的会员 = 当前搜索结果 + 已经选中的
 *
 * 少加后半截的话，远程搜索换一次关键词，之前选好的人就从列表里消失了，
 * 选项没了标签会退化成一个个数字 id。
 */
const options = computed(() => {
  const merged = new Map<number, Member>()
  for (const member of [...chosen.value, ...candidates.value]) {
    merged.set(member.id, member)
  }
  return [...merged.values()]
})

/** 还剩多少张可发（没设总量就是不限量） */
const remaining = computed(() => {
  if (!props.template?.total_quantity) return null
  return props.template.total_quantity - props.template.issued_count
})

/** 这次要发出去多少张——发之前得让人看见这个数 */
const willIssue = computed(() => memberIds.value.length * count.value)

function memberLabel(member: Member) {
  return member.nickname ? `${member.nickname}（${member.mobile ?? '无手机号'}）` : member.mobile
}

async function searchMembers(keyword: string) {
  searching.value = true
  try {
    const data = await getMembers({ search: keyword })
    candidates.value = data.members.filter((member) => member.is_active)
  } catch {
    // 拦截器已提示
  } finally {
    searching.value = false
  }
}

function handleSelectionChange(ids: number[]) {
  // 选中的人从当前选项里捞出来存着，之后换关键词搜索也不会丢
  chosen.value = ids
    .map((id) => options.value.find((member) => member.id === id))
    .filter((member): member is Member => !!member)
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    memberIds.value = []
    chosen.value = []
    count.value = 1
    remark.value = ''
    // 先拉一页进来，不然下拉是空的、也看不出有搜索这回事
    searchMembers('')
  }
)

async function handleSubmit() {
  if (!props.template) return
  if (!memberIds.value.length) {
    ElMessage.warning('至少要选一个会员')
    return
  }
  if (remaining.value !== null && willIssue.value > remaining.value) {
    ElMessage.warning(`这张券只剩 ${remaining.value} 张，这次要发 ${willIssue.value} 张`)
    return
  }

  issuing.value = true
  try {
    const data = await issueCoupons({
      template_id: props.template.id,
      member_ids: memberIds.value,
      count: count.value,
      remark: remark.value.trim(),
    })
    ElMessage.success(`发出 ${data.total} 张`)
    emit('success')
  } catch {
    // 拦截器已提示（模板停用、会员停用、总量不够等）
  } finally {
    issuing.value = false
  }
}

function handleClose() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="发券" width="480px" @close="handleClose">
    <div v-if="template" class="coupon-brief">
      <p class="coupon-name">{{ template.name }}</p>
      <p class="coupon-desc">
        {{ describeCoupon(template) }}
        · 适用门店：{{ template.is_all_stores ? '全公司' : template.store_names.join('、') }}
      </p>
      <p class="coupon-desc">
        已发 {{ template.issued_count }} 张<template v-if="remaining !== null">
          ，还剩 {{ remaining }} 张</template>
      </p>
    </div>

    <el-form label-width="88px">
      <el-form-item label="发给谁">
        <el-select
          v-model="memberIds"
          multiple
          filterable
          remote
          reserve-keyword
          :remote-method="searchMembers"
          :loading="searching"
          placeholder="搜手机号或昵称"
          class="full-width"
          @change="handleSelectionChange"
        >
          <el-option
            v-for="member in options"
            :key="member.id"
            :label="memberLabel(member)"
            :value="member.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="每人几张">
        <el-input-number v-model="count" :min="1" :max="99" />
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="remark" placeholder="选填，如：门店开业活动" />
      </el-form-item>
    </el-form>

    <p class="summary">
      这次共发出 <strong>{{ willIssue }}</strong> 张
      <span v-if="remaining !== null" class="muted">（发完还剩 {{ remaining - willIssue }} 张）</span>
    </p>

    <p class="note">
      发出去就是成本，所以「发券」和「管模板」是两个权限码。
      券一旦发出就收不回来，只能等它自己过期。
    </p>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="issuing" @click="handleSubmit">确认发放</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.full-width {
  width: 100%;
}

.coupon-brief {
  padding: 12px 16px;
  margin-bottom: 16px;
  background: #f5f5f5;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
}

.coupon-name {
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 4px;
}

.coupon-desc {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.6;
}

.summary {
  padding-top: 12px;
  border-top: 1px solid #e5e5e5;
  font-size: 14px;
  color: #1f1f1f;
}

.muted {
  font-size: 12px;
  color: #a0a0a0;
}

.note {
  margin-top: 8px;
  font-size: 12px;
  color: #a0a0a0;
  line-height: 1.6;
}
</style>