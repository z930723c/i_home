import functools

from flask import session, jsonify, g
from werkzeug.routing import BaseConverter


# 定义正则转换器
from ihome.utils.response_code import RET


class ReConverter(BaseConverter):
    """"""
    def __init__(self, url_map, regex):
        # 调用父类的初始化方法
        super(ReConverter, self).__init__(url_map)
        # 保存正则表达式
        self.regex = regex

# 定义验证登录状态校验的装饰器
def login_required(view_func):
    # wraps函数的作用是将wrapper内层函数的属性设置为被装饰函数view_func的属性
    @functools.wraps(view_func)
    def wrpper(*args,**kwargs):
        #判断用户登陆状态
        user_id=session.get("user_id")

        if user_id is None:
            # 未登录，返回未登录信息
            return jsonify(errno=RET.DATAERR,eeeor="用户未登录")

        # 将user_id保存到g对象中，在视图函数中可以通过g对象获取保存数据
        g.user_id = user_id

        #已登录，执行函数
        return view_func(*args,**kwargs)
    return wrpper

