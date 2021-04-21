from django.urls.conf import re_path
from goods.views import IndexView, DetailView, ListView

app_name = 'goods'

urlpatterns = [
    re_path(r'^index$', IndexView.as_view(), name='index'),  # 主页面
    re_path(r'^detail/(?P<sku_id>\d+)$', DetailView.as_view(), name="detail"),  # 详情页
    re_path(r'^list/(?P<type_id>\d+)/(?P<show_mode>\w+)/(?P<page_number>\d+)$', ListView.as_view(), name="list"),  # 列表u页
    # re_path(r'^search/$', SHView.as_view(), name='search'), # 搜索


]
