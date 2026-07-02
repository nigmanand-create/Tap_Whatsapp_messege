class DynamicContextError(Exception):
    """Base exception for dynamic context engine."""
    error_code = "INTERNAL_ERROR"


class ConfigurationError(DynamicContextError):
    """Raised when flow configuration is missing or unconfigured in registry."""
    error_code = "FLOW_NOT_FOUND"


class ValidationError(DynamicContextError):
    """Raised when incoming payload fails validation regex or required checks."""
    error_code = "VALIDATION_FAILED"


class AuthenticationError(DynamicContextError):
    """Raised when webhook secret token validation fails."""
    error_code = "UNAUTHORIZED"


class ProviderExecutionError(DynamicContextError):
    """Raised when data provider execution (e.g., BigQuery TVF) fails or times out."""
    error_code = "PROVIDER_EXECUTION_FAILED"
