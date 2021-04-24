from django.contrib import admin
from goods.models import GoodsSKU, IndexGoodsBanner, GoodsType, IndexPromotionBanner
from celery_task.tasks import generate_static_index_page
from django.core.cache import cache


class BaseModelAdmin(admin.ModelAdmin):
    """ 商品模型管理类 """

    def save_model(self, request, obj, form, change):
        """ 当后台数据更改的时候调用"""
        super().save_model(request, obj, form, change)
        # 重新生成index静态页面
        generate_static_index_page.delay()
        # 删除缓存
        cache.delete("context")

    def delete_model(self, request, obj):
        """ 当后台数据删除的时候调用 """
        super().delete_model(request, obj)
        # 重新生成index静态页面
        generate_static_index_page.delay()
        # 删除缓存
        cache.delete("context")


class GoodsSKUAdmin(BaseModelAdmin):
    pass


class IndexGoodsBannerAdmin(BaseModelAdmin):
    pass


class GoodsTypeAdmin(BaseModelAdmin):
    pass


class IndexPromotionBannerAdmin(BaseModelAdmin):
    pass


admin.site.register(GoodsSKU, GoodsSKUAdmin)
admin.site.register(IndexGoodsBanner, IndexGoodsBannerAdmin)
admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
