
class Config(object):
    #数据库配置 盐 指定数据库 自动修改
    SECRET_KEY = 'XHSOI*Y9dfs9cshd9'
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:zhangchan@localhost:3306/ihome"
    SQLALCHEMY_TRACK_MODIFICATIONS = True

    #redis配置
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = 6379

class DevelopmentClass(Config):
    """开发模式的配置信息"""
    DEBUG = True
    pass


class PepductClass(Config):
    """生产模式配置信息"""
    pass



#创建配置类对象的字典映射
config_map = {
    "develop":DevelopmentClass,
    "product":PepductClass
}