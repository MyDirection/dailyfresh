from django.urls.conf import re_path
from cart.views import AddCartView, CartView, DeleteView, UpdateView

app_name = 'cart'

urlpatterns = [
    re_path(r'^add_cart$', AddCartView.as_view(), name="add_cart"),  # 添加到购物车
    re_path(r'^cart$', CartView.as_view(), name='cart'),    # 购物车
    re_path(r'^delete$', DeleteView.as_view(), name='delete'),  # 删除
    re_path(r'^update$', UpdateView.as_view(), name="update"),     # 更新
]