from celery import Celery
from django.conf import settings
from django.core.mail import send_mail

# 在任务处理者中加载django环境
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
django.setup()



# 创建Celery对象
# broker: 中间人(redis)
app = Celery("celery_task.tasks", broker="redis://192.168.233.135:6379/2")


# 创建向邮箱发送激活链接任务
@app.task
def send_register_activate_email(user_name, secret_data, email):
    # 向用户的邮箱发送帐号的激活码
    message = """
                   <h1>%s欢迎你加入天天生鲜注册会员</h1>
                   <h2>点击下面链接来激活账号, 此链接30分钟之内有效</h2>
                   <a href="http://192.168.233.132:8000/user/activate/%s">http://192.168.233.132:8000/activate/%s</a>

               """ % (user_name, secret_data, secret_data)

    subject = "天天生鲜"
    email_from = settings.EMAIL_FROM
    send_mail(subject, '', email_from, [email], html_message=message)
