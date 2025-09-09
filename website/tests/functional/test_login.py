class LoginPageTest:
    def test_can_view_login_page(self, client):
        response = client.get("/", follow=True)
        assert response.status_code == 200
        assert "Log In" in response.content.decode()
        assert response.content.decode().count("Log In") == 1

    def test_can_view_password_reset_page(self, client):
        response = client.get("/accounts/password/reset/")
        assert response.status_code == 200
        assert "Reset My Password" in response.content.decode()
        assert response.content.decode().count("Reset My Password") == 1
