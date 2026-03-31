import time

from datetime import datetime, timezone

from arcor2.data.common import ActionMetadata, Pose, StrEnum, Joint, Position, Orientation, quaternion
from arcor2.data.object_type import Models
from arcor2_object_types.abstract import CollisionObject
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
            time.sleep(0.05)
    
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

    # def grab_moving_object(self, starting_point: Pose, belt_speed: float = 50, *, an: str | None = None) -> Pose:
    #     """Grab an object moving on the conveyor belt"""

    #     basic_vector = [0,1,0];
    # #     print(f"Pokzanie pred as_Quaternion", flush=True)
    # #     q = self.pose.orientation.as_quaternion()
    # #     print(f"Pokzanie pred rotaciou", flush=True)
    # #     direction = quaternion.rotate_vectors(q, basic_vector)  # direction of the belt movement based on the conveyor orientation
    # #     print(f"Pokzanie po rotacii: {direction}, type: {type(direction)}, 0. clen {direction[0]}", flush=True)

    # #     moving_constant = 2.7;

    # #     add_x = direction[0] * 0.001 * belt_speed * moving_constant
    # #     add_y = direction[1] * 0.001 * belt_speed * moving_constant
    # #     add_z = direction[2] * 0.001 * belt_speed * moving_constant + 0.05 # add some vertical offset to ensure the gripper goes above the object

    # #     new_position = Position(
    # #         x=starting_point.position.x + add_x,
    # #         y=starting_point.position.y + add_y,
    # #         z=starting_point.position.z + add_z
    # #     )
    # #     start = datetime.now(timezone.utc)

    # #     print(f"MOVING: {type(direction)}, add_x: {add_x}, add_y: {add_y}, add_z: {add_z}", flush=True)

    # #     catch_pose = Pose(
    # #         orientation=starting_point.orientation,
    # #         position=new_position # simple prediction of the catch position based on the belt speed
    # #     )

    # #     move(catch_pose);

    # #     remain = 2.0 - (datetime.now(timezone.utc) - start).total_milliseconds()
    # #     remain_in_sec = 2.0 - (datetime.now(timezone.utc) - start).total_seconds()
    # #     print(f"Elapsed time for move: {remain} ms a {remain_in_sec} sec", flush=True)
    # #     if remain > 0:
    # #         time.sleep(remain / 1000)
        
    # #     catch_pose.position.z -= 0.05  # move down to the object
    # #     move(catch_pose);
    # #     catch_pose.position.z += 0.05  # move back up with the object
    # #     move(catch_pose);

    # #     position = self.pose
    # #     #print(f"ACTION POINT pose: {point_pose}", flush=True)
    # #     print(f"BELT_INFO_SELF: {self}", flush=True)
    # #     print(f"STARTING_POINT: {starting_point}", flush=True)
    # #     print(f"CATCH_POSE_SELF: {catch_pose}", flush=True)
    # #     #print(f"POSITION: {position}", flush=True)
    # #     return catch_pose
    
    # grab_moving_object.__action__ = ActionMetadata()  # type: ignore