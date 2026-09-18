import os
import sys

# 把项目根目录放进 sys.path，让下面那句 `from backend.app import ...` 找得到 backend 包。
#
# **这一段不能省，它是「本地一切正常、一上服务器 gunicorn 就起不来」的原因。**
#
# 三种跑法解决 import 的机制不一样：
#
#   flask run        Flask 自己会从 wsgi.py 往上找，发现 backend/ 是个包，把项目根插进去
#   manage.py        里面手动插了（那段注释讲的是同一件事）
#   gunicorn         **谁都没插**。它不是 Flask，只把「当前目录」放进 sys.path，
#                    而当前目录是 backend/，backend 这个包在它的上一层 → ImportError
#
# 还有一个更隐蔽的地方：本地 .venv 是 virtualenv 建的，**virtualenv 会自动把项目根
# 加进 sys.path**（`python -c "import sys; print(sys.path)"` 最后能看到一条项目根路径）。
# 所以本地一直是对的——**靠的是 venv 的功劳，不是代码写对了**。
# 容器里没有 virtualenv（依赖直接装进系统 Python），那层保护就没了。
#
# 实机表现：容器启动自检那三条命令（走 manage.py）全部 ✅，
# gunicorn 却报 "Worker failed to boot"，容器起来又挂、挂了又起。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app  # noqa: E402

app = create_app()

if __name__ == '__main__':
    app.run()
