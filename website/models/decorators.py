from functools import wraps


def check_zero_args(arg_names):
    """
    This decorator is used with the "calculate()" method on an output metric.
    It checks to see if any of the arguments are zero and if so returns zero for the resulting calculation.

    This is used to catch specific errors where a zero value means that the output metric
    isn't relevant for the intervention and would result in things like dividing by zero or a negative value.

    This logic can't be included in the calculate() method because that method is parsed by
      `convert_calculate_to_excel_formula()` and only permits a very limited subset of operations

    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get the function's argument names
            func_args = func.__code__.co_varnames

            # Map arguments to their values
            arg_dict = dict(zip(func_args, args))
            arg_dict.update(kwargs)

            # Check if any specified argument is zero
            for arg_name in arg_names:
                if arg_dict.get(arg_name) == 0:
                    return 0

            # If none of the specified arguments are zero, call the function
            return func(*args, **kwargs)

        return wrapper

    return decorator
