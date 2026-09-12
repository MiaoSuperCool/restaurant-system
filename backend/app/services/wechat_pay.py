"""微信支付 V3 协议实现

**这个文件里全是真代码**——真实项目接微信支付要写的就是这些。
但本项目没有商户号，所以只能对着自建的模拟网关（tools/mock_wechat_gateway.py）
跑，证明协议这一层是对的。

--------------------------------------------------------------------------
微信支付 V3 的三件事，每一件都有个「不做会出事」的理由：

**1. 请求要签名**（SHA256withRSA）
商户用自己的私钥签，微信拿商户的公钥验。目的是让微信确定「这个请求真的
来自这家商户」，而不是别人伪造的。

**2. 回调要验签**
微信异步通知「这笔钱收到了」时，会用**微信的私钥**签名，商户拿微信的
**平台公钥**验。**这一步绝对不能省**——回调地址是公开的，谁都能往上打；
不验签的话，伪造一个「支付成功」的通知就能白吃一顿饭。

**3. 回调内容要解密**（AES-256-GCM）
回调的 body 里，敏感信息（订单号、金额）是加密的，用商户在商户平台设的
APIv3 密钥解。用 AEAD 模式，解密时会连带校验内容没被篡改。
"""
import base64
import json
import time
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 微信支付 V3 的签名算法标识
SIGN_TYPE = 'WECHATPAY2-SHA256-RSA2048'


class WeChatPayError(Exception):
    """微信支付相关的错误（签名不对、解密失败、接口报错）"""


# ---------------------------------------------------------------------------
# 密码学原语：签名 / 验签 / 加解密
# 抽成纯函数，是因为模拟网关那边要用「反向操作」（签发响应、加密回调），
# 两边共用同一套实现才能证明协议是对的。
# ---------------------------------------------------------------------------

def load_private_key(pem: str):
    return serialization.load_pem_private_key(pem.encode(), password=None)


def load_public_key(pem: str):
    """微信给的平台公钥是 X.509 证书，不是裸公钥——这里两种都认"""
    pem_bytes = pem.encode()
    if b'BEGIN CERTIFICATE' in pem_bytes:
        from cryptography.x509 import load_pem_x509_certificate
        return load_pem_x509_certificate(pem_bytes).public_key()
    return serialization.load_pem_public_key(pem_bytes)


def rsa_sign(private_key_pem: str, message: str) -> str:
    """SHA256withRSA 签名，返回 base64

    私钥格式是商户平台上下的 apiclient_key.pem。
    """
    signature = load_private_key(private_key_pem).sign(
        message.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


def rsa_verify(public_key_pem: str, message: str, signature_b64: str) -> bool:
    """验签。**返回 False 而不是抛异常**——调用方只需要知道「过没过」"""
    try:
        load_public_key(public_key_pem).verify(
            base64.b64decode(signature_b64),
            message.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def assert_api_v3_key(api_v3_key: str):
    """APIv3 密钥必须是 32 字节

    长度不对的话，AESGCM 初始化时才报错，而且报的是「密钥长度不对」这种
    底层信息——不如在这里给一句能看懂的。
    """
    if len(api_v3_key.encode('utf-8')) != 32:
        raise WeChatPayError(
            f'APIv3 密钥必须是 32 字节，当前是 '
            f'{len(api_v3_key.encode("utf-8"))} 字节'
        )


def aes_gcm_decrypt(api_v3_key: str, nonce: str, ciphertext_b64: str,
                    associated_data: str = '') -> str:
    """解密回调里的 resource

    APIv3 密钥是商户自己在商户平台设的 32 位字符串。
    AEAD 模式：解密时会连带校验内容没被改过——密文被篡改会直接抛 InvalidTag。
    """
    assert_api_v3_key(api_v3_key)
    try:
        return AESGCM(api_v3_key.encode('utf-8')).decrypt(
            nonce.encode('utf-8'),
            base64.b64decode(ciphertext_b64),
            associated_data.encode('utf-8') if associated_data else None,
        ).decode('utf-8')
    except InvalidTag as err:
        # 这个错误基本只有两种原因：APIv3 密钥填错了，或者密文被改过
        raise WeChatPayError('回调解密失败：APIv3 密钥不对，或内容被篡改') from err


def aes_gcm_encrypt(api_v3_key: str, nonce: str, plaintext: str,
                    associated_data: str = '') -> str:
    """加密（模拟网关构造回调时用；真实对接用不到）"""
    return base64.b64encode(
        AESGCM(api_v3_key.encode('utf-8')).encrypt(
            nonce.encode('utf-8'),
            plaintext.encode('utf-8'),
            associated_data.encode('utf-8') if associated_data else None,
        )
    ).decode()


# ---------------------------------------------------------------------------
# 客户端
# ---------------------------------------------------------------------------

class WeChatPayClient:
    """微信支付 V3 客户端

    只实现这个项目用得到的三个接口：JSAPI 下单、查单、退款。
    真实项目里这三个够覆盖 95% 的场景。

    参数从商户平台拿：
        mchid              商户号
        appid              下单的小程序 AppID（和商户号不是一回事）
        serial_no          商户 API 证书序列号
        private_key_pem    商户 API 私钥（apiclient_key.pem）
        api_v3_key         APIv3 密钥（解密回调用）
        platform_public_key  微信支付平台公钥/证书（验回调用）
    """

    def __init__(self, mchid, appid, serial_no, private_key_pem, api_v3_key,
                 platform_public_key='', base_url='https://api.mch.weixin.qq.com',
                 timeout=10):
        self.mchid = mchid
        self.appid = appid
        self.serial_no = serial_no
        self.private_key_pem = private_key_pem
        self.api_v3_key = api_v3_key
        self.platform_public_key = platform_public_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    # ---------- 请求签名 ----------

    def build_authorization(self, method, url_path, body=''):
        """构造 Authorization 头

        待签字符串的规定格式（顺序和换行都不能错，多一个空格微信就拒）：
            HTTP方法\\nURL路径\\n时间戳\\n随机串\\n请求体\\n
        注意最后那个 \\n —— 请求体为空时也要留。
        """
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex.upper()
        message = f'{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n'
        signature = rsa_sign(self.private_key_pem, message)
        return (
            f'{SIGN_TYPE} mchid="{self.mchid}",'
            f'nonce_str="{nonce}",'
            f'signature="{signature}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{self.serial_no}"'
        )

    def _request(self, method, url_path, payload=None):
        """发请求并验签响应

        **响应也要验签**：微信的响应是微信签的，验一下才能确定不是中间人伪造的。
        """
        import urllib.error
        import urllib.request

        body = json.dumps(payload, ensure_ascii=False) if payload is not None else ''
        req = urllib.request.Request(
            self.base_url + url_path,
            data=body.encode('utf-8') if payload is not None else None,
            method=method,
        )
        req.add_header('Authorization', self.build_authorization(method, url_path, body))
        req.add_header('Accept', 'application/json')
        req.add_header('User-Agent', 'restaurant-system/1.0')
        if payload is not None:
            req.add_header('Content-Type', 'application/json')

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode('utf-8')
                self._verify_response(resp.headers, raw)
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as err:
            detail = err.read().decode('utf-8', errors='replace')
            raise WeChatPayError(f'微信支付接口报错 HTTP {err.code}: {detail}') from err

    def _verify_response(self, headers, body):
        """验证微信响应的签名

        没配平台公钥时跳过（比如本地对着模拟网关跑、只关心业务字段时）。
        生产环境必须配上，否则这一层防护是空的。
        """
        if not self.platform_public_key:
            return
        timestamp = headers.get('Wechatpay-Timestamp', '')
        nonce = headers.get('Wechatpay-Nonce', '')
        signature = headers.get('Wechatpay-Signature', '')
        if not (timestamp and nonce and signature):
            raise WeChatPayError('微信响应缺少签名头')
        # 防重放：微信要求超过 5 分钟的应答直接拒
        if abs(int(time.time()) - int(timestamp)) > 300:
            raise WeChatPayError('微信响应的时间戳超过 5 分钟，可能是重放')
        if not rsa_verify(self.platform_public_key,
                          f'{timestamp}\n{nonce}\n{body}\n', signature):
            raise WeChatPayError('微信响应验签失败')

    # ---------- 三个接口 ----------

    def create_jsapi_order(self, out_trade_no, amount_fen, description, openid,
                           notify_url, attach=''):
        """JSAPI 下单：拿到 prepay_id，前端再拿它去调起收银台

        **金额单位是「分」**，不是元。这是微信的约定，也是最容易写错的地方——
        把元当分传过去，收的钱就是标价的百分之一。

        appid 是**下单的小程序**的 AppID，不是商户号。两个都要有：
        微信要确认「这个商户的这个应用」在收款。
        """
        return self._request('POST', '/v3/pay/transactions/jsapi', {
            'appid': self.appid,
            'mchid': self.mchid,
            'out_trade_no': out_trade_no,
            'description': description,
            'notify_url': notify_url,
            'attach': attach,
            'amount': {'total': int(amount_fen), 'currency': 'CNY'},
            'payer': {'openid': openid},
        })

    def query_order(self, out_trade_no):
        """查单：对账和补单全靠它

        注意这里的 url_path 带上了 `?mchid=...`——**签名要覆盖 query string**。
        这是微信的规矩，也是接支付时很容易踩的一个坑：漏了 query 部分，
        单号查得到、查单一调就报签名错误。
        """
        return self._request(
            'GET', f'/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={self.mchid}'
        )

    def create_refund(self, out_trade_no, out_refund_no, refund_fen, total_fen,
                      reason=''):
        """申请退款

        注意要同时传 refund 和 total：微信按「原订单总额」校验这次退的是不是超了，
        这是防超额退款的一道保障。
        """
        return self._request('POST', '/v3/refund/domestic/refunds', {
            'out_trade_no': out_trade_no,
            'out_refund_no': out_refund_no,
            'reason': reason,
            'amount': {'refund': int(refund_fen), 'total': int(total_fen), 'currency': 'CNY'},
        })

    # ---------- 回调 ----------

    def parse_callback(self, headers, body):
        """处理微信的异步回调：**先验签、再解密**，顺序不能反

        验签是为了确认「这条通知真的来自微信」，解密是为了读出内容。
        如果先解密再验签，等于把未经验证的数据交给了解密逻辑。

        返回解密后的业务数据（dict）。
        """
        timestamp = headers.get('Wechatpay-Timestamp', '')
        nonce = headers.get('Wechatpay-Nonce', '')
        signature = headers.get('Wechatpay-Signature', '')

        if not self.platform_public_key:
            raise WeChatPayError('没配微信平台公钥，无法验签回调——生产环境必须配')

        if abs(int(time.time()) - int(timestamp)) > 300:
            raise WeChatPayError('回调时间戳超过 5 分钟，可能是重放')

        if not rsa_verify(self.platform_public_key,
                          f'{timestamp}\n{nonce}\n{body}\n', signature):
            raise WeChatPayError('回调验签失败——这条通知不是微信发的')

        notification = json.loads(body)
        resource = notification.get('resource') or {}
        plaintext = aes_gcm_decrypt(
            self.api_v3_key,
            resource.get('nonce', ''),
            resource.get('ciphertext', ''),
            resource.get('associated_data', ''),
        )
        return json.loads(plaintext)
