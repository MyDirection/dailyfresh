from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from goods.models import GoodsSKU
from django.views import View
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin


# /add_cart
class AddCartView(View):
    def post(self, request):
        """ 添加到购物车 """
        # 获取数据
        user = request.user
        # 判断用户是否登录
        if not user.is_authenticated:
            return JsonResponse({"code": "00", "err_mesg": "请登录"})

        sku_id = request.POST.get("sku_id")
        count = int(request.POST.get("count"))

        # 校验数据
        if not all([sku_id, count]):
            """ 数量不合法 """
            return JsonResponse({"code": "01", "err_mesg": "数据不完整"})

        if count <= 0:
            return JsonResponse({"code": 0, "err_mesg": "数量不能为小于且不能等于零"})

        # todo: 添加到购物车
        # 判断商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({"code": 1, "err_mesg": "商品不存在"})

        # 获取redis 连接对象
        con = get_redis_connection("default")
        # 组织key
        user_key = "cart_%d" % user.id
        # 尝试获取曾经 曾添加的商品数量
        past_count = con.hget(user_key, sku_id)
        if not past_count:
            past_count = 0

        count = int(past_count) + count
        # 判断商品库存是否足够
        if sku.stock < count:
            """ 商品库存不足 """
            return JsonResponse({"code": 2, "err_mesg": "商品库存不足"})
        # 将添加的商品信息添加到redis数据库
        con.hset(user_key, sku.id, count)

        # 获取最新的购物车里的数量
        cart_count = int(con.hlen(user_key))
        return JsonResponse({"code": 3, "mesg": "添加成功", "cart_count": cart_count})


# /cart
class CartView(LoginRequiredMixin, View):
    def get(self, request):
        """ 购物车页面 """
        user = request.user

        # todo: 获取用户购物车中的商品
        # 获取redis连接
        con = get_redis_connection('default')
        # 组织key
        cart_key = "cart_%d" % user.id
        sku_ids = con.hkeys(cart_key)   # 也可直接使用con.hgetall() --直接获取所有属性和值
        skus = []
        total_count = 0
        subtotal = 0
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id)
            count = int(con.hget(cart_key, sku_id))
            subtotal += round(sku.price * int(count), 2)
            total_count += count
            # 动态的添加属性， 给sku添加数量, 添加小记
            sku.count = count
            sku.subtotal = subtotal
            skus.append(sku)
            subtotal = 0

        # 组织模板上下文
        params = {
            "skus": skus,
            "total_count": total_count,
        }

        return render(request, "cart.html", params)


# /delete
class DeleteView(View):
    def post(self, request):
        """ 删除 """
        user = request.user
        # 验证用户是否登录
        if not user.is_authenticated:
            """ 用户未登录"""
            return JsonResponse({"code": 0, "err_mesg": "请登录"})
        # 获取数据
        sku_id = request.POST.get("sku_id")

        # 验证商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            """ 商品不存在"""
            return JsonResponse({"code": 1, "err_mesg": "该商品不存在，无法删除"})

        # todo： 删除购物车中的商品
        con = get_redis_connection("default")
        # 组织key
        cart_key = "cart_%d" % user.id
        # 删除商品
        con.hdel(cart_key, sku.id)
        # 获取最新的购物车商品数量
        sku_count = con.hvals(cart_key)
        total_count = 0
        # 累加商品的件数
        for count in sku_count:
            total_count += int(count)

        return JsonResponse({'code': 2, "total_count": total_count})


# /update
class UpdateView(View):
    def post(self, request):
        """ 更新购物车中的商品数量 """
        # 接受数据
        user = request.user
        sku_id = request.POST.get('sku_id')
        sku_count = int(request.POST.get('sku_count'))

        # 判断用户是否登录
        if not user.is_authenticated:
            """ 用户未登录"""
            return JsonResponse({"code": 0, "err_mesg": "请登录"})
        # 校验数据
        if not all([sku_id, sku_count]):
            """ 数据不完整 """
            return JsonResponse({'code': 1, "err_mesg": "数据不完整"})

        if sku_count <= 0:
            """ 数量不正确"""
            return JsonResponse({'code': 2, "err_mesg": "数量不得小于0"})

        # 验证视频是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            """ 商品不存在"""
            return JsonResponse({"code": 3, "err_mesg": "商品不存在"})

        # todo: 更新商品数量
        # 判断商品数量是否超过库存
        if sku_count > sku.stock:
            """ 库存不足"""
            return JsonResponse({"code": 4, 'err_mesg': '库存不足'})
        # 获取redis 连接
        con = get_redis_connection("default")
        # 组织key
        cart_key = "cart_%d" % user.id
        con.hset(cart_key, sku_id, sku_count)

        # 获取最新的商品数量
        total_count = 0
        sku_counts = con.hvals(cart_key)
        for count in sku_counts:
            total_count += int(count)

        return JsonResponse({'code': 5, "total_count": total_count})





