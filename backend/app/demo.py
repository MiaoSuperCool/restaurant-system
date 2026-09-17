"""演示数据：一条命令把系统填满，clone 下来就能看到东西

**为什么需要这个**

代码写得再完整，别人 clone 下来跑起来是个空系统，前三分钟就走了。
`flask seed-demo` 造出 6 家门店、一套完整菜单、各角色各一个账号、
几个会员和他们的券包、一批各种状态的订单——打开就能点、就能演示。

**为什么不走 service 层**

service 层到处要用 current_user（记审计、判数据范围），而 CLI 里没有请求上下文，
current_user 会直接抛异常。所以这里是直接建模型对象。

唯一的例外是算价：`OrderService.build_order_item()` 是纯函数（不碰 current_user），
所以复用它。**不能另写一份算价逻辑**——两处各算各的，迟早会漂移。

种子数据是幂等的（按编码/用户名/菜名认领），可以反复执行；
加 --reset 会先清空业务数据再重建。
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

# 演示账号统一密码（写在命令输出里告诉使用者）
DEMO_PASSWORD = 'Demo123!'

# ---------------------------------------------------------------- 数据定义

STORES = [
    # (编码, 名称, 类型, 地址, 电话)
    ('S001', '解放路店', 'dine_in', '杭州市上城区解放路 128 号', '0571-87001001'),
    ('S002', '文三路店', 'fast_food', '杭州市西湖区文三路 258 号', '0571-87001002'),
    ('S003', '武林门店', 'dine_in', '杭州市拱墅区武林路 66 号', '0571-87001003'),
    ('S004', '滨江宝龙店', 'fast_food', '杭州市滨江区江南大道 222 号', '0571-87001004'),
    ('S005', '西溪印象城店', 'dine_in', '杭州市余杭区五常大道 100 号', '0571-87001005'),
    ('S006', '萧山万象汇店', 'fast_food', '杭州市萧山区市心北路 666 号', '0571-87001006'),
]

CATEGORIES = [
    # (名称, 图标, 适用门店编码 —— 空列表 = 全公司通用)
    ('招牌面食', '🍜', []),
    ('米饭套餐', '🍚', []),
    ('小食', '🥟', []),
    ('饮品', '🥤', []),
    # 只在两家堂食大店卖——顺便演示「分类适用门店」这个功能
    ('商务套餐', '💼', ['S001', 'S003']),
]

DISHES = [
    # (分类, 名称, 基础价, 描述, 规格组)
    # 规格组 = (组名, 单选/多选, 是否必选, [(选项名, 加价)])
    ('招牌面食', '红烧牛肉面', '32.00', '招牌，牛骨汤底熬 8 小时', [
        ('份量', 'single', True, [('标准', '0'), ('大份', '4')]),
        ('辣度', 'single', True, [('微辣', '0'), ('中辣', '0'), ('特辣', '0')]),
        ('加料', 'multiple', False, [('加蛋', '3'), ('加牛肉', '8')]),
    ]),
    ('招牌面食', '番茄鸡蛋面', '22.00', '不辣，适合小朋友', [
        ('份量', 'single', True, [('标准', '0'), ('大份', '3')]),
        ('加料', 'multiple', False, [('加蛋', '3')]),
    ]),
    ('招牌面食', '雪菜肉丝面', '26.00', '杭帮口味', [
        ('份量', 'single', True, [('标准', '0'), ('大份', '3')]),
        ('辣度', 'single', True, [('不辣', '0'), ('微辣', '0')]),
    ]),
    ('招牌面食', '金牌猪软骨面', '38.00', '软骨炖到入口即化', [
        ('份量', 'single', True, [('标准', '0'), ('大份', '5')]),
    ]),
    ('米饭套餐', '台式卤肉饭', '28.00', '配溏心蛋和青菜', [
        ('份量', 'single', True, [('标准', '0'), ('加饭', '3')]),
    ]),
    ('米饭套餐', '香煎鸡腿饭', '32.00', '现煎鸡腿排', [
        ('份量', 'single', True, [('标准', '0'), ('加饭', '3')]),
        ('加料', 'multiple', False, [('加蛋', '3'), ('加鸡腿', '10')]),
    ]),
    ('米饭套餐', '咖喱牛肉饭', '35.00', '日式咖喱', [
        ('辣度', 'single', True, [('原味', '0'), ('微辣', '0')]),
    ]),
    ('小食', '鲜肉小笼包', '18.00', '现包现蒸', [
        ('数量', 'single', True, [('6 只', '0'), ('8 只', '5')]),
    ]),
    ('小食', '手工煎饺', '16.00', '底脆馅足', []),
    ('小食', '凉拌黄瓜', '12.00', '开胃解腻', []),
    ('饮品', '可乐', '6.00', '', [
        ('温度', 'single', True, [('冰', '0'), ('常温', '0')]),
    ]),
    ('饮品', '酸梅汤', '8.00', '自家熬的', []),
    ('饮品', '现磨豆浆', '5.00', '', [
        ('甜度', 'single', True, [('正常糖', '0'), ('无糖', '0')]),
    ]),

    # 「商务套餐」分类只在大店卖（见 CATEGORIES 里的 store_codes）。
    # 放进两道菜是为了让这个功能**看得出效果**：在文三路店（S002）的菜单里
    # 就看不到这两道——否则分类的「适用门店」是个没人能验证的功能
    ('商务套餐', '商务午市套餐', '58.00', '两荤一素配例汤，工作日午市', []),
    ('商务套餐', '商务双人餐', '108.00', '两人份，含主食和饮品', []),
]

STAFF = [
    # (用户名, 姓名, 角色码, 归属门店, 用工类型, 是否公用账号)
    ('laoban', '张老板', 'boss', None, 'full_time', False),
    ('yunying', '李运营', 'ops_manager', None, 'full_time', False),
    ('caiwu', '王会计', 'finance', None, 'full_time', False),
    ('dianzhang', '刘店长', 'store_manager', 'S001', 'full_time', False),
    ('zhiban', '陈值班', 'shift_manager', 'S001', 'full_time', False),
    ('shouyin', '赵收银', 'cashier', 'S001', 'full_time', False),
    ('fuwuyuan', '孙服务', 'waiter', 'S001', 'part_time', False),
    # 公用账号：服务员共用一台设备登录，下单时选「实际操作人」
    ('gongyong', '前厅公用账号', 'waiter', 'S001', 'full_time', True),
    ('houcu', '周后厨', 'kitchen', 'S001', 'full_time', False),
]

# 菜品配图：路径相对前端的 public/（web-staff 直接拿它当卡片背景）
#
# 单独一张表而不是塞进 DISHES 的元组里——那样每个分类都要跟着改结构，
# 而配图本来就只给个别菜用（其余菜品走默认的纯色卡片）
#
# 原图要先跑 `scripts/optimize_dish_images.py` 压成 WebP（缩到 800px、59KB 左右），
# 别把几 MB 的原图直接丢进 public/
DISH_IMAGES = {
    '红烧牛肉面': '/dishes/beef-noodle.webp',
}

MEMBERS = [
    # (手机号, 昵称, 充值本金, 赠送, 积分)
    # 三个各演示一种状态，演示「会员」页时一眼能看出区别
    ('13800138001', '陈小姐', '500.00', '50.00', 320),   # 老顾客：储值 + 积分都有
    ('13800138002', '李先生', '200.00', '0', 1580),      # 积分攒得多，能演示抵扣
    ('13800138003', '王女士', '0', '0', 0),              # 刚办卡，还没充过值
]

COUPON_TEMPLATES = [
    # 券模板。用 dict 不用元组：`valid_from` / `total_quantity` / `stores` 都是
    # 可选的，元组得靠占位符凑，读起来不知道第几个是什么
    #
    # **有效期按「相对今天多少天」写**，不写死日期——否则 clone 下来跑两个月，
    # 演示券全过期了。负数 = 已经过去，专门留着演示「过期是算出来的」
    # （见 models/coupon.py 开头），不是过期了忘了删
    {
        'name': '满 100 减 20',
        'type': 'full_cut', 'value': '20.00', 'min_amount': '100.00',
        'valid_days': 30,
        'issue': [('13800138001', 1), ('13800138002', 1)],
    },
    {
        # 折扣券：value 是折扣率，不是减多少钱。两种类型都得有，
        # 不然「折扣券」这个分支在界面上永远看不到
        'name': '周三会员日 85 折',
        'type': 'discount', 'value': '0.85', 'min_amount': '50.00',
        'valid_days': 90,
        'issue': [('13800138002', 1)],
    },
    {
        # 只在这两家店能用——演示「适用门店」（在别的店点单时它不会出现）
        'name': '解放路店周年庆 满 50 减 15',
        'type': 'full_cut', 'value': '15.00', 'min_amount': '50.00',
        'valid_days': 45,
        'stores': ['S001', 'S003'],
        'total_quantity': 200,
        'issue': [('13800138001', 1)],
    },
    {
        # 还没生效：20 天后才开始。和过期一样是算出来的，界面上单独一档
        'name': '下月店庆 满 200 减 30',
        'type': 'full_cut', 'value': '30.00', 'min_amount': '200.00',
        'start_days': 20, 'valid_days': 50,
        'issue': [('13800138001', 1)],
    },
    {
        # 已经过期。**库里那行的 status 还是 unused**——这正是要演示的：
        # 过期不是写进库的状态，是每次现算的
        'name': '去年的老券 减 15',
        'type': 'full_cut', 'value': '15.00', 'min_amount': '0',
        'valid_days': -30,
        'issue': [('13800138001', 1)],
    },
    {
        # 没人领的模板：演示「发券」时有东西可选，也演示「没发出去过的能删」
        'name': '新客立减 10 元',
        'type': 'full_cut', 'value': '10.00', 'min_amount': '0',
        'valid_days': 60,
        # **挂到券中心**：顾客端「券中心」页要有东西可领，不然那一页是空的。
        # 每人限领一张——这正是自领和员工发券的区别所在
        'claimable': True, 'per_member_limit': 1,
    },
    {
        # 券中心里的第二张：折扣券，而且限量。
        # 两个字段一起演示：「已领 x/50」和「领完了」长什么样
        'name': '周末 88 折',
        'type': 'discount', 'value': '0.88', 'min_amount': '30.00',
        'valid_days': 30, 'total_quantity': 50,
        'claimable': True, 'per_member_limit': 2,
    },
]

STORE_DISH_OVERRIDES = [
    # (门店编码, 菜名, 价格 / None 表示不改价, 是否上架, 每日限量 / None 表示不限)
    # 武林门店在景区边上，整体贵一点
    ('S003', '红烧牛肉面', '36.00', True, None),
    ('S003', '金牌猪软骨面', '42.00', True, None),
    # 西溪印象城店限量供应——演示「每日限量」
    ('S005', '红烧牛肉面', '35.00', True, 30),
    # 快餐店不做这两样——演示「单店下架」
    ('S002', '咖喱牛肉饭', None, False, None),
    ('S004', '酸梅汤', None, False, None),
    ('S006', '鲜肉小笼包', None, False, None),
]

ORDERS = [
    # (门店, 来源, 状态, 下单人, 备注, [(菜名, 数量, [选项名])], [(支付方式, 金额说明)])
    # 金额说明：'full' = 付清余额，'half' = 付一半，'rest' = 付剩下的，'20.00' = 指定金额
    {'store': 'S001', 'source': 'dine_in', 'status': 'pending', 'operator': 'shouyin',
     'remark': '', 'items': [('红烧牛肉面', 2, ['大份', '特辣', '加蛋']),
                             ('酸梅汤', 2, [])], 'payments': []},
    {'store': 'S001', 'source': 'takeaway', 'status': 'pending', 'operator': 'gongyong',
     'actual_operator': 'fuwuyuan', 'remark': '打包，不要香菜',
     'items': [('台式卤肉饭', 1, ['加饭'])], 'payments': []},
    {'store': 'S003', 'source': 'dine_in', 'status': 'pending', 'operator': 'laoban',
     'remark': '', 'items': [('金牌猪软骨面', 1, ['大份']),
                             ('手工煎饺', 1, [])], 'payments': []},

    {'store': 'S001', 'source': 'dine_in', 'status': 'accepted', 'operator': 'shouyin',
     'remark': '', 'items': [('香煎鸡腿饭', 2, ['标准', '加蛋'])], 'payments': []},
    {'store': 'S005', 'source': 'delivery', 'status': 'accepted', 'operator': 'shouyin',
     'remark': '送到隔壁写字楼 12 楼', 'items': [('红烧牛肉面', 3, ['大份', '中辣']),
                                                 ('可乐', 3, ['冰'])], 'payments': []},

    {'store': 'S001', 'source': 'dine_in', 'status': 'completed', 'operator': 'shouyin',
     'remark': '', 'items': [('红烧牛肉面', 2, ['标准', '微辣']),
                             ('鲜肉小笼包', 1, ['8 只'])],
     'payments': [('wechat', 'full')]},
    {'store': 'S002', 'source': 'takeaway', 'status': 'completed', 'operator': 'shouyin',
     'remark': '', 'items': [('番茄鸡蛋面', 1, ['大份', '加蛋'])],
     'payments': [('cash', 'full')]},
    # 组合支付：先付一半，取餐时付剩下的
    {'store': 'S001', 'source': 'dine_in', 'status': 'completed', 'operator': 'shouyin',
     'remark': '先付定金', 'items': [('金牌猪软骨面', 4, ['大份'])],
     'payments': [('balance', 'half'), ('cash', 'rest')]},
    {'store': 'S004', 'source': 'delivery', 'status': 'completed', 'operator': 'shouyin',
     'remark': '顾客买的美团套餐', 'items': [('咖喱牛肉饭', 1, ['微辣']), ('凉拌黄瓜', 1, [])],
     'payments': [('groupon', 'full')]},
    {'store': 'S003', 'source': 'dine_in', 'status': 'completed', 'operator': 'dianzhang',
     'remark': '老顾客', 'items': [('雪菜肉丝面', 2, ['大份', '微辣']),
                                   ('现磨豆浆', 2, ['无糖'])],
     'payments': [('wechat', 'full')]},
    {'store': 'S006', 'source': 'takeaway', 'status': 'completed', 'operator': 'shouyin',
     'remark': '', 'items': [('台式卤肉饭', 1, ['标准']), ('可乐', 1, ['常温'])],
     'payments': [('groupon', 'full')]},
    {'store': 'S001', 'source': 'dine_in', 'status': 'cancelled', 'operator': 'shouyin',
     'remark': '客人临时有事走了', 'items': [('红烧牛肉面', 1, ['标准', '中辣'])],
     'payments': []},
]


DEMO_REFUNDS = [
    # 挂在第几笔订单上（ORDERS 的下标）、退款比例（1 = 全退）、原因、类型、走到哪一步
    # 三种状态各留一个，退款页打开就有东西看
    {'order_index': 5, 'ratio': 0.5, 'reason': '顾客投诉菜品有问题，协商退一半',
     'type': 'online', 'stage': 'settled'},
    {'order_index': 9, 'ratio': 1.0, 'reason': '顾客当场退货，已现金退还',
     'type': 'offline', 'stage': 'settled'},
    # 这一笔挂在「已完成」的订单上：顾客事后投诉、门店发起部分退款，
    # 是很常见的情况，也顺便演示「已完成」和「有退款」并不冲突
    {'order_index': 6, 'ratio': 0.3, 'reason': '上错菜，退差价',
     'type': 'online', 'stage': 'pending'},
]


# ---------------------------------------------------------------- 执行

def _days_after(now, days):
    """「今天起多少天」→ 具体时间点；None 原样返回

    券的有效期都用相对天数写（见 COUPON_TEMPLATES 上面的注释），换算就这一处。
    """
    if days is None:
        return None
    return now + timedelta(days=days)


def _clear_business_data():
    """清空业务数据（保留员工、权限、门店这些基础配置）

    **审计日志也一起清**。正常情况下审计日志是只增不删的，这里破例是因为
    `seed-demo --reset` 的语义就是「把演示环境恢复到干净状态」——不清的话，
    反复调试攒下的几百条登录记录会把真正想展示的操作淹掉。
    生产环境绝对不该有这种入口。
    """
    from backend.app.extensions import db
    from backend.app.models import (
        AuditLog,
        Balance,
        BalanceTxn,
        GrouponVoucher,
        LegacyMap,
        Member,
        Order,
        OrderItem,
        OrderItemOption,
        Payment,
        Points,
        PointsTxn,
        Reconciliation,
        Refund,
        RefundTxn,
        SyncRecord,
        UserCoupon,
    )

    # 按外键依赖顺序删（这些表之间是 RESTRICT，顺序反了删不掉）：
    # 资产流水 → 订单 → 资产账户 → 会员——`order.member_id` 是 RESTRICT，
    # 订单没删完就删不掉会员。
    #
    # **券模板不删**（所以上面没进口 CouponTemplate）：它和菜单一样算「配置」，
    # 清掉的只是发到人手里的券。反正是按名字幂等重建的，重灌一遍就回来了
    #
    # **老系统那三张表要删干净**：迁移结果挂在会员身上（`LegacyMap.target_id`、
    # 储值账户），会员一删它们就成了指向空气的孤儿记录；更糟的是再跑
    # `import-legacy` 时，映射还在 → 老号被当成「迁过了」跳过 → 储值那笔钱凭空消失。
    # 所以宁可从零再来一遍：`--reset` 之后把 `import-legacy` 和 `reconcile` 都补跑
    for model in (RefundTxn, Refund, GrouponVoucher, UserCoupon,
                  BalanceTxn, PointsTxn,
                  OrderItemOption, Payment, OrderItem, Order,
                  Balance, Points, Member,
                  LegacyMap, SyncRecord, Reconciliation,
                  AuditLog):
        model.query.delete()
    db.session.commit()


def _write_demo_audit(order):
    """给演示订单补审计记录

    演示数据是直接建模型对象的（CLI 里没有请求上下文，走不了 service 层），
    所以不会自动产生审计。但审计日志页是这套系统的卖点之一，空空如也的话
    演示时看不出东西——这里按真实操作的格式补上，字段和 AuditService.log
    写出来的一模一样。

    一笔订单按它走到哪一步，留下几条记录：已完成的订单在现实中会留下
    CREATE → ACCEPT → COMPLETE 三条，只补一条的话，审计页看起来像流程缺了环。
    """
    from backend.app.extensions import db
    from backend.app.models import AuditLog

    chain = {
        'pending': ['CREATE_ORDER'],
        'accepted': ['CREATE_ORDER', 'ACCEPT_ORDER'],
        'completed': ['CREATE_ORDER', 'ACCEPT_ORDER', 'COMPLETE_ORDER'],
        'cancelled': ['CREATE_ORDER', 'CANCEL_ORDER'],
    }[order.status]

    for action in chain:
        db.session.add(AuditLog(
            operator_id=order.operator_id,
            operator_name=order.operator_name or '顾客自助',
            action=action,
            resource='order',
            status='success',
            new_value={'order_no': order.order_no,
                       'payable_amount': float(order.payable_amount)},
        ))

    # 收款也留痕——收款是设计文档点名的关键动作之一
    for index in range(len(order.payments)):
        db.session.add(AuditLog(
            operator_id=order.payments[index].operator_id,
            operator_name=order.payments[index].operator_name or '顾客自助',
            action='COLLECT_PAYMENT',
            resource='order',
            status='success',
            new_value={'order_no': order.order_no,
                       'payment_no': order.payments[index].payment_no,
                       'amount': float(order.payments[index].amount)},
        ))


def seed_demo(reset=False):
    """造演示数据。返回一份统计，给 CLI 打印用

    幂等：门店按编码认领、菜品按名称认领、员工按用户名认领，
    已经存在的不重建，只补齐缺的。订单不做幂等（每次执行都在原有基础上
    继续下单），要重来一遍用 reset=True。
    """
    from backend.app.extensions import db
    from backend.app.models import (
        Balance,
        BalanceTxn,
        Category,
        CouponTemplate,
        Dish,
        DishOption,
        DishOptionGroup,
        GrouponVoucher,
        Member,
        Order,
        Payment,
        Points,
        PointsTxn,
        Refund,
        RefundTxn,
        Role,
        Staff,
        Store,
        StoreDish,
        UserCoupon,
    )
    from backend.app.services.order_service import OrderService

    if reset:
        _clear_business_data()

    stats = {'stores': 0, 'categories': 0, 'dishes': 0, 'staff': 0, 'members': 0,
             'overrides': 0, 'coupon_templates': 0, 'coupons': 0,
             'orders': 0, 'payments': 0, 'refunds': 0, 'groupons': 0}

    # ---------- 门店 ----------
    stores_by_code = {}
    for code, name, store_type, address, phone in STORES:
        store = Store.query.filter_by(code=code).first()
        if not store:
            store = Store(code=code, name=name, store_type=store_type,
                          address=address, phone=phone)
            db.session.add(store)
            stats['stores'] += 1
        stores_by_code[code] = store
    db.session.flush()

    # ---------- 分类 ----------
    categories_by_name = {}
    for order_index, (name, icon, store_codes) in enumerate(CATEGORIES):
        category = Category.query.filter_by(name=name).first()
        if not category:
            category = Category(name=name, icon=icon, sort_order=order_index)
            db.session.add(category)
            stats['categories'] += 1
        category.stores = [stores_by_code[c] for c in store_codes]
        categories_by_name[name] = category
    db.session.flush()

    # ---------- 菜品（含规格组）----------
    dishes_by_name = {}
    for order_index, (cat_name, name, price, desc, groups) in enumerate(DISHES):
        dish = Dish.query.filter_by(name=name).first()
        if not dish:
            dish = Dish(
                category=categories_by_name[cat_name], name=name,
                base_price=Decimal(price), description=desc, sort_order=order_index,
                image=DISH_IMAGES.get(name, ''),
            )
            for g_index, (g_name, g_type, required, options) in enumerate(groups):
                group = DishOptionGroup(
                    name=g_name, selection_type=g_type,
                    is_required=required, sort_order=g_index,
                )
                for o_index, (o_name, extra) in enumerate(options):
                    group.options.append(DishOption(
                        name=o_name, extra_price=Decimal(extra), sort_order=o_index,
                    ))
                dish.option_groups.append(group)
            db.session.add(dish)
            stats['dishes'] += 1
        elif not dish.image and name in DISH_IMAGES:
            # 已经建过的菜补上配图——种子数据的语义是「已存在的不重建、缺的补上」，
            # 配图是后加的，老环境跑一遍就能有
            dish.image = DISH_IMAGES[name]
        dishes_by_name[name] = dish
    db.session.flush()

    # ---------- 门店菜品覆盖（多店定价）----------
    for store_code, dish_name, price, available, limit in STORE_DISH_OVERRIDES:
        store, dish = stores_by_code[store_code], dishes_by_name[dish_name]
        override = StoreDish.query.filter_by(store_id=store.id, dish_id=dish.id).first()
        if not override:
            override = StoreDish(store_id=store.id, dish_id=dish.id)
            db.session.add(override)
            stats['overrides'] += 1
        override.price = Decimal(price) if price else None
        override.is_available = available
        override.daily_limit = limit
    db.session.flush()

    # ---------- 员工账号 ----------
    for phone_index, (username, real_name, role_code, store_code,
                      employment_type, is_shared) in enumerate(STAFF, start=1):
        staff = Staff.query.filter_by(username=username).first()
        if staff:
            continue
        role = Role.query.filter_by(code=role_code).first()
        if role is None:
            raise RuntimeError(
                f'角色 {role_code} 不存在——先执行 flask seed-rbac 再灌演示数据'
            )
        staff = Staff(
            username=username, real_name=real_name,
            email=f'{username}@demo.local',
            mobile=f'1380000{phone_index:04d}',
            store_id=stores_by_code[store_code].id if store_code else None,
            employment_type=employment_type, is_shared=is_shared,
        )
        staff.set_password(DEMO_PASSWORD)
        staff.roles = [role]
        db.session.add(staff)
        stats['staff'] += 1
    db.session.flush()

    staff_by_username = {s.username: s for s in Staff.query.all()}
    option_ids = {
        (dish.name, option.name): option.id
        for dish in Dish.query.all()
        for group in dish.option_groups
        for option in group.options
    }

    # ---------- 会员 + 储值 + 积分 ----------
    # 一期的演示订单都是散客单（顾客端不登录，member_id 一直空着）；这里造几个
    # 会员，让「会员」「储值」「积分」三个页面有东西可看。
    #
    # 直接建模型对象 + 流水（CLI 里没有请求上下文，走不了 service 层——和订单
    # 那边一个道理）。但**流水的字段要和 service 记的一模一样**：本金/赠送各记
    # 各的、带变动后余额——不然演示数据的账自己就对不上。
    for mobile, nickname, principal, bonus, points in MEMBERS:
        if Member.query.filter_by(mobile=mobile).first():
            continue                        # 幂等：按手机号认领
        member = Member(mobile=mobile, nickname=nickname)
        db.session.add(member)
        db.session.flush()
        stats['members'] += 1

        principal, bonus = Decimal(principal), Decimal(bonus)
        if principal or bonus:
            db.session.add(Balance(member_id=member.id,
                                   principal=principal, bonus=bonus))
            # 和 BalanceService.recharge 一样记**两条**流水：本金是收入、
            # 赠送是营销成本，报表上是两回事
            if principal:
                db.session.add(BalanceTxn(
                    member_id=member.id, type=BalanceTxn.TYPE_RECHARGE,
                    principal_delta=principal, bonus_delta=Decimal('0'),
                    principal_after=principal, bonus_after=Decimal('0'),
                    remark='演示数据：开卡充值',
                ))
            if bonus:
                db.session.add(BalanceTxn(
                    member_id=member.id, type=BalanceTxn.TYPE_BONUS,
                    principal_delta=Decimal('0'), bonus_delta=bonus,
                    principal_after=principal, bonus_after=bonus,
                    remark='演示数据：充值赠送',
                ))

        if points:
            db.session.add(Points(member_id=member.id, balance=points))
            db.session.add(PointsTxn(
                member_id=member.id, type=PointsTxn.TYPE_MIGRATE,
                delta=points, after=points,
                legacy_no=f'LEGACY-{mobile}',
                remark='演示数据：从老系统迁过来的积分',
            ))
    db.session.flush()

    # ---------- 券模板 + 发券 ----------
    # 模板按名字认领（幂等）；发出去的券按「这个会员手里本来有几张」补齐，
    # 反复跑不会越攒越多，删掉几张再跑一遍又能补回演示要的数量
    members_by_mobile = {m.mobile: m for m in Member.query.all()}
    coupon_now = datetime.now(timezone.utc)
    for spec in COUPON_TEMPLATES:
        template = CouponTemplate.query.filter_by(name=spec['name']).first()
        if not template:
            template = CouponTemplate(name=spec['name'])
            db.session.add(template)
            stats['coupon_templates'] += 1

        # **每次跑都把定义里的字段写回去**，不只是新建的时候。
        #
        # 和门店菜品覆盖（STORE_DISH_OVERRIDES）一个做法：演示数据是「演示环境
        # 的一部分」，跑一遍就该恢复成定义的样子。券模板后来加了 is_claimable /
        # per_member_limit 两个字段——只在新建立时赋值的话，老环境跑多少遍
        # 券中心都是空的
        template.type = spec['type']
        template.value = Decimal(spec['value'])
        template.min_amount = Decimal(spec.get('min_amount') or '0')
        template.valid_from = _days_after(coupon_now, spec.get('start_days'))
        template.valid_to = _days_after(coupon_now, spec['valid_days'])
        template.total_quantity = spec.get('total_quantity')
        template.is_claimable = spec.get('claimable', False)
        template.per_member_limit = spec.get('per_member_limit')
        template.stores = [stores_by_code[c] for c in spec.get('stores', [])]
        db.session.flush()                  # 下面发券要用 template.id

        for mobile, count in spec.get('issue', []):
            member = members_by_mobile[mobile]
            already = UserCoupon.query.filter_by(
                template_id=template.id, member_id=member.id).count()
            for _ in range(count - already):
                db.session.add(UserCoupon(
                    template_id=template.id,
                    member_id=member.id,
                    received_at=coupon_now,
                    # 发券人是「演示数据」不是某个员工——真发券时这里会是
                    # 收银/店长的名字（见 CouponService.issue）
                    issued_by_name='演示数据',
                ))
                stats['coupons'] += 1
    db.session.flush()

    # ---------- 订单 ----------
    base_time = datetime.now(timezone.utc)
    for index, spec in enumerate(ORDERS):
        store = stores_by_code[spec['store']]
        operator = staff_by_username.get(spec['operator'])
        # 公用账号下单时记实际操作人
        actual = staff_by_username.get(spec.get('actual_operator')) or operator

        order = Order(
            order_no=OrderService.next_order_no(store),
            # 顾客端查订单的凭据。演示数据直接建模型对象（不走 create_order），
            # 所以这里要手动给——不然演示订单在顾客端查不到
            query_token=secrets.token_hex(12),
            store_id=store.id,
            source=spec['source'],
            status=spec['status'],
            remark=spec['remark'],
            operator_id=actual.id if actual else None,
            operator_name=(actual.real_name or actual.username) if actual else '',
        )

        total = Decimal('0')
        for dish_name, quantity, chosen in spec['items']:
            dish = dishes_by_name[dish_name]
            override = StoreDish.query.filter_by(
                store_id=store.id, dish_id=dish.id
            ).first()
            ids = [option_ids[(dish_name, name)] for name in chosen]
            # 复用下单时的算价逻辑，保证演示数据和真实下单算出来的钱一致
            item = OrderService.build_order_item(dish, override, quantity, ids)
            order.items.append(item)
            total += item.subtotal

        order.total_amount = total
        order.payable_amount = total
        order.discount_amount = Decimal('0')
        order.paid_amount = Decimal('0')

        # 支付：一笔一笔地记，金额说明见 ORDERS 上面的注释
        for method, amount_spec in spec['payments']:
            remaining = order.payable_amount - order.paid_amount
            if amount_spec == 'half':
                amount = (remaining / 2).quantize(Decimal('0.01'))
            else:
                amount = remaining
            seq = len(order.payments) + 1
            payment = Payment(
                method=method, amount=amount,
                payment_no=f'{order.order_no}-P{seq:02d}',
            )
            payment.mark_success(
                transaction_no=(f'WX{order.order_no}{seq:02d}'
                                if method == 'wechat' else ''),
                operator_id=actual.id if actual else None,
                operator_name=(actual.real_name or actual.username) if actual else '',
            )
            order.payments.append(payment)
            order.paid_amount = order.paid_amount + amount
            stats['payments'] += 1

        db.session.add(order)
        db.session.flush()
        # 把下单时间往前铺开，列表看起来才像一天下来的单子
        order.created_at = base_time - timedelta(minutes=(len(ORDERS) - index) * 17)
        _write_demo_audit(order)
        stats['orders'] += 1

    # ---------- 退款单 ----------
    # 订单是按 ORDERS 的顺序建的，这里按下标找回它们
    created_orders = (Order.query
                      .order_by(Order.id)
                      .all())[-len(ORDERS):] if ORDERS else []
    for spec in DEMO_REFUNDS:
        order = created_orders[spec['order_index']]
        amount = (order.payable_amount * Decimal(str(spec['ratio']))).quantize(Decimal('0.01'))
        if amount <= 0 or amount > order.refundable_amount:
            continue

        applicant = staff_by_username.get('shouyin') or staff_by_username.get('laoban')
        approver = staff_by_username.get('dianzhang') or staff_by_username.get('laoban')
        refund = Refund(
            refund_no=f'{order.order_no}-R01',
            order_id=order.id,
            amount=amount,
            reason=spec['reason'],
            type=spec['type'],
            applicant_id=applicant.id if applicant else None,
            applicant_name=(applicant.real_name or applicant.username) if applicant else '',
        )
        if spec['stage'] in ('approved', 'settled'):
            refund.status = Refund.STATUS_APPROVED
            refund.approver_id = approver.id if approver else None
            refund.approver_name = (approver.real_name or approver.username) if approver else ''
            refund.approve_remark = '情况属实'
            refund.approved_at = base_time
        if spec['stage'] == 'settled':
            refund.status = Refund.STATUS_SETTLED
            refund.txns.append(RefundTxn(
                order_id=order.id,
                amount=amount,
                method=('cash' if spec['type'] == 'offline' else 'original'),
                transaction_no=('' if spec['type'] == 'offline'
                                else f'WXREFUND{order.order_no[-4:]}-{spec["order_index"]:02d}'),
                operator_id=approver.id if approver else None,
                operator_name=(approver.real_name or approver.username) if approver else '',
                settled_at=base_time,
            ))
            order.refunded_amount = order.refunded_amount + amount

        db.session.add(refund)
        stats['refunds'] += 1

    # ---------- 团购券核销记录 ----------
    # 订单里用团购券付过款的那几笔，补一条对应的核销记录。
    # 真实流程里这两件事是同时发生的（GrouponService.verify 一次做两件），
    # 演示数据直接建模型对象，所以要手动补上，否则核销记录页是空的。
    for order in created_orders:
        for index, payment in enumerate(order.payments, start=1):
            if payment.method != Payment.METHOD_GROUPON:
                continue
            db.session.add(GrouponVoucher(
                # 券码按平台的习惯编一个（美团券码一般是 MT 开头的一长串）。
                # 用完整单号而不是尾几位——不同门店同一天同一序号的订单，
                # 单号尾段是一样的，截短了会撞（券码有唯一约束，撞了就报错）
                code=f'MT{order.order_no.replace("-", "")}{index:02d}',
                platform=GrouponVoucher.PLATFORM_MEITUAN,
                amount=payment.amount,
                order_id=order.id,
                payment_id=payment.id,
                verified_by_id=payment.operator_id,
                verified_by_name=payment.operator_name,
                verified_at=payment.paid_at or base_time,
            ))
            stats['groupons'] += 1

    db.session.commit()
    logger.info('演示数据就绪：%s', stats)
    return stats
