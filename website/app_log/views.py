from ombucore.admin.views import AddView, ChangeView, DeleteView

add_view = AddView
change_view = ChangeView
delete_view = DeleteView


class ModelFormViewLogMixin:
    log_fn = None

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.log_fn:
            self.log_fn(self.object, self.request.user)
        return response
