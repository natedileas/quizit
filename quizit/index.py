import json
from urllib.parse import parse_qs
import time
import math
import random
import logging
import pathlib


from flask_socketio import SocketIO, join_room, leave_room, close_room, rooms, emit
from flask import Flask, render_template, request

from quizit import quiz
from quizit import config as cfg


app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, logger=True)

players = []
groups = {}

config = cfg.load()

QUIZ_DIR = pathlib.Path(__file__).parent.resolve() / 'quizzes'


@app.route("/")
def player():
    return render_template("player.html.j2", config=config)


@socketio.on("connect")
def player_connect():
    global players
    q = parse_qs(request.query_string)
    q = {key.decode("utf-8"): value[0].decode("utf-8")
         for (key, value) in q.items()}

    players.append(
        {
            "id": request.sid,
            "active": True,
            "group": "",
            "leader": False,
            "join": False,
            "watch": False,
            "playing": False,
            "guid": "",
        }
    )

    logging.info("Player {} connected!".format(request.sid))


@socketio.on("disconnect")
def player_disconnect():
    global players
    player_index = next(
        (i for (i, x) in enumerate(players) if x["id"] == request.sid), None
    )
    if player_index != None:
        players[player_index]["active"] = False
    logging.info("Player disconnected!")


@socketio.on('fetch')
def fetch(json):
    # Get the player with the same GUID
    player_index = next(
        (i for (i, x) in enumerate(players)
         if x["guid"] == json["guid"]), None
    )
    # If we could find a player with the same GUID
    if player_index != None:
        # Get the 'old' player object
        old_player_index = next(
            (i for (i, x) in enumerate(players)
             if x["id"] == request.sid), None
        )
        # Delete the object
        if old_player_index != None:
            del players[old_player_index]
        # Update the player's ID to the current socket ID
        players[player_index]["id"] = request.sid
        # Send all the details to update client
        emit("set_player", players[player_index])
    else:
        logging.info('Could not find player guid.')
        # associate the sid with the guid.
        player_index = next(
            (i for (i, x) in enumerate(players)
             if x["id"] == request.sid), None
        )
        if player_index:
            players[player_index]['guid'] = json["guid"]

    # TODO check if group is playing and set stuff accordingly.


@socketio.on('start_group')
def start_group(json):
    """ Set up a new group. """
    global groups
    global players

    # TODO make this a real uuid, with a shorter join code.
    # TODO also make this more robust. no while.
    new_group_id = ''.join(random.choices('ABCDEFGH', k=4))
    while new_group_id in groups:
        new_group_id = ''.join(random.choices('ABCDEFGH', k=4))

    groups[new_group_id] = {
        'id': new_group_id,
        'active': False,
        'items': quiz.Quiz(QUIZ_DIR / "test.yaml"),
        'n_players': 0
    }

    player_index = next(
        (i for (i, x) in enumerate(players)
         if x["id"] == request.sid), None
    )
    if player_index:
        players[player_index]['leader'] = True

    emit('new_group_started', {
        'group': new_group_id, 'guid': json['guid']})

# TODO shutdown group


@socketio.on('shutdown_group')
def shutdown_group(json):
    """ The leader has exited or something else has happened. """
    global groups

    # TODO validation
    group = json['group']

    groups[group]['active'] = False

    socketio.emit('reset', to=group)
    close_room(group)


@socketio.on('join_group')
def join_group(json):
    """ this player wants to join this group """
    global groups
    global players

    # TODO check if the've already join
    # TODO check if the maximum number has been reached
    # TODO other validation
    group = json['group']
    try:
        groups[group]['n_players'] += 1
    except KeyError:
        emit('group_join_fail', {'reason': f'Cannot join {group}. Group does not exist.'})
        return

    logging.info(rooms())
    join_room(group)
    logging.info(rooms())

    player_index = next(
        (i for (i, x) in enumerate(players)
         if x["id"] == request.sid), None
    )
    if player_index:
        players[player_index]['group'] = group
        players[player_index]['join'] = True

    logging.info('player %s joining group %s.', request.sid, group)
    emit('group_joined', {'group': group})

    logging.info('n_group_members %s.', groups[group]['n_players'])
    socketio.emit('n_group_members', dict(
        number=groups[group]['n_players']), to=group)


@socketio.on('leave_group')
def leave_group(json):
    """ This player wants to leave the group. """
    global groups
    global players
    # TODO check if member in group
    # TODO check group exists
    group = json['group']

    try:
        groups[group]['n_players'] -= 1
    except KeyError:
        logging.warning(
            'player %s tried to leave group %s which does not exist.', request.sid, group)
        emit('fail', {'reason': 'group does not exist'})
        return

    player_index = next(
        (i for (i, x) in enumerate(players)
         if x["id"] == request.sid), None
    )
    if player_index:
        players[player_index]['group'] = ""
        players[player_index]['join'] = False

    logging.info('player %s leaving group %s.', request.sid, group)
    leave_room(group)

    logging.info('n_group_members %s.', groups[group]['n_players'])
    socketio.emit('n_group_members', dict(
        number=groups[group]['n_players']), to=group)

    emit('reset')


@socketio.on('start_round')
def start_round(json):
    """ Send the signal that this group's round is starting. """
    global groups

    try:
        group = groups[json['group']]
    except KeyError:
        emit('fail', {'reason': 'group does not exist'})
        return

    # TODO check that the starter is a member of the group and the leader.
    group['active'] = True

    logging.info('round starting for group: %s', group['id'])
    socketio.emit('round_started', {
        'group': group['id']}, to=group['id'])


@socketio.on('send_next_item')
def send_next_item(json):
    """ Get the next item off the group's list and send it. """
    try:
        group = groups[json['group']]
    except KeyError:
        emit('fail', {'reason': 'group does not exist'})
        return

    item = group['items'].next_question()
    logging.info('sending item %s to group: %s', item, group['id'])
    socketio.emit('show_next_item', item, to=group['id'])


@socketio.on('answer')
def answer(json):
    try:
        group = groups[json['group']]
    except KeyError:
        emit('fail', {'reason': 'group does not exist'})
        return

    # this will let the question / quiz class compose a message
    # TODO check that the user is part of this group.
    group['items'].got_answer(json)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    socketio.run(app, debug=True, host="0.0.0.0")

    # TODO db / save players or
