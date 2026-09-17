"""两套 token：员工的（员工小程序）和顾客的（顾客小程序）

**为什么是 itsdangerous 而不是 JWT**：它本来就在依赖里——Flask 自己就用它签
session cookie。签名、过期、防篡改，三样都有，不用为了一件事多装一个库。
JWT 多给的是「跨语言可读」和一套标准 claim，这个项目里没有第二个语言要读它。

**无状态**：服务端不存 token，所以「把某个 token 删掉」这种操作不存在。
撤销靠版本号（`Staff.token_version`）：登出或改密码时 +1，旧 token 里带的版本
对不上就废了（见 `AuthService.logout`）。顾客那边没有版本号，原因见 `issue_member_token`。

**token 里只放「你是谁」，不放权限。** 权限每次请求现查——这样改了角色、
停了账号立刻生效，不用等 token 过期。这也是 `permission_required` 一行都不用改的原因。

**为什么要分类型**：员工和顾客是两套账号体系（设计文档第 3 条）。载荷里不带类型的话，
`request_loader` 会拿着一个 member_id 去 staff 表里查——**可能真的查到一个无关的人**
（两张表的 id 都是自增的）。所以每个 token 都带 `typ`，解析时先看它。

**有效期先解开才知道**：员工 7 天、顾客 30 天，而类型在载荷里。所以
`parse_token` 只验签、不判过期，由 `parse_staff_token` / `parse_member_token`
按类型各判各的。
"""
from datetime import datetime, timezone

from flask import current_app, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

# 和 session 的签名分开：同一个 key 签两种东西，哪天想单独换一种就麻烦了
SALT = 'mp-token'

# 两种 token 的类型标记
TYPE_STAFF = 'staff'
TYPE_MEMBER = 'member'


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=SALT)


def staff_token_max_age():
    """员工 token 有效期（秒）。小程序不像网页那样天天重新登录，所以给得比 session 长"""
    return int(current_app.config.get('MP_TOKEN_MAX_AGE', 7 * 24 * 3600))


def member_token_max_age():
    """顾客 token 有效期（秒）。比员工的长——顾客是「想起来才打开一次」的用法"""
    return int(current_app.config.get('MEMBER_TOKEN_MAX_AGE', 30 * 24 * 3600))


def issue_token(staff):
    """给员工签一个 token

    载荷里带 `ver`（`token_version`）：登出/改密码时那个数 +1，
    这个 token 下次用就对不上了。
    """
    return _serializer().dumps({
        'typ': TYPE_STAFF, 'uid': staff.id, 'ver': staff.token_version or 0,
    })


def issue_member_token(member):
    """给顾客签一个 token

    **没有 `ver`**（员工那个 `token_version` 顾客没有）。顾客端不需要它：

    - 「登出」就是手机上把 token 删掉，没有公用设备要清场
    - 顾客没有密码，也就没有「改密码要踢掉旧凭据」这回事
    - 停用账号（`Member.is_active`）每次请求都会查库检查，那个是最要紧的

    也就是说，**这一条链路上唯一需要「立刻生效」的东西（停用）已经覆盖了**，
    版本号在这里只是多一列。
    """
    return _serializer().dumps({'typ': TYPE_MEMBER, 'uid': member.id})


def bearer_token():
    """从 `Authorization: Bearer xxx` 里取出 token；没有就返回 None

    只认这一种写法（大小写不敏感），不认 query 参数里传 token——
    URL 会被写进日志、referer、浏览器历史，token 不该出现在那些地方。
    """
    header = request.headers.get('Authorization', '')
    if not header.lower().startswith('bearer '):
        return None
    return header[7:].strip() or None


def parse_token(token):
    """验签，返回 `(载荷, 签发时间)`；签名不对返回 None

    **不在这儿判过期**——有效期是按 token 类型定的（员工 7 天、顾客 30 天），
    而类型在载荷里，得先解开才知道。调用方拿到签发时间自己比，见下面两个函数。
    """
    try:
        return _serializer().loads(token, return_timestamp=True)
    except BadSignature:
        # 伪造的、或者改过 SECRET_KEY，两种情况都当没有
        return None


def _expired(issued_at, max_age):
    return (datetime.now(timezone.utc) - issued_at).total_seconds() > max_age


def parse_staff_token(token):
    """员工 token → 载荷；签名不对、类型不对、过期，一律 None"""
    parsed = parse_token(token)
    if not parsed:
        return None
    payload, issued_at = parsed
    if payload.get('typ') != TYPE_STAFF:
        return None
    return None if _expired(issued_at, staff_token_max_age()) else payload


def parse_member_token(token):
    """顾客 token → 载荷；签名不对、类型不对、过期，一律 None"""
    parsed = parse_token(token)
    if not parsed:
        return None
    payload, issued_at = parsed
    if payload.get('typ') != TYPE_MEMBER:
        return None
    return None if _expired(issued_at, member_token_max_age()) else payload
