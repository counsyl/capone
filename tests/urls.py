from django.conf import settings
from django.contrib import admin
from django.conf.urls import include
from django.conf.urls import patterns
from django.conf.urls import url


admin.autodiscover()


urlpatterns = patterns(
    '',
    url(r'^admin/', include(admin.site.urls)),
)

if settings.DEBUG:
    urlpatterns += patterns(
        'django.contrib.staticfiles.views',
        url(r'^static/(?P<path>.*)$', 'serve'),
    )
