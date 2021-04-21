from haystack import indexes
from goods.models import GoodsSKU


# 对莫个类中的某个数据建立索引
class GoodsSKUIndex(indexes.SearchIndex, indexes.Indexable):
    """ 商品索引类 """
    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):
        return GoodsSKU

    def index_queryset(self, using=None):
        return self.get_model().objects.all()