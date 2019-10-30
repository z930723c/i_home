#第三方包
from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
import redis
import logging
from logging.handlers import RotatingFileHandler


#自建函数
from config import config_map
from ihome.utils.commons import ReConverter

#创建数据库对象
db = SQLAlchemy()

#创建redis连接对象
redis_store = None

#配置日志信息
#设置日志等级
logging.basicConfig(level=logging.INFO)
#创建入职记录器设置文件存储路径 单个文件上限大小  最多保存日志文件个数
file_log_handle = RotatingFileHandler(filename="logs/log",
                                      maxBytes=1024*1024*1024,
                                      backupCount=10)
#创建日志记录的格式
formatter = logging.Formatter("%(levelname)s "
                              "%(filename)s "
                              "%(lineno)s "
                              "%(message)s")
#为日志记录器注册日志格式
file_log_handle.setFormatter(formatter)
# 为全局的日志工具对象（flask app使用的）添加日志记录器
logging.getLogger().addHandler(file_log_handle)



#工厂模式
def create_app(config_name):
    """
    创建flask引用对象
    :param conf_name: str 配置模式的名字 develop product
    :return: Flask的实例对象
    """
    app = Flask(__name__)

    #根据字典get方法获取配置模式的配置参数的类
    config_class = config_map.get(config_name)
    app.config.from_object(config_class)

    #使用app初始化db
    db.init_app(app)

    #初始化redis
    global redis_store
    redis_store = redis.Redis(host=config_class.REDIS_HOST,port=config_class.REDIS_PORT)

    #利用flask_session将session保存到redis中
    Session(app)

    #添加csrf防护
    CSRFProtect(app)

    #自定义正则装换器
    app.url_map.converters['re'] = ReConverter

    #注册蓝图
    from ihome.api_1_0 import api
    app.register_blueprint(api,url_prefix="/api/v1.0")

    #注册静态文件蓝图
    from ihome.web_html import html
    app.register_blueprint(html)

    return app


