from django.shortcuts import render, redirect, reverse
from django.views import View
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.conf import settings
from user.models import User
import re
from itsdangerous import TimedJSONWebSignatureSerializer as Serialiezer
from celery_task import tasks
from user.models import Address
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from django.core.paginator import Paginator

# /register
class RegisterView(View):
    def get(self, request):
        """ 注册页面 """
        return render(request, 'register.html')

    def post(self, request):
        """ 注册处理 """
        # 接收数据
        user_name = request.POST.get("username")
        password = request.POST.get("password")
        email = request.POST.get("email")
        allow = request.POST.get("allow")

        # 校验数据
        if not all([user_name, password, email]):
            """ 数据不完整 """
            return JsonResponse({"data": 0, "err_mesg": "数据不完整"})

        # 校验邮箱是否合法
        r = r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$'
        rel = re.match(r, email)
        if not rel:
            """邮箱不合法"""
            return JsonResponse({"data": 1, "err_mesg": " 邮箱地址不合法"})

        # 判断用户是否勾选协议
        if allow != "on":
            """ 没有勾选天天生鲜用户使用协议"""
            return JsonResponse({"data": 2, "err_mesg": "请勾选协议"})

        # todo: 注册用户信息
        user = None
        # 判断用户名 是否存在
        try:
            user = User.objects.get(username=user_name)
        except User.DoesNotExist as e:
            pass
        if not user:
            """ 用户不存在 """
            # 创建用户
            user = User.objects.create_user(username=user_name, password=password, email=email)

            # 帐号默认未激活
            user.is_active = 0
            user.save()

            # todo:向用户邮箱发送帐号激活链接
            # 加密用户的id
            serializer = Serialiezer(settings.SECRET_KEY, 1800)
            secret_data = serializer.dumps({"user_id": user.id}).decode()
            # 向用户邮箱发送帐号激活链接
            tasks.send_register_activate_email.delay(user_name, secret_data, email)
            # 创建成功 返回信息
            return JsonResponse({"data": 3, "mesg": "已向您的邮箱发送帐号激活链接，请注意查收"})
        else:
            """ 用户已存在 """
            return JsonResponse({"data": 4, "err_mesg": "用户已经存在"})


# /activate/
class ActivateView(View):
    def get(self, request, secret_data):
        """ 帐号激活 """
        # 接受待激活帐号的id
        serializer = Serialiezer(settings.SECRET_KEY, 1800)
        try:
            secret_data = serializer.loads(secret_data)
            user_id = secret_data["user_id"]
        except Exception as e:
            return HttpResponse("该激活码已失效")

        # todo: 激活帐号
        user = User.objects.get(id=user_id)
        user.is_active = 1
        user.save()
        return redirect("user:login")


# /login
class LoginView(View):
    def get(self, request):
        """ 登录页面 """
        # 获取用户名
        username = request.COOKIES.get("username")
        if not username:
            username = ''
        return render(request, "login.html", {"username": username})

    def post(self, request):
        """ 登录验证"""
        # 接收数据
        username = request.POST.get("username")
        password = request.POST.get("pwd")
        remember = request.POST.get("remember")

        # 获取用户访问上一回访问的url
        next_url = request.GET.get("next", reverse("goods:index"))

        # 校验数据
        if not all([username, password]):
            """ 数据不完整 """
            return render(request, "login.html", {"data": 0, "err_mesg": "数据不完整"})

        # todo: 验证用户
        user = authenticate(username=username, password=password)
        if user is not None:
            """ 验证成功 """
            # 判断该帐号是否激活
            if user.is_active:
                """ 帐号已激活"""
                # 记录用户的登录状态
                login(request, user)
                response = redirect(next_url)
                # 判断是否记住用户名
                if remember == 'on':
                    response.set_cookie("username", username, 7 * 24 * 3600)

                # 响应客户端
                return response

            else:
                """ 帐号没有激活 """
                # 加密用户的id
                serializer = Serialiezer(settings.SECRET_KEY, 1800)
                secret_data = serializer.dumps({"user_id": user.id}).decode()
                tasks.send_register_activate_email.delay(user.username, secret_data, user.email)
                response = render(request, "login.html", {"err_mesg": "该帐号没有激活，已经想你的邮箱发送激活链接"})
                return response
        else:
            """ 验证失败"""
            return render(request, "login.html", {"err_mesg": "帐号或密码错误"})


# /logout
class LogoutView(LoginRequiredMixin, View):
    def get(self, request):
        """ 退出登录"""
        # 退出登录
        logout(request)
        return redirect(reverse("goods:index"))


# /center
class CenterView(LoginRequiredMixin,View):
    def get(self, request):
        """ 用户中心"""
        # 获取用户
        user = request.user
        # 获取用户的地址信息
        try:
            address = Address.objects.get(user=user, is_default=True)
        except Address.DoesNotExist as e:
            address = None

        # 组织用户key
        user_key = "history_%d" % user.id

        # 获取redis链接
        con = get_redis_connection("default")

        # 获取用户最近浏览的商品id
        sku_ids = con.lrange(user_key, '0', '-1')[0:5]

        skus = []
        # 根据商品的id获取所有用户浏览的商品的信息
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id)
            skus.append(sku)

        # 组织模板上下文
        params = {
            "address": address,
            "page_num": 1,
            "skus": skus
        }
        return render(request, "user_center_info.html", params)


# /order
class OrderView(LoginRequiredMixin, View):
    def get(self, request, page_num):
        """ 用户订单页"""
        # 接收登录的的用户
        user = request.user

        # todo: 获取订单信息
        orders = OrderInfo.objects.filter(user=user).order_by("-create_time")
        for order in orders:
            """ 动态的添加属性"""
            total_price = 0
            # 根据订单信息查询出商品订单
            order_goods = OrderGoods.objects.filter(order=order)
            for goods in order_goods:
                """ 累加总计"""
                total_price += goods.price

            order.order_goods = order_goods
            order.total_price = total_price
            order.status = OrderInfo.ORDER_STATUS[order.order_status]

        p = Paginator(orders, 2)
        page = p.get_page(page_num)

        # 组织模板上下文
        params = {
            "orders": orders,
            "page_num": 2,
            "page": page,
        }
        return render(request, "user_center_order.html", params)


# /address
class AddressView(LoginRequiredMixin, View):
    def get(self, request):
        """ 用户地址页"""
        # 接收登录的用户信息
        user = request.user

        # todo: 获取用户地址信息
        try:
            address = Address.objects.get(user=user, is_default=True)
        except Address.DoesNotExist as e:
            address = None

        # 组织模板上下文
        params = {
            "address": address,
            "page_num": 3,
        }

        return render(request, "user_center_site.html", params)


    def post(self, request):
        """ 提交用户编辑的地址 """
        # 接收数据
        user = request.user
        receiver = request.POST.get("recviver")
        detail_addr = request.POST.get("detail_addr")
        zip_code = request.POST.get("zip_code")
        phone = request.POST.get("phone")

        # 校验数据
        if not all([receiver, detail_addr, phone]):
            """ 数据不完整 """
            return render(request, "user_center_site.html", {"err_mesg": "数据不完整"})

        # 校验手机号码是否正确
        expression = r"^1(3[0-9]|5[0-3,5-9]|7[1-3,5-8]|8[0-9])\d{8}$"
        rel = re.match(expression, phone)
        print(rel)
        if not rel:
            """ 手机号码不合法"""
            return render(request, "user_center_site.html", {"err_mesg": "手机号码不合法"})

        # todo: 将用户编辑的地址提交到数据库

        # 查找用户有没有默认的收货地址
        try:
            addr = Address.objects.get(user=user, is_default=True)
        except Address.DoesNotExist as e:
            """ 没有默认收获地址 """
            address = Address.objects.create(
                user=user,
                receiver=receiver,
                addr=detail_addr,
                zip_code=zip_code,
                phone=phone,
                is_default=True, # 将此地址设为默认地址
            )
            return redirect(reverse("user:address"))

        # 添加一条地址信息
        address = Address.objects.create(
            user=user,
            receiver=receiver,
            addr=detail_addr,
            zip_code=zip_code,
            phone=phone,
            is_default=False,
        )
        return redirect(reverse("user:address"))






