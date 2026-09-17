import logging

from flask import has_request_context
from flask_login import current_user

from backend.app.errors import NotFoundError
from backend.app.extensions import db
from backend.app.models import AuditLog

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def get_all_logs():
        return AuditLog.query.all()

    @staticmethod
    def get_log_by_id(log_id):
        log = db.session.get(AuditLog, log_id)
        if not log:
            raise NotFoundError('日志不存在')
        return log

    @staticmethod
    def get_paginated_logs(page, per_page, search):
        query = AuditLog.query

        if search:
            query = query.filter(
                db.or_(
                    # operator_id 是整数，需要用 cast 转换后才能用 ilike
                    db.cast(AuditLog.operator_id, db.String).ilike(f'%{search}%'),
                    AuditLog.operator_name.ilike(f'%{search}%'),
                    AuditLog.action.ilike(f'%{search}%'),
                    AuditLog.status.ilike(f'%{search}%'),
                )
            )

        return (query
                .order_by(AuditLog.created_at.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def current_operator(default_name='系统'):
        """当前操作人 `(id, 名字)`；**没有请求上下文时**退回 `(None, default_name)`

        定时任务、迁移命令这些**不是人在页面上点**的动作也要记审计，
        可那时候 `current_user` 取出来是 None。与其让每个调用点自己判断，
        不如在这儿一次判掉。

        判断必须用 `has_request_context()`：`current_user` 是个 LocalProxy，
        `current_user is None` **恒为假**（比的是代理对象本身，不是它取出来的值），
        写错了要等到 `current_user.id` 那一下才炸。
        """
        if not has_request_context():
            return None, default_name
        return current_user.id, current_user.real_name or current_user.username

    @staticmethod
    def log(operator_id=None, operator_name='', action='', resource=None,
            old_value=None, new_value=None, status='success'):
        # 审计日志失败不应该影响其他逻辑，所以在 log 方法里一并使用
        # try/except 处理，以免其他调用的地方还要处理
        try:
            log = AuditLog(
                operator_id=operator_id,
                operator_name=operator_name,
                action=action,
                resource=resource,
                old_value=old_value,
                new_value=new_value,
                status=status
            )

            db.session.add(log)
            db.session.commit()
            return log
        except Exception as e:
            db.session.rollback()
            logger.error(f'审计日志写入失败 action={action}: {e}')
            return None
