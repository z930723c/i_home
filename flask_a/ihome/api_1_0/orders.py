from datetime import datetime
from flask import request, jsonify, current_app, g

from ihome import db, redis_store
from ihome.api_1_0 import api
from ihome.models import House, Order
from ihome.utils.commons import login_required
from ihome.utils.response_code import RET

# GET /api/v1.0/orders
@api.route("/orders",methods=["POST"])
@login_required
def save_order():
    """保存订单"""
    user_id = g.user_id

    #获取参数
    order_data = request.get_json()
    if not order_data:
        return jsonify(errno=RET.PARAMERR,errmsg="参数错误")

    #提取参数
    house_id = order_data.get("house_id")  # 预定的房屋编号
    start_date_str = order_data.get("start_data") # 预定的起始时间
    end_date_str = order_data.get("end_date") # 预定的结束时间

    #参数检查
    if not all([house_id,start_date_str,end_date_str]):
        return jsonify(errno=RET.PARAMERR,errmsg="参数错误")

    #日期格式检查
    try:
        #
        start_date = datetime.strptime(start_date_str,"%Y-%m-%d")
        end_date = datetime.strptime(end_date_str,"%Y-%m-%d")
        assert start_date <= end_date
        #计算预定的天数
        days = (end_date - start_date).days + 1
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR,errmsg="日期格式错误")

    #验证房屋id
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="获取房屋信息失败")
    if not house:
        return jsonify(errno=RET.NODATA, errmsg="房屋不存在")

    #预定的房屋是否是房东自己的
    if user_id == house.user_id:
        return jsonify(errno=RET.ROLEERR,errmsg="不能预定自己的房屋")

    #查询订单是否有冲突
    try:
        count = Order.query.filter(Order.house_id==house_id,
                                   Order.begin_date<=end_date,
                                   Order.end_data>=start_date).count()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg="数据库查询错误")
    if count > 0:
        return jsonify(errno=RET.DATAERR,errmsg="房屋已经被预定")

    #订单总额
    amount = days * house.price

    #保存订单数据
    order = Order(user_id=user_id,
                  house_id=house_id,
                  begin_date=start_date,
                  end_date=end_date,
                  days = days,
                  house_price=house.price,
                  amount=amount)
    try:
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg="保存订单失败")

    return jsonify(errno=RET.OK,
                   errmsg="OK",
                   data={"order_id":order.id})



@api.route("/user/orders", methods=["GET"])
@login_required
def get_user_orders():
    """查询用户订单"""
    user_id = g.user_id

    #用户身份
    role = request.args.get("role","")

    #查询订单数据
    try:
        if role == "landlord": # 作为房东身份
            houses = House.query.filter(user_id==user_id).all()
            houses_ids = [house.id for house in houses]
            #查询房东所属房子的订单
            orders = Order.query.filter(Order.house_id.in_(houses_ids))\
                                .order_by(Order.create_time
                                          .desc()).all()
        else: # 房客身份查询
            orders = Order.query.filter(Order.user_id==user_id)\
                                .order_by(Order.create_time
                                          .desc()).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg="数据库查询错误")

    #拼接返回的字典数据
    orders_li = []
    if orders:
        for order in orders:
            orders_li.append(order.to_dict())

    return jsonify(errno=RET.DBERR,errmsg="数据库查询错误")


@api.route('/orders/<int:order_id>/status',methods=["PUT"])
@login_required
def accept_reject_order(order_id):
    """接单，拒单"""
    user_id = g.user_id

    #获取参数
    req_data = request.get_json()
    if not req_data:
        return jsonify(errno=RET.PARAMERR,errmsg="参数错误")

    action = req_data.get("action")
    if action not in ["accept","reject"]:
        return jsonify(errno=RET.PARAMERR,errmsg="参数错误")

    #查询订单
    try:
        #根据订单号查询订单,订单要处在待接单状态
        order = Order.query.filter_by(Order.id==order_id,Order.status=="WAIT_ACCEPT").first()
        house = order.house
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg="无法获取订单数据")

    #确保房东只能修改自己房子的订单
    if not order or user_id != house.user_id:
        return jsonify(errno=RET.REQERR,errmsg="操作无效")

    #修改订单状态
    if action == "accept":
        #接单
        order.status = "WAIT_PAYMENT"
    elif action == "reject":
        #拒单
        #获取拒单原因
        reason = req_data.get("reason")
        if not reason:
            return jsonify(errno=RET.PARAMERR,errmsg="缺少拒单原因")
        order.status = "REJECTED"
        order.comment = reason

    #提交修改到数据库
    try:
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg="操作失败")

    return jsonify(errno=RET.OK,errmsg="OK")


@api.route('/orders/int:<order_id>/comment',methods=["PUT"])
@login_required
def save_order_comment(order_id):
    """保存订单评论信息"""
    user_id = g.user.id
    #获取参数
    req_data = request.get_json()
    comment = req_data.get("comment")  #评价信息

    #检查参数
    if not comment:
        return jsonify(errno=RET.PARAMERR,errmsg="参数错误")

    try:
        #需要确保只能评论自己下的订单，而且订单处于为评论状态
        order = Order.query.filter(Order.id==order_id,
                           Order.user_id==user_id,
                           Order.status=="WAIT_COMMENT")
        house = order.house
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg="无法获取订单数量")

    if not order:
        return jsonify(error=RET.REQERR,errmsg="操作无效")

    try:
        #将订单数据状态设置为已完成
        order.status="COMPLETE"
        #保存订单评论信息
        order.comment=comment
        #房屋的完成订单数加1
        house.room_count += 1
        db.session.add(order)
        db.session.add(house)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg="操作失败")

    #后屋数据有更新，清除房屋缓存，
    try:
        redis_store.delete("house_info_%s" % order.house_id)
    except Exception as e:
        current_app.logger.error(e)

    return jsonify(errno=RET.OK,errmsg="OK")