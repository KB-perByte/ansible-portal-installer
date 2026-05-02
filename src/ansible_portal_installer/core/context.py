"""Installation context that tracks state across operations."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class InstallContext:
    """Context object that maintains state during installation."""

    # Timestamps
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # Build state
    build_completed: bool = False
    plugins_built: list[str] = field(default_factory=list)
    build_output_dir: Optional[Path] = None

    # Publish state
    publish_completed: bool = False
    image_reference: Optional[str] = None
    registry_authenticated: bool = False

    # Deploy state
    deploy_completed: bool = False
    namespace_created: bool = False
    secrets_created: list[str] = field(default_factory=list)
    helm_release_name: Optional[str] = None
    portal_route: Optional[str] = None

    # Verification state
    verification_passed: bool = False
    verification_errors: list[str] = field(default_factory=list)

    def mark_completed(self) -> None:
        """Mark the installation as completed."""
        self.completed_at = datetime.now()

    @property
    def duration(self) -> Optional[float]:
        """Get installation duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict:
        """Convert context to dictionary for display."""
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration,
            "build_completed": self.build_completed,
            "plugins_built": self.plugins_built,
            "publish_completed": self.publish_completed,
            "image_reference": self.image_reference,
            "deploy_completed": self.deploy_completed,
            "helm_release_name": self.helm_release_name,
            "portal_route": self.portal_route,
            "verification_passed": self.verification_passed,
        }
