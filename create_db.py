"""
首次建库脚本：读取 backend/.env 中的 DATABASE_URL，创建其中指定的数据库。

用法（在项目根目录执行）：
    python create_db.py

说明：
- 库名直接取自 .env 的 DATABASE_URL（不再是硬编码）
- 当前按 MySQL 语法建库（utf8mb4）；换其他数据库请自行调整
"""
import re
from urllib.parse import urlsplit

from sqlalchemy import create_engine, text

# 从 backend/.env 读出完整 DATABASE_URL
with open(r'backend\.env', encoding='utf-8') as f:
    env = f.read()
raw_url = re.search(r'DATABASE_URL=(\S+)', env).group(1).strip()

# 拆出服务器地址和库名
url = urlsplit(raw_url)
db_name = url.path.lstrip('/')
if not db_name or not re.fullmatch(r'[\w-]+', db_name):
    raise SystemExit(f'无法从 DATABASE_URL 解析出库名: {raw_url}')

server_url = url._replace(path='').geturl()

# 去掉库名部分，只连到数据库服务器本身
engine = create_engine(server_url)
with engine.connect() as conn:
    conn.execute(text(
        f'CREATE DATABASE IF NOT EXISTS `{db_name}` '
        'CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
    ))
    conn.commit()
print(f'数据库 {db_name} 已就绪')