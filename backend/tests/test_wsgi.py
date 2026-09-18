"""gunicorn 那条启动路径

只测一件事：**wsgi.py 必须自己把项目根加进 sys.path**。
"""
import os
import subprocess
import sys
import textwrap

# <项目根>/backend
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# <项目根>
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)


def test_wsgi_bootstraps_without_the_venv_helping():
    """把项目根从 sys.path 里挖掉之后，wsgi 还导得进来吗

    这是**本地怎么写都是对的、一上服务器就炸**的那一类：

    本地 `.venv` 是 virtualenv 建的，它会自动把项目根塞进 sys.path，
    于是 `from backend.app import create_app` 一直都能找到包——**靠的是 venv 的功劳**。
    容器里没有 virtualenv（依赖直接装进系统 Python），gunicorn 又只把「当前目录」
    加进 sys.path，而 `backend` 这个包在它的上一层，于是报
    `ModuleNotFoundError: No module named 'backend'`。

    实机表现：容器启动自检那三条命令（走 manage.py，它自己插了路径）全部 ✅，
    gunicorn 却报 "Worker failed to boot"，容器起来又挂、挂了又起。

    这个用例把那层 venv 保护手动拆掉，逼 wsgi.py 自己站住。
    真机上踩过一次，所以留个守门的。
    """
    code = textwrap.dedent(f'''
        import os, sys
        root = os.path.normcase({PROJECT_ROOT!r})
        sys.path[:] = [p for p in sys.path
                       if os.path.normcase(os.path.abspath(p or ".")) != root]
        import wsgi
        print("WSGI_OK", type(wsgi.app).__name__)
        ''')
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=BACKEND_DIR, capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert 'WSGI_OK' in result.stdout
