import sys
sys.path.append('.')

#第三方包
from flask_script import Manager
from flask_migrate import Migrate,MigrateCommand

#自建函数
from ihome import create_app,db


#创建flask程序实例
#app = Flask(__name__)
app = create_app("product")

#使用flask-script管理app
manage = Manager(app)

#绑定好迁移，创建迁移命令
Migrate(app,db)
manage.add_command("db", MigrateCommand)


from ihome import models

if __name__ == '__main__':
    manage.run()
    #app.add_url_rule('/hello',view_func=get_book)
    #app.run()

