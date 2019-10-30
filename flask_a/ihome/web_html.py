from flask import Blueprint, current_app, make_response

#创建静态文件蓝图
html = Blueprint("web_html",__name__)

#导入蓝图的视图
@html.route("/<re(r'.*'):file_name>")
def get_html(file_name):
    """提供html文件"""

    # 如果html_file_name为""， 表示访问的路径是/ ,请求的是主页
    if not file_name:
        file_name = "index.html"

    # 如果资源名不是favicon.ico
    if file_name != "favicon.ico":
        file_name = "html/" + file_name

    print(file_name)
    #flask提供的返回静态文件的方法
    return make_response(current_app.send_static_file(file_name))
