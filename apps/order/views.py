from django.shortcuts import render, redirect, reverse
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views import View
from utils.mixin import LoginRequiredMixin
from user.models import Address
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from django_redis import get_redis_connection
from datetime import datetime
from django.db import transaction
import os

# 支付所需模块
from order.alipay import AliPay


# /place_order
class PlaceOrderView(LoginRequiredMixin, View):
    def post(self, request):
        """ 订单页面"""
        # 接收数据
        user = request.user
        sku_ids = request.POST.getlist('sku_id')

        # 校验数据
        if not sku_ids:
            """ 数据不完整"""
            return redirect(reverse("cart:cart"))

        # todo: 获取提交订单页面，所需数据

        # 获取收获地址信息
        address = Address.objects.filter(user=user)
        # 获取redis连接
        con = get_redis_connection("default")
        cart_ket = "cart_%d" % user.id
        # 总价格
        sku_total_price = 0
        total_count = 0
        skus = []
        # 获取商品信息
        for id in sku_ids:
            sku = GoodsSKU.objects.get(id=id)
            # 获取商品数量
            count = int(con.hget(cart_ket, id))
            subtotal = round(count * sku.price, 2)
            sku_total_price += subtotal
            total_count += count
            # 动态的添加属性
            sku.count = count
            sku.subtotal = subtotal
            skus.append(sku)
        # 通过子系统查出邮费
        freight = 10

        sku_ids = ','.join(sku_ids)

        # 组织模板上下文
        params = {
            "address": address,
            "skus": skus,
            "freight": freight,
            "sku_total_price": sku_total_price,
            "total_count": total_count,
            "total_price": sku_total_price + freight,
            "sku_ids": sku_ids,
        }
        return render(request, "place_order.html", params)


# /create_order
class CreateOrderView(View):
    @transaction.atomic
    def post(self, request):
        """ 创建订单 """
        user = request.user
        # 判断用户是否登录
        if not user.is_authenticated:
            """ 用户未登录"""
            return JsonResponse({"code": 0, "err_mesg": "请登录"})

        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_style = request.POST.get("pay_style")
        sku_ids = request.POST.get("sku_ids")

        # 校验数据
        if not all([addr_id, pay_style, sku_ids]):
            """数据不完整"""
            return JsonResponse({"code": 1, "err_mesg": "数据完整"})
        # 校验支付方式
        if pay_style not in OrderInfo.PAY_METHOD.keys():
            """ 支付方式不正确"""
            return JsonResponse({"code": 2, "err_mesg": "支付方式不正确"})
        # todo: 创建订单核心业务

        # 订单编号 日期+用户id
        order_id = datetime.now().strftime("%Y%m%d%H%M%S") + "%d" % user.id

        # 验证地址信息是否正确
        try:
            addr = Address.objects.get(id=addr_id, user=user)
        except Address.DoesNotExist:
            """ 地址信息不存在"""
            return JsonResponse({"code": 3, "err_mesg": "地址信息不存在"})

        # 初始化字段数据
        total_count = 0
        total_price = 0
        # 运费（通过子系统查询，这里是写死的）
        transit_price = 10

        # 事务保存点
        save_point = transaction.savepoint()
        try:
            # todo:  向df_order_info 添加一条记录
            order_info = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                addr=addr,
                pay_method=pay_style,
                total_count=total_count,
                total_price=total_price,
                transit_price=transit_price,
            )

            # todo: 有多少个个商品就向df_order_goods添加多少记录
            # 数据转换
            sku_ids = sku_ids.split(',')

            # 获取redis连接
            con = get_redis_connection("default")
            # 组织key
            cart_key = "cart_%d" % user.id

            for sku_id in sku_ids:
                for i in range(3):
                    # 查询商品信息
                    try:
                        # sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        """ 商品不存在 """
                        transaction.savepoint_rollback(save_point)
                        return JsonResponse({"code":4, "err_mesg": "商品不存在"})

                    # 获取购物车中的商品数量
                    count = con.hget(cart_key, sku_id)
                    price = round(int(count) * sku.price, 2)
                    # 累计总价格，和总件数
                    total_count += int(count)
                    total_price += price

                    # todo: 判断库存是否足够
                    if int(count) > sku.stock:
                        """ 库存不足"""
                        transaction.savepoint_rollback(save_point)
                        return JsonResponse({"code": 5, "err_mesg": "库存不足"})

                    # 增加该商品的销量， 并且更新库存
                    prev_stock = sku.stock
                    new_stock = prev_stock - int(count)
                    new_sales = sku.sales + int(count)

                    print("user:", user.id, "stock:", sku.stock, "循环次数", i)
                    res = GoodsSKU.objects.filter(id=sku_id, stock=prev_stock).update(
                        stock=new_stock,
                        sales=new_sales
                    )

                    if res == 0:
                        """ 更新失败"""
                        if i == 2:
                            """ 两次机会都更新失败"""
                            transaction.savepoint_rollback(save_point)
                            return JsonResponse({"code": 6, "err_mesg": "提交失败"})
                        continue

                    # todo: 向df_order_goods添加一条记录
                    order_goods = OrderGoods.objects.create(
                        order=order_info,
                        sku=sku,
                        count=int(count),
                        price=price,
                    )
                    break
        except Exception as e:
            transaction.savepoint_rollback(save_point)
            return JsonResponse({"code": 8, "err_mesg": "服务器发生了不可预料的错误"})

        # 提交事务中所做的操作
        transaction.savepoint_commit(save_point)
        # 更新订单信息表中的总价格和总件数
        order_info.total_count = total_count
        order_info.total_price = total_price
        order_info.save()

        # 删除购物车中的商品
        con.hdel(cart_key, *sku_ids)

        return JsonResponse({"code": 7, "err_meg": "提交成功"})


# /order/pay
class OrderPayView(View):
    def post(self, request):
        """ 订单支付 """
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"code": 0, "errmesg": "请登录"})
        # 接受数据
        order_id = request.POST.get("order_id")

        # 校验数据
        if not order_id:
            return JsonResponse({"code": 1, "errmesg": "无效订单"})
        try:
            order = OrderInfo.objects.get(
                order_id=order_id,
                user=user,
                order_status=1,  # 未支付状态
                pay_method=3,   # 支付方式为支付宝支付
            )
        except OrderInfo.DoesNotExist:
            return JsonResponse({"code": 2, "errmesg": "订单无效,原因(支付方式只支持支付宝、或该订单可能已经支付)"})

        # todo: 使用python的 sdk 调用支付接口
        total_price = order.total_price + order.transit_price

        # 初始化
        alipay = AliPay(
            appid="2021000117621746",  # 支付宝沙箱里面的APPID，需要改成你自己的
            app_notify_url=None,   # 如果支付成功，支付宝会向这个地址发送POST请求
            return_url=None,  # 如果支付成功，重定向回到你的网站的地址
            alipay_public_key_path=settings.ALIPAY_PUBLIC,  # 支付宝公钥
            app_private_key_path=settings.APP_PRIVATE,  # 应用私钥
            debug=True,  # 默认False,True表示使用沙箱环境测试
        )
        # 生成支付宝支付接口
        query_params = alipay.direct_pay(
            subject="天天生鲜%s" % order_id,  # 商品简单描述
            out_trade_no=order_id,  # 商户订单号
            total_amount=str(total_price),  # 交易金额(单位: 元 保留俩位小数)
        )

        # 拼接url，转到支付宝支付页面
        pay_url = "https://openapi.alipaydev.com/gateway.do?{}".format(query_params)

        return JsonResponse({"code": 3, "pay_url": pay_url})


# /order/check
class CheckPayView(View):
    def post(self, request):
        """ 查询支付结果"""
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"code": 0, "errmesg": "请登录"})
        # 接受数据
        order_id = request.POST.get("order_id")

        # 校验数据
        if not order_id:
            return JsonResponse({"code": 1, "errmesg": "无效订单"})
        try:
            order = OrderInfo.objects.get(
                order_id=order_id,
                user=user,
                order_status=1,  # 未支付状态
                pay_method=3,  # 支付方式为支付宝支付
            )
        except OrderInfo.DoesNotExist:
            return JsonResponse({"code": 2, "errmesg": "订单无效,原因(支付方式只支持支付宝、或该订单可能已经支付)"})

        # todo: 使用python的 sdk 调用支付接口
        # 初始化
        alipay = AliPay(
            appid="2021000117621746",  # 支付宝沙箱里面的APPID，需要改成你自己的
            app_notify_url=None,  # 如果支付成功，支付宝会向这个地址发送POST请求
            return_url=None,  # 如果支付成功，重定向回到你的网站的地址
            alipay_public_key_path=settings.ALIPAY_PUBLIC,  # 支付宝公钥
            app_private_key_path=settings.APP_PRIVATE,  # 应用私钥
            debug=True,  # 默认False,True表示使用沙箱环境测试
        )
        while True:
            # 查询支付结果， 获取响应信息
            response = alipay.api_alipay_trade_query(order_id)
            """
               response = {
                   "trade_no": "2017032121001004070200176844",
                   "code": "10000",
                   "invoice_amount": "20.00",
                   "open_id": "20880072506750308812798160715407",
                   "fund_bill_list": [
                     {
                       "amount": "20.00",
                       "fund_channel": "ALIPAYACCOUNT"
                     }
                   ],
                   "buyer_logon_id": "csq***@sandbox.com",
                   "send_pay_date": "2017-03-21 13:29:17",
                   "receipt_amount": "20.00",
                   "out_trade_no": "out_trade_no15",
                   "buyer_pay_amount": "20.00",
                   "buyer_user_id": "2088102169481075",
                   "msg": "Success",
                   "point_amount": "0.00",
                   "trade_status": "TRADE_SUCCESS", # 支付状态
                   "total_amount": "20.00"
            }  
        """
            code = response.get('code')
            if code == '10000' and response.get('trade_status') == 'TRADE_SUCCESS':
                """ 订单支付成功"""
                # 获取支付交易码
                trade_number = response.get("trade_no")
                # 修改订单的状态
                order.order_status = 2
                order.trade_id = trade_number
                # 响应客户端
                return JsonResponse({"code": 3, "mesg": "支付成功"})
            elif code == '40004' or (code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                """ 接口调用成功，用户正在支付中"""
                import time
                time.sleep(3)
                continue
            else:
                """ 支付失败 """
                return JsonResponse({"code": 4, "errmesg": "支付失败"})














