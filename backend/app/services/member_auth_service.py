"""顾客端登录：手机号 + 验证码，**登录即注册**

真实小程序里顾客登录基本只有两条路：微信一键登录（授权手机号），或者手机号 + 验证码。
微信那条要真 AppID，这里没有，所以走验证码。**但两条路的终点是一样的**：
拿到一个手机号（或 openid）→ 找到或创建一个 `Member`。所以换掉的是"怎么证明你是你"，
不是"登录之后干什么"。

**登录即注册**：手机号是新的时候顺手建一个 Member，不单独做注册页。
这是真实小程序的形态——顾客不会为了点个单先填一遍注册表单。
员工代客办卡那条路（`MemberService.create`）还在，两者最终落到同一张表。

验证码存库不存缓存，理由见 `models/member.py` 里 `MemberVerifyCode` 的说明。
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from backend.app.errors import BusinessError
from backend.app.extensions import db
from backend.app.models import Member, MemberVerifyCode
from backend.app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

RESOURCE = 'member_auth'

# 验证码位数。6 位数字 = 100 万种，配合下面那几条限制够用了：
# 5 分钟过期、错 5 次作废、同一手机号 60 秒才能重发
CODE_DIGITS = 6

# 开发/演示环境把验证码直接回显（真发短信要网关，见 README 的「哪些是模拟的」）
CODE_ECHO_CONFIG = 'MEMBER_CODE_ECHO'


def _now():
    """库里存的是不带时区的 UTC，比时间统一用这个"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _echo_enabled():
    from flask import current_app
    return bool(current_app.config.get(CODE_ECHO_CONFIG, True))


class MemberAuthService:
    # ---------- 校验 ----------

    @staticmethod
    def assert_mobile(mobile):
        """手机号格式。

        **只做最基础的检查**（11 位数字、1 开头），不搞什么运营商号段白名单——
        那种校验除了拦住合法的虚拟号段，什么用都没有。真实系统里真正拦得住的是
        「这个号收得到验证码」这件事本身。
        """
        mobile = (mobile or '').strip()
        if not (len(mobile) == 11 and mobile.isdigit() and mobile.startswith('1')):
            raise BusinessError('手机号格式不对')
        return mobile

    # ---------- 发验证码 ----------

    @staticmethod
    def send_code(mobile):
        """生成一条验证码，返回给接口下发的东西

        **「发送」这一步是模拟的**：真发短信要网关，这里只写日志 + 开发环境回显。
        但发送**周围**那些东西都是真的——限流、过期、一次性、错误次数，
        它们才是防刷的关键，短信网关换一个供应商也还是这些。
        """
        mobile = MemberAuthService.assert_mobile(mobile)

        latest = (MemberVerifyCode.query
                  .filter_by(mobile=mobile)
                  .order_by(MemberVerifyCode.id.desc())
                  .first())
        if latest:
            waited = (_now() - latest.created_at).total_seconds()
            if waited < MemberVerifyCode.RESEND_INTERVAL_SECONDS:
                raise BusinessError(
                    f'刚发过，'
                    f'{int(MemberVerifyCode.RESEND_INTERVAL_SECONDS - waited)} 秒后再试'
                )

            # 顺手清掉这个手机号的陈年旧行：验证码表是只增不减的，
            # 不在这里清理就得靠定时任务（而这是个演示项目，没有定时任务）
            cutoff = _now() - timedelta(days=1)
            MemberVerifyCode.query.filter(
                MemberVerifyCode.mobile == mobile,
                MemberVerifyCode.created_at < cutoff,
            ).delete()

        # secrets 而不是 random：验证码是凭据，random 种子的可预测性是真问题
        code = ''.join(secrets.choice('0123456789') for _ in range(CODE_DIGITS))
        record = MemberVerifyCode.issue(mobile, code)
        db.session.add(record)
        db.session.commit()

        logger.info('[模拟短信] 验证码发给 %s：%s（%d 秒内有效）',
                    mobile, code, MemberVerifyCode.TTL_SECONDS)

        data = {'mobile': mobile, 'expires_in': MemberVerifyCode.TTL_SECONDS}
        if _echo_enabled():
            # 演示环境直接把码带回去，省得去翻日志。生产环境必须关掉——
            # 回显等于验证码形同虚设，谁填一下都能登进别人的账号
            data['code'] = code
            data['note'] = '演示环境回显；真实环境这一步会发短信'
        return data

    # ---------- 校验 + 登录 ----------

    @staticmethod
    def _take_valid_code(mobile, code):
        """找出这个手机号最新那条可用的验证码，逐条检查并返回

        **检查顺序是有讲究的**：先看有没有、再看用过没、再看过期没，
        最后才比数字。每一步失败给的话都不一样——顾客需要知道
        「是重新获取」还是「是不是输错了」，含糊的报错会让人反复试。
        """
        record = (MemberVerifyCode.query
                  .filter_by(mobile=mobile)
                  .order_by(MemberVerifyCode.id.desc())
                  .first())
        if not record:
            raise BusinessError('请先获取验证码')

        if record.is_used:
            raise BusinessError('这个验证码已经用过了，请重新获取')
        if record.is_expired:
            raise BusinessError('验证码过期了，请重新获取')
        if record.attempt_count >= MemberVerifyCode.MAX_ATTEMPTS:
            raise BusinessError('错误次数太多，请重新获取验证码')

        if not secrets.compare_digest(record.code, code or ''):
            # 错一次记一次。不记的话一个验证码可以拿来暴力试六位数字
            record.attempt_count += 1
            db.session.commit()
            left = MemberVerifyCode.MAX_ATTEMPTS - record.attempt_count
            raise BusinessError(f'验证码不对（还能试 {left} 次）' if left > 0
                                else '验证码不对，错误次数已用完，请重新获取')

        return record

    @staticmethod
    def login(mobile, code):
        """验证码换会员 + token；**会员不存在就顺手建一个**（登录即注册）"""
        from backend.app.utils.token import issue_member_token

        mobile = MemberAuthService.assert_mobile(mobile)
        record = MemberAuthService._take_valid_code(mobile, code)

        record.mark_used()

        member = Member.query.filter_by(mobile=mobile).first()
        is_new = member is None
        if is_new:
            member = Member(mobile=mobile)
            db.session.add(member)
            db.session.flush()

        # 停用要在**验证码通过之后**才判：反过来的话，一个停用的号码
        # 会得到「账号已停用」——那等于告诉别人这个号在系统里存在
        if not member.is_active:
            db.session.rollback()
            raise BusinessError('这个账号已经停用了，联系门店处理')

        db.session.commit()

        AuditService.log(
            operator_id=None,
            # 顾客不在员工表里，审计的 operator_id 是空的；名字用手机号，
            # 出了事能对上人
            operator_name=f'顾客 {mobile}',
            action='MemberRegister' if is_new else 'MemberLogin',
            resource=RESOURCE,
            status='success',
            new_value={'member_id': member.id, 'mobile': mobile},
        )

        return member, issue_member_token(member), is_new

    # ---------- 拿 token 换人 ----------

    @staticmethod
    def resolve_token(token):
        """顾客 token → 会员；无效、过期、类型不对、账号停用，一律 None

        和员工那边（`AuthService.resolve_token`）一样**每次请求都查一次库**——
        顾客被停用（门店黑名单、刷单）之后下一条请求就进不来，
        不用等 token 那 30 天过期。
        """
        from backend.app.utils.token import parse_member_token

        payload = parse_member_token(token)
        if not payload:
            return None

        member = db.session.get(Member, payload.get('uid'))
        if not member or not member.is_active:
            return None
        return member
