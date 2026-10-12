from django.contrib.auth.models import User

try:
    u = User.objects.create_user("playtest_temp", "p@t.t", "pT12345!", is_staff=True)
    print("user")
except Exception as e:
    print("err", e)
