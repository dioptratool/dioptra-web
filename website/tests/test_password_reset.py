import json

import pytest
from django.contrib.auth import get_user_model

from website.tests.factories import UserFactory


@pytest.mark.django_db
def test_password_reset_flow(client, mailoutbox):
    """
    Tests the password reset flow: requesting a new password,
    receiving the reset link via email and finally resetting the
    password to a new value.
    """

    # Setuo the user
    user = UserFactory()
    user.set_password("doe")
    user.save()

    # Request new password
    client.post(
        "/accounts/password/reset/",
        data={"email": user.email},
    )
    assert len(mailoutbox) == 2
    assert mailoutbox[1].to == [user.email]
    body = mailoutbox[1].body
    assert body.find("https://") > 0

    # Extract URL for `password_reset_from_key` view and access it
    url = body[body.find("/accounts/password/reset/") :].split('">')[0]
    resp = client.get(url)
    assert resp.status_code == 200
    assert "token_fail" not in resp.context_data

    # Reset the password
    resp = client.post(
        url,
        {
            "password1": "newpass123!",
            "password2": "newpass123!",
        },
        follow=True,
    )
    assert resp.status_code == 200
    assert "token_fail" not in resp.context_data

    # Check the new password is in effect
    user = get_user_model().objects.get(pk=user.pk)
    assert user.check_password("newpass123!")

    # Trying to reset the password against the same URL (or any other
    # invalid/obsolete URL) returns a bad token response
    resp = client.post(url, {"password1": "newpass123!", "password2": "newpass123!"})

    assert resp.context_data["token_fail"]

    # Same should happen when accessing the page directly
    response = client.get(url)
    assert response.context_data["token_fail"]

    # When in XHR views, it should respond with a 400 bad request
    # code, and the response body should contain the JSON-encoded
    # error from the adapter
    response = client.post(
        url,
        {"password1": "newpass123!", "password2": "newpass123!"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code == 400
    data = json.loads(response.content.decode("utf8"))
    assert "invalid" in data["form"]["errors"][0]
