from django.conf import settings
import requests
import random
import time

messages_cache = {}

def send_message(subject, content):
    """
    Small markdown for beauty and send message to slack channel via webhooking
    Notification url should looks like this:
        https://hooks.slack.com/services/XXXXXX/YYYYYY/ZZZZZZZ
    Details can be found here:
        https://api.slack.com/messaging/webhooks#posting_with_webhooks
    """
    t = time.time()
    data = {
        "blocks": [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Server*: {settings.SERVER_NAME}\n*Subject*: {subject}\n*Message* : {content}"
            }
        }]}
    url = settings.NOTIFICATION_HOOK_URL
    previous_version = messages_cache.get(subject)
    if url and (previous_version is None or previous_version+60*60 < t) :
        requests.post(url, json=data)
        messages_cache[subject] = t

def send_admin_email(subject, content):
    """ Write admin emailing logic here
    We don't use email, so we just send Slack messages :) """

    if settings.DEBUG:
        send_message(subject, content)
    elif not settings.DEBUG:
        send_message(subject, content)
