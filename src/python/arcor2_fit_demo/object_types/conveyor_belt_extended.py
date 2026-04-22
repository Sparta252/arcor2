import time

from datetime import datetime, timezone

from arcor2.data.common import ActionMetadata, Pose, StrEnum, Joint, Position, WebApiError
from arcor2.data.object_type import Models
from arcor2_object_types.abstract import CollisionObject
from arcor2.exceptions import Arcor2Exception
from arcor2_web import rest

from .conveyor_belt import ConveyorBelt, Direction, ConveyorBeltSettings 
from .fit_common_mixin import FitCommonMixin, UrlSettings  # noqa:ABS101


class ConveyorBeltExtended(ConveyorBelt):
    #storage_url: str = "http://fit-demo-storage:5018"
    mesh_filename = "conveyor_belt_extended.fbx"
    _ABSTRACT = False

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Models,
        settings: ConveyorBeltSettings,
    ) -> None:
        super().__init__(obj_id, name, pose, collision_model, settings)

        self._stop_ir_waiting = False
        self.color_sensor_active = False
        self.ir_sensor_active = False

    def cleanup(self) -> None:
        self.stop_ir_waiting()
        try:
            self.set_velocity(0.0, Direction.RIGHT, an=None)
        except (WebApiError, rest.RestException):
            pass  # ignore errors during cleanup

        try:
            if self.color_sensor_active:
                self.enable_color_sensor(False)
            if self.ir_sensor_active:
                self.enable_ir_sensor(False)
        except (WebApiError, rest.RestException):
            pass  # ignore errors during cleanup

    def enable_color_sensor(self, enable: bool = True, *, an: str | None = None) -> None:
        """Enable GP2 color sensor.

        :param enable: bool - True to enable, False to disable
        """
        self.color_sensor_active = enable
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/color_sensor/state",
            params={"enable": enable},
        )
    
    enable_color_sensor.__action__ = ActionMetadata()  # type: ignore

    def read_color_sensor(self, *, an: str | None = None) -> int:
        """Read color value from GP2 color sensor."""
        resp = rest.call(
            rest.Method.GET,
            f"{self.settings.url}/color_sensor/read",
            return_type=int
        )
        if type(resp) == int:
            return resp

        raise Arcor2Exception("read_color_sensor: cannot parse int from response")

    read_color_sensor.__action__ = ActionMetadata()  # type: ignore

    def ifColor(self, color_value: int, red: bool = False, green: bool = False, blue: bool = False, strict_mode: bool = False, *, an: str | None = None) -> bool:
        """Check if the color sensor reads the specified color value.

        :param color_value: 3-digit number representing RGB components (e.g., 101 means Red=1, Green=0, Blue=1)
        :param red: whether red component is detected
        :param green: whether green component is detected
        :param blue: whether blue component is detected
        :param strict_mode: if True, all components must match; if False, any component match is sufficient
        :param an:
        :return: True if the color matches the specified value, False otherwise
        """
        resp = rest.call(
            rest.Method.GET,
            f"{self.settings.url}/color_sensor/color_match",
            params={"color_value": color_value, 
                    "red": red, 
                    "green": green, 
                    "blue": blue, 
                    "strict_mode": strict_mode},
            return_type=bool
        )

        if type(resp) == bool:
            return resp
        
        raise Arcor2Exception("ifColor: cannot parse bool from response")
        
    ifColor.__action__ = ActionMetadata()  # type: ignore
        
    def enable_ir_sensor(self, enable: bool = True, *, an: str | None = None) -> None:
        """Enable GP4 IR sensor.

        :param enable: bool - True to enable, False to disable
        """
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/ir_sensor/state",
            params={"enable": enable},
        )
        self.ir_sensor_active = enable
    
    enable_ir_sensor.__action__ = ActionMetadata()  # type: ignore

    def read_ir_sensor(self, *, an: str | None = None) -> bool:
        """Read value from GP4 IR sensor."""

        resp = rest.call(
            rest.Method.GET,
            f"{self.settings.url}/ir_sensor/read",
            return_type=bool
        )
        if type(resp) == bool:
            return resp
            
        raise Arcor2Exception("read_ir_sensor: cannot parse bool from response")
    
    read_ir_sensor.__action__ = ActionMetadata()  # type: ignore

    def stop_ir_waiting(self) -> None:
        """Stop waiting for IR sensor detection."""
        self._stop_ir_waiting = True
    

    def read_ir_until_detected(self, *, an: str | None = None) -> None:
        """Read value from GP4 IR sensor until object is detected."""

        self._stop_ir_waiting = False
        while not self.read_ir_sensor() and not self._stop_ir_waiting:
            time.sleep(0.05)
    
    read_ir_until_detected.__action__ = ActionMetadata(composite=True)  # type: ignore

    def get_pose(self, *, an: str | None = None) -> Pose:
        """Get current pose of the conveyor belt."""
        pose = self.pose
        return pose

    get_pose.__action__ = ActionMetadata()  # type: ignore

ConveyorBeltExtended.CANCEL_MAPPING[ConveyorBeltExtended.read_ir_until_detected.__name__] = ConveyorBeltExtended.stop_ir_waiting.__name__