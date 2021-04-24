from celery import Celery
from django.conf import settings
from django.core.mail import send_mail
from django.template import loader


# 在任务处理者中加载django环境
import os
# import django
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
# django.setup()
from goods.models import GoodsType, GoodsSKU, IndexGoodsBanner, IndexTypeGoodsBanner,IndexPromotionBanner




# 创建Celery对象
# broker: 中间人(redis)
app = Celery("celery_task.tasks", broker="redis://192.168.233.137:6379/2")


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


@app.task
def generate_static_index_page():
    """ 生成静态的 首页面 """
    # 获取所有商品的类型
    goods_types = GoodsType.objects.all()
    # 获取所有的轮播的商品
    index_goods_banners = IndexGoodsBanner.objects.all().order_by("index")
    # 获取所有促销商品
    index_promotion_banners = IndexPromotionBanner.objects.all().order_by("index")

    # 动态的给type添加属性
    for goods_type in goods_types:
        # 获取商品类型的所有title的展示信息
        title_goods_banners = IndexTypeGoodsBanner.objects.filter(type=goods_type, display_type=0).order_by("index")
        # 获取商品类型的所有图片的展示信息
        image_goods_banners = IndexTypeGoodsBanner.objects.filter(type=goods_type, display_type=1).order_by("index")

        # 动态的添加属性， 添加所有title的展示信息
        goods_type.title_goods_banners = title_goods_banners
        # 动态的添加属性 ，添加所有图片的展示信息
        goods_type.image_goods_banners = image_goods_banners

    # 购物车商品数量
    cart_count = 0

    # 组织模板上下文
    context = {
        "goods_types": goods_types,
        "index_goods_banners": index_goods_banners,
        "index_promotion_banners": index_promotion_banners,
        "cart_count": cart_count,
    }
    # 获取模板
    template = loader.get_template('static_index.html')
    # 渲染数据
    html = loader.render_to_string(template, context)
    save_path = os.path.join(settings.BASE_DIR, "static/index.html")
    with open(save_path, 'w') as f:
        f.write(html)

