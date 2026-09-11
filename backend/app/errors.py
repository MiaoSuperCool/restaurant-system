# 这两个自定义的异常类的作用是定义业务异常，如果使用Python内置的ValueError的话那么没有HTTP语义
# 全局处理器无法区分"预期的业务失败"(该返回 400/404 给用户)和"意外 bug"(该走 500 + 记日志)
class BusinessError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class NotFoundError(BusinessError):
    def __init__(self, message='资源不存在'):
        super().__init__(message, status_code=404)
