"""Custom exceptions for the application."""


class SquashAPIError(Exception):
    """Raised when Squash API returns an error."""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InvalidSquashTokenError(SquashAPIError):
    """Raised when the Squash token is invalid or expired."""
    def __init__(self, message: str = "Invalid or expired Squash token"):
        super().__init__(message, status_code=401)


class RepositoryError(Exception):
    """Raised when a repository operation fails."""
    pass


class RobotExecutionError(Exception):
    """Raised when Robot Framework execution fails."""
    def __init__(self, message: str, output: str = None):
        self.message = message
        self.output = output
        super().__init__(self.message)
