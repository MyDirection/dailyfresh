from django.shortcuts import render
from django.views import View
from django.http import HttpResponse
from goods.models import GoodsType, GoodsSKU, IndexGoodsBanner, IndexTypeGoodsBanner,IndexPromotionBanner
from django.http import HttpResponse, JsonResponse
from goods.models import GoodsSKU, GoodsType, Goods
from django_redis import get_redis_connection
from django.core.paginator import Paginator
from django.conf import settings
from django.template import loader
import os
from django.core.cache import cache


# /index
class IndexView(View):
    def get(self, request):
        """ 主页面 """
        # 尝试获取缓存
        context = cache.get('context')
        if not context:
            """ 还没有设置缓存"""
            user = request.user
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
            # 判断用户是否登录
            if user.is_authenticated:
                con = get_redis_connection("default")
                # 组织key
                cart_key = "cart_%d" % user.id
                cart_count = int(con.hlen(cart_key))

            # 组织模板上下文
            context = {
                "goods_types": goods_types,
                "index_goods_banners": index_goods_banners,
                "index_promotion_banners": index_promotion_banners,
                "cart_count": cart_count,
            }
            # 设置缓存
            cache.set("context", context, 7*24*60*60)
            print("设置缓存")
        return render(request, 'index.html', context)


# /detail
class DetailView(View):
    def get(self, request, sku_id):
        """ 详情页面显示"""
        user = request.user
        # 获取商品信息
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist as e:
            """ 商品不存在"""
            return HttpResponse(status=404)
        # 获取所有商品的类型
        types = GoodsType.objects.all()

        # 获取推荐相关的商品
        recommend_goods = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time').exclude(id=sku_id)[0:2]

        # 获取相同SPU但不同规格的商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=sku_id)

        # 用户购物车商品数量
        cart_count = 0
        # 判断用户是否登录
        if user.is_authenticated:
            # 添加浏览记录
            # 组织用户key
            user_key = "history_%d" % user.id
            cart_key = "cart_%d" % user.id
            # 获取 redis 链接
            con = get_redis_connection("default")
            # 看用户是否已经看过该商品, 如果有则删除，重新添加
            con.lrem(user_key, 0, sku_id)
            con.lpush(user_key, sku_id)
            # 只保留最新的五条数
            con.ltrim(user_key, 0, 4)
            # 获取购物车里的数量
            cart_count = int(con.hlen(cart_key))

        # 组织模板上下文
        params = {
            "sku": sku,
            "types": types,
            "cart_count": cart_count,
            "recommend_goods": recommend_goods,
            "same_spu_skus": same_spu_skus,
        }
        return render(request, "detail.html", params)


# /list
class ListView(View):
    def get(self, request, type_id, show_mode, page_number):
        """ 列表页显示 """
        user = request.user
        page_number = int(page_number)
        # 获取所在的商品类型
        types = GoodsType.objects.all()

        # 判断商品类型是否存在
        try:
            goods_type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            """ 商品类型不存在"""
            return HttpResponse(status=404)

        # 获取该类类型的所有商品
        if show_mode == 'popularity':

            skus = GoodsSKU.objects.filter(type=goods_type).order_by('sales')
        elif show_mode == 'price':

            skus = GoodsSKU.objects.filter(type=goods_type).order_by("price")
        else:

            skus = GoodsSKU.objects.filter(type=goods_type).order_by('-create_time')

        # 获取推荐的商品
        recommend_goods = GoodsSKU.objects.filter(type=goods_type).order_by("-create_time")[0:2]

        # 创建Paginator对象
        p = Paginator(skus, settings.NUM_PAGE)

        # 创建Page对象
        page = p.get_page(page_number)

        # 页码控制，每一页只显示5条页码
        num_pages = p.num_pages
        pages = 0

        if num_pages < 5:
            pages = range(1, num_pages+1)
        elif page_number <= 3:
            pages = range(1, 6)
        elif num_pages - page_number <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page_number - 2, page_number + 3)

        # 购物车数量
        cart_count = 0

        # 判断用户是否登录
        if user.is_authenticated:
            # 获取redis链接
            con = get_redis_connection("default")
            cart_key = "cart_%d" % user.id
            cart_count = int(con.hlen(cart_key))

        # 组织模板上下文
        params = {
            "types": types,
            "goods_type": goods_type,
            "recommend_goods": recommend_goods,
            "skus": skus,
            "cart_count": cart_count,
            "page": page,
            "pages": pages,
            "show_mode": show_mode,
        }


        return render(request, "list.html", params)


# # /search_
# class SHView(View):
#     def get(self, request):
#         return render(request, "search.html")









