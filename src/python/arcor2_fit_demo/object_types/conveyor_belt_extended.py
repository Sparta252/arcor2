import time
from dataclasses import dataclass

from arcor2 import rest
from arcor2.data.common import ActionMetadata, Pose, StrEnum
from arcor2.data.object_type import Models
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import CollisionObject

from .conveyor_belt import ConveyorBelt, Direction
from .fit_common_mixin import FitCommonMixin, UrlSettings  # noqa:ABS101


class ConveyorBeltExtended(ConveyorBelt):
    mesh_filename = "conveyor_belt_extended.fbx"
    _ABSTRACT = False

    def enable_color_sensor(self, *, an: str | None = None) -> None:
        """Enable GP2 color sensor."""
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/color_sensor/state",
            params={"enable": True},
        )

    enable_color_sensor.__action__ = ActionMetadata()  # type: ignore


    def disable_color_sensor(self, *, an: str | None = None) -> None:
        """Disable GP2 color sensor."""
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/color_sensor/state",
            params={"enable": False},
        )
        
    disable_color_sensor.__action__ = ActionMetadata()  # type: ignore
