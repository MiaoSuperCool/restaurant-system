"""顾客端（小程序）用的服务

和内部接口的区别不只是「不用登录」——它面对的是**不受信任的调用方**：

- 顾客能看到的菜单要过滤掉本店下架的菜（内部菜单要显示，因为店长要管理）
- 查订单不能只凭单号（单号可读、可猜，遍历一遍就看到别人的订单了）
- 下单接口没有权限码可查——因为顾客本来就不在权限体系里

**但算价必须复用内部那一套**（OrderService.build_order）。价格是这个系统的命根子，
有两条算价路径迟早会算出两个数。
"""
import secrets

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Order, Payment, Store
from backend.app.services.audit_service import AuditService
from backend.app.services.order_service import OrderService
from backend.app.services.points_service import PointsService
from backend.app.services.store_dish_service import StoreDishService

RESOURCE = 'order'


class PublicService:
    @staticmethod
    def get_open_stores():
        """能点单的门店：只返回营业中的

        休息中和已停业的店不该出现在顾客的选店列表里——点了也下不了单。
        """
        return (Store.query
                .filter(Store.business_status == Store.STATUS_OPEN)
                .order_by(Store.code)
                .all())

    @staticmethod
    def get_menu(store_id):
        return StoreDishService.get_public_menu(store_id)

    @staticmethod
    def create_order(store_id, data, member=None):
        """顾客自助下单

        `member` 传登录的顾客（没登录就是 None）。**登录了就挂上**——
        不挂的话这一单和这个人没关系：积分攒不到、券也用不上、
        「我的订单」还是只能靠本地存的令牌查。没登录照样能下单，只是这些都没有。
        """
        store = db.session.get(Store, store_id)
        if not store:
            raise NotFoundError('门店不存在')
        if store.business_status != Store.STATUS_OPEN:
            raise BusinessError(
                f'「{store.name}」'
                f'{Store.STATUS_LABELS.get(store.business_status)}，暂时不接单'
            )

        try:
            # 和内部代点单走同一个 build_order：算价、规格校验、单号生成都是同一套
            order = OrderService.build_order(
                store, data['items'], data['source'], data.get('remark', ''),
                member_id=member.id if member else None,
            )
            db.session.add(order)

            # 券也走内部那条路的同一段逻辑（归属校验、算抵扣、标记已用都在里面），
            # **放在 build_order 之后**：那是个纯构造，而这一步要真动数据库、
            # 还要改应付金额
            OrderService.apply_coupon(order, data.get('user_coupon_id'))

            db.session.commit()

            AuditService.log(
                operator_name='顾客自助',
                action='CREATE_ORDER',
                resource=RESOURCE,
                status='success',
                new_value=order.to_dict(),
            )
            return order
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_name='顾客自助',
                action='CREATE_ORDER',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def find_order(order_no, token):
        """凭「单号 + 查询令牌」找订单

        只凭单号不行：单号是可读的、也是可以猜的（S001-20260912-0001、0002……），
        遍历一遍就看到了别人点了什么、花了多少。所以下单时另发一个随机令牌。

        单号不存在和令牌不对**返回同一个错误**——分开报的话，
        试探的人能靠错误信息区分「这单存在但令牌错」和「这单不存在」。
        """
        order = Order.query.filter_by(order_no=order_no).first()
        if not order or not token or not secrets.compare_digest(order.query_token, token):
            raise NotFoundError('订单不存在，或查询凭据不正确')
        return order

    @staticmethod
    def pay(order, method):
        """模拟支付

        **没有对接真实的微信支付。** 这里只是把「钱付了」这件事记下来。

        真实对接要做的是：服务端调微信的统一下单拿 prepay_id → 小程序里
        wx.requestPayment 调起收银台 → 微信异步回调 → **验签** → 才认这笔钱。
        其中验签那一步是关键：不验签的话，伪造一个回调就能白吃一顿。

        现在这套流程完全没做，`docs/设计决策.md` 和 README 里都标着「未对接」。

        **顾客端只认模拟的微信支付**：现金要到店给，储值要输密码验证——
        那些是收银台的事。以前这里来者不拒，传 `balance` 既不扣余额也不报错，
        等于白吃一顿（钱没从任何地方出，单子却显示付了）。
        """
        if method != Payment.METHOD_WECHAT:
            raise BusinessError('这个入口只支持微信支付，其他方式请到店结算')

        if order.status == Order.STATUS_CANCELLED:
            raise BusinessError('订单已取消，不能支付')

        remaining = order.payable_amount - order.paid_amount
        if remaining <= 0:
            raise BusinessError('这单已经付过了')

        try:
            payment = Payment(
                order_id=order.id,
                method=method,
                amount=remaining,
                payment_no=f'{order.order_no}-P{len(order.payments) + 1:02d}',
            )
            payment.mark_success(
                # 流水号前面加 MOCK，一眼能看出这是模拟的、不是微信真实的单号。
                # 真接上之后要去掉这个前缀，否则财务对账时会拿它去和微信账单核
                transaction_no=f'MOCK{secrets.token_hex(8).upper()}',
                operator_name='顾客自助',
            )
            order.payments.append(payment)
            order.paid_amount = order.paid_amount + remaining

            # **收款就返积分**——和员工端收款（`OrderService.add_payment`）
            # 共用同一条规则。以前这条路径漏了，顾客登录着买东西，
            # 积分一分不涨（而单子明明是挂在他名下的）
            PointsService.earn_for_payment(order, remaining)

            db.session.commit()

            AuditService.log(
                operator_name='顾客自助',
                action='COLLECT_PAYMENT',
                resource=RESOURCE,
                status='success',
                new_value=payment.to_dict(),
            )
            return payment
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_name='顾客自助',
                action='COLLECT_PAYMENT',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def cancel_order(order):
        """顾客自己取消订单

        只在「还没接单、还没付款」时允许——门店已经开始做了就不能顾客说取消就取消。
        已付款的要走退款（那条路要有员工审批）。
        """
        if order.status != Order.STATUS_PENDING:
            raise BusinessError(
                f'订单已经是「{order.STATUS_LABELS[order.status]}」，不能自己取消；'
                f'请联系门店'
            )
        if order.refundable_amount > 0:
            raise BusinessError('订单已付款，请联系门店处理退款')

        order.status = Order.STATUS_CANCELLED
        db.session.commit()
        AuditService.log(
            operator_name='顾客自助',
            action='CANCEL_ORDER',
            resource=RESOURCE,
            status='success',
            new_value=order.to_dict(),
        )
        return order
