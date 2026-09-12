"""微信支付的模拟网关

**这不是生产代码**，是给 wechat_pay.py 做对手方的：本项目没有商户号，
但协议这一层（签名、验签、加解密）是对是错，必须有个东西能真的验一遍。

它按微信支付 V3 的规矩办事：

- 校验商户请求的签名（用商户的公钥，模拟微信那边的做法）
- 用它**自己的私钥**给响应签名——这样客户端的验签逻辑也能真的跑到，
  而不是被跳过
- 能构造加密的回调通知（AEAD_AES_256_GCM）

跑起来当个本地假微信：
    python -m backend.app.services.wechat_pay_mock           # 默认 :9090
"""
import json
import time
import uuid

from flask import Flask, jsonify, request

from backend.app.services.wechat_pay import (
    aes_gcm_encrypt,
    rsa_sign,
    rsa_verify,
)

# 模拟网关写死的密钥（真实环境当然是微信的，这里方便本地跑）
DEFAULT_API_V3_KEY = 'mock_apiv3_key_32_bytes_padding!'
# AES-256 要求密钥正好 32 字节。写成别的长度不会在导入时报错，
# 而是等到解密时才炸——加这一行让它当场暴露
assert len(DEFAULT_API_V3_KEY.encode('utf-8')) == 32, 'APIv3 密钥必须是 32 字节'


def generate_keypair():
    """现造一对 RSA 密钥——模拟网关的「平台私钥」和商户的「商户私钥」都用它生成"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def create_mock_gateway(mchid='1900000001', merchant_public_key='',
                        platform_private_key='', api_v3_key=DEFAULT_API_V3_KEY):
    """构造模拟网关的 Flask 应用

    参数：
        merchant_public_key   商户的公钥——网关用它验证商户请求的签名
        platform_private_key  网关自己的私钥——用它给响应和回调签名
        api_v3_key            对称密钥——加密回调用
    """
    app = Flask(__name__)
    # 收到的请求记在这里，测试里可以断言「网关到底收到了什么」
    app.config['RECEIVED'] = []
    # 下单成功后，这些单号能查到「已支付」
    app.config['PAID_ORDERS'] = {}

    def _verify_merchant_request(body):
        """模拟微信那边做的事：验商户的签名

        真实环境微信验不过会返回 401 并带上原因码；这里简化成返回一个错误串。
        """
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('WECHATPAY2-SHA256-RSA2048'):
            return '缺少或格式不对的 Authorization 头'
        if not merchant_public_key:
            return None    # 没配商户公钥就不验（本地图省事）

        parts = dict(
            item.split('=', 1) for item in auth.split(' ', 1)[1].split(',')
        )
        timestamp = parts.get('timestamp', '').strip('"')
        nonce = parts.get('nonce_str', '').strip('"')
        signature = parts.get('signature', '').strip('"')

        if abs(int(time.time()) - int(timestamp)) > 300:
            return '请求时间戳超过 5 分钟'
        # **要用 full_path（含 query string），不能用 path。**
        # 微信规定待签字符串里的 URL 是「路径 + query」——
        # 查单接口长这样：/v3/pay/transactions/out-trade-no/xxx?mchid=123，
        # 少了 ?mchid=... 这一段，签名就对不上。
        # full_path 在没有 query 时会带个尾部的 '?'，要去掉。
        full_path = request.full_path.rstrip('?')
        message = f'{request.method}\n{full_path}\n{timestamp}\n{nonce}\n{body}\n'
        if not rsa_verify(merchant_public_key, message, signature):
            return '签名验证失败'
        return None

    def _signed_response(payload, status=200):
        """用网关自己的私钥给响应签名——客户端那边会验

        **返回体必须就是签名时那个字符串。** 一开始这里用的是 flask.jsonify，
        它自己会重新序列化一遍（空格、键序都可能不一样），结果签的和发的
        字节对不上，客户端验签必失败。

        真实对接踩的也是同一个坑：签名覆盖的必须是实际发出去的那串字节，
        不是「内容相同的另一串」。
        """
        body = json.dumps(payload, ensure_ascii=False)
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex.upper()

        resp = app.response_class(body, status=status, mimetype='application/json')
        if platform_private_key:
            resp.headers['Wechatpay-Timestamp'] = timestamp
            resp.headers['Wechatpay-Nonce'] = nonce
            resp.headers['Wechatpay-Signature'] = rsa_sign(
                platform_private_key, f'{timestamp}\n{nonce}\n{body}\n'
            )
            resp.headers['Wechatpay-Serial'] = 'MOCK_PLATFORM_CERT_001'
        return resp

    @app.post('/v3/pay/transactions/jsapi')
    def create_order():
        raw = request.get_data(as_text=True)
        error = _verify_merchant_request(raw)
        app.config['RECEIVED'].append({'path': request.path, 'body': raw, 'error': error})
        if error:
            return _signed_response({'code': 'SIGN_ERROR', 'message': error}, 401)

        data = json.loads(raw)
        prepay_id = f'mock_prepay_{uuid.uuid4().hex[:24]}'
        app.config['PAID_ORDERS'][data['out_trade_no']] = {
            'prepay_id': prepay_id,
            'amount': data['amount']['total'],
        }
        return _signed_response({'prepay_id': prepay_id})

    @app.get('/v3/pay/transactions/out-trade-no/<out_trade_no>')
    def query_order(out_trade_no):
        raw = request.get_data(as_text=True)
        error = _verify_merchant_request(raw)
        if error:
            return _signed_response({'code': 'SIGN_ERROR', 'message': error}, 401)

        record = app.config['PAID_ORDERS'].get(out_trade_no)
        if not record:
            return _signed_response(
                {'code': 'ORDER_NOT_EXIST', 'message': '订单不存在'}, 404
            )
        return _signed_response({
            'out_trade_no': out_trade_no,
            'transaction_id': f'mock_txn_{out_trade_no}',
            'trade_state': 'SUCCESS',
            'amount': {'total': record['amount'], 'currency': 'CNY'},
        })

    @app.post('/v3/refund/domestic/refunds')
    def create_refund():
        raw = request.get_data(as_text=True)
        error = _verify_merchant_request(raw)
        app.config['RECEIVED'].append({'path': request.path, 'body': raw, 'error': error})
        if error:
            return _signed_response({'code': 'SIGN_ERROR', 'message': error}, 401)

        data = json.loads(raw)
        # 微信会校验「退款金额不能超过原订单金额」——模拟网关也照做，
        # 这样客户端万一传错单位（元当成分）能当场发现
        record = app.config['PAID_ORDERS'].get(data['out_trade_no'])
        if not record:
            return _signed_response(
                {'code': 'ORDER_NOT_EXIST', 'message': '原订单不存在'}, 404
            )
        if data['amount']['refund'] > record['amount']:
            return _signed_response(
                {'code': 'PARAM_ERROR', 'message': '退款金额超过原订单金额'}, 400
            )

        return _signed_response({
            'out_refund_no': data['out_refund_no'],
            'out_trade_no': data['out_trade_no'],
            'refund_id': f'mock_refund_{uuid.uuid4().hex[:20]}',
            'status': 'PROCESSING',
            'amount': data['amount'],
        })

    @app.post('/mock/send-callback')
    def send_callback():
        """测试用：构造一条**加密的**支付成功通知，就像微信真的推过来那样

        返回「加密后的 resource + 该带的签名头」，调用方拿去调
        WeChatPayClient.parse_callback 就能走完验签 + 解密整条链路。
        """
        data = request.get_json() or {}
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex.upper()
        resource_nonce = uuid.uuid4().hex[:12]

        plaintext = json.dumps({
            'out_trade_no': data.get('out_trade_no', ''),
            'transaction_id': f'mock_txn_{data.get("out_trade_no", "")}',
            'trade_state': 'SUCCESS',
            'amount': {'total': data.get('amount', 0)},
        }, ensure_ascii=False)

        body = json.dumps({
            'id': uuid.uuid4().hex,
            'event_type': 'TRANSACTION.SUCCESS',
            'resource_type': 'encrypt-resource',
            'resource': {
                'algorithm': 'AEAD_AES_256_GCM',
                'ciphertext': aes_gcm_encrypt(
                    api_v3_key, resource_nonce, plaintext, 'transaction'
                ),
                'nonce': resource_nonce,
                'associated_data': 'transaction',
            },
        }, ensure_ascii=False)

        headers = {'Wechatpay-Timestamp': timestamp, 'Wechatpay-Nonce': nonce}
        if platform_private_key:
            headers['Wechatpay-Signature'] = rsa_sign(
                platform_private_key, f'{timestamp}\n{nonce}\n{body}\n'
            )
        return jsonify({'body': body, 'headers': headers})

    return app


if __name__ == '__main__':   # pragma: no cover
    _private, _public = generate_keypair()
    create_mock_gateway(merchant_public_key=_public,
                        platform_private_key=_private).run(port=9090, debug=False)
