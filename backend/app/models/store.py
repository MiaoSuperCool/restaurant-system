"""门店：整个系统的核心实体

订单、员工、库存、门店菜品全都挂在门店下，所以它必须是一期第一个建的表。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class Store(BaseModel):
    __tablename__ = 'store'

    # ---------- 枚举值 ----------
    # 门店类型：快餐店和堂食大店的作业方式不同（快餐主推自取/外卖，堂食大店要桌台）
    TYPE_FAST_FOOD = 'fast_food'
    TYPE_DINE_IN = 'dine_in'
    TYPE_LABELS = {
        TYPE_FAST_FOOD: '快餐店',
        TYPE_DINE_IN: '堂食大店',
    }

    # 营业状态：休息中可恢复（临时打烊），已停业是终态（不再上线）
    STATUS_OPEN = 'open'
    STATUS_RESTING = 'resting'
    STATUS_CLOSED = 'closed'
    STATUS_LABELS = {
        STATUS_OPEN: '营业中',
        STATUS_RESTING: '休息中',
        STATUS_CLOSED: '已停业',
    }

    # 运行模式：灰度切换用——一店一店从老系统切到新系统
    MODE_LEGACY = 'legacy'
    MODE_NEW = 'new'
    MODE_LABELS = {
        MODE_LEGACY: '老系统',
        MODE_NEW: '新系统',
    }

    # ---------- 字段 ----------
    # 门店编码：外部对接（老系统映射、ERP、对账）靠它认店，改编码会断链，慎改
    code = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False, index=True)
    store_type = db.Column(db.String(20), nullable=False, default=TYPE_DINE_IN)
    address = db.Column(db.String(255), nullable=False, default='')
    phone = db.Column(db.String(20), nullable=False, default='')

    # ---------- 给顾客看的展示信息 ----------
    # 这两个字段不出现在任何业务逻辑里，纯粹是「顾客点开这家店想看什么」：
    # 一句话介绍 + 几点开门几点关。
    #
    # 为什么单列而不是塞进 remark：`remark` 是内部备注（「这家店在装修，
    # 对接人王工」这类），是要给员工看的，不能顺手拿去给顾客看。
    description = db.Column(db.String(255), nullable=False, default='')
    business_hours = db.Column(db.String(64), nullable=False, default='')

    business_status = db.Column(db.String(20), nullable=False, default=STATUS_OPEN)
    # 灰度切换期间：老系统为权威时新系统只读该店数据
    run_mode = db.Column(db.String(20), nullable=False, default=MODE_NEW)

    remark = db.Column(db.String(255), nullable=False, default='')

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'store_type': self.store_type,
            'store_type_label': self.TYPE_LABELS.get(self.store_type, self.store_type),
            'address': self.address,
            'phone': self.phone,
            # 给顾客看的：一句话介绍 + 营业时间
            'description': self.description,
            'business_hours': self.business_hours,
            'business_status': self.business_status,
            'business_status_label': self.STATUS_LABELS.get(
                self.business_status, self.business_status
            ),
            'run_mode': self.run_mode,
            'run_mode_label': self.MODE_LABELS.get(self.run_mode, self.run_mode),
            'remark': self.remark,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
