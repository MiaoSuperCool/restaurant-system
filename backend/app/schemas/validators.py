"""schema 层共用的校验器"""
from marshmallow import validate


def one_of(labels: dict):
    """把模型上的 {值: 中文名} 枚举常量转成 OneOf 校验器

    合法取值锁在模型那一份定义上，schema 和各处代码不各写各的字符串。
    """
    return validate.OneOf(list(labels.keys()), error='{input} 不是合法的取值')
