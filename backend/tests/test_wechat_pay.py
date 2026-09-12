"""微信支付协议测试

本项目没有商户号，所以对不了真实的微信。但**协议这一层必须能验**——
签名对不对、篡改能不能发现、回调解密失败会不会漏过去，
这些是「接支付」这件事里最容易写错、也最不能写错的地方。

做法是自建一个模拟网关（app/services/wechat_pay_mock.py），
它按微信的规矩办事：验商户签名、用自己的私钥签响应、构造加密回调。
客户端对着它跑一遍，等于把真实链路走完了，只差一个商户号。
"""
import json
import threading

import pytest
from werkzeug.serving import make_server

from backend.app.services.wechat_pay import (
    WeChatPayClient,
    WeChatPayError,
    aes_gcm_decrypt,
    aes_gcm_encrypt,
    rsa_sign,
    rsa_verify,
)
from backend.app.services.wechat_pay_mock import (
    DEFAULT_API_V3_KEY,
    create_mock_gateway,
    generate_keypair,
)

# ---------------------------------------------------------------------------
# 密码学原语
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def keypair():
    return generate_keypair()


def test_sign_and_verify_roundtrip(keypair):
    """签名和验签是一对——自己签的自己能验过"""
    private_pem, public_pem = keypair
    message = 'POST\n/v3/pay/transactions/jsapi\n1700000000\nNONCE\n{"a":1}\n'

    signature = rsa_sign(private_pem, message)
    assert rsa_verify(public_pem, message, signature) is True


def test_tampered_message_fails_verification(keypair):
    """内容被改一个字，验签就该失败——这正是签名存在的意义"""
    private_pem, public_pem = keypair
    message = 'POST\n/v3/pay/transactions/jsapi\n1700000000\nNONCE\n{"a":1}\n'
    signature = rsa_sign(private_pem, message)

    # 改金额
    tampered = message.replace('{"a":1}', '{"a":999999}')
    assert rsa_verify(public_pem, tampered, signature) is False

    # 改路径
    assert rsa_verify(public_pem, message.replace('/v3/pay', '/v3/refund'),
                      signature) is False


def test_verify_with_wrong_key_fails(keypair):
    """换个公钥就验不过——伪造者拿不到商户私钥，也就签不出能过验的串"""
    private_pem, _public_pem = keypair
    _other_private, other_public = generate_keypair()
    message = 'hello'
    assert rsa_verify(other_public, message, rsa_sign(private_pem, message)) is False


def test_aes_gcm_roundtrip():
    """回调解密的加解密是一对"""
    plaintext = json.dumps({'out_trade_no': 'S001-20260912-0001', 'amount': 3200})
    ciphertext = aes_gcm_encrypt(DEFAULT_API_V3_KEY, 'abcdef123456', plaintext, 'transaction')
    assert aes_gcm_decrypt(DEFAULT_API_V3_KEY, 'abcdef123456', ciphertext,
                           'transaction') == plaintext


def test_aes_gcm_wrong_key_raises():
    """APIv3 密钥填错要明确报错，不能返回一堆乱码当数据用"""
    ciphertext = aes_gcm_encrypt(DEFAULT_API_V3_KEY, 'abcdef123456', 'secret', 'transaction')
    with pytest.raises(WeChatPayError, match='APIv3 密钥'):
        aes_gcm_decrypt('wrong_key_32_bytes_xxxxxxxxxxxx', 'abcdef123456',
                        ciphertext, 'transaction')


def test_aes_gcm_tampered_ciphertext_raises():
    """密文被改过——AEAD 模式会在解密时报错，不会静默返回错误内容"""
    ciphertext = aes_gcm_encrypt(DEFAULT_API_V3_KEY, 'abcdef123456', 'secret', 'transaction')
    tampered = ciphertext[:-4] + ('AAAA' if not ciphertext.endswith('AAAA') else 'BBBB')
    with pytest.raises(WeChatPayError):
        aes_gcm_decrypt(DEFAULT_API_V3_KEY, 'abcdef123456', tampered, 'transaction')


# ---------------------------------------------------------------------------
# 对着模拟网关跑完整流程
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def gateway():
    """起一个模拟网关（后台线程），返回客户端和断言用的东西"""
    merchant_private, merchant_public = generate_keypair()
    platform_private, platform_public = generate_keypair()

    app = create_mock_gateway(
        merchant_public_key=merchant_public,
        platform_private_key=platform_private,
    )
    server = make_server('127.0.0.1', 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    client = WeChatPayClient(
        mchid='1900000001',
        appid='wxmockappid0001',
        serial_no='MOCK_SERIAL_001',
        private_key_pem=merchant_private,
        api_v3_key=DEFAULT_API_V3_KEY,
        platform_public_key=platform_public,   # 客户端要验网关的响应签名
        base_url=f'http://127.0.0.1:{server.server_port}',
    )
    yield {'client': client, 'app': app,
           'platform_public': platform_public, 'platform_private': platform_private,
           'merchant_private': merchant_private}
    server.shutdown()


def test_jsapi_order_through_gateway(gateway):
    """JSAPI 下单：请求签名能被网关验过，响应签名能被客户端验过"""
    resp = gateway['client'].create_jsapi_order(
        out_trade_no='S001-20260912-0001',
        amount_fen=3200,          # 注意是「分」
        description='餐饮订单',
        openid='mock_openid_001',
        notify_url='https://example.com/notify',
    )
    assert resp['prepay_id'].startswith('mock_prepay_')

    # 网关确实收到了、而且签名验证是通过的
    received = gateway['app'].config['RECEIVED'][-1]
    assert received['error'] is None
    assert '"total": 3200' in received['body']


def test_query_order_through_gateway(gateway):
    resp = gateway['client'].create_jsapi_order(
        out_trade_no='S001-20260912-0002', amount_fen=100,
        description='测试', openid='o1', notify_url='https://example.com/n',
    )
    assert resp['prepay_id']

    result = gateway['client'].query_order('S001-20260912-0002')
    assert result['trade_state'] == 'SUCCESS'
    assert result['amount']['total'] == 100


def test_refund_through_gateway(gateway):
    """退款：网关会按微信的规矩校验「退款额不超过原订单额」"""
    gateway['client'].create_jsapi_order(
        out_trade_no='S001-20260912-0003', amount_fen=5000,
        description='测试', openid='o1', notify_url='https://example.com/n',
    )

    ok = gateway['client'].create_refund(
        out_trade_no='S001-20260912-0003', out_refund_no='RF-001',
        refund_fen=2000, total_fen=5000, reason='顾客投诉',
    )
    assert ok['status'] == 'PROCESSING'
    assert ok['amount']['refund'] == 2000

    # 退超过原单金额 → 拒（这条是防「把元当成分」那类单位错误的第一道闸）
    with pytest.raises(WeChatPayError, match='超过原订单金额'):
        gateway['client'].create_refund(
            out_trade_no='S001-20260912-0003', out_refund_no='RF-002',
            refund_fen=999999, total_fen=5000,
        )


def test_callback_verify_and_decrypt(gateway):
    """完整的回调处理：验签 → 解密 → 拿到业务数据"""
    import urllib.request

    gateway['client'].create_jsapi_order(
        out_trade_no='S001-20260912-0004', amount_fen=8800,
        description='测试', openid='o1', notify_url='https://example.com/n',
    )

    # 让模拟网关构造一条加密通知（就像微信真的推过来那样）
    base = gateway['client'].base_url
    req = urllib.request.Request(
        f'{base}/mock/send-callback',
        data=json.dumps({'out_trade_no': 'S001-20260912-0004', 'amount': 8800}).encode(),
        method='POST', headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        payload = json.loads(resp.read().decode())

    # 走真实客户端：先验签、再解密
    data = gateway['client'].parse_callback(payload['headers'], payload['body'])
    assert data['out_trade_no'] == 'S001-20260912-0004'
    assert data['trade_state'] == 'SUCCESS'
    assert data['amount']['total'] == 8800


def test_forged_callback_is_rejected(gateway):
    """**伪造的回调必须被拒**——这是支付对接里最不能漏的一步

    回调地址是公开的，谁都能往上打。不验签的话，伪造一条「支付成功」
    就能白吃一顿饭。这里模拟攻击者：拿自己的私钥签一条内容对得上的通知。
    """
    forged_private, _forged_public = generate_keypair()
    import time

    timestamp = str(int(time.time()))
    nonce = 'FORGED_NONCE'
    body = json.dumps({
        'event_type': 'TRANSACTION.SUCCESS',
        'resource': {
            'algorithm': 'AEAD_AES_256_GCM',
            'ciphertext': aes_gcm_encrypt(DEFAULT_API_V3_KEY, 'nonce12345678',
                                           '{"out_trade_no":"FAKE","trade_state":"SUCCESS"}',
                                           'transaction'),
            'nonce': 'nonce12345678',
            'associated_data': 'transaction',
        },
    }, ensure_ascii=False)
    # 攻击者用自己的私钥签——内容完全对得上，但签名不是微信的
    forged_signature = rsa_sign(forged_private, f'{timestamp}\n{nonce}\n{body}\n')

    with pytest.raises(WeChatPayError, match='验签失败'):
        gateway['client'].parse_callback(
            {'Wechatpay-Timestamp': timestamp, 'Wechatpay-Nonce': nonce,
             'Wechatpay-Signature': forged_signature},
            body,
        )


def test_callback_without_platform_key_is_refused(gateway):
    """没配平台公钥时必须拒绝，而不是「跳过验签继续处理」"""
    no_key_client = WeChatPayClient(
        mchid='1900000001', appid='wxmockappid0001', serial_no='S',
        private_key_pem=gateway['merchant_private'],
        api_v3_key=DEFAULT_API_V3_KEY,
        platform_public_key='',        # 故意不配
        base_url=gateway['client'].base_url,
    )
    with pytest.raises(WeChatPayError, match='无法验签'):
        no_key_client.parse_callback(
            {'Wechatpay-Timestamp': '1', 'Wechatpay-Nonce': 'n',
             'Wechatpay-Signature': 'sig'},
            '{}',
        )


def test_stale_callback_is_rejected(gateway):
    """超过 5 分钟的回调拒掉——防重放：把昨天那条成功通知再发一次"""
    import time

    old_timestamp = str(int(time.time()) - 3600)
    nonce = 'OLD_NONCE'
    body = '{"event_type":"TRANSACTION.SUCCESS","resource":{}}'
    # 用网关的私钥正经签一条——内容、签名都对，只有时间戳是旧的
    signature = rsa_sign(gateway['platform_private'], f'{old_timestamp}\n{nonce}\n{body}\n')

    with pytest.raises(WeChatPayError, match='重放'):
        gateway['client'].parse_callback(
            {'Wechatpay-Timestamp': old_timestamp, 'Wechatpay-Nonce': nonce,
             'Wechatpay-Signature': signature},
            body,
        )


def test_authorization_header_format(gateway):
    """Authorization 头的格式微信卡得很死，五个字段一个都不能少"""
    auth = gateway['client'].build_authorization('POST', '/v3/pay/transactions/jsapi', '{}')
    assert auth.startswith('WECHATPAY2-SHA256-RSA2048 ')
    for field in ('mchid=', 'nonce_str=', 'signature=', 'timestamp=', 'serial_no='):
        assert field in auth
