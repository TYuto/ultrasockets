import os
import logging
import redis
import gevent
from flask import Flask, make_response, request
from flask_sockets import Sockets

import json

REDIS_URL = os.environ['REDIS_URL']

app = Flask(__name__)
app.debug = 'DEBUG' in os.environ

sockets = Sockets(app)
redis = redis.from_url(REDIS_URL)



class ChatBackend(object):
    """Interface for registering and updating WebSocket clients."""

    def __init__(self):
        self.clients = {}
        self.pubsub = redis.pubsub()
        self.pubsub.subscribe("websocket_message")

    def __iter_data(self):
        for data in self.pubsub.listen():
            try:
                json.loads(data.get('data'))
            except:
                continue
            yield json.loads(data.get('data'))

    def register(self, client, uuid):
        if uuid in self.clients:
            self.clients[uuid].append(client)
        else:
            self.clients[uuid] = [client]

    def send(self, client, data, uuid):
        """Send given data to the registered client.
        Automatically discards invalid connections."""
        try:
            client.send(json.dumps(data))
        except Exception as e:
            print(e.message)
            self.clients[uuid].remove(client)

    def run(self):
        """Listens for new messages in Redis, and sends them to clients."""
        for data in self.__iter_data():
            uuid = data.get('uuid')
            message = data.get('message')
            gevent.spawn(self.castForRoom, message, uuid)
            

    def start(self):
        """Maintains Redis subscription in the background."""
        gevent.spawn(self.run)
    
    def castForRoom(self, message, uuid):

        print(self.clients)
        if uuid in self.clients:
            print(self.clients[uuid])
            for client in self.clients[uuid]:
                gevent.spawn(self.send, client, message, uuid)

socket_c = ChatBackend()
socket_c.start()

@sockets.route('/receive/<uid>/')
def outbox(ws, uid):
    socket_c.register(ws, uid)
    while not ws.closed:
        gevent.sleep(0.1)

@app.route('/send/<uid>/', methods=["POST"])
def add_block_for_debug(uid):
    data = {
        'message': request.json,
        'uuid': uid
    }
    redis.publish('websocket_message', json.dumps(data))
    return make_response('ok')


