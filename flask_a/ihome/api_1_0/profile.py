from flask import g, request, jsonify, current_app, session

from ihome import db, constants
from ihome.api_1_0 import api
from ihome.models import User
from ihome.utils.commons import login_required
from ihome.utils.image_storage import storage
from ihome.utils.response_code import RET


@api.route("/users/avatar",methods=["POST"])
@login_required
def set_user_avatar():
    """设置用户的头像
    获取参数：头像图片
    验证参数：
    上传头像到存储服务器：返回地址
    更新用户头像数据：
    """
    user_id = g.user_id

    #获取参数
    image_file = request.files.get("avatar")

    if image_file is None:
        return jsonify(errno=RET.PARAMERR,errmsg="未上传图片")


    image_data=image_file.read()

    #上传图片到七牛存储，返回文件名
    try:
        file_name = storage(image_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR,errmsg="上传图片失败")

    #保存文件名到用户头像字段
    try:
        User.query.filter_by(id=user_id).update({"avatar_url":file_name})
        db.session.commit()
    except Exception as e:
        db.session.rallback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR,errmsg="保存图片信息失败")

    #拼接图片url
    avatar_url = constants.QINIU_URL_DOMAIN + file_name
    #保存成功返回数据
    return jsonify(errno=RET.OK,errmasg="保存成功",data = {"avatar_url":avatar_url})

@api.route("/users/name",methods=["PUT"])
@login_required
def change_user_name():
    """修改用户名"""
    #获取用户id
    user_id = g.user.id


    #接收参数 user_id username
    req_data = request.get_json()
    if req_data is None:
        return jsonify(errno=RET.PARAMERR,errmsg="参数不完整")

    name = req_data.get("name")
    if not name:
        return jsonify(errno=RET.PARAMERR,errmsg="名字不能为空")

    #保存更新数据库
    try:
        User.query.filter_by(id=user_id).update({"name":name})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.PARAMERR,errmsg="数据库用户更新错误")

    #修改session中name字段
    session["name"] = name
    return jsonify(errno=RET.OK,errmsg="OK",data={"name":name})


@api.route("/user",methods=["GET"])
@login_required
def get_user_profile():
    """获取个人信息"""
    #g对象那拿取用户id
    user_id = g.user_id

    #查询当前用户数据
    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="获取用户信息失败")

    if user is None:
        return jsonify(errno=RET.OK, errmsg="无效操作")

    #返回数据
    return jsonify(errno=RET.OK,errmsg="OK",data={"data":user.to_dict()})

@api.route("user/auth",methods=["GET"])
@login_required
def get_user_auth():
    """获取用户实名认证信息"""
    # g对象那拿取用户id
    user_id = g.user_id


    # 查询当前用户数据
    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="获取用户信息失败")

    #验证用户
    if user is None:
        return jsonify(errno=RET.OK, errmsg="无效操作")

    # 返回数据
    return jsonify(errno=RET.OK, errmsg="OK", data={"data": user.auth_to_dict()})



@api.route("/users/auth",methods=["POST"])
@login_required
def set_user_auth():
    """保存用户的实名认证信息"""

    #g对象获取当前用户id
    user_id = g.user_id

    #接收参数
    req_data = request.get_json()
    real_name = req_data.get("real_name")
    id_card = req_data.get("is_card")

    #验证参数
    if not all([real_name,id_card]):
        return jsonify(errno=RET.PARAMERR,errmsg="参数不完整")

    #保存数据
    try:
        User.query.get(user_id,real_name=None,id_card=None).\
            update({"real_name":real_name,"is_card":id_card})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg="实名认证保存失败")

    #返回响应
    return jsonify(errno=RET.OK,errmsg="OK")
