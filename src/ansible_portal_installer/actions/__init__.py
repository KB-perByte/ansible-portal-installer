"""Actions for installer operations."""

from .build import build_plugins
from .publish import publish_image
from .deploy import deploy_helm
from .verify import verify_deployment, check_prerequisites
from .upgrade import helm_upgrade_command
from .health import health_check_command
from .logs import collect_logs_command
from .templates import generate_config_command

__all__ = [
    "build_plugins",
    "publish_image",
    "deploy_helm",
    "verify_deployment",
    "check_prerequisites",
    "helm_upgrade_command",
    "health_check_command",
    "collect_logs_command",
    "generate_config_command",
]
