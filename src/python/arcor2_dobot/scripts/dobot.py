#!/usr/bin/env python3

import argparse
import copy
import json
import logging
import os
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Response, jsonify, request

from arcor2 import env
from arcor2.data.common import Joint, Pose, Position, StrEnum, quaternion
from arcor2.data.scene import LineCheck
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2_dobot import version
from arcor2_dobot.dobot import Dobot, DobotApiException, MoveType
from arcor2_dobot.exceptions import DobotGeneral, NotFound, StartError, WebApiError
from arcor2_dobot.m1 import DobotM1
from arcor2_dobot.magician import DobotMagician
from arcor2_scene_data import scene_service
from arcor2_web.flask import RespT, create_app, run_app

logger = get_logger(__name__)


class DobotModels(StrEnum):
    MAGICIAN = "magician"
    M1 = "m1"


URL = os.getenv("ARCOR2_DOBOT_URL", "http://localhost:5018")
DOBOT_PORT = os.getenv("ARCOR2_DOBOT_PORT", "/dev/dobot")
DOBOT_MODEL = DobotModels(os.getenv("ARCOR2_DOBOT_MODEL", DobotModels.MAGICIAN))

SERVICE_NAME = f"Dobot Web API ({DOBOT_MODEL})"

dobot_model_mapping: dict[DobotModels, type[Dobot]] = {DobotModels.MAGICIAN: DobotMagician, DobotModels.M1: DobotM1}

assert set(dobot_model_mapping.keys()) == DobotModels.set()


app = create_app(__name__)

_dobot: None | Dobot = None
_mock = False


def started() -> bool:
    return _dobot is not None


def requires_started(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not started():
            raise StartError("Not started")
        return f(*args, **kwargs)

    return wrapped


@app.route("/state/start", methods=["PUT"])
def put_start() -> RespT:
    """Start the robot.
    ---
    put:
        description: Start the robot.
        tags:
           - State
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **DobotGeneral**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if started():
        raise StartError("Already started.")

    if not isinstance(request.json, dict):
        raise DobotGeneral("Body should be a JSON dict containing Pose.")

    pose = Pose.from_dict(request.json)

    global _dobot

    _dobot = dobot_model_mapping[DOBOT_MODEL](pose, DOBOT_PORT, _mock)

    return Response(status=204)


@app.route("/state/stop", methods=["PUT"])
@requires_started
def put_stop() -> RespT:
    """Stop the robot.
    ---
    put:
        description: Stop the robot.
        tags:
           - State
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    global _dobot
    assert _dobot is not None
    _dobot.cleanup()
    _dobot = None
    return Response(status=204)


@app.route("/state/started", methods=["GET"])
def get_started() -> RespT:
    """Get the current state.
    ---
    get:
        description: Get the current state.
        tags:
           - State
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: boolean
            500:
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    return jsonify(started())


@app.route("/color_sensor/state", methods=["PUT"])
@requires_started
def put_color_sensor_enable() -> RespT:
    """Enable or disable the color sensor.
    ---
    put:
        description: Enable or disable the color sensor.
        tags:
           - Color Sensor
        parameters:
            - in: query
              name: enable
              schema:
                type: boolean
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """   
    state = request.args.get("enable", "false").lower() == "true"
    assert _dobot is not None
    _dobot.set_color_sensor(state)
    return Response(status=204)

@app.route("/color_sensor/read", methods=["GET"])
@requires_started
def get_color_sensor_color() -> RespT:
    """Get the color sensor value.
    ---
    get:
        description: Get the color sensor value.
        tags:
           - Color Sensor
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: integer
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """   
    assert _dobot is not None
    return jsonify(_dobot.read_color_sensor()), 200

@app.route("/color_sensor/color_match", methods=["GET"])
def get_color_sensor_color_match() -> RespT:
    """Check if the color sensor output matches the specified color.
    ---
    get:
        description: Logic comparison of color sensor output value with provided color/s.
        tags:
           - Color Sensor
        parameters:
            - name: colorValue
              in: query
              schema:
                type: integer
                default: 0
            - name: red
              in: query
              schema:
                type: boolean
                default: false
            - name: green
              in: query
              schema:
                type: boolean
                default: false
            - name: blue
              in: query
              schema:
                type: boolean
                default: false
            - name: strict
              in: query
              schema:
                type: boolean
                default: false
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: boolean
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert _dobot is not None

    color_value = int(request.args.get("colorValue", "0"))
    red = request.args.get("red", "false").lower() == "true"
    green = request.args.get("green", "false").lower() == "true"
    blue = request.args.get("blue", "false").lower() == "true"
    strict = request.args.get("strict", "false").lower() == "true" # all components must match

    # color value is a 3-digit number representing RGB components
    # e.g., 101 means Red=1, Green=0, Blue=1
    color_value_red = color_value // 100
    color_value_green = color_value // 10 % 10
    color_value_blue = color_value % 10

    
    if strict:  
        match = ((red == color_value_red) and (green == color_value_green) and (blue == color_value_blue))
    else:  # non-strict mode, at least one component must match
        match = (red == color_value_red == 1) or (green == color_value_green == 1) or (blue == color_value_blue == 1) or (not (red or green or blue))

    return jsonify(match), 200

@app.route("/ir_sensor/state", methods=["PUT"])
@requires_started
def put_ir_sensor_enable() -> RespT:
    """Enable or disable the infrared sensor.
    ---
    put:
        description: Enable or disable the IR sensor.
        tags:
           - IR Sensor
        parameters:
            - in: query
              name: enable
              schema:
                type: boolean
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """   
    state = request.args.get("enable", "false").lower() == "true"
    assert _dobot is not None
    _dobot.set_ir_sensor(state)
    return Response(status=204)


@app.route("/ir_sensor/read", methods=["GET"])
@requires_started
def get_ir_sensor_detect() -> RespT:
    """Get the IR sensor value.
    ---
    get:
        description: Get the IR sensor value.
        tags:
           - IR Sensor
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: boolean
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """   
    assert _dobot is not None
    return jsonify(_dobot.read_ir_sensor()), 200


@app.route("/conveyor/speed", methods=["PUT"])
@requires_started
def put_conveyor_speed() -> RespT:
    """Set the conveyor belt speed.
    ---
    put:
        description: Set the conveyor belt speed in cm/s.
        tags:
           - Conveyor Belt
        parameters:
            - name: velocity
              in: query
              schema:
                type: number
                default: 5.0
                format: float
                minimum: 0
                maximum: 12.0
            - in: query
              name: direction
              schema:
                type: string
                default: forward
                enum:
                    - left
                    - right
              description: Direction
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    speed = float(request.args.get("velocity", default=5.0))
    direction = request.args.get("direction", default="left")

    assert _dobot is not None
    # converting cm/s to mm/s
    _dobot.conveyor_speed(speed * 10, 1 if direction == "left" else -1)
    return Response(status=204)


@app.route("/conveyor/distance", methods=["PUT"])
@requires_started
def put_conveyor_distance() -> RespT:
    """Set the conveyor belt distance.
    ---
    put:
        description: Set the conveyor belt distance.
        tags:
           - Conveyor Belt
        parameters:
            - name: velocity
              in: query
              schema:
                type: number
                default: 5.0
                format: float
                minimum: 0
                maximum: 12.0
            - name: distance
              in: query
              schema:
                type: number
                default: 1
                format: float
                minimum: 0
            - in: query
              name: direction
              schema:
                type: string
                default: left
                enum:
                    - left
                    - right
              description: Direction
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    speed = float(request.args.get("velocity", default=5.0))
    direction = request.args.get("direction", default="left")
    distance = float(request.args.get("distance", default=1))

    assert _dobot is not None
    # converting cm/s to mm/s
    _dobot.conveyor_distance(speed * 10, distance * 10, 1 if direction == "left" else -1)
    return Response(status=204)


@app.route("/eef/pose", methods=["GET"])
@requires_started
def get_eef_pose() -> RespT:
    """Get the EEF pose.
    ---
    get:
        description: Get the EEF pose.
        tags:
           - Robot
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        $ref: Pose
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert _dobot is not None
    return jsonify(_dobot.get_end_effector_pose()), 200


@app.route("/eef/pose", methods=["PUT"])
@requires_started
def put_eef_pose() -> RespT:
    """Set the EEF pose.
    ---
    put:
        description: Set the EEF pose.
        tags:
           - Robot
        parameters:
            - in: query
              name: moveType
              schema:
                type: string
                enum:
                    - JUMP
                    - LINEAR
                    - JOINTS
              required: true
              description: Move type
            - name: velocity
              in: query
              schema:
                type: number
                format: float
                minimum: 0
                maximum: 100
            - name: acceleration
              in: query
              schema:
                type: number
                format: float
                minimum: 0
                maximum: 100
            - in: query
              name: safe
              schema:
                type: boolean
                default: false
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            200:
              description: Ok
            500:
              description: "Error types: **General**, **DobotGeneral**, **StartError**, **NotFound**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert _dobot is not None

    if not isinstance(request.json, dict):
        raise DobotGeneral("Body should be a JSON dict containing Pose.")

    pose = Pose.from_dict(request.json)
    move_type = MoveType(request.args.get("moveType", MoveType.JUMP))
    velocity = float(request.args.get("velocity", default=50.0))
    acceleration = float(request.args.get("acceleration", default=50.0))
    safe = request.args.get("safe") == "true"

    if safe:
        cp = _dobot.get_end_effector_pose()

        ip1 = copy.deepcopy(cp)
        ip2 = copy.deepcopy(pose)

        for _attempt in range(20):
            res = scene_service.line_check(LineCheck(ip1.position, ip2.position))

            if res.safe:
                break

            if move_type == MoveType.LINEAR:
                raise DobotGeneral("There might be a collision.")

            ip1.position.z += 0.01
            ip2.position.z += 0.01

        else:
            raise NotFound("Can't find safe path.")

        logger.debug(f"Collision avoidance attempts: {_attempt}")

        if _attempt > 0:
            _dobot.move(ip1, move_type, velocity, acceleration)
            _dobot.move(ip2, move_type, velocity, acceleration)

    _dobot.move(pose, move_type, velocity, acceleration)
    return Response(status=204)


@app.route("/home", methods=["PUT"])
@requires_started
def put_home() -> RespT:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert _dobot is not None
    _dobot.home()
    return Response(status=204)


@app.route("/hand_teaching", methods=["GET"])
@requires_started
def get_hand_teaching() -> RespT:
    """Get hand teaching status.
    ---
    get:
        description: Get hand teaching status.
        tags:
           - Robot
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: boolean
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert _dobot
    return jsonify(_dobot.hand_teaching_mode)


@app.route("/hand_teaching", methods=["PUT"])
@requires_started
def put_hand_teaching() -> RespT:
    """Set hand teaching status.
    ---
    put:
        description: Set hand teaching status.
        tags:
           - Robot
        parameters:
            - in: query
              name: enabled
              schema:
                type: boolean
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert _dobot
    _dobot.hand_teaching_mode = request.args.get("enabled") == "true"
    return Response(status=204)


@app.route("/suck", methods=["PUT"])
@requires_started
def put_suck() -> RespT:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert _dobot is not None
    _dobot.suck()
    return Response(status=204)


@app.route("/release", methods=["PUT"])
@requires_started
def put_release() -> RespT:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert _dobot is not None
    _dobot.release()
    return Response(status=204)


@app.route("/joints", methods=["GET"])
@requires_started
def get_joints() -> RespT:
    """Get the current state.
    ---
    get:
        description: Get the current state.
        tags:
           - Robot
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: Joint
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert _dobot is not None
    return jsonify(_dobot.robot_joints())


@app.route("/ik", methods=["PUT"])
@requires_started
def put_ik() -> RespT:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: Joint
            500:
              description: "Error types: **General**, **DobotGeneral**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert _dobot is not None

    if not isinstance(request.json, dict):
        raise DobotGeneral("Body should be a JSON dict containing Pose.")

    pose = Pose.from_dict(request.json)
    return jsonify(_dobot.inverse_kinematics(pose))


@app.route("/fk", methods=["PUT"])
@requires_started
def put_fk() -> RespT:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        requestBody:
              content:
                application/json:
                  schema:
                    type: array
                    items:
                        $ref: Joint
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        $ref: Pose
            500:
              description: "Error types: **General**, **DobotGeneral**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert _dobot is not None

    if not isinstance(request.json, list):
        raise DobotGeneral("Body should be a JSON array containing joints.")

    joints = [Joint.from_dict(j) for j in request.json]
    return jsonify(_dobot.forward_kinematics(joints))

@app.route("/pickup_moving_object", methods=["PUT"])
@requires_started
def put_pickup_moving_object() -> RespT:
    """Pick up a moving object from the conveyor belt.
    ---
    put:
        description: >
          Compute catch pose from starting pose, belt pose, belt speed and direction.
          Then move to the catch pose with activated suction cup and pick up the object.
        tags:
           - Robot
        parameters:
            - name: velocity
              in: query
              schema:
                type: number
                format: float
                minimum: 0
                maximum: 12
              description: Speed of the conveyor belt in cm/s.
              default: 5.0
            - name: direction
              in: query
              schema:
                type: string
                default: left
                enum:
                    - left
                    - right
              description: Direction of the conveyor belt movement.
        requestBody:
              content:
                application/json:
                  schema:
                    type: array
                    items:
                      $ref: Pose
                    description: "[starting pose, belt pose]"
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        $ref: Pose
            500:
              description: "Error types: **General**, **DobotGeneral**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert _dobot is not None

    if not isinstance(request.json, list) or len(request.json) != 2:
        raise DobotGeneral("Body should be a JSON array with [starting_pose, belt_pose].")

    starting_pose = Pose.from_dict(request.json[0])
    belt_pose = Pose.from_dict(request.json[1])
    velocity = float(request.args.get("velocity", default=5.0))
    belt_speed_mm_s = velocity * 10
    direction = request.args.get("direction", default="left")

    # Calculate the catch pose based on the starting pose, belt pose, belt speed and direction.
    basic_vector = [0, 1, 0]
    q = belt_pose.orientation.as_quaternion()
    direction_vector = quaternion.rotate_vectors(q, basic_vector)
    moving_constant = 2.0 + 0.7  # (2.0) time to reach above the catch position and (0.7) time to move down to grasp + both with some safety margin
    add_x = direction_vector[0] * 0.001 * belt_speed_mm_s * moving_constant * (1 if direction == "left" else -1)
    add_y = direction_vector[1] * 0.001 * belt_speed_mm_s * moving_constant * (1 if direction == "left" else -1)
    add_z = direction_vector[2] * 0.001 * belt_speed_mm_s * moving_constant + 0.05  # add some vertical offset (pickup)

    catch_position = Position(
        x=starting_pose.position.x + add_x,
        y=starting_pose.position.y + add_y,
        z=starting_pose.position.z + add_z
    )

    catch_pose = Pose(
        orientation=starting_pose.orientation,
        position=catch_position
    )

    # Move to the catch pose with activated suction cup and pick up the object.
    started = datetime.now(timezone.utc)
    _dobot.suck()
    _dobot.move(catch_pose, MoveType.JOINTS, 100, 100)

    remaining_time = 2.15 - (datetime.now(timezone.utc) - started).total_seconds() # time to reach above the catch position + safety margin to ensure object is in the right position
    if remaining_time > 0:
        time.sleep(remaining_time)

    catch_pose.position.z -= 0.05  # move down to the object
    _dobot.move(catch_pose, MoveType.JOINTS, 100, 100)
    catch_pose.position.z += 0.05  # move back up with the object


    return jsonify(catch_pose), 200


@app.errorhandler(DobotApiException)
def handle_dobot_exception(e: DobotApiException) -> tuple[str, int]:
    return json.dumps(DobotGeneral(str(e)).to_dict()), 500


def main() -> None:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument("-m", "--mock", action="store_true", default=env.get_bool("ARCOR2_DOBOT_MOCK"))

    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.DEBUG if env.get_bool("ARCOR2_DOBOT_DEBUG") else logging.INFO,
    )

    args = parser.parse_args()
    logger.setLevel(args.debug)

    global _mock
    _mock = args.mock
    if _mock:
        logger.info("Starting as a mock!")

    if not args.swagger:
        scene_service.wait_for()

    run_app(
        app,
        SERVICE_NAME,
        version(),
        port_from_url(URL),
        [Pose, Joint, WebApiError],
        args.swagger,
        dependencies={"ARCOR2 Scene": "1.0.0"},
    )

    if _dobot:
        _dobot.cleanup()


if __name__ == "__main__":
    main()
