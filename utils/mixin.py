from django.contrib.auth.decorators import login_required



class LoginRequiredMixin():
    @classmethod
    def as_view(cls, **initkwargs):
        # 获取视图函数
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)


