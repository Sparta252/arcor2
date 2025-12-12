import time
from dataclasses import dataclass
import random
import logging

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

    def enable_color_sensor(self, enable: bool = True, *, an: str | None = None) -> None:
        """Enable GP2 color sensor."""
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/color_sensor/state",
            params={"enable": enable},
        )
    
    enable_color_sensor.__action__ = ActionMetadata()  # type: ignore


    def read_color_sensor(self, *, an: str | None = None) -> int:
        """Read color value from GP2 color sensor."""
        local_logger = logging.getLogger(__name__ + ".color_sensor")
        local_logger.setLevel(logging.DEBUG)  # Len pre tento logger
        resp = rest.call(
            rest.Method.GET,
            f"{self.settings.url}/color_sensor/read",
            return_type=int
        )
        if type(resp) == int:
            return resp
            
        # if hasattr(resp, "json"):
        #     return int(resp.json())

        raise Arcor2Exception("read_color_sensor: cannot parse int from response")


    read_color_sensor.__action__ = ActionMetadata()  # type: ignore

