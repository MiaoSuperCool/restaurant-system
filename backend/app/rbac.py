"""权限码目录 + 预置角色（RBAC 的种子数据）

这里是权限体系的唯一事实来源：
- PERMISSIONS：全项目所有合法的权限码，命名统一为「资源:动作」
- ROLES：设计文档《餐饮多门店系统 — 数据模型与角色权限设计》里定下的角色矩阵

seed_rbac() 是幂等的，可以反复执行：新增权限码之后跑一次就同步进库，
预置角色的权限被改乱了也能一键还原成设计文档定义的样子。

改动这个文件之后要执行：flask seed-rbac
"""
import logging

logger = logging.getLogger(__name__)

# 「老板」用这个标记表示拥有全部权限，避免每加一个权限码就要去改一次老板的定义
ALL = '*'

# ---------- 权限码 ----------
# (权限码, 中文名, 分组)。分组只影响展示（分配界面按组排列），不参与判权。

PERMISSIONS = [
    # 组织与账号
    ('store:view', '门店查看', '组织与账号'),
    ('store:manage', '门店管理（增删门店）', '组织与账号'),
    ('staff:manage', '本店员工账号管理（含兼职开停）', '组织与账号'),
    ('staff:manage:all', '全公司账号管理（店长/总部账号）', '组织与账号'),
    ('schedule:manage', '排班管理', '组织与账号'),
    ('system:config', '系统配置', '组织与账号'),

    # 菜单与菜品
    ('menu:view', '菜单查看', '菜单与菜品'),
    ('menu:create', '新增菜品', '菜单与菜品'),
    ('menu:update', '修改菜品', '菜单与菜品'),
    ('menu:delete', '删除菜品', '菜单与菜品'),
    ('dish:price:edit', '改价', '菜单与菜品'),
    ('dish:online', '上下架', '菜单与菜品'),

    # 交易
    ('order:create', '代客点单', '交易'),
    ('order:receive', '接单', '交易'),
    ('order:view', '订单查看', '交易'),
    ('order:cancel', '取消订单', '交易'),
    ('pay:collect', '收款', '交易'),

    # 退款（退款一律走审批单，所以「发起」和「审批」是分开的两个权限）
    ('refund:apply', '发起退款申请', '退款'),
    ('refund:approve', '审批退款（限额内）', '退款'),
    ('refund:approve:large', '审批大额退款', '退款'),
    ('refund:view', '退款查看', '退款'),

    # 营销
    ('coupon:verify', '核销优惠券', '营销'),
    ('coupon:issue', '发放优惠券', '营销'),
    ('coupon:manage', '管理券模板', '营销'),
    ('campaign:manage', '活动管理', '营销'),

    # 会员
    ('member:view', '会员查看', '会员'),
    ('member:balance:view', '查看储值余额', '会员'),
    ('member:manage', '会员管理', '会员'),
    ('points:adjust', '调整积分', '会员'),

    # 库存
    ('stock:view', '库存查看', '库存'),
    ('stock:manage', '库存管理', '库存'),

    # 报表与财务
    ('report:store', '本店报表', '报表与财务'),
    ('report:all', '全公司报表', '报表与财务'),
    ('finance:view', '财务查看', '报表与财务'),
    ('finance:export', '财务导出', '报表与财务'),

    # 对接与审计
    ('sync:view', '同步/对账状态查看', '对接与审计'),
    ('audit:view', '审计日志查看', '对接与审计'),
]

PERMISSION_NAMES = {code: name for code, name, _ in PERMISSIONS}


def permission_name(code):
    """权限码 → 中文名（报错文案用）；目录里没有就退回权限码本身"""
    return PERMISSION_NAMES.get(code, code)


# ---------- 预置角色 ----------
# 角色是不同权限的集合
# data_scope：store = 只能碰本店数据，all = 6 家店都能碰。

# 一线员工看菜单是干活的前提（点单、出单都要先看菜），所以前厅后厨都给 menu:view
_FRONT_LINE_MENU = ['menu:view']

# 收银员的权限集合，值班经理和店长都是它的超集，抽出来避免三处各写一遍
_CASHIER_PERMISSIONS = [
    'order:create', 'order:receive', 'order:view',
    'pay:collect', 'coupon:verify', 'member:balance:view', 'refund:apply',
    *_FRONT_LINE_MENU,
]

# 值班经理 = 收银员 + 顶班时多出来的那几项
_SHIFT_MANAGER_PERMISSIONS = _CASHIER_PERMISSIONS + [
    'order:cancel', 'refund:approve', 'refund:view',
    'report:store', 'stock:view', 'schedule:manage',
]

ROLES = [
    {
        'code': 'waiter',
        'name': '服务员',
        'description': '代客点单，看本店订单',
        'data_scope': 'store',
        'permissions': ['order:create', 'order:view', *_FRONT_LINE_MENU],
    },
    {
        'code': 'kitchen',
        'name': '后厨',
        'description': '本店出单',
        'data_scope': 'store',
        'permissions': ['order:view', *_FRONT_LINE_MENU],
    },
    {
        'code': 'cashier',
        'name': '收银员',
        'description': '接单、收款、核销券、查余额、发起退款',
        'data_scope': 'store',
        'permissions': _CASHIER_PERMISSIONS,
    },
    {
        'code': 'shift_manager',
        'name': '值班经理',
        'description': '店长不在时顶班，是受限版店长：大额退款批不了',
        'data_scope': 'store',
        'permissions': _SHIFT_MANAGER_PERMISSIONS,
    },
    {
        'code': 'store_manager',
        'name': '店长',
        'description': '本店的菜单、价格、员工、库存、排班；不能发全店券、不能改总部活动、不能看别店',
        'data_scope': 'store',
        # **必须是值班经理的超集**——设计文档原文说值班经理是「受限版店长」，
        # 下属能干的事上司干不了是荒唐的。test_rbac 里有条测试专门守这个不变量。
        'permissions': _SHIFT_MANAGER_PERMISSIONS + [
            'store:view',
            'menu:view', 'menu:update',
            'dish:price:edit', 'dish:online',
            'stock:manage', 'staff:manage',
        ],
    },
    {
        'code': 'ops_manager',
        'name': '运营主管',
        'description': '全公司的菜单、价格、活动、发券',
        'data_scope': 'all',
        'permissions': [
            'store:view',
            'menu:view', 'menu:create', 'menu:update', 'menu:delete',
            'dish:price:edit', 'dish:online',
            'campaign:manage', 'coupon:issue', 'coupon:manage',
            'member:view', 'member:manage',
            'report:all',
        ],
    },
    {
        'code': 'finance',
        'name': '财务',
        'description': '营业额、储值、退款、导出；不能碰菜单和价格',
        'data_scope': 'all',
        'permissions': [
            'store:view', 'order:view', 'refund:view',
            'member:balance:view',
            'report:all', 'finance:view', 'finance:export', 'sync:view',
        ],
    },
    {
        'code': 'boss',
        'name': '老板',
        'description': '全部权限，含门店管理、全公司账号管理和审计日志',
        'data_scope': 'all',
        'permissions': ALL,
    },
]


def seed_rbac():
    """把权限目录和预置角色写进库里（幂等，可反复执行）

    返回 (新建权限数, 新建角色数, 更新角色数)
    """
    from backend.app.extensions import db
    from backend.app.models import Permission, Role

    created_permissions = 0
    code_to_permission = {}

    for order, (code, name, group) in enumerate(PERMISSIONS):
        permission = Permission.query.filter_by(code=code).first()
        if permission is None:
            permission = Permission(code=code)
            db.session.add(permission)
            created_permissions += 1
        # 名称/分组/排序以本文件为准，目录改了执行一次就同步过去
        permission.name = name
        permission.group = group
        permission.sort_order = order
        code_to_permission[code] = permission
    db.session.flush()

    created_roles = 0
    updated_roles = 0
    for order, spec in enumerate(ROLES):
        role = Role.query.filter_by(code=spec['code']).first()
        if role is None:
            role = Role(code=spec['code'])
            db.session.add(role)
            created_roles += 1
        else:
            updated_roles += 1

        role.name = spec['name']
        role.description = spec['description']
        role.data_scope = spec['data_scope']
        role.is_builtin = True
        role.sort_order = order

        wanted = spec['permissions']
        if wanted == ALL:
            wanted = list(code_to_permission)

        # 目录里写错权限码要当场报出来，不能静默少给一个权限——
        # 这种错会一直藏到某个店长发现自己改不了价才暴露
        unknown = [c for c in wanted if c not in code_to_permission]
        if unknown:
            raise ValueError(f"角色「{spec['name']}」引用了不存在的权限码：{unknown}")

        role.permissions = [code_to_permission[c] for c in wanted]

    db.session.commit()
    logger.info(
        '权限种子同步完成：新建权限 %s 个、新建角色 %s 个、更新角色 %s 个',
        created_permissions, created_roles, updated_roles,
    )
    return created_permissions, created_roles, updated_roles
