import json
from datetime import datetime

from flask import jsonify, current_app, g, request
from ihome import redis_store, constants, db
from ihome.api_1_0 import api
from ihome.models import Area, House, Facility, HouseImage, User, Order
from ihome.utils.commons import login_required
from ihome.utils.image_storage import storage
from ihome.utils.response_code import RET



@api.route("/areas")
def get_areas_info():
    """获取城区信息"""
    #从redis中获取缓存
    try:
        area_dict = redis_store.get("area_info")
    except Exception as e:
        current_app.logger.reeor(e)
    else:
        if area_dict is not None:
            current_app.logger.info("hit redis area_info")
            # 有缓存 返回数据
            return jsonify(errno=RET.OK,errmsg="OK",data=area_dict)

    #无缓存，查询数据库
    try:
        area_li = Area.query.all()
        print(area_li)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg="数据库查询失败")

    # 拼装城区数据
    aera_dict_li = []
    for area in area_li:
        aera_dict_li.append(area.to_dict())

    #设置缓存到redis
    try:
        redis_store.setex("area_info",constants.AREA_INFO_REDIS_CACHE_EXPIRES,aera_dict_li)
    except Exception as e:
        current_app.logger.error(e)

    #返回数据
    return jsonify(errno=RET.OK,errmsg="OK",data=aera_dict_li)


@api.route("/houses/info",methods=["POST"])
@login_required
def save_house_info():
    """保存房屋基本信息"""
    user_id = g.user_id
    house_data = request.get_json()

    #接收参数
    title = house_data.get("title") # 房屋名称
    price = house_data.get("price") # 房屋单价
    ared_id = house_data.get("area_id") # 房屋所属城区
    address = house_data.get("address") # 房屋地址
    room_count = house_data.get("room_count") # 房间容纳人数
    acreage = house_data.get("acreage") #房间面积
    unit = house_data.get("unit") #房间布局
    capacity = house_data.get("capacity") # 房屋容纳人数
    beds = house_data.get("beds") # 房屋卧床数据
    deposit = house_data.get("deposit") # 押金
    min_days = house_data.get("min_days") # 最小入住天数
    max_days = house_data.get("max_days") #最大入住天数

    #验证参数
    if not all([title,price,ared_id,address,room_count,acreage,unit,capacity,beds,deposit,min_days,max_days]):
        return jsonify(errno=RET.PARAMERR,errmsg="参数不完整")

    #校验金额
    try:
        price = int(price)
        deposit = int(deposit)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR,errmsg="金额参数错误")

    #判断城区id是否存在
    try:
         area = Area.query.get(ared_id)
    except Exception as e:
         current_app.logger.error(e)
         return jsonify(errno=RET.DBERR,errmsg="数据库异常")
    if area is None:
        return jsonify(errno=RET.NODATA,errmsg="城区信息有误")

    #保存房屋信息
    house = House(user_id=user_id,ared_id=ared_id,title=title,price=price,address=address,room_count=room_count,acreage=acreage,unit=unit,capacity=capacity,beds=beds,deposit=deposit,min_days=min_days,max_days=max_days)

    #处理房屋的设施信息
    facility_ids = house_data.get("facility")

    #验证设施信息是否为空
    if facility_ids is not None:
        try:
            #验证设施是否存在
            facilities = Facility.query.filter(Facility.id.in_(facility_ids)).all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR,errmsg="数据库异常")
        if facilities:
            #表示有合法的设施数据
            #保存设施数据
            house.facilities=facilities

    try:
        db.session.add(house)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg="保存数据库失败")

    #保存数据成功
    return jsonify(errno=RET.DBERR,errmsg="OK",data={"house":house.id})


@api.route("/houses/image",methods=["POST"])
@login_required
def save_house_image():
    """保存房屋的图片"""
    user_id= g.user_id

    #接收数据
    image_file = request.files.get("house_image")
    house_id = request.form.get("house_id")

    #验证数据
    if not all([image_file,house_id]):
        return jsonify(errno=RET.PARAMERR,error="参数错误")

    #验证house_id数据是否存在
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.loggwe.error(e)
        return jsonify(errno=RET.DBERR,errmsg="数据库查询错误")

    if house is None:
        return jsonify(errno=RET.NODATA,errmsg="房屋不存在")

    image_data = image_file.read()
    try:
        #上传图片到七牛
        file_name = storage(image_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR,errmsg="保存图片失败")

    #保存数据
    house_image = HouseImage(house_id=house_id,url=file_name)
    db.session.add(house_image)

    #处理房屋的主图片
    if not house.index_image_url:
        house.index_image_url = file_name
        db.session.add(house)

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg="保存图片数据异常")

    image_url = constants.QINIU_URL_DOMAIN + file_name
    return jsonify(errno=RET.OK,errmsg="OK",data={"image_url":image_url})

@api.route("/user/houses",methods=["GET"])
@login_required
def get_user_houses():
    """获取房东发布的房源信息条目"""
    user_id = g.user_id

    #筛选数据
    try:
        user = User.query.get(user_id)
        houses = user.houses
        #houses = House.query.filter_by(user_id=user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,reemsg="数据库查询失败")

    if houses is None:
        return jsonify(errno=RET.NODATA,reemsg="当前用户未发布房源")

    houses_li = []
    for house in houses:
        houses_li.append(house.to_basic_dict())
    return jsonify(errno=RET.OK,errmsg="OK",data={"house_li":houses_li})




@api.route("/houses/index",methods=["GET"])
def get_house_index():
    """获取主页幻灯片展示的房屋基本信息"""
    #尝试从缓存中获取信息
    try:
        ret = redis_store.get("house_index_data")
    except Exception as e:
        current_app.logger.error(e)
        ret = None

    #有缓存
    if ret:
    # 返回数据
        return jsonify(errno=RET.OK,errmsg="OK",data=ret)

    #无缓存，查询数据库
    try:
        houses = House.query.order_by(House.order_count.desc).limit(constants.HOME_PAGE_MAX_HOUSES)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.DBERR,errmsg="数据库查询失败")

    #拼接数据
    house_li = []
    for house in houses:
        if house.index_image_url is None:
            continue
        house_li.append(house.to_basic_dict())

    # 设置缓存
    try:
        redis_store.setex("house_index_data",constants.HOME_PAGE_DATA_REDIS_EXPIRES,house_li)
    except Exception as e:
        current_app.logger.error(e)

    #返回数据
    return jsonify(errno=RET.OK,errmsg="OK",)


@api.route("houses/<int:house_id>",methods=["GET"])
def get_house_detail(house_id):
    """获取房屋详情"""
    try:
        house = House.query.get(house_id=house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.OK,errmsg="数据库查询失败")

    house_dict = house.to_full_dict()
    return jsonify(errno=RET.OK,errmsg="OK",data={"data":house_dict})

# GET /api/v1.0/houses?sd=2017-10-31&ed=2017-2-23&aid=7&sk=new&p=1
@api.route("/houses")
def get_house_list():
    """获取房屋的列表信息(搜索页面)"""
    #获取参数
    start_date = request.args.get("sd", default="")
    end_date = request.args.get("sd", default="")
    area_id = request.args.get("sd", default="")
    sort_key = request.args.get("sd", default="new")
    page = request.args.get("sd")
    #校验参数
    try:
        if start_date:
            start_date=datetime.strptime(start_date,"%Y-%m-%d")
        elif end_date:
            end_date=datetime.strptime(end_date,"%Y-%m-%d")
        if start_date and end_date:
            # 起始要小于结束时间
            assert start_date <= end_date
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.OK,errmsg="日期参数有误")

    # 城区编号要合法存在
    if area_id:
        try:
            area = Area.query.get(area_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR,errmsg="区域参数有误")

    #关键字要合法存在  默认为最新上线

    #页码必须整数，否则设置为1
    try:
        if int(page) > 0:
            page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    #获取缓存数据
    redis_key = 'house_%s_%s_%s_%s' % (start_date,end_date,area_id,sort_key)
    try:
        resp_json = redis_store.hget(redis_key,page)
    except Exception as e:
        current_app.logger.error(e)
    else:
        if resp_json:
            return resp_json,200,{"Content_Type":"application/json"}

    #过滤条件的查询容器
    filter_params = []

    #冲突的订单对象
    confict_orders = None

    try:
        if start_date and end_date:
            confict_orders = Order.query.filter(Order.begin_date <= end_date,Order.end_data >=start_date).all()
        elif start_date:
            confict_orders = Order.query.filter(Order.end_data >= start_date).all()
        elif end_date:
            confict_orders = Order.query.filter(Order.begin_date <= end_date).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.OK,errmsg="数据库查询失败")

    #如果存在冲突订单
    if confict_orders:
        #拿出房屋id
        confict_orders_ids = [order.house_id for order in confict_orders]
        if confict_orders_ids:
            #如果存在冲突的房间id，追加订单过滤条件到过滤容器
            filter_params.append(House.id.notin_(confict_orders_ids))

    #区域条件
    if area_id:
        #区域合法，追加
        filter_params.append(House.area_id==area_id)

    #解包过滤容器，补充排序条件
    if sort_key == "booking": # 入住人数最多
        house_query = House.query.filter(*filter_params).order_by(House.order_count.desc())
    if sort_key == "price-inc": # 价格升序
        house_query = House.query.filter(*filter_params).order_by(House.price.asc())
    if sort_key == "price-desc": # 价格降序
        house_query = House.query.filter(*filter_params).order_by(House.price.desc())
    else:  # 上线时间排序
        house_query = House.query.filter(*filter_params).order_by(House.create_time.desc())

    #处理分页
    try:
        page_obj = house_query.paginate(page=page,
                                        per_page=constants.HOUSE_LIST_PAGE_CAPACITY,
                                        error_out=False)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errnp=RET.DBERR,errmsg="数据库错误")

    #获取页面数据
    houses = [house.to_basic_dict() for house in page_obj.items]

    #获取总页数
    total_page = page_obj.pages

    #拼接返回数据
    resp_dict = dict(errno=RET.OK,errmsg="OK",data={"total_page":total_page,
                                                    "current_page":page,
                                                    "houses":houses})
    resp_json = json.dumps(resp_dict)

    #页面逻辑
    if page <= total_page:
        try:
            #设置缓存
            redis_key = 'house_%s_%s_%s_%s' % (start_date,
                                               end_date,
                                               area_id,
                                               sort_key)
            pipeline = redis_store.pipeline()
            pipeline.multi()

            pipeline.hset(redis_key,page,page,resp_json)
            pipeline.expire(redis_key,constants.HOUES_LIST_PAGE_REDIS_CACHE_EXPIRES)

            #执行语句
            pipeline.execute()
        except Exception as e:
            current_app.logger.error(e)

    #返回数据
    return resp_json,200,{"Content-Type":"application/json"}













