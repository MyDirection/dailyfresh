from django.conf import settings
from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client


class FDFSStorage(Storage):
    """ 文件上传处理类 """
    def __init__(self, fdfs_conf=None, base_url=None):
        self.fdfs_conf = fdfs_conf
        if fdfs_conf is None:
            self.fdfs_conf = settings.FDFS_CLIENT_CONF

        self.base_url = base_url
        if base_url is None:
            self.base_url = settings.FDFS_SERVER_ADDR


    def _open(self, name, mode='rb'):
        """ 打开文件 """
        pass

    def _save(self, name, content):
        """ 当上传的文件保存时执行"""
        # content 为该文件的file 对象
        # name 为该文件的名字
        # 创建连接
        client = Fdfs_client(self.fdfs_conf)
        # 通过文件内容上传文件
        res = client.upload_by_buffer(content.read())
        if res['Status'] != 'Upload successed.':
            """ 上传文件失败"""
            raise Exception("fdfs文件上传失败！")
        # 返回文件id
        return res.get('Remote file_id')

    def exists(self, name):
        """ 判断文件名是否重复"""
        return False

    def url(self, name):
        """ 返回访问文件的url """
        # name 为文件的id
        return self.base_url + name




