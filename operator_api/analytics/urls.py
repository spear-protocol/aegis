from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^wallets$', views.WalletsView.as_view(), name='analytics-wallets'),
    url(r'^transactions$', views.TransfersView.as_view(),
        name='analytics-transfers'),
    url(r'^challenges$', views.ChallengesView.as_view(),
        name='analytics-challenges'),
    url(r'^deposits$', views.DepositsView.as_view(), name='analytics-deposits'),
    url(r'^withdrawals$', views.WithdrawalsView.as_view(),
        name='analytics-withdrawals'),
]
