<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createStore, updateStore } from '@/api/stores'
import type { Store } from '@/api/types'
import {
  BUSINESS_STATUS_OPTIONS,
  RUN_MODE_OPTIONS,
  STORE_TYPE_OPTIONS,
} from '@/constants/store'

const props = defineProps<{
  modelValue: boolean
  store: Store | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}>()

const saving = ref(false)

// 字段名与 StoreCreateSchema 保持一致
const form = reactive({
  code: '',
  name: '',
  store_type: 'dine_in',
  address: '',
  phone: '',
  business_status: 'open',
  run_mode: 'new',
  remark: '',
})

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    form.code = props.store?.code ?? ''
    form.name = props.store?.name ?? ''
    form.store_type = props.store?.store_type ?? 'dine_in'
    form.address = props.store?.address ?? ''
    form.phone = props.store?.phone ?? ''
    form.business_status = props.store?.business_status ?? 'open'
    form.run_mode = props.store?.run_mode ?? 'new'
    form.remark = props.store?.remark ?? ''
  }
)

async function handleSubmit() {
  if (!form.code.trim() || !form.name.trim()) {
    ElMessage.warning('请填写门店编码和名称')
    return
  }

  saving.value = true
  try {
    const payload = {
      code: form.code.trim(),
      name: form.name.trim(),
      store_type: form.store_type,
      address: form.address.trim(),
      phone: form.phone.trim(),
      business_status: form.business_status,
      run_mode: form.run_mode,
      remark: form.remark.trim(),
    }
    if (props.store) {
      await updateStore(props.store.id, payload)
      ElMessage.success('修改成功')
    } else {
      await createStore(payload)
      ElMessage.success('创建成功')
    }
    emit('success')
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

function handleClose() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="store ? '编辑门店' : '新增门店'"
    width="520px"
    @close="handleClose"
  >
    <el-form label-width="88px">
      <el-form-item label="门店编码">
        <el-input v-model="form.code" placeholder="如 S001，对接老系统和 ERP 靠它认店" />
      </el-form-item>
      <el-form-item label="门店名称">
        <el-input v-model="form.name" placeholder="如 解放路店" />
      </el-form-item>
      <el-form-item label="门店类型">
        <el-select v-model="form.store_type" class="full-width">
          <el-option
            v-for="item in STORE_TYPE_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="地址">
        <el-input v-model="form.address" placeholder="用于外卖配送范围与门店导航" />
      </el-form-item>
      <el-form-item label="电话">
        <el-input v-model="form.phone" placeholder="门店对外电话，打小票用" />
      </el-form-item>
      <el-form-item label="营业状态">
        <el-select v-model="form.business_status" class="full-width">
          <el-option
            v-for="item in BUSINESS_STATUS_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="运行模式">
        <el-select v-model="form.run_mode" class="full-width">
          <el-option
            v-for="item in RUN_MODE_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <div class="field-hint">灰度切换用：该店由老系统还是新系统承接订单</div>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.full-width {
  width: 100%;
}

.field-hint {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.5;
  margin-top: 4px;
}
</style>