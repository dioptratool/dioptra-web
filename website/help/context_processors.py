def help_context(request):
    return {
        "step_guidance_is_open": bool(int(request.COOKIES.get("step_guidance_open", 0))),
    }
