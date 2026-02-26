import time

from arcor2.data.common import ActionMetadata, Pose
from arcor2.exceptions import Arcor2Exception
from arcor2_web import rest

from .conveyor_belt import ConveyorBelt, Direction


class ConveyorBeltExtended(ConveyorBelt):
    mesh_filename = "conveyor_belt_extended.fbx"
    _ABSTRACT = False

    def enable_color_sensor(self, enable: bool = True, *, an: str | None = None) -> None:
        """Enable GP2 color sensor.
        :param enable: bool - True to enable, False to disable
        """
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
        :param color_value: int - 3-digit number representing RGB components (e.g., 101 means Red=1, Green=0, Blue=1)
        :param red: bool - whether red component is detected
        :param green: bool - whether green component is detected
        :param blue: bool - whether blue component is detected
        :param strict_mode: bool - if True, all components must match; if False, any component match is sufficient
        """
        # color value is a 3-digit number representing RGB components
        # e.g., 101 means Red=1, Green=0, Blue=1
        color_value_red = color_value // 100
        color_value_green = color_value // 10 % 10
        color_value_blue = color_value % 10
        if strict_mode:  # all components must match
            return (red == color_value_red) and (green == color_value_green) and (blue == color_value_blue)
        else:  # non-strict mode, at least one component must match
            return (red == color_value_red == 1) or (green == color_value_green == 1) or (blue == color_value_blue == 1) or (not (red or green or blue))
        
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

    def read_ir_until_detected(self, *, an: str | None = None) -> None:
        """Read value from GP4 IR sensor until object is detected."""
        while not self.read_ir_sensor():
            time.sleep(0.1)
    
    read_ir_until_detected.__action__ = ActionMetadata(composite=True)  # type: ignore

    def test_position(self, *, an: str | None = None) -> Pose:
        """Get middle position of the conveyor belt."""
        position = self.pose
        print(position)
        return position
    
    test_position.__action__ = ActionMetadata()  # type: ignore