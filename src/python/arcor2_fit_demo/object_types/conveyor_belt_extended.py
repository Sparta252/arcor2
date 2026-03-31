from arcor2.data.common import ActionMetadata, Pose
from arcor2.exceptions import Arcor2Exception
from arcor2_web import rest
#from src.python.arcor2_calibration import quaternions

from .conveyor_belt import ConveyorBelt, Direction
from .fit_common_mixin import FitCommonMixin, UrlSettings  # noqa:ABS101


class ConveyorBeltExtended(ConveyorBelt):
    #storage_url: str = "http://fit-demo-storage:5018"
    mesh_filename = "conveyor_belt_extended.fbx"
    _ABSTRACT = False

    def cleanup(self):
        self.set_velocity(0.0, Direction.RIGHT)
        self.enable_color_sensor(False)
        self.enable_ir_sensor(False)

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

    def ifColor(self, red: bool = False, green: bool = False, blue: bool = False, strict_mode: bool = False, *, an: str | None = None) -> bool:
        """Check if the color sensor reads the specified color.

        :param red: whether red component should be detected
        :param green: whether green component should be detected
        :param blue: whether blue component should be detected
        :param strict_mode: if True, all components must match; if False, any component match is sufficient
        :param an:
        :return: True if the color matches the specified value, False otherwise
        """
        return rest.call(
            rest.Method.POST,
            f"{self.settings.url}/color_sensor/ifColor",
            params={"red": red, "green": green, "blue": blue, "strict_mode": strict_mode},
            return_type=bool,
        )
        
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
        """Wait until the IR sensor detects an object."""
        rest.call(
            rest.Method.POST,
            f"{self.settings.url}/ir_sensor/wait_until_detected",
        )
    
    read_ir_until_detected.__action__ = ActionMetadata(composite=True)  # type: ignore

    def test_position(self, *, an: str | None = None) -> Pose:
        """Get middle position of the conveyor belt."""
        
        position = self.pose
        #print(f"ACTION POINT pose: {point_pose}", flush=True)
        print(f"BELT_INFO_SELF: {self}", flush=True)
        #print(f"POSITION: {position}", flush=True)
        return position
    
    test_position.__action__ = ActionMetadata()  # type: ignore

    def get_pose(self, *, an: str | None = None) -> Pose:
        """Get current pose of the conveyor belt."""
        pose = self.pose
        return pose

    get_pose.__action__ = ActionMetadata()  # type: ignore
