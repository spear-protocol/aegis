from django.conf.urls import url, include
from rest_framework.routers import DefaultRouter
from . import views


urlpatterns = [
    url(r'^$', views.OperatorStatusView.as_view(), name='operator-status'),
    url(r'^tokens/$', views.TokenListView.as_view(), name='token-list'),
    url(r'^(?P<left_token>(0x)?[a-fA-F0-9]{40})/(?P<right_token>(0x)?[a-fA-F0-9]{40})/orderbook$',
        views.SwapListView.as_view(), name='swap-list'),
    url(r'^(?P<left_token>(0x)?[a-fA-F0-9]{40})/(?P<right_token>(0x)?[a-fA-F0-9]{40})/matches$',
        views.MatchingPriceListView.as_view(), name='matching-list'),
    url(r'^(?P<eon_number>[0-9]+)/(?P<token>(0x)?[a-fA-F0-9]{40})/(?P<wallet>(0x)?[a-fA-F0-9]{40})/$',
        views.WalletDataView.as_view(), name='wallet-sync'),
    url(r'^(?P<token>(0x)?[a-fA-F0-9]{40})/(?P<wallet>(0x)?[a-fA-F0-9]{40})/whois$',
        views.WalletIdentifierView.as_view(), name='wallet-sync'),
    url(r'^transactions/$',
        views.ConciseTransactionViewSet.as_view({'get': 'list'}), name='transfer-list'),
    url(r'^transactions/(?P<pk>[0-9]+)/$', views.TransactionViewSet.as_view(
        {'get': 'retrieve'}), name='transfer-detail'),
]
