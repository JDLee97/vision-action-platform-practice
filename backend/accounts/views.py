"""회원가입. 로그인·로그아웃은 Django 기본 뷰(LoginView, LogoutView)를 그대로 사용한다."""

from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render


def signup(request):
    if request.user.is_authenticated:
        return redirect("analyses:index")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():  # 중복 아이디·비밀번호 규칙·비밀번호 확인 일치를 검사
            user = form.save()
            login(request, user)  # 가입 직후 바로 로그인
            return redirect("analyses:index")
    else:
        form = UserCreationForm()

    return render(request, "accounts/signup.html", {"form": form})
