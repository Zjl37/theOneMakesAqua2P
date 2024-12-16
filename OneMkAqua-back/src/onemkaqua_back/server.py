import json
from logging import root
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import threading
import random

from onemkaqua_back.utils import call_llm_judge_question


app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")

# Constants

INIT_WORD = '水'
TIME_LIMIT = 21.0

# Data Structures
rooms: dict[str, dict] = {}
players: dict[str, str] = {}  # Maps socket IDs to room IDs
players_name: dict[str, str] = {}  # Maps socket IDs to nickname

# Utility Functions


def broadcast_rooms():
    """Broadcast the updated list of rooms to all connected clients."""
    room_list = [
        {"id": room_id, "title": room["title"], "players": len(room["players"])} for room_id, room in rooms.items()
    ]
    socketio.emit("updateRooms", room_list)


def get_opponent(room_id: str, player_id: str) -> str:
    """Get the opponent's socket ID in a room."""
    return next((p for p in rooms[room_id]["players"] if p != player_id), None)


def switch_turn(room_id: str):
    """Switch the turn to the other player and start the timer."""
    if room_id in rooms and len(rooms[room_id]["players"]) == 2:
        # Cancel any existing timeout
        rooms[room_id]["timeout_active"] = None

        # Switch turn
        current_turn = rooms[room_id]["turn"]
        rooms[room_id]["turn"] = get_opponent(room_id, current_turn)
        next_turn = rooms[room_id]["turn"]

        # # Notify the next player it's their turn
        # socketio.emit("serverMessage", "轮到你了。", room=next_turn)

        # Start a new timer
        rooms[room_id]["timeout_active"] = rooms[room_id]["combo"]
        socketio.start_background_task(
            handle_turn_timeout, room_id, next_turn, rooms[room_id]["combo"])


def handle_turn_timeout(room_id: str, player_id: str, combo: int):
    """Handle timeout when a player fails to submit text within TIME_LIMIT."""
    socketio.sleep(TIME_LIMIT)
    # print("=== 1 ")
    if room_id in rooms and rooms[room_id]["turn"] == player_id and rooms[room_id]["timeout_active"] == combo:
        # print("=== 2 ")
        # Notify the player and the opponent
        socketio.emit("gameOver", {
            "win": False, "reason": "你失败了！（超时）"}, room=player_id)
        opponent = get_opponent(room_id, player_id)
        if opponent:
            socketio.emit("gameOver", {
                "win": True, "reason": "对方超时，你获胜！"}, room=opponent)

        # End the game by removing the room
        del rooms[room_id]
        broadcast_rooms()


def handle_judge_question(question: str, room_id, caller_player):
    try:
        # Game logic: call llm to check if the text is correct
        json_str = call_llm_judge_question(question, rooms[room_id]['llmKey'])

        opponent = get_opponent(room_id, caller_player)

        obj = json.loads(json_str)
        judge_msg = obj['explanation']
        correct = obj['correct']
        next_word = obj['next_word']
        emoji = obj['emoji']

        # Notify the player about the judgment
        payload = {
            "correct": correct,
            "message": judge_msg,
            "word": next_word,
            "emoji": emoji,
        }
        socketio.emit("textJudgment", payload | {
                      "my_turn": False}, to=caller_player)
        socketio.emit("textJudgment", payload | {"my_turn": True}, to=opponent)

        # If incorrect, notify the opponent and end the game
        if not correct:
            del rooms[room_id]
            broadcast_rooms()
        else:
            rooms[room_id]["combo"] += 1
            # Switch turn and notify the opponent
            switch_turn(room_id)
            # if opponent:
            #     socketio.emit("serverMessage", "轮到你了！", room=opponent)

        if room_id in rooms:
            rooms[room_id]["last_word"] = next_word
    except Exception as e:
        what = f"服务器出错了！请查看控制台或尝试重新提交。\n\n{e}"
        socketio.emit("serverError", {
                      "what": what, "retry": True}, to=caller_player)
        socketio.emit("serverError", {
                      "what": what, "retry": True}, to=opponent)

        if room_id in rooms:
            rooms[room_id]["judgePending"] = None
        raise e


def handle_judge_question_fake(question: str, room_id, caller_player):
    try:
        socketio.sleep(1)
        opponent = get_opponent(room_id, caller_player)

        correct = random.randint(1, 20) > 4
        judge_msg = random.choice([
            '太对了！阿巴阿巴。',
            '是这样的！你真聪明！',
        ]) if correct else random.choice([
            '答得不对，请再接再厉！',
            '不对哦，请不要气馁！'
        ])
        next_word = question[question.rfind("“")+1:question.rfind("”")]
        emoji = random.choice(['🔥', '🚰', '🌍', '⬜️', '💨', '🪵', '😊'])

        # Notify the player about the judgment
        payload = {
            "correct": correct,
            "message": judge_msg,
            "word": next_word,
            "emoji": emoji,
        }
        socketio.emit("textJudgment", payload | {
                      "my_turn": False}, to=caller_player)
        socketio.emit("textJudgment", payload | {"my_turn": True}, to=opponent)

        # If incorrect, notify the opponent and end the game
        if not correct:
            del rooms[room_id]
            broadcast_rooms()
        else:
            rooms[room_id]["combo"] += 1
            # Switch turn and notify the opponent
            switch_turn(room_id)
            # if opponent:
            #     socketio.emit("serverMessage", "轮到你了！", room=opponent)

        if room_id in rooms:
            rooms[room_id]["last_word"] = next_word
    except Exception as e:
        what = f"服务器出错了！请查看控制台或尝试重新提交。\n\n{e}"
        socketio.emit("serverError", {
                      "what": what, "retry": True}, to=caller_player)
        socketio.emit("serverError", {
                      "what": what, "retry": True}, to=opponent)

        if room_id in rooms:
            rooms[room_id]["judgePending"] = None
        raise e

# Socket Handlers


@socketio.on("connect")
def on_connect():
    """Handle a new client connection."""
    print(f"Client connected: {request.sid}")
    broadcast_rooms()


@socketio.on("disconnect")
def on_disconnect():
    """Handle client disconnection."""
    print(f"Client disconnected: {request.sid}")
    if request.sid in players:
        room_id = players.pop(request.sid)
        if room_id in rooms:
            rooms[room_id]["players"].remove(request.sid)
            opponent = get_opponent(room_id, request.sid)
            if opponent:
                emit("gameOver", {"win": True,
                     "reason": "对方连接已断开，你获胜！"}, room=opponent)
            if not rooms[room_id]["players"]:
                del rooms[room_id]
        broadcast_rooms()


@socketio.on("getRooms")
def handle_get_rooms():
    """Send the list of available rooms to the client."""
    broadcast_rooms()


@socketio.on("createRoom")
def handle_create_room(data):
    """Handle room creation."""
    title: str = data.get('title')
    llmKey: str = data.get('llmKey')
    my_nickname: str = data.get('my_nickname')
    room_id = f"room_{len(rooms) + 1}"
    rooms[room_id] = {"title": title, "players": [],
                      "llmKey": llmKey, "turn": None}

    join_room(room_id)
    players[request.sid] = room_id
    players_name[request.sid] = f"{my_nickname}〔{request.remote_addr}〕"
    rooms[room_id]["players"] = [request.sid]

    broadcast_rooms()
    emit("joinRoomSuccess", room_id)


@socketio.on("joinRoom")
def handle_join_room(data):
    """Handle joining a room."""
    room_id: str = data.get('room_id')
    if room_id not in rooms:
        emit("joinRoomFail", "房间不存在！")
        return
    if len(rooms[room_id]["players"]) >= 2:
        emit("joinRoomFail", "啊哦，房间已满！")
        return

    my_nickname: str = data.get('my_nickname')
    print(my_nickname)

    join_room(room_id)
    players[request.sid] = room_id
    players_name[request.sid] = f"{my_nickname}〔{request.remote_addr}〕"
    rooms[room_id]["players"].append(request.sid)

    emit("joinRoomSuccess", room_id)

    # Assign turn if the room is now full
    if len(rooms[room_id]["players"]) == 2:
        # First player starts
        rooms[room_id]["turn"] = rooms[room_id]["players"][0]
        rooms[room_id]["combo"] = 0
        rooms[room_id]["last_word"] = INIT_WORD
        emit("gameStart", {'init_word': INIT_WORD, 'my_turn': True, 'opponent_name': players_name[rooms[room_id]["players"][1]]},
             to=rooms[room_id]["players"][0])
        emit("gameStart", {'init_word': INIT_WORD, 'my_turn': False, 'opponent_name': players_name[rooms[room_id]["players"][0]]},
             to=rooms[room_id]["players"][1])

        # Start a new timer
        rooms[room_id]["timeout_active"] = rooms[room_id]["combo"]
        socketio.start_background_task(
            handle_turn_timeout, room_id, rooms[room_id]["players"][0], rooms[room_id]["combo"])

    broadcast_rooms()


@socketio.on("leaveRoom")
def handle_leave_room(data):
    """Handle leaving a room."""
    if request.sid not in players:
        return
    print("##", request.sid, "left the room.")
    room_id = players.pop(request.sid)
    if room_id in rooms:
        rooms[room_id]["players"].remove(request.sid)
        opponent = get_opponent(room_id, request.sid)
        if opponent:
            emit("gameOver", {"win": True,
                 "reason": "对方退出了游戏。你获胜！"}, room=opponent)
        if not rooms[room_id]["players"]:
            del rooms[room_id]
    broadcast_rooms()


@socketio.on("submitText")
def handle_submit_text(data):
    """Handle text submission."""
    room_id = data.get("roomId")
    text = data.get("text")
    if not room_id or room_id not in rooms:
        return

    # Enforce turn-based rules
    if rooms[room_id]["turn"] != request.sid:
        emit("serverMessage", "不是你的回合！", room=request.sid)
        return

    if rooms[room_id].get("judgePending", None) == rooms[room_id]["combo"]:
        emit("serverMessage", "请勿重复提交！", room=request.sid)
        return

    rooms[room_id]["judgePending"] = rooms[room_id]["combo"]

    rooms[room_id]["timeout_active"] = None
    last_word = rooms[room_id]["last_word"]

    question = f'“{last_word}”能生成“{text}”吗？'

    opponent = get_opponent(room_id, request.sid)
    socketio.emit("setPending", to=opponent)

    if rooms[room_id]["llmKey"] == "sk-faketestfaketestfaketestfaketest":
        # fake test does not really call llm
        socketio.start_background_task(
            handle_judge_question_fake, question, room_id, request.sid)
    else:
        socketio.start_background_task(
            handle_judge_question, question, room_id, request.sid)


@socketio.on("typing")
def handle_typing(data):
    """Handle real-time typing updates."""
    room_id = data.get("roomId")
    text = data.get("text")
    if not room_id or room_id not in rooms:
        return

    opponent = get_opponent(room_id, request.sid)
    if opponent:
        emit("opponentTyping", text, room=opponent)

# Flask Routes (Optional)


@app.route("/")
def index():
    """Basic health check route."""
    return jsonify({"status": "Server is running"}), 200


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=3000, debug=True)
