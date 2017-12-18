#!/usr/bin/python

# NOTES
#
# game offers, messages, and ongoing games should no longer be statically
# included in the document, they will be fetched dynamically with a client
# command.

from socket import gethostname, gethostbyname
from sys import argv
from random import choice
import re
from threading import Timer
import os
import subprocess
from cgi import escape
from datetime import datetime
from traceback import print_exc
from thread import start_new_thread

import cherrypy as cp
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket, EchoWebSocket
import chess

from metaclass import InstanceUnifier

ADMINS = [('RobbieGM', 'utf8'), ('ParkerS', 'capjacksparrow45'),
          ('JosephW', 'Arman@2003')]  # user-pass admin list
ADMIN_USERNAMES = [a[0] for a in ADMINS]  # quick-scan list of admin usernames
users = {}
game_offers = {}
games = {}
global_messages = []
# game_page = open('dyn/game.html').read()
# choose_username_html = open('dyn/choose_username.html').read()
# terms_and_conditions = open('dyn/terms.html').read()
# index_html = open('dyn/index.html').read()
DYNAMIC_HTML = {
    'index': open('dyn/index.html').read(),
    'terms': open('dyn/terms.html').read(),
    'choose_username': open('dyn/choose_username.html').read(),
    'game': open('dyn/game.html').read(),
    'wrapper': open('dyn/main_page_wrapper.html').read()
}
LEGAL_VARIANT_LIST = [
    'normal',
    'atomic',
    'race-kings',
    'fischer-random',
    'crazyhouse',
    'suicide',
    'sniper',
    'koth',
    'three-check',
    'cheshire-cat',
    'annihilation',
    'gryphon',
    'cornerless',
    'mutation',
    'bomb']

READABLE_VARIANTS = {
    'normal': 'Standard',
    'race-kings': 'Racing kings',
    'atomic': 'Atomic',
    'fischer-random': 'Fischer random',
    'crazyhouse': 'Crazyhouse',
    'suicide': 'Suicide',
    'sniper': 'Sniper chess',
    'koth': 'KOTH',
    'three-check': 'Three-check',
    'cheshire-cat': 'Cheshire cat',
    'annihilation': 'Annihilation',
    'gryphon': 'Gryphon chess',
    'mutation': 'Mutation',
    'bomb': 'Bomb chess'
}


def generate_guid():
    # Shouldn't use: /&?%\;"':
    ALLOWED_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
    SESSION_TOKEN_LENGTH = 20
    session_token = ''
    for i in range(SESSION_TOKEN_LENGTH):
        session_token += choice(ALLOWED_CHARS)
    return session_token


def main_page_wrap(html, css='', split_mode=False):
    if split_mode:
        arr = html.split('{head_body_split}', 1)
        return DYNAMIC_HTML['wrapper'].format(head=arr[0], body=arr[1])
    else:
        return DYNAMIC_HTML['wrapper'].format(
            body=html, head='<style>' + css + '</style>')


def username_required(func):
    def wrapper(*args, **kwargs):
        if 'session_token' in cp.request.cookie and cp.request.cookie[
                'session_token'].value in users:
            return func(*args, **kwargs)
        else:
            raise cp.HTTPRedirect('/choose_username')
    return wrapper


def switch_bw(c):
    if c == 'white':
        return 'black'
    if c == 'black':
        return 'white'
    print "switch_bw: argument was not 'black' or 'white'."
    return c


def msg(*args):
    return ':'.join(args)


class GameOffer(object):

    __metaclass__ = InstanceUnifier
    instances = game_offers
    primary_key = 'game_id'

    def __init__(self, offered_by, variant, minutes,
                 delay, play_as):
        self.offered_by = offered_by
        self.variant = variant
        self.minutes = minutes
        self.delay = delay
        self.play_as = play_as

    def delete(self):
        User.broadcast_to(['withdrawgame', self.game_id], 'all', role='main')
        del game_offers[self.game_id]


class Game(object):

    __metaclass__ = InstanceUnifier
    instances = games
    primary_key = 'game_id'

    def __init__(self, white_player, black_player, variant, minutes, delay):
        minutes = int(minutes)
        delay = int(delay)
        self.white_player = white_player
        self.black_player = black_player
        self.variant = variant
        #self.minutes = minutes
        self.delay = delay
        self.board = chess.Board() # REVISE: add variants
        self.msgs = []
        self.spectator_msgs = []
        self.takeback_offeror = ''
        self.moves = []
        self.draw_offeror = ''
        self.last_move_date = datetime.now()
        self.seconds_remaining_white = minutes * 60
        self.seconds_remaining_black = minutes * 60
        #self.timer = Timer(self.white_seconds_remaining)
        #self.timer.daemon = True

    def conclude(self, winner, reason=None):
        User.broadcast_to('ongoinggamefinished:' + self.game_id, 'all', role='main')
        # be free, white and black to play another game
        self.white_player.game_id = None
        self.black_player.game_id = None

        reason = reason if reason else '(unspecified reason)'
        win_str = 'Game over' # don't mess up too hard on the user end if something goes wrong here
        if winner == None:
            win_str = 'Draw'
        elif winner == chess.WHITE:
            win_str = 'White wins'
        elif winner == chess.BLACK:
            win_str = 'Black wins'
        message = '<h2>Game Over</h2><p>%s by %s</p>' % (win_str, reason)
        self.broadcast_event('showmessage', message)

        self.destruct()

    @property
    def versus_string(self):
        return self.white_player.username + ' vs. ' + self.black_player.username

    def broadcast_event(self, *args, **kwargs):
        args = [list(args), 'all']
        kwargs['role'] = ('game', self.game_id)
        User.broadcast_to(*args, **kwargs)

    def move(self, m):
        def get_reason():
            if self.board.is_checkmate():
                return 'checkmate'
            if self.board.is_variant_end():
                return 'variant ending'
            if self.board.is_stalemate():
                return 'stalemate'
            if self.board.is_insufficient_material():
                return 'insufficient material'
            if self.board.is_seventyfive_moves():
                return 'seventy-five move rule'
            if self.board.can_claim_threefold_repetition():
                return 'threefold repetition'
            if self.board.can_claim_fifty_moves():
                return 'fifty move rule'

        self.board.push_uci(m)
        self.broadcast_event('fen', self.board.fen())
        if self.board.is_game_over(claim_draw=True):
            winner = None
            res = self.board.result(claim_draw=True)
            if res == '1-0':
                winner = chess.WHITE
            if res == '0-1':
                winner = chess.BLACK
            self.conclude(winner, reason=get_reason())

        if self.board.is_check():
            self.broadcast_event('game', 'check')


class User(object):

    __metaclass__ = InstanceUnifier
    instances = users
    primary_key = 'session_token'

    def __init__(self, username, ip_addr=None):
        self.username = username
        self.sockets = []
        self.game_id = None
        self.silenced = False
        self.ip_addr = ip_addr

    @staticmethod
    def broadcast_to(message, recipients, role='all', single_socket_override=False, from_token='FROM_SERVER', signify_owned=False):
        if type(message) != str:
            message = msg(*message)

        if type(role) == str:
            role = (role,)
        if type(role) == list:
            role = tuple(role)
            print 'Warning: use tuples instead of arrays for role parameter in User.broadcast_to for consistency.'
        try:
            for session_token in users:
                if session_token in recipients or recipients == 'all':
                    for socket in users[session_token].sockets:
                        if socket.role == role or role == ('all',) or (len(users[session_token].sockets) == 0 and single_socket_override):
                            is_owned = from_token == session_token
                            extra = None
                            if signify_owned:
                                extra = ':owned' if is_owned else ':foreign'
                            else:
                                extra = ''
                            socket.send(message + extra, False)
        except Exception as e:
            print_exc()

    @staticmethod
    def get_users_where(**kwargs):
        if len(kwargs) != 1:
            raise TypeError(
                'get_users_where takes exactly 1 name/value pair in kwargs (%s given)' % len(kwargs))
        key = kwargs.keys()[0]
        val = kwargs[key]
        selected_users = [users[st] for st in users if getattr(users[st], key) == val]
        return selected_users

    def logout(self, force=True):
        if force or len(self.sockets) == 0:
            if self.game_id in games:
                winner = None
                if self is self.game.white_player:
                    winner = chess.BLACK
                elif self is self.game.black_player:
                    winner = chess.WHITE
                else:
                    raise Exception()
                self.game.conclude(winner, reason='disconnection')
            for offer_id in game_offers.keys():
                if game_offers[offer_id].offered_by is self:
                    game_offers[offer_id].delete()
            print 'User ' + self.username + ' logged out.'
            self.destruct()

    def start_logout_timer(self):
        self.logout_timer = Timer(10, self.logout, [False])
        self.logout_timer.daemon = True
        self.logout_timer.start()

    def on_socket_close(self):
        if len(self.sockets) == 0:
            print 'User ' + self.username + ' has 5 seconds to reconnect'
            self.start_logout_timer()

    def execute_js(self):
        pass

    def silence(self, seconds):
        def unsilence():
            self.silenced = False
        self.silenced = True
        t = Timer(seconds, unsilence)
        t.start()

    @property
    def game(self):
        if self.game_id in games:
            return games[self.game_id]

    @property
    def opponent(self):
        if self.game:
            if self.game.white_player is self:
                return self.game.black_player
            if self.game.black_player is self:
                return self.game.white_player
        return None


class MainWebSocket(WebSocket):

    __metaclass__ = InstanceUnifier
    instances = []

    def __init__(self, *args, **kwargs):
        WebSocket.__init__(self, *args, **kwargs)
        self.session_token = None
        self.role = None

    def emit(self, *args):
        self.send(msg(*args), False)

    def emit_user_all(self, *args):
        for sock in self.user.sockets:
            self.emit(*args)

    @property
    def user(self):
        return users[self.session_token]

    def opened(self):  # IMPORTANT: NEVER SEND MESSAGES WHEN SOCKET HAS JUST OPENED
        if self.session_token:
            print 'Socket opened. User: ' + self.user.username
            self.user.sockets.append(self)
        else:
            print 'User is not logged in, but requested socket'
            # self.terminate() # << causes weird errors (because socket doesn't exist?)

    def closed(self, code, reason=None):
        if self.session_token in users:
            print 'MainWebSocket.closed. User: ' + self.user.username
            self.user.sockets.remove(self)
            self.user.on_socket_close()
            if self.role:
                if self.role[0] == 'spectate':
                    pass
                elif self.role[0] == 'play' and self.user.game:
                    pass
        self.destruct()

    def received_message(self, received):
        try:
            print 'Socket data: ' + received.data
            msg = received.data
            msg_params = msg.split(':')
            cmd = msg_params[0]

            def setrole(*role):
                self.role = tuple(role)

            def creategame(variant, mins, secs, color):
                if not variant in LEGAL_VARIANT_LIST:
                    return
                if self.user.game_id in games:
                    self.emit('showmessage', '<h3>You are already in a game</h3><p>Please finish the game you are in before you create another game.</p>')
                else:
                    variant, mins, secs, color = msg_params[1:]
                    offer = GameOffer(self.user, variant, mins, secs, color)
                    User.broadcast_to(['gameoffer', self.user.username, READABLE_VARIANTS[variant], mins, secs, color, offer.game_id], 'all', role='main', from_token=self.user.session_token, signify_owned=True)

            def get(which, *args):
                if which == 'games':
                    for game_id in games:
                        g = games[game_id]
                        self.emit('ongoinggame', game_id,
                                  g.versus_string, READABLE_VARIANTS[g.variant])
                elif which == 'messages':
                    [self.emit('message', m) for m in global_messages]
                elif which == 'game_offers':
                    for game_id in game_offers:
                        g = game_offers[game_id]
                        owned = 'owned' if g.offered_by is self.user else 'foreign'
                        self.emit('gameoffer', g.offered_by.username, READABLE_VARIANTS[g.variant], g.minutes, g.delay, g.play_as, game_id, owned)
                elif which == 'fen':
                    if args[0] in games:
                        game_id = args[0]
                        fen = games[game_id].board.fen()
                        self.emit('fen', fen)
                    else:
                        self.emit('showmessage',
                                  '<h2>This game doesn\'t exist anymore.</h2>')

            def acceptgame(offer_id):
                if not offer_id in game_offers:
                    self.emit(
                        'showmessage',
                        '<h3>That game offer is gone</h3><p>The game offer you accepted doesn\'t exist anymore.</p>')
                    return
                if self.user.game_id in games:
                    self.emit(
                        'showmessage',
                        '<h3>You are already in a game</h3><p>Please finish the game you are in before you accept another game.')
                    return

                if game_offers[offer_id].offered_by is self.user:
                    # accepting your own game = withdrawal
                    game_offers[offer_id].delete()
                else:
                    offer = game_offers[offer_id]
                    opponent = offer.offered_by
                    opponent_color = offer.play_as
                    if opponent_color == 'random':
                        opponent_color = choice(['white', 'black'])
                    your_color = switch_bw(opponent_color)
                    if opponent_color == 'white':
                        white = opponent
                        black = self.user
                    elif your_color == 'white':
                        white = self.user
                        black = opponent

                    g = None
                    try:
                        g = Game(white, black, offer.variant, offer.minutes, offer.delay)
                    except Exception as e:
                        print_exc()
                        print e
                    self.user.game_id = g.game_id
                    opponent.game_id = g.game_id

                    recipients = [self.user.session_token, opponent.session_token]
                    User.broadcast_to(['gameready', g.game_id], recipients, role='main')
                    User.broadcast_to(['ongoinggame', g.game_id, g.versus_string, READABLE_VARIANTS[game_offers[offer_id].variant]], 'all', role='main')

                    print 'opp: ' + opponent_color
                    print 'you: ' + your_color
                    game_offers[offer_id].delete()

                    for oid in game_offers:
                        if game_offers[oid].offered_by in (white, black):
                            game_offers[oid].delete()

            def message(text):
                if not self.user.silenced:
                    text = escape(text)
                    text = '<span class="message-sender">' + self.user.username + '</span> ' + text
                    global_messages.append(text)
                    User.broadcast_to(['message', text], 'all', role='main')
                    if len(global_messages) > 25:
                        global_messages.pop(0)
                        self.emit('popmessage')
                    self.user.silence(1.5)

            def game(cmd, *args):
                def move(m):
                    g = self.user.game
                    if (g.board.turn == chess.WHITE and self.user is g.white_player) or (
                            g.board.turn == chess.BLACK and self.user is g.black_player):
                        try:
                            g.move(m)
                        except ValueError:
                            self.emit('invalidmove')
                    else:
                        self.emit('invalidmove')

                def message():
                    pass

                def takeback():
                    pass

                def draw():
                    pass

                def resign():
                    pass
                sublocals = locals()
                sublocals = {func_name: func for (func_name, func) in sublocals.items() if callable(func)}
                if cmd in sublocals:
                    sublocals[cmd](*args)

            # expose local functions as commands to websocket
            fn_locals = locals()
            fn_locals = {
                func_name: func for func_name,
                func in fn_locals.items() if callable(func)}
            msg_params_after_cmd = msg_params[1:]
            if cmd in fn_locals:
                fn_locals[cmd](*msg_params_after_cmd)

        except Exception as e:  # don't ask me why this is necessary; remove the try/except statement and all errors get silenced
            print 'Exception in MainWebSocket.received_message'
            print_exc()


class Root(object):

    def __init__(self):
        self.game = GamePath()

    @cp.expose
    @username_required
    def index(self):
        return main_page_wrap(DYNAMIC_HTML['index'])

    @cp.expose
    def choose_username(self, **request_params):
        if cp.request.method == 'GET':
            if 'session_token' in cp.request.cookie:
                session_token = cp.request.cookie['session_token']
                if User.get_users_where(session_token=session_token):
                    users[session_token].logout()
            cp.response.cookie['session_token'] = 'expires_now'
            cp.response.cookie['session_token']['expires'] = 0
            return main_page_wrap(DYNAMIC_HTML['choose_username'], split_mode=True)
        elif cp.request.method == 'POST':
            if not request_params['username']:
                raise cp.HTTPError(400)
            uname = escape(request_params['username'])  # xss protection
            reject = (
                (request_params['settings'], 'You don\'t appear to be human.'),
                (len(uname) > 20, 'Username is too long (over 20 characters).'),
                (uname in [users[sestok].username for sestok in users],
                 'Another user is already using this username.'),
                (not re.search(r'^[a-zA-Z0-9\-_\s\.]+$', uname) or uname.isspace(),
                 'Username must be non-space and may only contain letters, numbers, dashes, spaces, periods, and underscores.')
            )
            for condition in reject:
                if condition[0]:
                    return main_page_wrap('<h2>Could not choose username</h2><p>{reason}<a href="/choose_username">Repick username</a></p>'.format(reason=condition[1]))
            u = User(uname, ip_addr=cp.request.remote.ip)
            cp.response.cookie['session_token'] = u.session_token
            raise cp.HTTPRedirect('/')
        else:
            raise cp.HTTPError(405)

    @cp.expose
    @username_required
    def socket(self):
        logged_in = True
        if 'session_token' in cp.request.cookie:
            session_token = cp.request.cookie['session_token'].value
            if session_token in users:
                handler = cp.request.ws_handler
                handler.session_token = session_token
            else:
                logged_in = False
                print 'User requested socket while logged out. (invalid session token)'
        else:
            logged_in = False
            print 'User requested socket while logged out. (nonexistent session token)'
        if not logged_in:
            raise cp.HTTPError(403)

    def _cp_dispatch(self, vpath):
        if vpath[0] == 'g' and len(vpath) == 2:
            cp.request.params['game_id'] = vpath.pop()
            return self.game


class GamePath(object):

    @cp.expose
    @username_required
    def g(self, game_id):
        # print game_id
        # return main_page_wrap('<article><h2>test</h2></article>')

        if not game_id in games:
            return main_page_wrap('''<article>
                <h2>That Game is Gone</h2>
                <p>The game you requested doesn't exist. It may have ended, or you may have mistyped the URL.</p>
                </article>''')
        game = games[game_id]
        user = users[cp.request.cookie['session_token'].value]

        is_spectator = True
        if user.game.game_id == user.game.game_id:
            is_spectator = False

        if is_spectator:
            return main_page_wrap(DYNAMIC_HTML['game'].format(
                opponent_username=game.black_player,
                username=game.white_player,
                white_player=game.white_player.username,
                black_player=game.black_player.username,
                is_spectating=True
            ))
        else:
            opp_uname = user.opponent.username
            return main_page_wrap(DYNAMIC_HTML['game'].format(
                opponent_username=opp_uname,
                username=user.username,
                white_player=game.white_player.username,
                black_player=game.black_player.username,
                is_spectating=False
            ))


def error_404(status, message, traceback, version):
    return main_page_wrap(
        '<article><h2>404 Not Found</h2><p>The page you requested doesn\'t exist.</p></article>')


cfg = {'/static': {
    'tools.staticdir.on': True,
    'tools.staticdir.dir': 'static',
    'tools.caching.on': True,
    'tools.caching.delay': 30,
},
    '/': {
        'tools.staticdir.root': os.getcwd(),
},
    'global': {
        'server.socket_host': '127.0.0.1',
        'server.socket_port': (int(argv[len(argv) - 1]) if argv[len(argv) - 1].isdigit() else 80),
        'response.timeout': 6000,  # ms
        'error_page.404': error_404,
    #       'log.access_file': '',
    #       'log.error_file': '/tmp/cp-error.log',
        'log.screen': True,
        'tools.trailing_slash.on': False,
    #       'server.ssl_certificate': 'certificate.crt',
    #       'server.ssl_private_key': 'private.key'
},
    '/socket': {
        'tools.websocket.on': True,
        'tools.websocket.handler_cls': MainWebSocket
},
    '/favicon.ico': {
        'tools.staticfile.on': True,
        'tools.staticfile.filename': os.getcwd() + '/favicon.ico'
}
}

WebSocketPlugin(cp.engine).subscribe()
cp.tools.websocket = WebSocketTool()

if __name__ == '__main__':
    def debug():
        while True:
            try:
                print eval(raw_input('>>> '))
            except Exception as e:
                print e
    start_new_thread(debug, ())
    cp.quickstart(Root(), '/', config=cfg)
