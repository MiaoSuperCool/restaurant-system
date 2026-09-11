import logging

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
    def log(operator_id=None, operator_name='', action='',
            old_value=None, new_value=None, status='success'):
        # 审计日志失败不应该影响其他逻辑，所以在 log 方法里一并使用
        # try/except 处理，以免其他调用的地方还要处理
        try:
            log = AuditLog(
                operator_id=operator_id,
                operator_name=operator_name,
                action=action,
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
