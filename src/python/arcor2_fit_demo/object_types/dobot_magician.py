from dataclasses import dataclass
from datetime import datetime, timezone
import time

from arcor2.data.common import ActionMetadata, Pose, StrEnum, Joint, Position, Orientation, quaternion
from arcor2_web import rest

from .abstract_dobot import AbstractDobot, MoveType  # noqa:ABS101
from .fit_common_mixin import UrlSettings  # noqa:ABS101

class Direction(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    
class Joints(StrEnum):
    J1 = "magician_joint_1"
    J2 = "magician_joint_2"
    J3 = "magician_joint_3"
    J4 = "magician_joint_4"
    J5 = "magician_joint_5"


@dataclass
class MagicianSettings(UrlSettings):
    url: str = "http://fit-demo-dobot-magician:5018"


class DobotMagician(AbstractDobot):
    _ABSTRACT = False
    urdf_package_name = "dobot-magician.zip"

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: MagicianSettings) -> None:
        super(DobotMagician, self).__init__(obj_id, name, pose, settings)
        self._start()

    def move_to_calibration_pose(self) -> None:
        joint_values = [  # TODO define as pose
            Joint(Joints.J1, -0.0115),
            Joint(Joints.J2, 0.638),
            Joint(Joints.J3, -0.5486),
            Joint(Joints.J4, -0.0898),
            Joint(Joints.J5, 1.41726),
        ]

        self.move(self.forward_kinematics("", joint_values), MoveType.LINEAR, 50)

    def inverse_kinematics(
        self,
        end_effector_id: str,
        pose: Pose,
        start_joints: None | list[Joint] = None,
        avoid_collisions: bool = True,
    ) -> list[Joint]:
        """Computes inverse kinematics.

        :param end_effector_id: IK target pose end-effector
        :param pose: IK target pose
        :param start_joints: IK start joints (not supported)
        :param avoid_collisions: Return non-collision IK result if true (not supported)
        :return: Inverse kinematics
        """

        return rest.call(rest.Method.PUT, f"{self.settings.url}/ik", body=pose, list_return_type=Joint)

    def forward_kinematics(self, end_effector_id: str, joints: list[Joint]) -> Pose:
        """Computes forward kinematics.

        :param end_effector_id: Target end effector name
        :param joints: Input joint values
        :return: Pose of the given end effector
        """

        return rest.call(rest.Method.PUT, f"{self.settings.url}/fk", body=joints, return_type=Pose)

    # def pickup_moving_object(self, starting_pose: Pose, target_pose: Pose, belt_speed: float = 50, direction: Direction = Direction.LEFT, *, an: str | None = None) -> None:
    #     """Pickup an object moving on the conveyor belt"""
        
    #     basic_vector = [0,1,0];
    #     q = self.pose.orientation.as_quaternion()
    #     direction = quaternion.rotate_vectors(q, basic_vector)  # direction of the belt movement based on the conveyor orientation
    #     moving_constant = 2.7;
    #     add_x = direction[0] * 0.001 * belt_speed * moving_constant
    #     add_y = direction[1] * 0.001 * belt_speed * moving_constant
    #     add_z = direction[2] * 0.001 * belt_speed * moving_constant + 0.05 # add some vertical offset to ensure the gripper goes above the object
    #     catch_position = Position(
    #         x=target_pose.position.x + add_x,
    #         y=target_pose.position.y + add_y,
    #         z=target_pose.position.z + add_z
    #     )
    #     catch_pose = Pose(
    #         orientation=target_pose.orientation,
    #         position=catch_position
    #     )
    #     start = datetime.now(timezone.utc)
    #     self.move(catch_pose, MoveType.JOINTS, 100, 100, safe=True)

    #     # remain_in_sec = 2.0 - (datetime.now(timezone.utc) - start).total_seconds()
    #     # if remain_in_sec > 0:
    #     #     time.sleep(remain_in_sec)
    #     time.sleep(2)

    #     catch_pose.position.z -= 0.05  # move down to the object
    #     self.move(catch_pose, MoveType.JOINTS, 100, 100, safe=True)
    #     catch_pose.position.z += 0.05  # move back up with the object

    # pickup_moving_object.__action__ = ActionMetadata()  # type: ignore