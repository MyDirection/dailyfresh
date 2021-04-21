from django.urls.conf import re_path
from order.views import PlaceOrderView, CreateOrderView


app_name = 'order'

urlpatterns = [
    re_path(r'^place_order$',PlaceOrderView.as_view(), name='place_order'),  # 提交订单页
    re_path(r'^create_order$', CreateOrderView.as_view(), name="create_order"),  # 创建订单
]