from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AccountTests(TestCase):
    def test_signup_logs_in_and_redirects(self):
        response = self.client.post(reverse("signup"), {
            "username": "student01", "password1": "VisionAi!2026", "password2": "VisionAi!2026",
        })
        self.assertRedirects(response, reverse("analyses:index"))
        self.assertTrue(User.objects.filter(username="student01").exists())

    def test_duplicate_username_rejected(self):
        User.objects.create_user("student01", password="VisionAi!2026")
        response = self.client.post(reverse("signup"), {
            "username": "student01", "password1": "VisionAi!2026", "password2": "VisionAi!2026",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="student01").count(), 1)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("analyses:index"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('analyses:index')}")

    def test_logout_requires_post(self):
        User.objects.create_user("student01", password="VisionAi!2026")
        self.client.login(username="student01", password="VisionAi!2026")
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))
