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
















