import re
from flask import request, jsonify, current_app, session


from ihome import redis_store, db, constants
from ihome.api_1_0 import api
from ihome.models import User
from ihome.utils.response_code import RET


@api.route("/users",methods=["POST"])
def register():
    """注册
    接收参数：
    校验参数： 手机号 短信验证码 密码 确认密码
    删除验证码：
    保存用户：到i_user数据表
    """
    #获取请求的json数据
    req_dict = request.get_json()

    mobile = req_dict.get("mobile")
    sms_code = req_dict.get('sms_code')
    password = req_dict.get("password")
    password2  = req_dict.get("password2")

    #校验参数
    if not all([mobile,sms_code,password,password2]):
        return jsonify(errno=RET.PARAMERR,errmsg="参数不完整")

    if not re.match(r"1[34578]\d{9}",mobile):
        return jsonify(errno=RET.PARAMERR,errmsg="手机号格式正确")

    if password != password2:
        return jsonify(errno=RET.PARAMERR,errmasg="两次密码输入不一致")

    #从redis中取出短信验证码
    try:
        real_sms_code = redis_store.get("sms_code_%s"%mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg="读取验证码失败")

    #判断短信验证码是否过期
    if real_sms_code is None:
        return jsonify(errno=RET.NODATA,errmsg="短信验证码")

    #删除短信验证码，防止重复使用校验
    try:
        redis_store.delete("sme_code_%s"%mobile)
    except Exception as e:
        current_app.logger.error(e)

    #校验短信验证码
    if real_sms_code != sms_code:
        return jsonify(errno=RET.DATAERR,errmsg="短信验证码不正确")

    #保存用户
    user = User(name=mobile,mobile=mobile)
    user.password = password

    try:
        db.session.add(user)
        db.session.commit()
    except InterruptedError as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAEXIST,errmsg="手机号已存在")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(error=RET.DBERR,errmsg="数据库操作异常")

    #保存登陆状态到session中
    session["name"] = user.name
    session["mobile"] = user.mobile
    session["user_id"] = user.id

    #返回结果
    return jsonify(erron=RET.OK,errmasg="注册成功")


@api.route("/session",methods=["GET"])
def login():
    """用户登陆
    参数接收：
    参数验证：
    发放session：
    """
    #接收参数
    req_dict = request.get_json()
    mobile = req_dict.get("mobile")
    password = req_dict.get("password")

    #校验参数
    #参数完整的验证
    if not all([mobile,password]):
        return jsonify(errno=RET.PARAMER,errmsg="参数不完整")

    #手机号的格式
    if not re.match(r"1[34578]\d{9}",mobile):
        return jsonify(errno=RET.PARAMERR,errmsg="手机号格式错误")

    #判断错误次数是否超过限制
    #使用字符串格式，access_num_请求ip："次数"
    user_ip = request.remote_addr
    try:
        access_nums = redis_store.get("access_num_%s"%user_ip)
    except Exception as e:
        current_app.logger.error(e)
    else:
        if access_nums is not None and int(access_nums) > constants.LOGIN_ERROR_MAX_TIMES:
            return jsonify(errno=RET.REQERR,errmsg="错误次数过多，请稍后重试")

    #从数据库查询此手机号的用户
    try:
        user = User.query.filter_by(mobile=mobile).first
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR,error="获取用户信息失败")

    #校验密码
    if user is None or user.check_password(password):
        try:
            #
            redis_store.incr("access_num_%s"%user_ip)
            redis_store.expire("access_num_%s"%user_ip,constants.LOGIN_ERROR_FORBID_TIME)
        except Exception as e:
            current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR,errmsg="用户名或密码错误")

    #验证成功，发放session
    session["name"] = user.name
    session["mobile"] = user.mobile
    session["user_id"] = user.id

    return jsonify(errno=RET.OK,errmsg="登录成功")


@api.route("/session",methods=["GET"])
def check_login():
    """检查登录状态"""
    #尝试从cession中获取用户的名字
    name = session.get("name")
    if name is None:
        return jsonify(errno=RET.SESSIONERR, errmsg="false")
    return jsonify(errno=RET.OK, errmsg="true", data={"name": name})

@api.route("/session",methods=["DELETE"])
def logout():
    session.clear()










