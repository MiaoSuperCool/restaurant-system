"""外键引用检查：删除前的「还有没有别的表在引用我」

手写「要检查哪些表」的清单迟早会漏。这里反过来，扫 SQLAlchemy metadata 里
所有指向目标表主键的外键——新表只要建了指向它的外键，就自动被覆盖。

**CASCADE 的外键会被跳过**：外键声明 ondelete='CASCADE' 表示「从属/关联」
（规格选项属于菜品、角色绑定属于员工），父记录删了子记录跟着走，不算阻塞。
只有 RESTRICT / SET NULL 这类才是真正的「外部依赖还在用」。
"""
from sqlalchemy import func

from backend.app.extensions import db

# 引用表的友好名（拼进报错文案给用户看）。
# 没登记的表的退回用表名——所以加新表不会漏检，只是文案暂时没那么好读。
TABLE_LABELS = {
    'staff': '员工',
    'store_dish': '门店菜品',
    'category_store': '分类适用范围',
    'category': '菜品分类',
    'dish': '菜品',
    'dish_option_group': '规格组',
    'dish_option': '规格选项',
    'order': '订单',
    'order_item': '订单明细',
    'store_inventory': '库存',
}


def find_referencing_rows(model, pk_value):
    """统计所有指向该行主键的外键引用，返回 {引用对象: 行数}

    返回空 dict 表示没有任何业务数据引用它，可以安全物理删除。
    """
    table_name = model.__tablename__
    references = {}

    for table in db.metadata.tables.values():
        columns = [
            fk.parent for fk in table.foreign_keys
            if fk.column.table.name == table_name and fk.column.name == 'id'
            # CASCADE = 从属/关联关系，跟着父记录一起删，不算阻塞引用
            and (fk.ondelete or '').upper() != 'CASCADE'
        ]
        if not columns:
            continue

        count = (db.session.query(func.count())
                 .select_from(table)
                 .filter(db.or_(*[column == pk_value for column in columns]))
                 .scalar())
        if count:
            label = TABLE_LABELS.get(table.name, table.name)
            references[label] = references.get(label, 0) + count

    return references


def describe_references(references):
    """{'员工': 3, '门店菜品': 12} → '员工 3 条、门店菜品 12 条'"""
    return '、'.join(f'{name} {count} 条' for name, count in references.items())
