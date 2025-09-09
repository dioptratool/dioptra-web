import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
class TestUsers:
    def test_email_case_insensitive_search(self):
        user = User.objects.create(email="Hacker@example.com")
        user2 = User.objects.get(email="hacker@example.com")
        assert user == user2

    def test_email_case_insensitive_unique(self):
        User.objects.create(email="Hacker@example.com")
        expected_msg = 'duplicate key value violates unique constraint "users_user_email_key"'
        with pytest.raises(IntegrityError) as e:
            User.objects.create(email="hacker@example.com")
            assert expected_msg == str(e.value)

    def test_emails_are_retrieved_as_lower_case(self):
        User.objects.create(email="HACKER@example.com")
        user_fetched = User.objects.get(email="HACKER@example.com")
        assert user_fetched.email == "hacker@example.com"
