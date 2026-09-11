# Makefile
# ============================================
# 定义常用命令的快捷方式
# ============================================

.PHONY: help dev prod test migrate upgrade shell

help:  ## 显示帮助
	@echo "可用命令："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev:  ## 启动开发服务器
	flask run --debug

prod:  ## 启动生产服务器
	gunicorn --bind 0.0.0.0:8000 wsgi:app

test:  ## 运行测试
	pytest -v

migrate:  ## 生成迁移脚本
	flask db migrate -m "$(message)"

upgrade:  ## 执行迁移
	flask db upgrade

shell:  ## 进入 Flask Shell
	flask shell

docker-up:  ## 启动 Docker 容器
	cd .. && docker compose up -d --build   # compose 文件在项目根目录

docker-down:  ## 停止 Docker 容器
	cd .. && docker compose down