# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-03-28 19:47
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0012_withdrawalrequest_slashed'),
    ]

    operations = [
        migrations.DeleteModel(
            name='State',
        ),
    ]