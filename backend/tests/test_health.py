"""健康检查、API 404、未登录 401 的基础契约测试"""


def test_health(client):
    resp = client.get('/health')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['data']['status'] == 'ok'


def test_unknown_api_path_returns_json_404(client):
    """/api 下不存在的路径返回 JSON 404，而不是前端 index.html"""
    resp = client.get('/api/not-exist')
    assert resp.status_code == 404
    body = resp.get_json()
    assert body['success'] is False


def test_protected_api_returns_401_json(client):
    """未登录访问受保护接口返回 401 JSON（而不是 302 跳转 HTML）"""
    resp = client.get('/api/staff')
    assert resp.status_code == 401
    body = resp.get_json()
    assert body['success'] is False
    assert '登录' in body['message']


def test_protected_api_with_ajax_header(client):
    """带 X-Requested-With 头（前端行为）结果一致"""
    resp = client.get('/api/audit', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert resp.status_code == 401
    assert resp.get_json()['success'] is False
