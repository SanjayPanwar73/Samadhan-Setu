class DomainError(Exception):
    """Business-rule violation rendered as ``{code, detail}`` with an HTTP status."""

    def __init__(self, code: str, detail: str, status_code: int = 409, extra: dict | None = None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code
        self.extra = extra or {}
