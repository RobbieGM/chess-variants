var navigate;
addEventListener('load', function() {
	var loader = document.getElementById('loader');
	var links = document.getElementsByTagName('a');
	for (var i = links.length - 1; i >= 0; i--) {
		links[i].onclick = function(e) {
			e.preventDefault();
			navigate(this.href);
		};
	};
	navigate = function(url) {
		loader.classList.add('active');
		history.pushState({}, '', url);
		var xhr = new XMLHttpRequest();
		xhr.open('get', url);
		xhr.onreadystatechange = function() {
			if (xhr.readyState == 4) {
				console.log(xhr.response);
				document.open();
				document.write(xhr.responseText);
				document.close();
				loader.classList.remove('active');
			}
		};
		xhr.send();
	};
});