from django.db import models


class AdminSiteModel(models.Model):
    """
    Empty model class that isn't managed so it won't create a database table.

    Used primarily to add arbitrary permissions that aren't associated with a
    model.
    """

    class Meta:
        managed = False  # Don't create a database table
        permissions = (("access_admin_central", "Access Admin Central"),)
