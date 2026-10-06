class CorrectionError(Exception):
    """
    A correction that cannot be applied as requested.

    The message is user-facing: the panel shows it and keeps the form open, and nothing is saved.
    """
