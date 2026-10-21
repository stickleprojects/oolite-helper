"use strict";

this.name = "ctxkeys";
this.author = "Kieron";
this.version = "0.1";
this.description = "Logs game context changes for the external Oolite key helper.";

// All messages leave the game through here, as JSON with a "type" field.
// Debug builds with a console connected get them over TCP; otherwise they go
// to Latest.log as "[ctxkeys]: {json}".
this._emit = function (type, data) {
	data = data || {};
	data.type = type;
	var json = JSON.stringify(data);
	if (typeof debugConsole !== "undefined" && debugConsole) {
		debugConsole.consoleMessage(json);
	} else {
		log("ctxkeys", json);
	}
};

this.startUp = function () {
	this._emit("hello", { version: this.version });
};

this.startUpComplete = function () {
	this._emit("ready", { docked: player.ship.docked, view: player.ship.viewDirection });
};

this.guiScreenChanged = function (to, from) {
	this._emit("gui", { to: to, from: from });
};

// F1-F4 in flight: forward/aft/port/starboard. The GUI screen stays MAIN.
this.viewDirectionChanged = function (to, from) {
	this._emit("view", { to: to, from: from });
};

this.shipDockedWithStation = function (station) {
	this._emit("docked", { station: station.displayName });
};

this.shipWillLaunchFromStation = function (station) {
	this._emit("launching", { station: station.displayName });
};
