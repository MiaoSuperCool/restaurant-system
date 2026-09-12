<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getRoles } from '@/api/roles'
import { createStaff, updateStaff } from '@/api/staff'
import { getStoreOptions } from '@/api/stores'
import type { Role, Staff, StoreOption } from '@/api/types'
import { EMPLOYMENT_TYPE_OPTIONS } from '@/constants/staff'

const props = defineProps<{
  modelValue: boolean
  staff: Staff | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}>()

const saving = ref(false)
const storeOptions = ref<StoreOption[]>([])
const roleOptions = ref<Role[]>([])

// 字段名与 StaffCreateSchema 保持一致
const form = reactive({
  username: '',
  real_name: '',
  email: '',
  mobile: '',
  password: '',
  store_id: null as number | null,
  role_ids: [] as number[],
  employment_type: 'full_time',
  is_shared: false,
  is_active: true,
  is_admin: false,
})

async function loadStoreOptions() {
  try {
    const data = await getStoreOptions()
    storeOptions.value = data.stores
  } catch {
    // 拦截器已提示；拉不到就只显示「总部」一项，不阻断填表
  }
}

async function loadRoleOptions() {
  try {
    const data = await getRoles()
    roleOptions.value = data.roles
  } catch {
    // 拦截器已提示
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    form.username = props.staff?.username ?? ''
    form.real_name = props.staff?.real_name ?? ''
    form.email = props.staff?.email ?? ''
    form.mobile = props.staff?.mobile ?? ''
    form.password = ''
    form.store_id = props.staff?.store_id ?? null
    form.role_ids = props.staff?.roles.map((role) => role.id) ?? []
    form.employment_type = props.staff?.employment_type ?? 'full_time'
    form.is_shared = props.staff?.is_shared ?? false
    form.is_active = props.staff?.is_active ?? true
    form.is_admin = props.staff?.is_admin ?? false
    loadStoreOptions()
    loadRoleOptions()
  }
)

async function handleSubmit() {
  if (!form.username.trim() || !form.real_name.trim()) {
    ElMessage.warning('请填写用户名和姓名')
    return
  }
  if (!form.email.trim() || !form.mobile.trim()) {
    ElMessage.warning('请填写邮箱和手机号')
    return
  }
  if (!props.staff && !form.password) {
    ElMessage.warning('请设置初始密码')
    return
  }

  saving.value = true
  try {
    const payload = {
      username: form.username.trim(),
      real_name: form.real_name.trim(),
      email: form.email.trim(),
      mobile: form.mobile.trim(),
      store_id: form.store_id,
      role_ids: form.role_ids,
      employment_type: form.employment_type,
      is_shared: form.is_shared,
      is_active: form.is_active,
      is_admin: form.is_admin,
    }
    if (props.staff) {
      // 编辑：密码留空表示不修改，不传给后端
      await updateStaff(props.staff.id, form.password ? { ...payload, password: form.password } : payload)
      ElMessage.success('修改成功')
    } else {
      await createStaff({ ...payload, password: form.password })
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

onMounted(loadStoreOptions)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="staff ? '编辑员工' : '新增员工'"
    width="520px"
    @close="handleClose"
  >
    <el-form label-width="88px">
      <el-form-item label="用户名">
        <el-input v-model="form.username" placeholder="登录用的账号" />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input v-model="form.real_name" placeholder="真实姓名" />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email" placeholder="邮箱" />
      </el-form-item>
      <el-form-item label="手机号">
        <el-input v-model="form.mobile" placeholder="手机号" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          :placeholder="staff ? '留空表示不修改' : '设置初始密码'"
        />
      </el-form-item>
      <el-form-item label="归属门店">
        <el-select v-model="form.store_id" clearable placeholder="不选表示总部账号" class="full-width">
          <el-option
            v-for="store in storeOptions"
            :key="store.id"
            :label="`${store.name}（${store.code}）`"
            :value="store.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="角色">
        <el-select
          v-model="form.role_ids"
          multiple
          clearable
          placeholder="不选表示没有任何权限"
          class="full-width"
        >
          <el-option
            v-for="role in roleOptions"
            :key="role.id"
            :label="`${role.name}（${role.data_scope_label}）`"
            :value="role.id"
          >
            <span>{{ role.name }}（{{ role.data_scope_label }}）</span>
            <span class="role-desc">{{ role.description }}</span>
          </el-option>
        </el-select>
        <div class="field-hint">权限和数据范围都由角色决定，可以兼多个角色</div>
      </el-form-item>
      <el-form-item label="用工类型">
        <el-select v-model="form.employment_type" class="full-width">
          <el-option
            v-for="item in EMPLOYMENT_TYPE_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="公用账号">
        <el-switch v-model="form.is_shared" />
        <div class="field-hint">服务员共用设备登录时打开，下单会另外记录实际操作人</div>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.is_active" />
      </el-form-item>
      <el-form-item label="超级管理员">
        <el-switch v-model="form.is_admin" />
        <div class="field-hint">只给初始管理员账号用，日常授权走角色</div>
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

.role-desc {
  float: right;
  font-size: 12px;
  color: #a0a0a0;
  margin-left: 16px;
}
</style>