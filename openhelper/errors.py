class AppError(Exception):
    """An error that can be presented in the active UI language."""

    def __init__(self, code: str, **params):
        self.key = code
        self.params = params
        super().__init__(code)

