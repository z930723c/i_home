from celery import Celery

#定义celery对象
from ihome.tasks import config

celery_app = Celery("ihome")

#加载配置文件
celery_app.config_from_object(config)

#自动搜寻异步任务
celery_app.autodiscover_tasks(["ihome.tasks.sms"])