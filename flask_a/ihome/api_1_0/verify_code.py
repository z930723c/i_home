from random import random

from flask import current_app, jsonify, make_response, request
from ihome import redis_store, constants
from ihome.api_1_0 import api
from ihome.models import User
from ihome.utils.response_code import RET


@api.route("/image_codes/<image_code_id>")
def get_image_code(image_code_id):
    """获取图片验证码"""
    #http://127.0.0.1:5000/api/v1.0/image_codes/222
    image_data = open('ihome/static/images/home01.jpg')
    name,text,image_data = image_code_id,6379,image_data.encoding

    try:
        redis_store.setex("image_code_%s"%image_code_id,constants.IMAGE_CODE_REDIS_EXPIRES,text)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.DBERR,errmsg="保存图片验证码失败")

    resp = make_response(image_data)
    resp.headers["Content-Type"] = "image/jpg"
    return resp

@api.route("/sms_codes/re(r'1[34578]\d{9}'):mobile")
def get_sms_code(mobile):
    """获取短信验证码"""
    #http://127.0.0.1:5000/api/v1.0/sms_codes/19929978964
    #获取图片验证码
    image_code = request.args.get("image_code")
    #获取图片验证码id
    image_code_id = request.args.get('image_code_id')

    #校验参数
    if not all([image_code,image_code_id]):
        return jsonify(errno=RET.PARAMERR,errmsg="参数不完整")

    # 从redis中取出真实的图片验证码
    try:
        real_image_code = redis_store.get("image_code_%s" % image_code_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="redis数据库异常")

    # 判断图片验证码是否过期
    if real_image_code is None:
        # 表示图片验证码没有或者过期
        return jsonify(errno=RET.NODATA, errmsg="图片验证码失效")

    #删除验证码
    try:
        redis_store.delete("image_code_%s"%image_code_id)
    except:
        current_app.logger.error(e)

    #与用户填写值进行比较
    if real_image_code.lower() != image_code.lower():
        return jsonify(errno=RET.DATAERR,errmsg="图片验证码错误")

    #判断手机号在60秒之内有没有操作记录
    try:
        send_flag = redis_store.get("send_sms_code_%s"%mobile)
    except Exception as e:
        current_app.logger.error(e)
    else:
        # 表示在60秒内之前有过发送的记录
        if send_flag is not None:
            return jsonify(erron=RET.REQERR,errmsg="请求归于频繁")

    #判断手机号是否存在
    try:
        user = User.query.filter_by(mobile=mobile).first
    except Exception as e:
        current_app.logger.error(e)
    else:
        if user is not None:
            # 表示手机号已存在
            return jsonify(errno=RET.DATAEXIST,errmsg="手机号已注册")

    #如果手机号不存在，则生成短信验证码
    sms_code = "%06d" % random.randint(0,99999)

    try:
        #保存验证码
        redis_store.setex("sms_code_%s"%mobile,constants.SMS_CODE_REDIS_EXPIRES,sms_code)
        redis_store.setex("send_sms_code%s"%mobile,constants.SEND_SMS_CODE_INTERVAL,1)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,error="保存短信验证码异常")

    from ihome.tasks.task_sms import send_sms
    result_obj = send_sms.delay(mobile,[sms_code,int(constants.SMS_CODE_REDIS_EXPIRES/60)],1)
    print(result_obj.id)

    return jsonify(errno=RET.OK,errmsg="发送成功")





