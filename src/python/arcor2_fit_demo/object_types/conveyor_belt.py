import time
from datetime import datetime

from dataclasses import dataclass

from arcor2.data.common import ActionMetadata, Pose, StrEnum
from arcor2.data.object_type import Models
from arcor2.exceptions import Arcor2Exception
from arcor2_object_types.abstract import CollisionObject
from arcor2_web import rest

from .fit_common_mixin import FitCommonMixin, UrlSettings  # noqa:ABS101


class Direction(StrEnum):
    LEFT = "left"
    RIGHT = "right"


@dataclass
class ConveyorBeltSettings(UrlSettings):
    url: str = "http://fit-demo-dobot-magician:5018"


class ConveyorBelt(FitCommonMixin, CollisionObject):
    mesh_filename = "conveyor_belt.fbx"
    _ABSTRACT = False

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Models,
        settings: ConveyorBeltSettings,
    ) -> None:
        super(ConveyorBelt, self).__init__(obj_id, name, pose, collision_model, settings)

        iter: int = 0
        while True:
            if self._started():
                break
            time.sleep(0.1)
            iter += 1

            if iter > 10:
                raise Arcor2Exception("Failed to connect to the Dobot Service.")

    def cleanup(self):
        self.set_velocity(0.0, Direction.RIGHT)

    def set_velocity(
        self, velocity: float = 5.0, direction: Direction = Direction.RIGHT, *, an: None | str = None
    ) -> None:
        """Belt will move indefinitely with given velocity - value is in centimeters per second.

        :param velocity: velocity of the belt in centimeters per second
        :param direction: direction to move (left or right)
        :param an:
        :return:
        """

        assert 0.0 <= velocity <= 12.0

        print(f"DEBUG BEFORE speed_mm_s={velocity} direction={direction}", flush=True)
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/conveyor/speed",
            params={"velocity": velocity, "direction": direction},
        )

        # Testing speed
        # now = datetime.now()
        # mytime = now.strftime("%H:%M:%S.%f")[:-3]
        # print("TIME: ", mytime, flush=True)
        # #print
        #print(f"DEBUG speed_mm_s={velocity} direction={direction}", flush=True)
        # time.sleep(5)  # wait a bit to ensure the command is processed
        # rest.call(
        #     rest.Method.PUT,
        #     f"{self.settings.url}/conveyor/speed",
        #     params={"velocity": 0.0, "direction": direction},
        # )

    set_velocity.__action__ = ActionMetadata()  # type: ignore

    def move_distance(
        self,
        velocity: float = 1.0,
        distance: float = 5.0,
        direction: Direction = Direction.RIGHT,
        *,
        an: None | str = None,
    ) -> None:
        """Belt will move by given distance - values are in centimeters.

        :param velocity: velocity of the belt in centimeters per second
        :param distance: distance to move in centimeters
        :param direction: direction to move (left or right)
        :param an:
        :return:
        """

        assert 0.0 <= velocity <= 12.0
        assert 0.0 <= distance <= 9999.0

        print(f"DEBUG BEFORE speed_mm_s={velocity} direction={direction}", flush=True)
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/conveyor/distance",
            params={"velocity": velocity, "distance": distance, "direction": direction},
        )


        

    move_distance.__action__ = ActionMetadata()  # type: ignore
