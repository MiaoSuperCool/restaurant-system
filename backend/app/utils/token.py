"""员工小程序的 token：签发、校验、从请求里取出来

**为什么是 itsdangerous 而不是 JWT**：它本来就在依赖里——Flask 自己就用它签
session cookie。签名、过期、防篡改，三样都有，不用为了一件事多装一个库。
JWT 多给的是「跨语言可读」和一套标准 claim，这个项目里没有第二个语言要读它。

**无状态**：服务端不存 token，所以「把某个 token 删掉」这种操作不存在。
撤销靠 `Staff.token_version`：登出或改密码时 +1，旧 token 里带的版本对不上就废了
（见 `AuthService.logout`）。

**token 里只放「你是谁」，不放权限。** 权限每次请求现查——这样改了角色、
停了账号立刻生效，不用等 token 过期。这也是 `permission_required` 一行都不用改的原因。
"""
from flask import current_app, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# 和 session 的签名分开：同一个 key 签两种东西，哪天想单独换一种就麻烦了
SALT = 'staff-mp-token'


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=SALT)


def max_age():
    """token 有效期（秒）。小程序不像网页那样天天重新登录，所以给得比 session 长"""
    return int(current_app.config.get('MP_TOKEN_MAX_AGE', 7 * 24 * 3600))


def issue_token(staff):
    """给员工签一个 token

    载荷里带 `ver`（`token_version`）：登出/改密码时那个数 +1，
    这个 token 下次用就对不上了。
    """
    return _serializer().dumps({'uid': staff.id, 'ver': staff.token_version or 0})


def parse_token(token):
    """验签 + 看有没有过期，返回载荷；**无效或过期都返回 None**

    不抛异常：调用方（`request_loader`）要的是「这人是谁，或者没有」，
    拿一个异常去表达「没有」只会让每个调用点都包一层 try。
    """
    try:
        return _serializer().loads(token, max_age=max_age())
    except SignatureExpired:
        return None
    except BadSignature:
        # 签名不对 = 伪造的、或者改过 SECRET_KEY，两种情况都当没有
        return None


def bearer_token():
    """从 `Authorization: Bearer xxx` 里取出 token；没有就返回 None

    只认这一种写法（大小写不敏感），不认 query 参数里传 token——
    URL 会被写进日志、referer、浏览器历史，token 不该出现在那些地方。
    """
    header = request.headers.get('Authorization', '')
    if not header.lower().startswith('bearer '):
        return None
    return header[7:].strip() or None
