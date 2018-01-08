function validateUsername(name) {
	var xhr = new XMLHttpRequest();
	xhr.open('GET', '/validate_username?name='+name, false);
	xhr.send();
	return xhr.responseText == 'valid';
}
(function initLocalStorage() {
	var defaultLS = {
		darkSquareColor: '#555555',
		lightSquareColor: '#EEEEEE'
	};
	for (key in defaultLS) {
		if (localStorage[key] === undefined || localStorage[key] === null) {
			localStorage[key] = defaultLS[key];
		}
	}
})();
addEventListener('load', function() {
	var modalOverlay = document.getElementById('modal-overlay');
	function closeNavMenu(e) {
		e.preventDefault(); // don't fire both events
		if (document.getElementById('nav-menu').classList.contains('active')) {
			document.getElementById('nav-menu').classList.remove('active');
			document.getElementById('modal-overlay').classList.remove('active');
		}
	}
	modalOverlay.addEventListener('mousedown', closeNavMenu);
	modalOverlay.addEventListener('touchstart', closeNavMenu);
	document.body.addEventListener('keyup', function(evt) {
		if (evt.keyCode == 27) { //ESC
			dismissAlert();
		}
	});
	if (location.pathname == '/') {
		var chatBox = document.getElementById('msg-input');
		chatBox.onkeyup = function(e) {
			var keyCode = e.keyCode || e.which || e.charCode;
			if (keyCode == 13) {
				if (! /^\s*$/.test(this.value)) {
					socket.send('message:'+this.value);
					this.value = '';
				}
			}
		};
	}
	var navMenu = document.getElementById('nav-menu');
	for (var i = 0; i < navMenu.children.length; i++) {
		navMenu.children[i].onclick = function(e) {
			e.preventDefault();
			navMenu.classList.remove('active');
			var elt = this;
			setTimeout(function() {
				location.href = elt.href;
			}, 1000 * 0.2);
		};
	}
});
function showAlert(content, buttons, defaultButton) {
	if (!buttons || buttons.length === 0) { buttons = ['OK']; defaultButton = 'OK';}
	document.getElementById('modal-dialog').className = 'active';
	document.getElementById('modal-overlay').className = 'active';
	document.getElementById('modal-overlay').classList.remove('show-top');
	document.getElementById('modal-dialog-content').innerHTML = content;
	var html = '';
	for (var i=0;i<buttons.length;i++) {
		html += '<td '+(defaultButton==buttons[i] ? 'class="default-button"' : '')+'>'+buttons[i]+'</td>'
	}
	document.getElementById('modal-dialog-dismiss-row').innerHTML = html;
	var CVAlertButtons = document.getElementById('modal-dialog-dismiss-row').childNodes;
	for (var i=0;i<CVAlertButtons.length;i++) {
		CVAlertButtons[i].onclick = function() {
			dismissAlert(this.innerHTML);
		}
	}
}
function dismissAlert(result) {
	document.getElementById('modal-dialog').className = 'inactive';
	document.getElementById('modal-overlay').className = 'inactive';
	var noClear = onAlertDismiss(result);
	if (!noClear) { onAlertDismiss = function(){}; }
}
function screenFlash() {
	navigator.vibrate(50);
	var flash = document.getElementById('screen-flash-circle');
	flash.classList.add('animated');
	setTimeout(function() {
		flash.classList.remove('animated');
	}, 1000);
}
function toggleHamburgerMenu() {
	var navMenu = document.getElementById('nav-menu');
	var modalOverlay = document.getElementById('modal-overlay');
	if (navMenu.classList.contains('active')) {
		navMenu.classList.remove('active');
		modalOverlay.classList.remove('active');
	} else {
		navMenu.classList.add('active');
		modalOverlay.classList.add('show-top');
		modalOverlay.classList.add('active');
	}
}
function createGame(isChallenge) {
	var text = "\
	<!--div style='width: 100%; text-align: center'-->\
	<form style='margin-bottom: 1.16667rem'>\
	"+(isChallenge ? "<h3>Player to challenge</h3>\
	<input type='text' style='margin-bottom: 1.16667rem;' id='to-challenge'/>" : "")+"\
	<h3>Variant</h3>\
	<select id='variant' style='margin-bottom: 1.16667rem'>\
	<br/><br/>\
		<option value='normal'>Standard</option>\
		<option value='atomic'>Atomic</option>\
		<option value='race-kings'>Racing kings</option>\
		<option value='fischer-random'>Fischer random</option>\
		<option value='crazyhouse'>Crazyhouse</option>\
		<option value='suicide'>Suicide</option>\
		<option value='sniper'>Sniper chess</option>\
		<option value='koth'>King of the Hill</option>\
		<option value='three-check'>Three-check</option>\
		<option value='cheshire-cat'>Cheshire cat</option>\
		<option value='annihilation'>Annihilation</option>\
		<option value='gryphon'>Gryphon chess</option>\
		<option value='mutation'>Mutation</option>\
		<option value='bomb'>Bomb chess</option>\
	</select>\
	<h3>Time control</h3>\
	<table style='margin: 0; padding: 0; margin-bottom: 1.16667rem; table-layout: fixed' cellpadding='0' cellspacing='0'>\
	<tr><td id='display-minutes' style='min-width: 50px'>5min</td><td><input id='minutes' value='5' type='range' min='1' max='60' style='vertical-align: middle'/></td></tr>\
	<tr><td id='display-seconds' style='min-width: 50px'>8sec</td><td><input id='delay' value='8' type='range' min='0' max='30' style='vertical-align: middle;'/></td></tr>\
	</table>\
	<h3>Play as</h3>\
	<input type='radio' name='play-as' value='random' id='play-as-random' checked /> <label for='play-as-random'>Random color</label><hr style='height: 0.5em; margin: 0; visibility: hidden'/>\
	<input type='radio' name='play-as' value='white' id='play-as-white' /> <label for='play-as-white'>White</label><hr style='height: 0.5em; margin: 0; visibility: hidden'/>\
	<input type='radio' name='play-as' value='black' id='play-as-black' /> <label for='play-as-black'>Black</label>\
	</form>\
	<!--/div-->";
	showAlert(text, ['Cancel', 'Create game'], 'Create game');
	onAlertDismiss = function(result) {
		if (result == 'Create game') {
			screenFlash();
			var variant = document.getElementById('variant').value;
			var minutes = document.getElementById('minutes').value;
			var delay   = document.getElementById('delay').value;
			var playAs  = 'random';
			var radioButtons = document.getElementsByName('play-as');
			for (var i=0;i<radioButtons.length; i++) {
				if (radioButtons[i].checked == true) {
					playAs = radioButtons[i].value;
				}
			}
			if (isChallenge) {
				var playerToChallenge = document.getElementById('to-challenge');
				if (playerToChallenge && /^[a-zA-Z0-9\s]+$/.test(playerToChallenge.value)) {
					playerToChallenge = playerToChallenge.value;
					socket.send('creategame:'+variant+':'+minutes+':'+delay+':'+playAs+':'+playerToChallenge)
				}else{
					showAlert('<h3>Invalid input</h3><p>Player to challenge field is empty or is an invalid username.</p>');
				}
			}else{
				socket.send('creategame:'+variant+':'+minutes+':'+delay+':'+playAs);
			}
		}
	};
	setTimeout(function() {
		document.getElementById('delay').oninput = function() { document.getElementById('display-seconds').innerHTML = this.value+'sec'; };
		document.getElementById('delay').onchange = function() { document.getElementById('display-seconds').innerHTML = this.value+'sec'; };
		document.getElementById('minutes').oninput = function() { document.getElementById('display-minutes').innerHTML = this.value+'min'; };
		document.getElementById('minutes').onchange = function() { document.getElementById('display-minutes').innerHTML = this.value+'min'; };
	}, 200);
}
function acceptGame(gameId) {
	socket.send('acceptgame:'+gameId)
}
function spectateGame(gameId) {
	location.href = '/g/'+gameId;
}

var onAlertDismiss = function() { console.log('No action taken on alert dismiss. (default)'); };
var proto = location.protocol == 'https:' ? 'wss' : 'ws';
var socket = new WebSocket(proto+'://'+location.host+'/socket');
var socketSend = socket.send;
socket.send = function() {
	socketSend.apply(this, arguments); // debug if necessary
};
var hasOpened = false;
socket.onopen = function() {
	console.log('socket opened');
	hasOpened = true;
	if (location.pathname == '/') {
		socket.send('get:messages');
		socket.send('get:game_offers');
		socket.send('get:games');
	}
	var path = location.pathname.substr(1).split('/');
	if (path[0] == '') {
		socket.send('setrole:main');
	}else if (path[0] == 'g') {
		socket.send('setrole:game:'+path[1]);
	}
}
var suppressOfflineMessages = false;
socket.onclose = function() {
	console.log('socket closed');
	//if (!hasOpened) return;
	if ((['/choose_username', '/terms', '/about', '/blankpage', '/settings']).indexOf(location.pathname) !== -1) return;
	setTimeout(function() { // wait 3 seconds, no need to have this pop up when users exit the page (that closes the socket)
		showAlert('<h3>Network Error</h3><p>We are unable to connect to the Chessvars server. Please check your internet connection. If you think your internet connection is working, click reconnect.</p>', ['Cancel', 'Reconnect']);
		onAlertDismiss = function(result) {
			if (result == 'Reconnect') {
				location.reload();
			}
			suppressOfflineMessages = true;
		};
	}, 3000);
};
socket.onmessage = function(received) {
	function switch_bw(c) {
		if (c == 'white') return 'black';
		if (c == 'black') return 'white';
		return c;
	}
	var msg = received.data;
	console.log(msg);
	var msgargs = msg.split(':');
	if (msgargs[0] == 'gameoffer') {
		var colorClass = (msgargs[7] == 'owned') ? ' class="owned" ' : '';
		var playAs = (msgargs[7] == 'foreign') ? switch_bw(msgargs[5]) : msgargs[5];
		document.getElementById('offers-tbody').innerHTML += "<tr "+colorClass+"onclick='acceptGame(\""+msgargs[6]+"\")' id='offer-id-"+msgargs[6]+"'><td>"+msgargs[1]+"</td><td>"+msgargs[2]+"</td><td>"+msgargs[3]+" + "+msgargs[4]+"</td><td><div class='circle "+playAs+"'></div></tr>";
	}
	if (msgargs[0] == 'withdrawgame') {
		try {
			var elt = document.getElementById('offer-id-'+msgargs[1]);
			elt.parentNode.removeChild(elt);
		}catch(err) {}
	}
	if (msgargs[0] == 'showmessage') {
		showAlert(msgargs[1])
	}
	if (msgargs[0] == 'gameaccepted' || msgargs[0] == 'gameready') {
		screenFlash();
		location = '/g/'+msgargs[1];
	}
	if (msgargs[0] == 'gameconclusion') {
		gameConclusion(msgargs[1], msgargs[2], msgargs[3]);
	}
	if (msgargs[0] == 'fen') {
		try {
			loadFen(msgargs[1], msgargs[2])
		}catch(err) {/* Not /g/* page */}
	}
	if (msgargs[0] == 'gamemessage') {
		try {
			var gameMessage = msg.split(':').slice(2, msgargs.length).join(':');
			console.log(gameMessage);
			gameMessage(msgargs[1], gameMessage);
		}catch(err) {
			console.log(err);
			console.log('CVGameMessage not defined');
		}
	}
	if (msgargs[0] == 'takebackoffer') {
		takebackOffer();
	}
	if (msgargs[0] == 'drawdecline') {
		drawDecline();
	}
	if (msgargs[0] == 'takeback') {
		takeback();
	}
	if (msgargs[0] == 'drawoffer') {
		drawOffer();
	}
	if (msgargs[0] == 'popmessage' && location.pathname == '/') {
		var txt = document.getElementById('msg-box').children[0];
		txt.parentNode.removeChild(txt);
	}
	if (msgargs[0] == 'message' && location.pathname == '/') {
		var txt = document.createElement('div');
		txt.innerHTML = msg.slice(8, msg.length);
		var msgBox = document.getElementById('msg-box');
		msgBox.appendChild(txt);
		msgBox.scrollTop = msgBox.scrollHeight;
	}
	if (msgargs[0] == "ongoinggame" && location.pathname == '/') {
		document.getElementById('games-tbody').innerHTML += '<tr id="game-id-'+msgargs[1]+'"><td>'+msgargs[2]+'</td><td>'+msgargs[3]+'</td><td><button material raised onclick="CVSpectateGame(\''+msgargs[1]+'\')">Spectate game</button></td></tr>';
	}
	if (msgargs[0] == "ongoinggamefinished" && location.pathname == '/') {
		var elt = document.getElementById('game-id-'+msgargs[1]);
		if (elt) {
			elt.parentNode.removeChild(elt);
		}
	}
};