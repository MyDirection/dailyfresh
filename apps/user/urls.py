from django.urls.conf import re_path
from user.views import LoginView, RegisterView, ActivateView, LogoutView, CenterView, OrderView, AddressView
app_name = 'user'

urlpatterns = [
    re_path(r'^login$', LoginView.as_view(), name="login"), # 登录页面
    re_path(r'^register$', RegisterView.as_view(), name="register"), # 注册页面
    re_path(r'^activate/(?P<secret_data>.*)$', ActivateView.as_view(), name="activate"), # 账号激活
    re_path(r'^logout$', LogoutView.as_view(), name="logout"), # 退出登录

    re_path(r'^center$', CenterView.as_view(), name="center"), # 用户中心
    re_path(r'^order/(?P<page_num>\d+)$', OrderView.as_view(), name="order"), # 用户订单
    re_path(r'^address$', AddressView.as_view(), name="address"), # 用户地址

]