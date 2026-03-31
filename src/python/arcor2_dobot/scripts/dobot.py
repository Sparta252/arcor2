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
    state_str = request.args.get("enable", "false").lower()
    if state_str == "true":
        state = True
    else:
        state = False
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

@app.route("/ir_sensor/state", methods=["PUT"])
@requires_started
def put_ir_sensor_enable() -> RespT:
    """Enable or disable the infraRed sensor.
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
    state_str = request.args.get("enable", "false").lower()
    if state_str == "true":
        state = True
    else:
        state = False
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


@app.route("/color_sensor/ifColor", methods=["POST"])
@requires_started
def post_color_sensor_if_color() -> RespT:
    """Check if the color sensor reads the specified color.
    ---
    post:
        description: Read the color sensor and check if it matches the specified color components.
        tags:
           - Color Sensor
        parameters:
            - in: query
              name: red
              schema:
                type: boolean
                default: false
            - in: query
              name: green
              schema:
                type: boolean
                default: false
            - in: query
              name: blue
              schema:
                type: boolean
                default: false
            - in: query
              name: strictMode
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
    color_value = _dobot.read_color_sensor()
    red = request.args.get("red", "false").lower() == "true"
    green = request.args.get("green", "false").lower() == "true"
    blue = request.args.get("blue", "false").lower() == "true"
    strict_mode = request.args.get("strictMode", "false").lower() == "true"

    color_value_red = color_value // 100
    color_value_green = color_value // 10 % 10
    color_value_blue = color_value % 10

    if strict_mode:
        result = (int(red) == color_value_red) and (int(green) == color_value_green) and (int(blue) == color_value_blue)
    else:
        result = (red and color_value_red == 1) or (green and color_value_green == 1) or (blue and color_value_blue == 1) or (not (red or green or blue))

    print(f"DEBUG ifColor: color_value={color_value} red={red} green={green} blue={blue} strict_mode={strict_mode} result={result}", flush=True)
    return jsonify(result), 200


@app.route("/ir_sensor/wait_until_detected", methods=["POST"])
@requires_started
def post_ir_wait_until_detected() -> RespT:
    """Wait until the IR sensor detects an object.
    ---
    post:
        description: Poll the IR sensor at 50 ms intervals until an object is detected or timeout is reached.
        tags:
           - IR Sensor
        parameters:
            - in: query
              name: timeout
              schema:
                type: number
                format: float
                default: 30.0
        responses:
            204:
              description: Ok - object detected
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert _dobot is not None
    timeout = float(request.args.get("timeout", "30.0"))
    start = time.monotonic()
    while not _dobot.read_ir_sensor():
        if time.monotonic() - start > timeout:
            raise DobotGeneral("IR sensor detection timeout.")
        time.sleep(0.05)
    return Response(status=204)


@app.route("/pickup/moving_object", methods=["POST"])
@requires_started
def post_pickup_moving_object() -> RespT:
    """Pick up an object moving on the conveyor belt.
    ---
    post:
        description: >
          Compute catch pose from starting pose, belt pose and belt speed,
          then execute suck + move + timed wait + move down to pick up the object.
        tags:
           - Robot
        parameters:
            - in: query
              name: beltSpeed
              schema:
                type: number
                format: float
                default: 5.0
              description: Belt speed in cm/s
        requestBody:
              content:
                application/json:
                  schema:
                    type: array
                    items:
                        $ref: Pose
                    description: "[starting_pose, belt_pose]"
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
    belt_speed_cm_s = float(request.args.get("beltSpeed", "5.0"))
    belt_speed_mm_s = belt_speed_cm_s * 10  # convert cm/s to mm/s

    basic_vector = [0, 1, 0]
    q = belt_pose.orientation.as_quaternion()
    direction = quaternion.rotate_vectors(q, basic_vector)
    moving_constant = 2.7
    add_x = direction[0] * 0.001 * belt_speed_mm_s * moving_constant
    add_y = direction[1] * 0.001 * belt_speed_mm_s * moving_constant
    add_z = direction[2] * 0.001 * belt_speed_mm_s * moving_constant + 0.05  # add vertical offset

    catch_position = Position(
        x=starting_pose.position.x + add_x,
        y=starting_pose.position.y + add_y,
        z=starting_pose.position.z + add_z,
    )
    catch_pose = Pose(orientation=starting_pose.orientation, position=catch_position)

    print(f"DEBUG pickup: belt_speed_cm_s={belt_speed_cm_s} belt_speed_mm_s={belt_speed_mm_s} catch_pose={catch_pose}", flush=True)

    start = datetime.now(timezone.utc)
    _dobot.suck()
    _dobot.move(catch_pose, MoveType.JOINTS, 100, 100)

    remain_in_sec = 2.15 - (datetime.now(timezone.utc) - start).total_seconds()
    if remain_in_sec > 0:
        print(f"Waiting for {remain_in_sec} seconds to synchronize with the moving object", flush=True)
        time.sleep(remain_in_sec)

    print(f"MOVING DOWN", flush=True)
    catch_pose.position.z -= 0.05  # move down to the object
    _dobot.move(catch_pose, MoveType.JOINTS, 100, 100)
    catch_pose.position.z += 0.05
    print(f"MOVING UP", flush=True)
    #_dobot.move(catch_pose, MoveType.JOINTS, 100, 100)

    return jsonify(catch_pose), 200


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
    print(f"DEBUG SENDING: speed_mm_s={speed*10} direction={direction}", flush=True)
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
    print(f"DEBUG SENDING: speed_mm_s={speed*10} direction={direction} distance_mm={distance*10}", flush=True)
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
